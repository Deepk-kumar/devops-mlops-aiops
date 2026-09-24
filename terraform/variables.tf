variable "kubeconfig_path" {
  description = "Ansible ne jo kubeconfig banayi uska path"
  type        = string
  default     = "../ansible/kubeconfig"
}

variable "minio_storage_size" {
  type    = string
  default = "10Gi"
}

variable "postgres_storage_size" {
  type    = string
  default = "5Gi"
}

variable "minio_buckets" {
  description = "MinIO buckets: DVC data, MLflow artifacts, model files"
  type        = list(string)
  default     = ["dvc-storage", "mlflow-artifacts", "models"]
}

# Reproducible builds ke liye chart versions pin karna achha hai.
# null = latest. Kaam karne ke baad `helm search repo` se version dekh kar yaha daal do.
variable "argocd_chart_version" {
  type    = string
  default = null
}

variable "minio_chart_version" {
  type    = string
  default = null
}

variable "kps_chart_version" {
  type    = string
  default = null
}

variable "loki_chart_version" {
  type    = string
  default = null
}

variable "alloy_chart_version" {
  type    = string
  default = null
}
