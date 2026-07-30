# Suffix keeps the subnet-wide DNS hostname label unique, so the stack can be
# deployed multiple times (or redeployed) into the same subnet.
resource "random_string" "hostname_suffix" {
  length  = 4
  special = false
  upper   = false
}

resource "oci_core_instance" "proxy" {
  compartment_id      = var.instance_compartment_ocid
  availability_domain = var.availability_domain
  display_name        = var.instance_display_name
  shape               = var.instance_shape

  dynamic "shape_config" {
    for_each = local.is_flex_shape ? [1] : []
    content {
      ocpus         = var.instance_ocpus
      memory_in_gbs = var.instance_memory_in_gbs
    }
  }

  source_details {
    source_type             = "image"
    source_id               = local.image_id
    boot_volume_size_in_gbs = var.boot_volume_size_in_gbs
  }

  create_vnic_details {
    subnet_id        = var.subnet_id
    assign_public_ip = var.assign_public_ip
    display_name     = "${var.instance_display_name}-vnic"
    hostname_label   = "${replace(lower(var.instance_display_name), "/[^a-z0-9]/", "")}-${random_string.hostname_suffix.result}"
    nsg_ids          = [oci_core_network_security_group.proxy.id]
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data           = base64encode(local.cloud_init)
  }

  lifecycle {
    ignore_changes = [source_details[0].source_id]
  }
}
