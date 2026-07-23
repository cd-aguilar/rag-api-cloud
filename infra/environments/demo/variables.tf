variable "project_name" {
  type    = string
  default = "rag-api-cloud"
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "container_image" {
  description = "URI completa de la imagen en ECR con el tag del build actual. La pasa deploy.yml despues de hacer push a ECR (no tiene default a proposito: sin imagen no hay nada que desplegar)."
  type        = string
}

variable "container_port" {
  description = "Puerto de la app (uvicorn). Unica fuente de verdad: se pasa explicito a alb y ecs para que nunca queden desincronizados."
  type        = number
  default     = 8000
}

variable "task_cpu" {
  type    = number
  default = 256
}

variable "task_memory" {
  type    = number
  default = 512
}

variable "desired_count" {
  type    = number
  default = 1
}
