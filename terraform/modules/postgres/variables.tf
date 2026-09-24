variable "namespace" { type = string }
variable "db_user" { type = string }
variable "db_password" {
  type      = string
  sensitive = true
}
variable "storage_size" { type = string }
