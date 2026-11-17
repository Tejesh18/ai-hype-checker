# The scorer runs the embedding model, which is too big for a zip Lambda.
# The model is downloaded at build time so a cold start never touches the
# network, and copied to /tmp on start because Lambda's /opt is read-only
# and onnxruntime wants to write next to the model.
FROM public.ecr.aws/lambda/python:3.12

RUN pip install --no-cache-dir "fastembed>=0.4" "httpx>=0.27" "selectolax>=0.3.21" "numpy>=1.26"

ENV MODEL_DIR=/tmp/models
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir='/opt/models')"

COPY src/aiwash/__init__.py src/aiwash/aws.py src/aiwash/claims.py src/aiwash/edgar.py \
     src/aiwash/lite.py src/aiwash/parse.py ${LAMBDA_TASK_ROOT}/aiwash/
COPY web/public/model.json labels/labels.csv build/embed_head.json ${LAMBDA_TASK_ROOT}/aiwash/
COPY infra/scorer_entry.py ${LAMBDA_TASK_ROOT}/

CMD ["scorer_entry.handler"]
