variable "default_admin_cidr" {
  type    = string
  default = "192.168.0.0/24"
}

variable "private_subnet_cidr" {
  type    = string
  default = "10.0.0.0/24"
}