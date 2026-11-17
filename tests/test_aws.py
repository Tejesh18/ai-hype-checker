"""Tests for the Lambda handlers against a fake S3 (moto)."""

import json

import boto3
import pytest
from moto import mock_aws

BUCKET = "test-bucket"


@pytest.fixture
def aws(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("BUCKET", BUCKET)
    with mock_aws():
        s3 = boto3.client("s3")
        s3.create_bucket(Bucket=BUCKET)
        s3.put_object(Bucket=BUCKET, Key="public/metrics.json", Body=b'{"n": 0}')
        from aiwash import aws as handlers

        monkeypatch.setattr(handlers, "BUCKET", BUCKET)
        monkeypatch.setattr(handlers, "s3", s3)
        yield s3, handlers


def _result(s3, ticker, year, n_claims):
    doc = {"summary": {"ticker": ticker, "fiscal_year": year}, "claims": [{"ticker": ticker}] * n_claims}
    s3.put_object(Bucket=BUCKET, Key=f"results/{ticker}/{year}.json", Body=json.dumps(doc).encode())


def _published(s3):
    return json.loads(s3.get_object(Bucket=BUCKET, Key="public/data.json")["Body"].read())


def test_publish_includes_every_results_file(aws):
    s3, h = aws
    _result(s3, "AAPL", 2026, 3)
    _result(s3, "MSFT", 2026, 2)
    h._publish()
    data = _published(s3)
    assert {c["ticker"] for c in data["companies"]} == {"AAPL", "MSFT"}
    assert len(data["claims"]) == 5
    assert data["updated"].endswith("UTC")


def test_publish_retries_when_another_scorer_wins_the_race(aws, monkeypatch):
    """Simulate a second scorer publishing between our read and our write.

    Our first conditional put must fail, and the retry must include the
    filing the other scorer added.
    """
    s3, h = aws
    _result(s3, "AAPL", 2026, 1)
    h._publish()

    real_put = s3.put_object
    calls = {"n": 0}

    def racing_put(**kwargs):
        if kwargs.get("Key") == "public/data.json" and calls["n"] == 0:
            calls["n"] += 1
            # another scorer lands NVDA and republishes first
            _result(s3, "NVDA", 2026, 4)
            real_put(Bucket=BUCKET, Key="public/data.json", Body=b'{"companies": [], "claims": []}')
        return real_put(**kwargs)

    monkeypatch.setattr(h.time, "sleep", lambda s: None)
    monkeypatch.setattr(s3, "put_object", racing_put)
    _result(s3, "MSFT", 2026, 2)
    h._publish()

    data = _published(s3)
    assert {c["ticker"] for c in data["companies"]} == {"AAPL", "MSFT", "NVDA"}
    assert len(data["claims"]) == 7
