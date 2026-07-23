output "alb_dns_name" {
  description = "URL publica del demo, ej: http://<esto>/query"
  value       = aws_lb.this.dns_name
}

output "target_group_arn" {
  description = "Lo necesita el modulo ecs para registrar el service"
  value       = aws_lb_target_group.app.arn
}

output "alb_arn" {
  value = aws_lb.this.arn
}
