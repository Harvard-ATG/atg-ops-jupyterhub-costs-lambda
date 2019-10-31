provider "aws" {
    region  = "us-east-1"
    version = "~> 2.32"
}

terraform {
  required_version = "0.12.9"
  backend "s3" {
    bucket = "atg-jupyterhub-terraform-remote-state"
    key    = "atg-jupyterhub-costs-lambda/terraform.tfstate"
    region = "us-east-1"
  }
}