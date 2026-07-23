variable "project_name" {
  description = "Prefijo usado para nombrar todos los recursos (ej: rag-api-cloud)"
  type        = string
}

variable "vpc_cidr" {
  description = "Bloque CIDR de la VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "azs" {
  description = "Zonas de disponibilidad a usar (el ALB exige al menos 2)"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "public_subnet_cidrs" {
  description = "CIDRs de las subnets publicas (ALB + NAT Gateway), una por AZ"
  type        = list(string)
  default     = ["10.0.0.0/24", "10.0.1.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDRs de las subnets privadas (tasks de ECS Fargate), una por AZ"
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.11.0/24"]
}

variable "container_port" {
  description = "Puerto en el que escucha la app dentro del contenedor (uvicorn)"
  type        = number
  default     = 8000
}
