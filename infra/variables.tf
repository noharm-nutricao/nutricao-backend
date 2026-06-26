variable "aws_region" {
  type    = string
  default = "us-east-2"
}

variable "project_name" {
  type    = string
  default = "nitra-lambda"
}

variable "image_uri" {
  type = string

  validation {
    condition     = length(trimspace(var.image_uri)) > 0
    error_message = "image_uri must not be empty."
  }
}

variable "db_host" {
  type = string
}

variable "db_name" {
  type = string
}

variable "db_user" {
  type = string
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "api_key" {
  type      = string
  sensitive = true
}

variable "enable_nutritional_job_schedule" {
  type    = bool
  default = true
}

variable "nutritional_job_schedule_expression" {
  type    = string
  default = "rate(3 minutes)"
}
