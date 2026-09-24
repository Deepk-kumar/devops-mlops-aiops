terraform {
  required_providers {
    kubernetes = {
      source = "hashicorp/kubernetes"
    }
  }
}

locals {
  labels = { app = "postgres" }
}

resource "kubernetes_secret_v1" "postgres" {
  metadata {
    name      = "postgres-credentials"
    namespace = var.namespace
  }
  data = {
    username = var.db_user
    password = var.db_password
  }
}

# Pehli baar start hone par ye SQL chalti hai: MLflow aur Airflow ke liye alag DB
resource "kubernetes_config_map_v1" "init" {
  metadata {
    name      = "postgres-init"
    namespace = var.namespace
  }
  data = {
    "init.sql" = <<-SQL
      CREATE DATABASE mlflow;
      CREATE DATABASE airflow;
    SQL
  }
}

resource "kubernetes_service_v1" "postgres" {
  metadata {
    name      = "postgres"
    namespace = var.namespace
  }
  spec {
    selector = local.labels
    port {
      port        = 5432
      target_port = 5432
    }
    cluster_ip = "None" # headless, StatefulSet ke liye
  }
}

resource "kubernetes_stateful_set_v1" "postgres" {
  metadata {
    name      = "postgres"
    namespace = var.namespace
    labels    = local.labels
  }

  spec {
    service_name = kubernetes_service_v1.postgres.metadata[0].name
    replicas     = 1

    selector {
      match_labels = local.labels
    }

    template {
      metadata {
        labels = local.labels
      }

      spec {
        container {
          name  = "postgres"
          image = "postgres:16-alpine"

          port {
            container_port = 5432
          }

          env {
            name = "POSTGRES_USER"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.postgres.metadata[0].name
                key  = "username"
              }
            }
          }
          env {
            name = "POSTGRES_PASSWORD"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.postgres.metadata[0].name
                key  = "password"
              }
            }
          }
          env {
            name  = "PGDATA"
            value = "/var/lib/postgresql/data/pgdata"
          }

          volume_mount {
            name       = "data"
            mount_path = "/var/lib/postgresql/data"
          }
          volume_mount {
            name       = "init"
            mount_path = "/docker-entrypoint-initdb.d"
          }

          readiness_probe {
            exec {
              command = ["pg_isready", "-U", var.db_user]
            }
            initial_delay_seconds = 10
            period_seconds        = 10
          }

          resources {
            requests = {
              cpu    = "100m"
              memory = "256Mi"
            }
            limits = {
              memory = "512Mi"
            }
          }
        }

        volume {
          name = "init"
          config_map {
            name = kubernetes_config_map_v1.init.metadata[0].name
          }
        }
      }
    }

    volume_claim_template {
      metadata {
        name = "data"
      }
      spec {
        access_modes = ["ReadWriteOnce"]
        resources {
          requests = {
            storage = var.storage_size
          }
        }
      }
    }
  }
}
