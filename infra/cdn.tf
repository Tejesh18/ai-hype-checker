# CloudFront in front of the private bucket. The site on GitHub Pages
# fetches public/data.json from here. Requests outside public/ get a 403
# because the bucket policy only lets CloudFront read that prefix.

resource "aws_cloudfront_origin_access_control" "data" {
  name                              = "${local.name}-data"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "site_data" {
  enabled         = true
  comment         = "AI Hype Checker site data"
  price_class     = "PriceClass_100" # US/Canada/Europe edges only; cheapest
  is_ipv6_enabled = true

  origin {
    origin_id                = "data"
    domain_name              = aws_s3_bucket.data.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.data.id
  }

  default_cache_behavior {
    target_origin_id       = "data"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true
    # AWS managed policies: CachingOptimized (honors the 5-minute
    # Cache-Control the scorer sets on data.json) and SimpleCORS
    # (Access-Control-Allow-Origin: * on every response).
    cache_policy_id            = "658327ea-f89d-4fab-a63d-7e88639e58f6"
    response_headers_policy_id = "60669652-455b-4ae9-85a4-c4c02393f86c"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}
