variable "region" {
  type    = string
  default = "us-east-1"
}

variable "sec_user_agent" {
  description = "Name and email the SEC asks every EDGAR client to send."
  type        = string
  sensitive   = true
}

variable "alert_email" {
  description = "Where failure alarms go. Empty means alarms still fire but nobody is emailed."
  type        = string
  default     = ""
}

variable "tickers" {
  type = list(string)
  default = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA",
    "JPM", "GS", "BAC", "XOM:34088", "JNJ", "WMT", "KO", "NFLX",
  ]
}

variable "years" {
  description = "How many recent 10-Ks to keep per company."
  type        = number
  default     = 2
}

variable "site_origin" {
  description = "Origin allowed to read public/ from the browser."
  type        = string
  default     = "https://tejesh18.github.io"
}

variable "scorer_image" {
  description = "ECR image URI (with digest) for the scorer. infra/deploy.sh builds and pushes it."
  type        = string
}
