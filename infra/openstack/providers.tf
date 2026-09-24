terraform {
  required_version = ">= 1.5.0"

  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "~> 3.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
  }
}

# Credentials code me nahi hote. Dono me se ek tareeka use karo:
#   1) OpenStack dashboard se "openrc.sh" download karo  ->  source openrc.sh
#   2) clouds.yaml banao aur  export OS_CLOUD=<naam>
provider "openstack" {}
