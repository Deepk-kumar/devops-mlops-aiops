terraform {
  required_providers {
    helm = {
      source = "hashicorp/helm"
    }
  }
}

# ---------- Prometheus + Alertmanager + Grafana ----------
resource "helm_release" "kps" {
  name       = "kps"
  namespace  = var.namespace
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  version    = var.kps_chart_version
  timeout    = 900

  values = [yamlencode({
    fullnameOverride = "kps" # service names: kps-grafana, kps-prometheus, kps-alertmanager

    grafana = {
      adminPassword = var.grafana_password
      persistence   = { enabled = true, size = "2Gi" }
      sidecar = {
        dashboards = {
          enabled         = true
          label           = "grafana_dashboard"
          searchNamespace = "ALL" # kisi bhi namespace ke ConfigMap se dashboard uthao
        }
      }
      additionalDataSources = [{
        name   = "Loki"
        type   = "loki"
        uid    = "loki"
        url    = "http://loki.${var.namespace}.svc.cluster.local:3100"
        access = "proxy"
      }]
    }

    prometheus = {
      prometheusSpec = {
        retention = "3d"
        # Har namespace ke ServiceMonitor / PrometheusRule uthao (sirf helm-release wale nahi)
        serviceMonitorSelectorNilUsesHelmValues = false
        podMonitorSelectorNilUsesHelmValues     = false
        ruleSelectorNilUsesHelmValues           = false
        probeSelectorNilUsesHelmValues          = false
        resources = {
          requests = { cpu = "200m", memory = "512Mi" }
          limits   = { memory = "1536Mi" }
        }
        storageSpec = {
          volumeClaimTemplate = {
            spec = {
              accessModes = ["ReadWriteOnce"]
              resources   = { requests = { storage = "10Gi" } }
            }
          }
        }
      }
    }

    alertmanager = {
      alertmanagerSpec = {
        resources = { requests = { cpu = "50m", memory = "64Mi" } }
      }
    }

    # k3s ye components alag se expose nahi karta, warna false alerts aate hain
    kubeEtcd              = { enabled = false }
    kubeControllerManager = { enabled = false }
    kubeScheduler         = { enabled = false }
    kubeProxy             = { enabled = false }
  })]
}

# ---------- Loki (logs, single-binary, filesystem storage) ----------
resource "helm_release" "loki" {
  name       = "loki"
  namespace  = var.namespace
  repository = "https://grafana.github.io/helm-charts"
  chart      = "loki"
  version    = var.loki_chart_version
  timeout    = 900

  values = [yamlencode({
    deploymentMode = "SingleBinary"

    loki = {
      auth_enabled  = false
      commonConfig  = { replication_factor = 1 }
      storage       = { type = "filesystem" }
      schemaConfig = {
        configs = [{
          from         = "2024-04-01"
          store        = "tsdb"
          object_store = "filesystem"
          schema       = "v13"
          index        = { prefix = "loki_index_", period = "24h" }
        }]
      }
    }

    singleBinary = {
      replicas    = 1
      persistence = { enabled = true, size = "10Gi" }
    }

    # Distributed mode ke components band
    backend        = { replicas = 0 }
    read           = { replicas = 0 }
    write          = { replicas = 0 }
    ingester       = { replicas = 0 }
    querier        = { replicas = 0 }
    queryFrontend  = { replicas = 0 }
    queryScheduler = { replicas = 0 }
    distributor    = { replicas = 0 }
    compactor      = { replicas = 0 }
    indexGateway   = { replicas = 0 }

    gateway      = { enabled = false }
    chunksCache  = { enabled = false }
    resultsCache = { enabled = false }
    lokiCanary   = { enabled = false }
    test         = { enabled = false }
    minio        = { enabled = false }
  })]
}

# ---------- Alloy: pod logs -> Loki ----------
resource "helm_release" "alloy" {
  name       = "alloy"
  namespace  = var.namespace
  repository = "https://grafana.github.io/helm-charts"
  chart      = "alloy"
  version    = var.alloy_chart_version
  timeout    = 600

  values = [yamlencode({
    # Single node cluster: 1 replica kaafi hai (DaemonSet se logs duplicate hote)
    controller = { type = "deployment", replicas = 1 }

    alloy = {
      configMap = {
        create  = true
        content = <<-EOT
          discovery.kubernetes "pods" {
            role = "pod"
          }

          discovery.relabel "pods" {
            targets = discovery.kubernetes.pods.targets

            rule {
              source_labels = ["__meta_kubernetes_namespace"]
              target_label  = "namespace"
            }
            rule {
              source_labels = ["__meta_kubernetes_pod_name"]
              target_label  = "pod"
            }
            rule {
              source_labels = ["__meta_kubernetes_pod_container_name"]
              target_label  = "container"
            }
            rule {
              source_labels = ["__meta_kubernetes_pod_label_app"]
              target_label  = "app"
            }
          }

          loki.source.kubernetes "pods" {
            targets    = discovery.relabel.pods.output
            forward_to = [loki.write.default.receiver]
          }

          loki.write "default" {
            endpoint {
              url = "http://loki.${var.namespace}.svc.cluster.local:3100/loki/api/v1/push"
            }
          }
        EOT
      }
    }
  })]

  depends_on = [helm_release.loki]
}
