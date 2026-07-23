variable "project_name" {
  description = "Prefijo para nombrar los recursos"
  type        = string
}

variable "vpc_id" {
  description = "VPC donde vive el ALB (output del modulo network)"
  type        = string
}

variable "public_subnet_ids" {
  description = "Subnets publicas donde se despliega el ALB (output del modulo network)"
  type        = list(string)
}

variable "alb_security_group_id" {
  description = "Security group del ALB (output del modulo network)"
  type        = string
}

variable "container_port" {
  description = "Puerto donde escucha la app dentro del contenedor"
  type        = number
  default     = 8000
}

variable "health_check_path" {
  description = "Path que usa el ALB para chequear salud de los tasks"
  type        = string
  default     = "/health"
}
