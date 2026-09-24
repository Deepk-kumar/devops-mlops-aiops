# ---------- Namespaces ----------
resource "kubernetes_namespace_v1" "ns" {
  for_each = toset(["platform", "argocd", "mlops", "monitoring"])

  metadata {
    name = each.key
    labels = {
      "app.kubernetes.io/part-of" = "self-healing-ml-platform"
    }
  }
}

# ---------- Random passwords (git me kabhi commit nahi honge) ----------
resource "random_password" "minio" {
  length  = 24
  special = false
}

resource "random_password" "postgres" {
  length  = 24
  special = false
}

# ---------- Modules ----------
module "minio" {
  source = "./modules/minio"

  namespace     = kubernetes_namespace_v1.ns["platform"].metadata[0].name
  root_user     = "minioadmin"
  root_password = random_password.minio.result
  storage_size  = var.minio_storage_size
  buckets       = var.minio_buckets
  chart_version = var.minio_chart_version
}

module "postgres" {
  source = "./modules/postgres"

  namespace    = kubernetes_namespace_v1.ns["platform"].metadata[0].name
  db_user      = "platform"
  db_password  = random_password.postgres.result
  storage_size = var.postgres_storage_size
}

module "argocd" {
  source = "./modules/argocd"

  namespace     = kubernetes_namespace_v1.ns["argocd"].metadata[0].name
  chart_version = var.argocd_chart_version
}
