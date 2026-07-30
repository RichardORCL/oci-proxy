output "instance_id" {
  description = "OCID of the proxy instance."
  value       = oci_core_instance.proxy.id
}

output "private_ip" {
  description = "Private IP address of the proxy instance."
  value       = oci_core_instance.proxy.private_ip
}

output "public_ip" {
  description = "Public IP address of the proxy instance (if assigned)."
  value       = oci_core_instance.proxy.public_ip
}

output "proxy_url_private" {
  description = "Proxy endpoint reachable from inside the VCN."
  value       = "http://${oci_core_instance.proxy.private_ip}:${var.proxy_port}"
}

output "proxy_url_public" {
  description = "Proxy endpoint via public IP (if assigned)."
  value       = var.assign_public_ip ? "http://${oci_core_instance.proxy.public_ip}:${var.proxy_port}" : "n/a (no public IP assigned)"
}

output "image_used" {
  description = "Ubuntu image used for the instance."
  value       = data.oci_core_images.ubuntu.images[0].display_name
}
