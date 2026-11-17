# --- schedules -------------------------------------------------------------

resource "aws_cloudwatch_event_rule" "hourly" {
  name                = "${local.name}-poll-edgar"
  schedule_expression = "rate(1 hour)"
}

resource "aws_cloudwatch_event_target" "poller" {
  rule = aws_cloudwatch_event_rule.hourly.name
  arn  = aws_lambda_function.poller.arn
}

resource "aws_lambda_permission" "events_invoke_poller" {
  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.poller.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.hourly.arn
}

resource "aws_cloudwatch_event_rule" "daily" {
  name                = "${local.name}-redrive-failed"
  schedule_expression = "cron(30 6 * * ? *)"
}

resource "aws_cloudwatch_event_target" "redrive" {
  rule = aws_cloudwatch_event_rule.daily.name
  arn  = aws_lambda_function.redrive.arn
}

resource "aws_lambda_permission" "events_invoke_redrive" {
  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.redrive.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily.arn
}

# --- failures ---------------------------------------------------------------

resource "aws_sqs_queue" "dlq" {
  name                      = "${local.name}-scorer-dlq"
  message_retention_seconds = 1209600 # 14 days, the SQS maximum
}

resource "aws_sns_topic" "alerts" {
  name = "${local.name}-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alert_email == "" ? 0 : 1
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# A filing failed scoring three times and is waiting in the DLQ
resource "aws_cloudwatch_metric_alarm" "dlq_not_empty" {
  alarm_name          = "${local.name}-filing-failed"
  alarm_description   = "A filing failed scoring 3 times. The daily redrive will retry it; check scorer logs."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = aws_sqs_queue.dlq.name }
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"
}

# EDGAR down, rate-limited, or the parser broke on a new filing format
resource "aws_cloudwatch_metric_alarm" "poller_errors" {
  alarm_name          = "${local.name}-poller-errors"
  alarm_description   = "The hourly EDGAR poll failed twice in a row."
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.poller.function_name }
  statistic           = "Sum"
  period              = 3600
  evaluation_periods  = 2
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"
}

output "bucket" {
  value = aws_s3_bucket.data.id
}

output "data_url" {
  value = "https://${aws_cloudfront_distribution.site_data.domain_name}/public/data.json"
}
