terraform {
  required_providers {
    helm = {
      source = "hashicorp/helm"
    }
  }
}

resource "helm_release" "minio" {
  name       = "minio"
  namespace  = var.namespace
  repository = "https://charts.min.io/"
  chart      = "minio"
  version    = var.chart_version
  timeout    = 600

  values = [yamlencode({
    mode         = "standalone"
    replicas     = 1
    rootUser     = var.root_user
    rootPassword = var.root_password

    persistence = {
      enabled = true
      size    = var.storage_size
    }

    resources = {
      requests = { memory = "512Mi" }
    }

    service        = { type = "ClusterIP" }
    consoleService = { type = "ClusterIP" }

    buckets = [for b in var.buckets : {
      name   = b
      policy = "none"
      purge  = false
    }]
  })]
}
