locals {
  ports = {
    ssh     = 22
    k3s_api = 6443
    http    = 80
    https   = 443
  }

  # Password sirf tab set hoga jab vm_password diya ho
  user_data = var.vm_password == null ? null : join("\n", [
    "#cloud-config",
    "ssh_pwauth: true",
    "password: ${jsonencode(var.vm_password)}",
    "chpasswd: { expire: false }",
  ])
}

data "openstack_images_image_v2" "ubuntu" {
  name        = var.image_name
  most_recent = true
}

data "openstack_networking_network_v2" "private" {
  name = var.private_network
}

# SSH key: sirf PUBLIC key upload hoti hai
resource "openstack_compute_keypair_v2" "this" {
  name       = "${var.vm_name}-key"
  public_key = file(pathexpand(var.ssh_public_key_path))
}

resource "openstack_networking_secgroup_v2" "this" {
  name        = "${var.vm_name}-sg"
  description = "Self-healing ML platform"
}

resource "openstack_networking_secgroup_rule_v2" "in" {
  for_each = local.ports

  security_group_id = openstack_networking_secgroup_v2.this.id
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = each.value
  port_range_max    = each.value
  remote_ip_prefix  = var.allowed_cidr
}

resource "openstack_compute_instance_v2" "vm" {
  name            = var.vm_name
  flavor_name     = var.flavor_name
  key_pair        = openstack_compute_keypair_v2.this.name
  security_groups = [openstack_networking_secgroup_v2.this.name]
  user_data       = local.user_data

  # Root disk volume se boot (flavor ki disk chhoti ho to bhi 80 GB milegi)
  block_device {
    uuid                  = data.openstack_images_image_v2.ubuntu.id
    source_type           = "image"
    destination_type      = "volume"
    volume_size           = var.disk_gb
    boot_index            = 0
    delete_on_termination = true
  }

  network {
    uuid = data.openstack_networking_network_v2.private.id
  }
}

resource "openstack_networking_floatingip_v2" "this" {
  pool = var.external_network
}

# VM ka port explicitly dhundo (instance attribute par bharosa nahi)
data "openstack_networking_port_v2" "vm" {
  device_id  = openstack_compute_instance_v2.vm.id
  network_id = data.openstack_networking_network_v2.private.id
}

resource "openstack_networking_floatingip_associate_v2" "this" {
  floating_ip = openstack_networking_floatingip_v2.this.address
  port_id     = data.openstack_networking_port_v2.vm.id
}

# Ansible inventory apne aap ban jayegi
resource "local_file" "ansible_inventory" {
  filename        = "${path.module}/../../ansible/inventory.openstack.ini"
  file_permission = "0644"
  content         = <<-EOT
    [k3s]
    ${var.vm_name} ansible_host=${openstack_networking_floatingip_v2.this.address} ansible_user=${var.ssh_user} ansible_ssh_private_key_file=${var.ssh_private_key_path} k3s_api_host=${openstack_networking_floatingip_v2.this.address}
  EOT

  depends_on = [openstack_networking_floatingip_associate_v2.this]
}
