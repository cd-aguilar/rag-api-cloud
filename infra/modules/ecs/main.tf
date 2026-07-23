data "aws_caller_identity" "current" {}

resource "aws_ecr_repository" "app" {
  name                 = var.project_name
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = { Name = var.project_name }
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${var.project_name}"
  retention_in_days = 7 # corto a proposito: portafolio, no hay razon de retener logs meses

  tags = { Name = var.project_name }
}

resource "aws_ecs_cluster" "this" {
  name = "${var.project_name}-cluster"

  setting {
    name  = "containerInsights"
    value = "disabled" # Container Insights tiene costo extra, no aporta al objetivo de portafolio
  }
}

# Sin esto, el service no puede usar FARGATE_SPOT en
# capacity_provider_strategy: el cluster necesita conocer explicitamente
# que capacity providers tiene disponibles antes de poder pedirselos.
resource "aws_ecs_cluster_capacity_providers" "this" {
  cluster_name       = aws_ecs_cluster.this.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE_SPOT"
    weight            = 1
  }
}

# --- Execution role: usado por el AGENTE de ECS para arrancar el
# contenedor (pull de ECR, escribir logs). NO es lo mismo que el
# permiso que necesita tu APP en runtime. ---
resource "aws_iam_role" "execution" {
  name = "${var.project_name}-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# --- Task role: usado por TU CODIGO (boto3 dentro de main.py) en
# runtime. Aca vive el permiso bedrock:InvokeModel que necesita
# rag_pipeline.py. Separar execution/task role es principio de
# menor privilegio: el agente de ECS no deberia poder invocar Bedrock,
# y tu app no deberia poder hacer pull de imagenes. ---
resource "aws_iam_role" "task" {
  name = "${var.project_name}-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "bedrock_invoke" {
  name = "${var.project_name}-bedrock-invoke"
  role = aws_iam_role.task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["bedrock:InvokeModel"]
      Resource = [
        # Embeddings: modelo directo, sin inference profile.
        "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.bedrock_embedding_model_id}",
        # Generacion: el modelo se invoca via cross-region inference
        # profile (prefijo "us."), que es un tipo de recurso distinto
        # y SI incluye el account ID en el ARN.
        "arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:inference-profile/${var.bedrock_llm_model_id}",
        # Un inference profile enruta a foundation models concretos en
        # varias regiones de la geografia "us"; sin este permiso amplio
        # (pero acotado a la familia de modelos usada) la invocacion
        # falla con AccessDenied aunque el permiso de arriba este bien.
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-haiku-4-5-*",
      ]
    }]
  })
}

resource "aws_ecs_task_definition" "app" {
  family                   = var.project_name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc" # obligatorio en Fargate
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn             = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name  = var.project_name
    image = var.container_image

    portMappings = [{
      containerPort = var.container_port
      protocol      = "tcp"
    }]

    environment = [
      { name = "RAG_BEDROCK_REGION", value = var.aws_region },
      { name = "RAG_BEDROCK_LLM_MODEL_ID", value = var.bedrock_llm_model_id },
      { name = "RAG_BEDROCK_EMBEDDING_MODEL_ID", value = var.bedrock_embedding_model_id },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.app.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])
}

resource "aws_ecs_service" "app" {
  name            = "${var.project_name}-service"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = var.desired_count

  # Debe correr despues de asociar los capacity providers al cluster.
  depends_on = [aws_ecs_cluster_capacity_providers.this]

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.ecs_security_group_id]
    assign_public_ip = false # subnet privada: sale por el NAT del modulo network
  }

  load_balancer {
    target_group_arn = var.target_group_arn
    container_name    = var.project_name
    container_port    = var.container_port
  }

  # Fargate Spot: hasta 70% mas barato que on-demand. Aceptable para
  # un demo de portafolio que tolera una interrupcion ocasional.
  capacity_provider_strategy {
    capacity_provider = "FARGATE_SPOT"
    weight            = 1
  }
}
