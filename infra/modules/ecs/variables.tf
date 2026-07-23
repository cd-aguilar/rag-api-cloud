variable "project_name" {
  type = string
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "private_subnet_ids" {
  description = "Output del modulo network"
  type        = list(string)
}

variable "ecs_security_group_id" {
  description = "Output del modulo network"
  type        = string
}

variable "target_group_arn" {
  description = "Output del modulo alb"
  type        = string
}

variable "container_port" {
  type    = number
  default = 8000
}

variable "container_image" {
  description = "URI completa de la imagen en ECR, ej: <account>.dkr.ecr.<region>.amazonaws.com/rag-api-cloud:latest. La pasa el workflow de GitHub Actions despues del build."
  type        = string
}

variable "task_cpu" {
  description = "vCPU del task en unidades Fargate (256 = 0.25 vCPU)"
  type        = number
  default     = 256
}

variable "task_memory" {
  description = "Memoria del task en MB"
  type        = number
  default     = 512
}

variable "desired_count" {
  description = "Cuantas tasks corren simultaneamente. 1 alcanza para un demo de portafolio."
  type        = number
  default     = 1
}

variable "bedrock_llm_model_id" {
  type    = string
  default = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
}

variable "bedrock_embedding_model_id" {
  type    = string
  default = "amazon.titan-embed-text-v2:0"
}
