# Design notes

Decisions, the things that went wrong, and what I'd do next.

## The problem, stated narrowly

Who would use this, and what do they need?

- **An analyst or investor** reading a 10-K wants to know if the AI section is substance or decoration, without reading 100 pages. Needs: per-company numbers, the actual sentences, a link to the page.
- **Someone drafting a disclosure** wants to know which sentences an SEC reviewer will flag as vague before filing. Needs: paste text, get labels, nothing leaves the browser.

Not in scope: judging whether a concrete claim is *true*. A concrete claim is checkable; checking it is a different project.

## Decisions

**Four labels, not two.** The first labeling pass used concrete vs vague and broke within twenty sentences: half of all AI sentences are risk disclosures ("AI could increase cyber risk"). Calling those vague would rank the most careful companies (banks) as the worst AI-washers. So risk and context became their own labels, and the substance score ignores them.

**Sample evenly across filings.** A random sample would have been mostly NVIDIA, Microsoft and Alphabet, who write over a third of all AI sentences. Up to 10 per filing keeps banks and retailers in the training data.

**Cross-validation, not a test split.** With 252 labels, one unlucky split moves macro F1 by 10 points. 5-fold stratified CV, same folds for every method.

**Embeddings over TF-IDF in production.** I first deployed the TF-IDF model because it's 183 KB and needs no ML libraries in Lambda. On the live data it moved the share of checkable claims from 15.5% to 11.5%, because it's much worse on the concrete label (0.59 vs 0.69 F1), the label the score depends on. That's a different answer, not a rounding error, so the scorer moved to a container image with the embedding model. Cold start went from ~0.2 s to ~0.6–1.0 s, which doesn't matter for a job that runs when a company files.

**Plain PyTorch for fine-tuning.** SetFit hung at step 0 on the 2-core machine I trained on (CPU near zero, so it was a deadlock, not slowness). A 30-line training loop (bge-small + linear head, class-weighted loss, 4 epochs) worked and is easier to explain anyway. It still lost to frozen embeddings, which is the honest result for ~200 training examples.

**Conditional writes instead of a lock.** Every scorer rebuilds `public/data.json` from all results. The first plan was to limit the scorer to one concurrent run, but a new AWS account has a concurrency limit of 10 and AWS won't let you reserve any of it. S3 conditional writes (`If-Match` on the ETag) solve it without a lock: a scorer that lost the race re-lists and retries. 20 of 30 backfill runs hit a conflict; none lost data.

**Private bucket behind CloudFront.** The account blocks public buckets, which is the right default. CloudFront with origin access control can read `public/` only; everything else returns 403.

## Things that broke

- **Amazon and Walmart had zero sections.** Their "ITEM 1A. Risk Factors" headings sit inside one-row layout tables, which the parser treated as data tables. Short single-row tables are now treated as text (`tests/test_parse.py`).
- **JPMorgan, Goldman and Bank of America were missing a year.** EDGAR's submissions API only includes about the last 1,000 filings, and banks file thousands of prospectuses a year. The older 10-K is in the paged history files.
- **Exxon disappeared.** The SEC's ticker file now maps XOM to a new holding company that hasn't filed a 10-K. XOM is pinned to Exxon Mobil Corp's CIK.
- **The first deploy scored nothing.** The hourly rule fired while Terraform was still creating the S3 trigger, so 30 filings landed with no event. `aiwash rescore` replays everything in `raw/`, and it's documented in DEPLOY.md.
- **Switching the scorer to a container dropped its S3 permission.** Replacing a Lambda deletes its resource policy. Terraform now re-creates the permission whenever the function is replaced (`replace_triggered_by`).

## Limitations

- 15 companies, two years each. A snapshot, not an index.
- One labeling pass with no second annotator, so no agreement number. The guide is public so anyone can dispute a specific call.
- Sentences are judged alone. A vague sentence followed by a concrete one still counts as vague.
- Company numbers come from a model with ~0.7 F1 on the labels that matter, so treat them as directional.
- Page numbers come from page breaks in the HTML and can be off by one from the PDF.

## Next

- A second annotator on 100 sentences, to report agreement.
- The S&P 100 over 2020–2026, to see when AI talk took off and whether substance kept up.
- More labels, then retry fine-tuning.
