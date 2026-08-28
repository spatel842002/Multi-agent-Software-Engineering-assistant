terraform {
  required_version = ">= 1.9.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.62"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.7"
    }
  }

  # Remote state is intentionally not configured here -- point this at your
  # own backend (S3 + DynamoDB lock table, or Terraform Cloud) before any
  # real `terraform apply`. See docs/deployment.md for the recommended setup.
  # backend "s3" {
  #   bucket         = "REPLACE_ME-masea-tfstate"
  #   key            = "eks/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "REPLACE_ME-masea-tflock"
  #   encrypt        = true
  # }
}
