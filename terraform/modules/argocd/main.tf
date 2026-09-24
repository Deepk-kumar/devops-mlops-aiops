terraform {
  required_providers {
    helm = {
      source = "hashicorp/helm"
    }
  }
}

resource "helm_release" "argocd" {
  name       = "argocd"
  namespace  = var.namespace
  repository = "https://argoproj.github.io/argo-helm"
  chart      = "argo-cd"
  version    = var.chart_version
  timeout    = 900

  values = [yamlencode({
    # Local setup: TLS ke bina UI chalao (port-forward se)
    configs = {
      params = {
        "server.insecure" = true
      }
    }
    # Laptop RAM bachane ke liye chhoti cheezein band
    dex           = { enabled = false }
    notifications = { enabled = false }
  })]
}
