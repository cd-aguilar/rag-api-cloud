module "network" {
  source = "../../modules/network"

  project_name    = var.project_name
  container_port  = var.container_port
}

module "alb" {
  source = "../../modules/alb"

  project_name           = var.project_name
  vpc_id                 = module.network.vpc_id
  public_subnet_ids      = module.network.public_subnet_ids
  alb_security_group_id  = module.network.alb_security_group_id
  container_port          = var.container_port
}

module "ecs" {
  source = "../../modules/ecs"

  project_name           = var.project_name
  aws_region              = var.aws_region
  private_subnet_ids     = module.network.private_subnet_ids
  ecs_security_group_id  = module.network.ecs_security_group_id
  target_group_arn        = module.alb.target_group_arn
  container_image         = var.container_image
  container_port           = var.container_port
  task_cpu                 = var.task_cpu
  task_memory              = var.task_memory
  desired_count            = var.desired_count
}
