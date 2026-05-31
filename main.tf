locals {
  vm_requests = yamldecode(file("${path.module}/vm-requests.yaml"))

  k8s_cluster_dirs = fileset("${path.module}/Kubernetes", "*")

  k8s_control_plane_request_files = [
    for cluster in local.k8s_cluster_dirs :
    "${path.module}/Kubernetes/${cluster}/control-plane-requests.yaml"
    if fileexists("${path.module}/Kubernetes/${cluster}/control-plane-requests.yaml")
  ]

  k8s_worker_request_files = [
    for cluster in local.k8s_cluster_dirs :
    "${path.module}/Kubernetes/${cluster}/worker-node-requests.yaml"
    if fileexists("${path.module}/Kubernetes/${cluster}/worker-node-requests.yaml")
  ]

  k8s_control_plane_maps = [
    for request_file in local.k8s_control_plane_request_files :
    yamldecode(file(request_file)).control_planes
  ]

  k8s_worker_maps = [
    for request_file in local.k8s_worker_request_files :
    yamldecode(file(request_file)).workers
  ]

  k8s_control_planes = length(local.k8s_control_plane_maps) > 0 ? merge(local.k8s_control_plane_maps...) : {}
  k8s_workers        = length(local.k8s_worker_maps) > 0 ? merge(local.k8s_worker_maps...) : {}

  vms = merge(
    local.vm_requests.vms,
    local.k8s_control_planes,
    local.k8s_workers
  )

  floating_ip_vms = {
    for name, vm in local.vms : name => vm
    if vm.floating_ip
  }

  k8s_vms = merge(
    local.k8s_control_planes,
    local.k8s_workers
  )
}

data "openstack_images_image_v2" "images" {
  for_each = local.vms

  name        = each.value.image
  most_recent = true
}

data "openstack_compute_flavor_v2" "flavors" {
  for_each = local.vms

  name = each.value.flavor
}

data "openstack_networking_network_v2" "networks" {
  for_each = local.vms

  name = each.value.network
}

data "openstack_networking_network_v2" "public" {
  name = "public"
}

resource "openstack_networking_secgroup_v2" "vm" {
  for_each = local.vms

  name        = "${each.key}-secgroup"
  description = "Security group for ${each.key}"
}

resource "openstack_networking_secgroup_rule_v2" "icmp" {
  for_each = local.vms

  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "icmp"
  remote_ip_prefix  = coalesce(try(each.value.admin_cidr, null), var.default_admin_cidr)
  security_group_id = openstack_networking_secgroup_v2.vm[each.key].id
}

resource "openstack_networking_secgroup_rule_v2" "ssh" {
  for_each = local.vms

  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = coalesce(try(each.value.admin_cidr, null), var.default_admin_cidr)
  security_group_id = openstack_networking_secgroup_v2.vm[each.key].id
}

resource "openstack_networking_secgroup_rule_v2" "private_internal" {
  for_each = local.vms

  direction         = "ingress"
  ethertype         = "IPv4"
  remote_ip_prefix  = var.private_subnet_cidr
  security_group_id = openstack_networking_secgroup_v2.vm[each.key].id
}

resource "openstack_networking_secgroup_rule_v2" "k8s_private_tcp" {
  for_each = local.k8s_vms

  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  remote_ip_prefix  = var.private_subnet_cidr
  security_group_id = openstack_networking_secgroup_v2.vm[each.key].id
}

resource "openstack_networking_secgroup_rule_v2" "k8s_private_udp" {
  for_each = local.k8s_vms

  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "udp"
  remote_ip_prefix  = var.private_subnet_cidr
  security_group_id = openstack_networking_secgroup_v2.vm[each.key].id
}

resource "openstack_networking_secgroup_rule_v2" "k8s_private_icmp" {
  for_each = local.k8s_vms

  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "icmp"
  remote_ip_prefix  = var.private_subnet_cidr
  security_group_id = openstack_networking_secgroup_v2.vm[each.key].id
}

resource "openstack_networking_port_v2" "vm" {
  for_each = local.vms

  name           = "${each.key}-port"
  network_id     = data.openstack_networking_network_v2.networks[each.key].id
  admin_state_up = true

  security_group_ids = [
    openstack_networking_secgroup_v2.vm[each.key].id
  ]
}

resource "openstack_compute_instance_v2" "vm" {
  for_each = local.vms

  name      = each.key
  image_id  = data.openstack_images_image_v2.images[each.key].id
  flavor_id = data.openstack_compute_flavor_v2.flavors[each.key].id
  key_pair  = each.value.keypair

  network {
    port = openstack_networking_port_v2.vm[each.key].id
  }
}

resource "openstack_networking_floatingip_v2" "vm" {
  for_each = local.floating_ip_vms

  pool = data.openstack_networking_network_v2.public.name
}

resource "openstack_networking_floatingip_associate_v2" "vm" {
  for_each = local.floating_ip_vms

  floating_ip = openstack_networking_floatingip_v2.vm[each.key].address
  port_id     = openstack_networking_port_v2.vm[each.key].id
}