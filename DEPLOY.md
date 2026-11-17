# Deploying the pipeline

The site on GitHub Pages is static. The data behind it comes from a small AWS
pipeline that checks SEC EDGAR every hour and scores any new 10-K.

```
EventBridge (hourly) -> Lambda aiwash-poller -> S3 raw/{ticker}/{accession}.htm
                                                    | S3 event
                                                    v
                                           Lambda aiwash-scorer -> S3 results/{ticker}/{year}.json
                                                    |                S3 public/data.json
                                                    |                        |
                         failed 3x -> SQS DLQ       |                CloudFront -> site
                                       |            |
               EventBridge (daily) -> Lambda aiwash-redrive -> replays into the scorer
               CloudWatch alarms -> SNS -> email
```

Everything is in `infra/` as Terraform. It fits in the AWS free tier: about
720 poller runs a month, a few scorer runs when companies file, one small
bucket and a CloudFront distribution with almost no traffic.

## What you need

- An AWS account and an IAM user or role that can create the resources in `infra/`
- Terraform 1.10 or newer, the AWS CLI, Python 3.12, `zip`
- The contact string the SEC asks EDGAR clients to send, e.g. `"Jane Doe jane@example.com"`

## First deploy

```bash
export AWS_REGION=us-east-1
export TF_VAR_sec_user_agent="Your Name you@example.com"
export TF_VAR_alert_email="you@example.com"        # optional; confirm the email AWS sends

./infra/build.sh        # build/lambda.zip, ~3 MB
./infra/bootstrap.sh    # creates the Terraform state bucket once, then terraform init
cd infra
terraform plan -out aiwash.tfplan
terraform apply aiwash.tfplan
```

Terraform prints `data_url`. Put it in the `LIVE` constant in `docs/index.html`.

The poller's first scheduled run uploads the last two 10-Ks for every company
in `var.tickers` and the scorer picks each one up. If filings land before the
S3 trigger exists (it happened on the first deploy here, because the hourly
rule fired while Terraform was still creating the notification), replay them:

```bash
uv run aiwash rescore --bucket "$(terraform -chdir=infra output -raw bucket)"
```

## Updating

| Change | Do this |
|---|---|
| Code in `src/aiwash/` or a new `docs/model.json` | `./infra/build.sh && terraform -chdir=infra apply`, then `aiwash rescore` so old filings use the new model |
| Add or remove a company | Edit `tickers` in `infra/variables.tf` and apply. The next hourly run fetches it. |
| New labels | `aiwash evaluate`, `aiwash site` (regenerates `docs/model.json`), then the code step above |

## When something breaks

- **Email "aiwash-filing-failed".** A filing failed scoring three times and is in the dead-letter queue. The daily redrive replays it at 06:30 UTC. If it keeps failing, it's usually a filing format the parser hasn't seen: `aws logs tail /aws/lambda/aiwash-scorer --since 1d`.
- **Email "aiwash-poller-errors".** Two hourly polls in a row failed. Usually EDGAR rate-limiting or downtime; it recovers on its own. Check the user agent if it doesn't.
- **Site shows "Snapshot copy".** The browser couldn't reach CloudFront and fell back to `docs/data.json` in the repo.

## Concurrency note

During a backfill up to ten scorers run at once (the default concurrency limit
on a new AWS account), and each rewrites `public/data.json`. Writes use S3
conditional requests (`If-Match` on the ETag), so a scorer that lost the race
re-reads and tries again instead of overwriting someone else's filing. On the
first backfill, 20 of 30 runs hit a conflict and retried; none lost data.

## Tearing it down

```bash
terraform -chdir=infra destroy
```

The data bucket has `force_destroy` set, since everything in it can be rebuilt
from EDGAR.

The state bucket (`aiwash-tfstate-<account>`) is left in place on purpose.
