output "minio_endpoint" {
  value = module.minio.endpoint
}

output "minio_root_user" {
  value = "minioadmin"
}

output "minio_root_password" {
  value     = random_password.minio.result
  sensitive = true
}

output "postgres_host" {
  value = module.postgres.host
}

output "postgres_user" {
  value = "platform"
}

output "postgres_password" {
  value     = random_password.postgres.result
  sensitive = true
}

output "grafana_user" {
  value = "admin"
}

output "grafana_password" {
  value     = random_password.grafana.result
  sensitive = true
}

output "next_steps" {
  value = <<-EOT
    make status            -> saare pods
    make argocd-password   -> ArgoCD admin password
    make argocd-ui         -> http://localhost:8080
    make minio-ui          -> http://localhost:9001
    make grafana-ui        -> http://localhost:3000  (admin / terraform output -raw grafana_password)
    make prometheus-ui     -> http://localhost:9090
    make alertmanager-ui   -> http://localhost:9093
    terraform output -raw minio_root_password
  EOT
}
