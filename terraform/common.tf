provider "aws" {
    region  = "us-east-1"
}

terraform {
  backend "s3" {
    bucket = "atg-jupyterhub-terraform-remote-state"
    key    = "atg-jupyterhub-costs-lambda/terraform.tfstate"
    region = "us-east-1"
  }
}