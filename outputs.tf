output "vms" {
  description = "Created OpenStack virtual machines"

  value = {
    for name, vm in openstack_compute_instance_v2.vm : name => {
      id     = vm.id
      name   = vm.name
      status = vm.power_state

      private_ips = [
        for fixed_ip in openstack_networking_port_v2.vm[name].all_fixed_ips : fixed_ip
      ]

      floating_ip = try(openstack_networking_floatingip_v2.vm[name].address, null)

      ssh_command = try(
        openstack_networking_floatingip_v2.vm[name].address != null
        ? "ssh ubuntu@${openstack_networking_floatingip_v2.vm[name].address}"
        : null,
        null
      )
    }
  }
}