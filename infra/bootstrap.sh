#!/usr/bin/env bash
# One-time: create the bucket that holds Terraform state, then init.
set -euo pipefail
cd "$(dirname "$0")"

account=$(aws sts get-caller-identity --query Account --output text)
state_bucket="aiwash-tfstate-${account}"
region="${AWS_REGION:-us-east-1}"

if ! aws s3api head-bucket --bucket "$state_bucket" 2>/dev/null; then
  aws s3api create-bucket --bucket "$state_bucket" --region "$region" >/dev/null
  aws s3api put-bucket-versioning --bucket "$state_bucket" --versioning-configuration Status=Enabled
  aws s3api put-public-access-block --bucket "$state_bucket" \
    --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
  echo "created $state_bucket"
fi

terraform init -backend-config="bucket=${state_bucket}"
