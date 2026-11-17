"""AWS Lambda handlers. Infrastructure is in infra/ (Terraform).

poller   runs hourly. Looks up each tracked company's latest 10-Ks on EDGAR
         and uploads any filing that isn't in S3 yet to raw/.
scorer   runs on every new object in raw/. Parses the filing, labels each AI
         sentence, writes results/{ticker}/{year}.json, then rebuilds
         public/data.json, which the site reads.
redrive  runs daily. Filings that failed scoring (after Lambda's own two
         retries) land in a dead-letter queue; this replays them so a bad
         night at the SEC doesn't leave a permanent hole.

Only the standard library, boto3 (built into Lambda), httpx and selectolax
are needed, so the deployment zip stays around 5 MB.
"""

from __future__ import annotations

import csv
import json
import os
import random
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import boto3

from .claims import extract_claims
from .edgar import Edgar
from .lite import LiteClassifier
from .parse import parse_10k

BUCKET = os.environ.get("BUCKET", "")
s3 = boto3.client("s3")
_clf: LiteClassifier | None = None


_gold: dict[str, str] | None = None


class EmbedClassifier:
    """bge-small embeddings + the logistic-regression head from training.

    Used by the scorer container. It's better than TF-IDF on the two labels
    the substance score depends on (concrete 0.69 vs 0.59 F1), and on the
    first deploy the TF-IDF model moved the share of checkable claims from
    15.5% to 11.5%, which is too big a shift to call a deployment detail.
    """

    def __init__(self, head_path: Path):
        import numpy as np
        from fastembed import TextEmbedding

        head = json.loads(head_path.read_text())
        self.np = np
        self.classes = head["classes"]
        self.coef = np.array(head["coef"], dtype=np.float32)
        self.intercept = np.array(head["intercept"], dtype=np.float32)
        self.model = TextEmbedding(model_name=head["embed_model"], cache_dir=os.environ.get("MODEL_DIR", "/opt/models"))

    def predict_many(self, texts: list[str]) -> list[str]:
        if not texts:
            return []
        np = self.np
        x = np.array(list(self.model.embed(texts, batch_size=32)), dtype=np.float32)
        x /= np.linalg.norm(x, axis=1, keepdims=True)
        return [self.classes[i] for i in (x @ self.coef.T + self.intercept).argmax(axis=1)]


def _classifier():
    global _clf
    if _clf is None:
        head = Path(__file__).with_name("embed_head.json")
        if head.exists():
            _clf = EmbedClassifier(head)
        else:
            _clf = LiteClassifier.load(Path(__file__).with_name("model.json"))
    return _clf


def _predict(texts: list[str]) -> tuple[list[str], str]:
    clf = _classifier()
    if isinstance(clf, EmbedClassifier):
        return clf.predict_many(texts), "embed"
    return [clf.predict(t) for t in texts], "tfidf"


def _labeled() -> dict[str, str]:
    """Sentences from the labeled set keep their label instead of a prediction."""
    global _gold
    if _gold is None:
        path = Path(__file__).with_name("labels.csv")
        _gold = {r["sentence"]: r["label"] for r in csv.DictReader(path.open())} if path.exists() else {}
    return _gold


def _exists(key: str) -> bool:
    try:
        s3.head_object(Bucket=BUCKET, Key=key)
        return True
    except s3.exceptions.ClientError:
        return False


def poller(event: dict, context: object) -> dict:
    tickers = os.environ["TICKERS"].split(",")
    years = int(os.environ.get("YEARS", "2"))
    # fresh cache per run: a warm Lambda reusing /tmp would never see new filings
    edgar = Edgar(cache_dir=tempfile.mkdtemp())
    uploaded = []
    for ticker in tickers:
        for f in edgar.ten_ks(ticker, limit=years):
            key = f"raw/{f.ticker}/{f.accession}.htm"
            if _exists(key):
                continue
            s3.put_object(
                Bucket=BUCKET, Key=key, Body=edgar.html(f).encode("utf-8"), ContentType="text/html",
                Metadata={"ticker": f.ticker, "fiscal-year": str(f.fiscal_year), "filed": f.filed, "url": f.url},
            )
            uploaded.append(key)
    print(json.dumps({"checked": len(tickers), "uploaded": uploaded}))
    return {"uploaded": uploaded}


def _score(key: str) -> dict:
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    meta = obj["Metadata"]
    ticker, year, url = meta["ticker"], int(meta["fiscal-year"]), meta["url"]
    html = obj["Body"].read().decode("utf-8", errors="replace")

    blocks = [
        {"ticker": ticker, "fiscal_year": year, "url": url, "page": b.page, "item": b.item, "is_table": b.is_table, "text": b.text}
        for b in parse_10k(html)
    ]
    gold = _labeled()
    found = extract_claims(blocks)
    predicted, source = _predict([f"{c.section}: {c.sentence}" for c in found])
    claims = []
    for c, p in zip(found, predicted):
        human = c.sentence in gold
        claims.append({
            "ticker": ticker, "fiscal_year": year, "section": c.section, "page": c.page,
            "label": gold[c.sentence] if human else p,
            "label_source": "human" if human else source,
            "sentence": c.sentence, "url": url,
        })
    n = Counter(c["label"] for c in claims)
    own = n["concrete"] + n["vague"]
    summary = {
        "ticker": ticker, "fiscal_year": year, "filed": meta.get("filed"), "ai_sentences": len(claims),
        "concrete": n["concrete"], "vague": n["vague"], "risk": n["risk"], "context": n["context"],
        "substance": round(n["concrete"] / own, 3) if own else None,
    }
    s3.put_object(
        Bucket=BUCKET, Key=f"results/{ticker}/{year}.json",
        Body=json.dumps({"summary": summary, "claims": claims}).encode(), ContentType="application/json",
    )
    return summary


def _current_etag(key: str) -> str | None:
    try:
        return s3.head_object(Bucket=BUCKET, Key=key)["ETag"]
    except s3.exceptions.ClientError:
        return None


def _publish(attempts: int = 10) -> None:
    """Rebuild public/data.json from every results file.

    During a backfill several scorers finish at once. Each one writes its own
    results file first, then rebuilds data.json with a conditional write: the
    put only succeeds if data.json hasn't changed since we looked. If another
    scorer got there first we re-list and try again, so the last successful
    write always includes every results file that existed when it listed.
    """
    key = "public/data.json"
    metrics = json.loads(s3.get_object(Bucket=BUCKET, Key="public/metrics.json")["Body"].read())
    for attempt in range(attempts):
        etag = _current_etag(key)
        companies, claims = [], []
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix="results/"):
            for item in page.get("Contents", []):
                doc = json.loads(s3.get_object(Bucket=BUCKET, Key=item["Key"])["Body"].read())
                companies.append(doc["summary"])
                claims.extend(doc["claims"])
        updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        body = json.dumps({"updated": updated, "companies": companies, "claims": claims, "metrics": metrics},
                          separators=(",", ":")).encode()
        condition = {"IfMatch": etag} if etag else {"IfNoneMatch": "*"}
        try:
            s3.put_object(Bucket=BUCKET, Key=key, Body=body, ContentType="application/json",
                          CacheControl="max-age=300", **condition)
            return
        except s3.exceptions.ClientError as e:
            if e.response["Error"]["Code"] not in ("PreconditionFailed", "ConditionalRequestConflict"):
                raise
            print(json.dumps({"publish_conflict": attempt + 1}))
            # spread out the retries so the same scorers don't collide again
            time.sleep(random.uniform(0.2, 1.0) * (attempt + 1))
    raise RuntimeError("could not publish data.json after retries")


def scorer(event: dict, context: object) -> dict:
    done = []
    for record in event.get("Records", []):
        key = record["s3"]["object"]["key"]
        done.append(_score(key))
    _publish()
    print(json.dumps({"scored": done}))
    return {"scored": len(done)}


def redrive(event: dict, context: object) -> dict:
    """Replay failed scorer events from the dead-letter queue."""
    sqs = boto3.client("sqs")
    lam = boto3.client("lambda")
    queue = os.environ["DLQ_URL"]
    replayed = 0
    while True:
        msgs = sqs.receive_message(QueueUrl=queue, MaxNumberOfMessages=10, WaitTimeSeconds=1).get("Messages", [])
        if not msgs:
            break
        for m in msgs:
            body = json.loads(m["Body"])
            # Lambda's on-failure destination wraps the original event
            payload = body.get("requestPayload", body)
            lam.invoke(FunctionName=os.environ["SCORER"], InvocationType="Event", Payload=json.dumps(payload).encode())
            sqs.delete_message(QueueUrl=queue, ReceiptHandle=m["ReceiptHandle"])
            replayed += 1
    print(json.dumps({"replayed": replayed}))
    return {"replayed": replayed}
