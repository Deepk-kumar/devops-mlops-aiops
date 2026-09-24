variable "namespace" { type = string }
variable "grafana_password" {
  type      = string
  sensitive = true
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
