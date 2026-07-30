# Network security group that allows proxy traffic from the permitted CIDR.
# Attached directly to the instance VNIC, so no security list changes are needed
# as long as the subnet's security lists do not block the traffic.
resource "oci_core_network_security_group" "proxy" {
  compartment_id = var.network_compartment_ocid
  vcn_id         = var.vcn_id
  display_name   = "${var.instance_display_name}-nsg"
}

resource "oci_core_network_security_group_security_rule" "proxy_ingress" {
  network_security_group_id = oci_core_network_security_group.proxy.id
  direction                 = "INGRESS"
  protocol                  = "6" # TCP
  source_type               = "CIDR_BLOCK"
  source                    = var.proxy_allowed_cidr
  description               = "Allow proxy clients"

  tcp_options {
    destination_port_range {
      min = var.proxy_port
      max = var.proxy_port
    }
  }
}

resource "oci_core_network_security_group_security_rule" "egress_all" {
  network_security_group_id = oci_core_network_security_group.proxy.id
  direction                 = "EGRESS"
  protocol                  = "all"
  destination_type          = "CIDR_BLOCK"
  destination               = "0.0.0.0/0"
  description               = "Allow all outbound traffic (proxy upstream)"
}
