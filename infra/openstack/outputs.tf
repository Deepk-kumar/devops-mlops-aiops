output "floating_ip" {
  value = openstack_networking_floatingip_v2.this.address
}

output "ssh_command" {
  value = "ssh -i ${var.ssh_private_key_path} ${var.ssh_user}@${openstack_networking_floatingip_v2.this.address}"
}
