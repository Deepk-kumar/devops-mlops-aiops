variable "vm_name" {
  type    = string
  default = "ml-platform"
}

variable "image_name" {
  description = "OpenStack me available Ubuntu image ka naam"
  type        = string
  default     = "ubuntu-22.04"
}

variable "flavor_name" {
  description = "Recommended: 4 vCPU / 16 GB RAM"
  type        = string
  default     = "m1.xlarge"
}

variable "disk_gb" {
  type    = number
  default = 80
}

variable "private_network" {
  description = "Tenant/private network ka naam"
  type        = string
  default     = "private"
}

variable "external_network" {
  description = "Floating IP pool / external network ka naam"
  type        = string
  default     = "public"
}

variable "ssh_public_key_path" {
  type    = string
  default = "~/.ssh/id_ed25519.pub"
}

variable "ssh_private_key_path" {
  description = "Ansible inventory me likhne ke liye (state me store nahi hoti)"
  type        = string
  default     = "~/.ssh/id_ed25519"
}

variable "ssh_user" {
  description = "Image ka default user (Ubuntu = ubuntu)"
  type        = string
  default     = "ubuntu"
}

variable "allowed_cidr" {
  description = "Kaun SSH (22) aur k3s API (6443) access kar sakta hai. Apna IP/32 daalo."
  type        = string
  default     = "0.0.0.0/0"
}

# OPTIONAL: password login. null = sirf SSH key (recommended).
variable "vm_password" {
  type      = string
  default   = null
  sensitive = true
}
