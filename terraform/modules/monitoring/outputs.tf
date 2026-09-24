output "grafana_service" {
  value = "kps-grafana.${var.namespace}.svc.cluster.local"
}
