#!/usr/bin/env bash
# Build build/lambda.zip for the python3.12 x86_64 Lambda runtime.
# boto3 is already in the runtime, so it's left out.
set -euo pipefail
cd "$(dirname "$0")/.."

rm -rf build/lambda && mkdir -p build/lambda
pip install --quiet --target build/lambda \
  --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 --only-binary=:all: \
  "httpx>=0.27" "selectolax>=0.3.21"

mkdir -p build/lambda/aiwash
cp src/aiwash/__init__.py src/aiwash/aws.py src/aiwash/claims.py src/aiwash/edgar.py \
   src/aiwash/lite.py src/aiwash/parse.py build/lambda/aiwash/
cp docs/model.json build/lambda/aiwash/model.json
cp labels/labels.csv build/lambda/aiwash/labels.csv

(cd build/lambda && zip -qr ../lambda.zip .)
echo "build/lambda.zip $(du -h build/lambda.zip | cut -f1)"
