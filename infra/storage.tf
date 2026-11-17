# One bucket, three prefixes:
#   raw/      filings as downloaded from EDGAR (private)
#   results/  per-filing scores (private)
#   public/   data.json + metrics.json the site reads (served via CloudFront)

resource "aws_s3_bucket" "data" {
  bucket = local.bucket
  # Everything in it can be rebuilt from EDGAR, so let destroy empty it
  # (including old versions) instead of failing on a non-empty bucket.
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    id     = "expire-old-versions"
    status = "Enabled"
    filter {}
    # data.json is rewritten on every filing; keep a week of history, not forever
    noncurrent_version_expiration {
      noncurrent_days = 7
    }
  }
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}

# The bucket stays private. Only CloudFront (cdn.tf) can read, and only public/.
resource "aws_s3_bucket_policy" "cloudfront_read" {
  bucket     = aws_s3_bucket.data.id
  depends_on = [aws_s3_bucket_public_access_block.data]
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "CloudFrontReadsSiteData"
      Effect    = "Allow"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.data.arn}/public/*"
      Condition = { StringEquals = { "AWS:SourceArn" = aws_cloudfront_distribution.site_data.arn } }
    }]
  })
}

resource "aws_s3_object" "metrics" {
  bucket       = aws_s3_bucket.data.id
  key          = "public/metrics.json"
  source       = "${path.module}/../results/metrics.json"
  etag         = filemd5("${path.module}/../results/metrics.json")
  content_type = "application/json"
}

# Every new filing in raw/ triggers the scorer
resource "aws_s3_bucket_notification" "raw" {
  bucket = aws_s3_bucket.data.id
  lambda_function {
    lambda_function_arn = aws_lambda_function.scorer.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "raw/"
  }
  depends_on = [aws_lambda_permission.s3_invoke_scorer]
}
