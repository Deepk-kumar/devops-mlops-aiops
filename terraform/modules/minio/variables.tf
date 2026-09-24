variable "namespace" { type = string }
variable "root_user" { type = string }
variable "root_password" {
  type      = string
  sensitive = true
}
variable "storage_size" { type = string }
variable "buckets" { type = list(string) }
variable "chart_version" {
  type    = string
  default = null
}
