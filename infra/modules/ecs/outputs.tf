output "ecr_repository_url" {
  description = "A esto le hace push la imagen el workflow de GitHub Actions"
  value       = aws_ecr_repository.app.repository_url
}

output "cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "service_name" {
  value = aws_ecs_service.app.name
}
