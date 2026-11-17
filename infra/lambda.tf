# infra/build.sh produces build/lambda.zip (the aiwash package + httpx +
# selectolax built for Lambda's Linux, + model.json).

locals {
  zip = "${path.module}/../build/lambda.zip"
}

data "aws_iam_policy_document" "assume_lambda" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${local.name}-lambda"
  assume_role_policy = data.aws_iam_policy_document.assume_lambda.json
}

resource "aws_iam_role_policy_attachment" "logs" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Least privilege: only this bucket, this queue, and invoking the scorer
data "aws_iam_policy_document" "lambda" {
  statement {
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.data.arn}/*"]
  }
  statement {
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.data.arn]
  }
  statement {
    actions   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:SendMessage", "sqs:GetQueueAttributes"]
    resources = [aws_sqs_queue.dlq.arn]
  }
  statement {
    actions   = ["lambda:InvokeFunction"]
    resources = ["arn:aws:lambda:${var.region}:${data.aws_caller_identity.me.account_id}:function:${local.name}-scorer"]
  }
}

resource "aws_iam_role_policy" "lambda" {
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda.json
}

resource "aws_lambda_function" "poller" {
  function_name    = "${local.name}-poller"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.12"
  handler          = "aiwash.aws.poller"
  filename         = local.zip
  source_code_hash = filebase64sha256(local.zip)
  timeout          = 600
  memory_size      = 512
  environment {
    variables = {
      BUCKET         = aws_s3_bucket.data.id
      TICKERS        = join(",", var.tickers)
      YEARS          = tostring(var.years)
      SEC_USER_AGENT = var.sec_user_agent
    }
  }
}

resource "aws_ecr_repository" "scorer" {
  name                 = "${local.name}-scorer"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true
  image_scanning_configuration {
    scan_on_push = true
  }
}

# The free tier covers 500 MB of image storage; keep only the last 3 images
resource "aws_ecr_lifecycle_policy" "scorer" {
  repository = aws_ecr_repository.scorer.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "keep last 3 images"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 3 }
      action       = { type = "expire" }
    }]
  })
}

# Container image: bge-small + the classification head (see infra/scorer.Dockerfile)
resource "aws_lambda_function" "scorer" {
  function_name = "${local.name}-scorer"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = var.scorer_image
  timeout       = 300
  memory_size   = 2048
  # Several scorers can run at once during a backfill. They don't overwrite
  # each other's data.json because publishing uses S3 conditional writes
  # (see _publish in src/aiwash/aws.py).
  environment {
    variables = { BUCKET = aws_s3_bucket.data.id }
  }
}

resource "aws_lambda_permission" "s3_invoke_scorer" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scorer.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.data.arn
  # AWS deletes a function's permissions when the function is replaced
  # (e.g. switching zip -> container), so re-create this alongside it.
  lifecycle {
    replace_triggered_by = [aws_lambda_function.scorer]
  }
}

# Lambda retries a failed async event twice, then sends it here
resource "aws_lambda_function_event_invoke_config" "scorer" {
  lifecycle {
    replace_triggered_by = [aws_lambda_function.scorer]
  }
  function_name                = aws_lambda_function.scorer.function_name
  maximum_retry_attempts       = 2
  maximum_event_age_in_seconds = 21600
  destination_config {
    on_failure {
      destination = aws_sqs_queue.dlq.arn
    }
  }
}

resource "aws_lambda_function" "redrive" {
  function_name    = "${local.name}-redrive"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.12"
  handler          = "aiwash.aws.redrive"
  filename         = local.zip
  source_code_hash = filebase64sha256(local.zip)
  timeout          = 60
  environment {
    variables = {
      BUCKET  = aws_s3_bucket.data.id
      DLQ_URL = aws_sqs_queue.dlq.url
      SCORER  = aws_lambda_function.scorer.function_name
    }
  }
}

resource "aws_cloudwatch_log_group" "fn" {
  for_each          = toset(["poller", "scorer", "redrive"])
  name              = "/aws/lambda/${local.name}-${each.key}"
  retention_in_days = 14
}
