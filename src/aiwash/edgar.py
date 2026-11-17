"""Fetch 10-K filings from SEC EDGAR.

EDGAR is free but asks every client to send a User-Agent with a name and
email, and to stay under 10 requests a second. Everything we download is
cached under data/raw so re-running ingest doesn't hit the SEC again.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"


@dataclass(frozen=True)
class Filing:
    ticker: str
    company: str
    cik: int
    accession: str
    filed: str  # date the filing was submitted
    period: str  # fiscal year end the report covers
    url: str

    @property
    def fiscal_year(self) -> int:
        return int(self.period[:4])


class Edgar:
    def __init__(self, cache_dir: str | Path = "data/raw", user_agent: str | None = None):
        ua = user_agent or os.environ.get("SEC_USER_AGENT")
        if not ua:
            raise RuntimeError(
                "SEC requires a contact User-Agent. Set SEC_USER_AGENT='Your Name you@example.com'."
            )
        self.client = httpx.Client(
            headers={"User-Agent": ua, "Accept-Encoding": "gzip, deflate"},
            timeout=60,
            follow_redirects=True,
        )
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)
        self._last_request = 0.0

    def _get(self, url: str) -> bytes:
        # ~6 requests/second, comfortably under the SEC's limit
        wait = 0.16 - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()
        resp = self.client.get(url)
        resp.raise_for_status()
        return resp.content

    def _cached(self, name: str, url: str) -> bytes:
        path = self.cache / name
        if path.exists():
            return path.read_bytes()
        data = self._get(url)
        path.write_bytes(data)
        return data

    def lookup(self, ticker: str) -> tuple[int, str]:
        """Ticker -> (CIK, company name).

        "XOM:34088" pins a ticker to a CIK. Needed when the SEC's ticker file
        points at a new holding company that hasn't filed a 10-K yet.
        """
        if ":" in ticker:
            sym, cik = ticker.split(":", 1)
            return int(cik), sym.upper()
        rows = json.loads(self._cached("company_tickers.json", TICKERS_URL)).values()
        for row in rows:
            if row["ticker"].upper() == ticker.upper():
                return int(row["cik_str"]), row["title"]
        raise KeyError(f"unknown ticker: {ticker}")

    def ten_ks(self, ticker: str, limit: int = 1) -> list[Filing]:
        """Most recent 10-K filings for a ticker, newest first."""
        cik, _ = self.lookup(ticker)
        sub = json.loads(self._cached(f"submissions_{cik}.json", SUBMISSIONS_URL.format(cik=cik)))
        out: list[Filing] = []

        # "recent" only holds the last ~1000 filings. Banks file thousands of
        # prospectuses a year, so older 10-Ks live in the paged files.
        pages = [sub["filings"]["recent"]]
        older = [f["name"] for f in sub["filings"].get("files", [])]
        while pages:
            page = pages.pop(0)
            for i, form in enumerate(page["form"]):
                if form != "10-K":  # skips 10-K/A amendments on purpose
                    continue
                acc = page["accessionNumber"][i]
                out.append(
                    Filing(
                        ticker=ticker.split(":")[0].upper(),
                        company=sub["name"],
                        cik=cik,
                        accession=acc,
                        filed=page["filingDate"][i],
                        period=page["reportDate"][i],
                        url=ARCHIVE_URL.format(
                            cik=cik, acc=acc.replace("-", ""), doc=page["primaryDocument"][i]
                        ),
                    )
                )
                if len(out) == limit:
                    return out
            if older:
                name = older.pop(0)
                pages.append(json.loads(self._cached(name, f"https://data.sec.gov/submissions/{name}")))
        return out

    def html(self, filing: Filing) -> str:
        raw = self._cached(f"{filing.ticker}_{filing.accession}.htm", filing.url)
        return raw.decode("utf-8", errors="replace")
