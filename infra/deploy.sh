#!/usr/bin/env bash
# Build everything and deploy. Needs TF_VAR_sec_user_agent set.
#   1. zip for the poller and redrive Lambdas
#   2. classification head trained on the current labels
#   3. make sure the ECR repo exists, then build and push the scorer image
#   4. terraform apply with that exact image digest
set -euo pipefail
cd "$(dirname "$0")/.."
region="${AWS_REGION:-us-east-1}"

./infra/build.sh
uv run --extra finetune python -c "
from pathlib import Path
from aiwash.model import export_embed_head, load_labels
export_embed_head(load_labels(), Path('build/embed_head.json'))
print('build/embed_head.json')"

terraform -chdir=infra apply -auto-approve -input=false \
  -target=aws_ecr_repository.scorer -target=aws_ecr_lifecycle_policy.scorer \
  -var scorer_image=placeholder >/dev/null
repo=$(terraform -chdir=infra state show -no-color aws_ecr_repository.scorer | awk -F'"' '/repository_url/ {print $2}')

aws ecr get-login-password --region "$region" | docker login --username AWS --password-stdin "${repo%%/*}" >/dev/null
tag=$(git rev-parse --short HEAD)-$(date +%s)
docker build --platform linux/amd64 --provenance=false -f infra/scorer.Dockerfile -t "$repo:$tag" .
docker push --quiet "$repo:$tag" >/dev/null
digest=$(aws ecr describe-images --repository-name "${repo##*/}" --image-ids imageTag="$tag" \
  --query 'imageDetails[0].imageDigest' --output text)

terraform -chdir=infra apply -auto-approve -input=false -var scorer_image="$repo@$digest"
echo "deployed scorer image $repo@$digest"
