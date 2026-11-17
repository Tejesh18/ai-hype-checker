terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
  # State lives in S3 so a lost laptop or Codespace doesn't orphan the stack.
  # The bucket is created once by infra/bootstrap.sh; see DEPLOY.md.
  backend "s3" {
    key          = "aiwash/terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { project = "ai-washing-detector" }
  }
}

data "aws_caller_identity" "me" {}

locals {
  name   = "aiwash"
  bucket = "${local.name}-${data.aws_caller_identity.me.account_id}"
}
