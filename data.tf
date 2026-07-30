# Latest Canonical Ubuntu platform image compatible with the selected shape.
data "oci_core_images" "ubuntu" {
  compartment_id           = var.tenancy_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = var.ubuntu_version
  shape                    = var.instance_shape
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

locals {
  is_flex_shape = can(regex("Flex", var.instance_shape))
  image_id      = data.oci_core_images.ubuntu.images[0].id

  cloud_init = templatefile("${path.module}/cloud-init.yaml.tftpl", {
    proxy_port         = var.proxy_port
    proxy_allowed_cidr = var.proxy_allowed_cidr
  })
}
