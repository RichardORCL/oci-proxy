# ---------------------------------------------------------------------------
# Variables injected automatically by OCI Resource Manager
# ---------------------------------------------------------------------------
variable "tenancy_ocid" {
  type        = string
  description = "OCID of the tenancy (injected by Resource Manager)."
}

variable "region" {
  type        = string
  description = "Region to deploy into (injected by Resource Manager)."
}

variable "compartment_ocid" {
  type        = string
  description = "OCID of the compartment where the stack runs (injected by Resource Manager)."
}

# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------
variable "instance_compartment_ocid" {
  type        = string
  description = "Compartment in which the proxy instance will be created."
}

variable "availability_domain" {
  type        = string
  description = "Availability domain for the proxy instance."
}

# ---------------------------------------------------------------------------
# Networking
# ---------------------------------------------------------------------------
variable "network_compartment_ocid" {
  type        = string
  description = "Compartment that contains the VCN and subnet."
}

variable "vcn_id" {
  type        = string
  description = "OCID of the existing VCN to deploy into."
}

variable "subnet_id" {
  type        = string
  description = "OCID of the existing subnet to attach the instance to."
}

variable "assign_public_ip" {
  type        = bool
  description = "Assign a public IP to the proxy instance (requires a public subnet)."
  default     = true
}

# ---------------------------------------------------------------------------
# Instance shape and size
# ---------------------------------------------------------------------------
variable "instance_shape" {
  type        = string
  description = "Compute shape for the proxy instance."
  default     = "VM.Standard.E4.Flex"
}

variable "instance_ocpus" {
  type        = number
  description = "Number of OCPUs (only used for flexible shapes)."
  default     = 1
}

variable "instance_memory_in_gbs" {
  type        = number
  description = "Amount of memory in GB (only used for flexible shapes)."
  default     = 8
}

variable "boot_volume_size_in_gbs" {
  type        = number
  description = "Boot volume size in GB."
  default     = 50
}

variable "ubuntu_version" {
  type        = string
  description = "Ubuntu version for the instance image."
  default     = "24.04"
}

variable "ssh_public_key" {
  type        = string
  description = "SSH public key used to access the instance as user 'ubuntu'."
}

variable "instance_display_name" {
  type        = string
  description = "Display name of the proxy instance."
  default     = "proxy-server"
}

# ---------------------------------------------------------------------------
# Proxy configuration
# ---------------------------------------------------------------------------
variable "proxy_port" {
  type        = number
  description = "TCP port the Squid proxy listens on."
  default     = 3128
}

variable "proxy_allowed_cidr" {
  type        = string
  description = "CIDR block allowed to use the proxy (also opened in the NSG)."
  default     = "10.0.0.0/16"
}
