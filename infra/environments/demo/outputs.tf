output "demo_url" {
  description = "URL publica del demo (ej: para el README y el post de LinkedIn)"
  value       = "http://${module.alb.alb_dns_name}"
}

output "ecr_repository_url" {
  description = "A esto le hace push la imagen el workflow de build"
  value       = module.ecs.ecr_repository_url
}

output "ecs_cluster_name" {
  value = module.ecs.cluster_name
}

output "ecs_service_name" {
  description = "Lo necesita deploy.yml para forzar un nuevo deployment tras el push"
  value       = module.ecs.service_name
}

output "chroma_bucket_name" {
  description = "Subir el indice aca: aws s3 sync data/chroma s3://<esto>/chroma-data/"
  value       = module.ecs.chroma_bucket_name
}
