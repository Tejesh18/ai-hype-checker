# AI-Washing Detector

Every company says "AI" now. This reads every sentence about AI in recent 10-K filings and labels it: a claim you can check, a claim you can't, a risk warning, or background. A small AWS pipeline checks SEC EDGAR every hour, so new filings show up on their own.

**Live: [tejesh18.github.io/ai-washing-detector](https://tejesh18.github.io/ai-washing-detector/)**: company table, every sentence with a link to the filing, and a box to paste your own disclosure text and see what reads as vague.

[![Company table on the live site](docs/screenshot.png)](https://tejesh18.github.io/ai-washing-detector/)

## Why

I work around equity research, and over the last two years "AI" has spread through every annual report. Some of it describes real work, a lot of it doesn't. The SEC has started charging firms for overstating their AI use, and most of its comment letters on AI disclosures ask for the same thing: be specific. That's measurable, so I measured it.

## What it found

From the latest two 10-Ks of 15 large companies (1,177 AI sentences):

- **Only 15% of AI sentences are checkable claims.** Half are risk warnings.
- **Apple went from 6 AI sentences to 47 in a year, and none is a checkable claim.** 39 are risk warnings.
- **NVIDIA backs up its AI talk the most:** 38 concrete claims (named products, launch dates, a 2.5x throughput number).
- **Tesla talks more and says less:** AI sentences 20 → 47, substance 88% → 37% (vague claims 1 → 17).
- **The big banks don't promote their AI at all.** JPMorgan and Goldman mention it 20–28 times each, all risk or background.

*Substance* = concrete / (concrete + vague). Risk warnings don't count either way, so a careful bank isn't punished for being careful.

## Architecture

```
EventBridge (hourly) ─> Lambda poller ─> S3 raw/            (new 10-Ks from EDGAR)
                                           │ S3 event
                                           ▼
                                   Lambda scorer (container: bge-small + classifier)
                                           │
                                           ├─> S3 results/{ticker}/{year}.json
                                           └─> S3 public/data.json ─> CloudFront ─> site
  failed 3x ─> SQS dead-letter queue ─> CloudWatch alarm ─> email
                    └─> daily redrive Lambda replays them
```

- **Terraform** for all of it (`infra/`), with remote state in S3 and native state locking.
- **Private bucket.** Only CloudFront can read, and only `public/`.
- **Scorer runs as a container image** from ECR because the embedding model doesn't fit a zip Lambda. Cold start ~0.6–1.0 s, peak memory ~1.1 GB.
- **Concurrent scorers don't clobber each other.** Every scorer rewrites `data.json`, so writes use S3 conditional requests (`If-Match`). On the first backfill, 20 of 30 runs collided, retried, and nothing was lost.
- **Fits the AWS free tier.**

Setup, updating, and what to do when an alarm fires: [DEPLOY.md](DEPLOY.md).

## How the labels work

| Label | Meaning | Example |
|---|---|---|
| concrete | A checkable claim about the company's own AI | "NVIDIA NIM ... delivers a 2.5x increase in token throughput" |
| vague | A claim about its own AI with nothing to check | "We use, and expect to increasingly use, emerging technologies, including AI, across our operations" |
| risk | AI as a threat, cost or regulation | "The increasing sophistication of AI technologies poses a greater risk of identity fraud" |
| context | Laws, market, boilerplate | "In the EU, ... the AI Act ... [is] rapidly changing compliance requirements" |

252 sentences, sampled evenly across all 30 filings, are labeled against [a written guide](labels/GUIDELINES.md). Four approaches were compared on the same 5-fold split:

| Method | Macro F1 | Concrete | Vague |
|---|---|---|---|
| Keyword rules | 0.61 | 0.59 | 0.52 |
| TF-IDF + logistic regression | 0.73 | 0.59 | 0.67 |
| **bge-small embeddings + logistic regression** | **0.73** | **0.69** | **0.68** |
| bge-small fine-tuned | 0.70 | 0.68 | 0.60 |

Fine-tuning lost: with ~200 training sentences per fold it overfits. The pipeline uses embeddings + logistic regression. The in-browser draft checker uses the TF-IDF model, ported to JavaScript (identical predictions on all 252 labeled sentences).

More on the decisions, what went wrong, and limitations: [DESIGN.md](DESIGN.md).

## Run it locally

No API keys. Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
export SEC_USER_AGENT="Your Name you@example.com"   # the SEC asks every client for a contact
uv sync
uv run aiwash ingest && uv run aiwash claims
uv run aiwash evaluate --methods rules,tfidf,embed
uv run aiwash score --method embed && uv run aiwash site
uv run --group dev pytest
```

Data comes from SEC EDGAR. Not investment advice.
