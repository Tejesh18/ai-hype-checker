from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import typer
from rich.console import Console
from rich.table import Table

from .claims import ai_mentions, extract_claims
from .edgar import Edgar
from .parse import parse_10k

app = typer.Typer(help="Does a company's AI talk have receipts?", no_args_is_help=True)
console = Console()

# Large companies across tech, finance, energy, health and retail. Not just
# tech, because "everyone says AI now" is the interesting part.
DEFAULT_TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA",
    "JPM", "GS", "BAC", "XOM:34088", "JNJ", "WMT", "KO", "NFLX",
]  # XOM is pinned: the ticker file now points at a new holding company

BLOCKS_PATH = Path("data/blocks.parquet")
CLAIMS_PATH = Path("data/claims.parquet")


@app.command()
def ingest(
    tickers: list[str] = typer.Argument(None, help="Tickers to fetch. Defaults to 15 large caps."),
    years: int = typer.Option(2, help="How many recent 10-Ks per company."),
) -> None:
    """Download 10-Ks and split them into page- and section-aware text blocks."""
    edgar = Edgar()
    rows = []
    for ticker in tickers or DEFAULT_TICKERS:
        for filing in edgar.ten_ks(ticker, limit=years):
            blocks = parse_10k(edgar.html(filing))
            rows.extend(
                {"ticker": filing.ticker, "fiscal_year": filing.fiscal_year, "url": filing.url,
                 "page": b.page, "item": b.item, "is_table": b.is_table, "text": b.text}
                for b in blocks
            )
            sections = len({b.item for b in blocks if b.item})
            console.print(f"{filing.ticker} FY{filing.fiscal_year}: {len(blocks):>5} blocks, {sections:>2} sections")
    BLOCKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), BLOCKS_PATH)
    console.print(f"[green]wrote {len(rows)} blocks to {BLOCKS_PATH}[/green]")


def _filings() -> dict[tuple[str, int], list[dict]]:
    out: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for b in pq.read_table(BLOCKS_PATH).to_pylist():
        out[(b["ticker"], b["fiscal_year"])].append(b)
    return out


@app.command()
def claims() -> None:
    """Pull every AI sentence out of the ingested filings."""
    filings = _filings()
    rows = []
    table = Table("ticker", "FY", "AI claims", "mentions /10k words", "Risk Factors", "Business", "MD&A")
    for (ticker, year), blocks in sorted(filings.items()):
        found = extract_claims(blocks)
        rows.extend(asdict(c) for c in found)
        words = sum(len(b["text"].split()) for b in blocks)
        by_item = Counter(c.item for c in found)
        table.add_row(
            ticker, str(year), str(len(found)),
            f"{ai_mentions(' '.join(b['text'] for b in blocks)) / words * 10_000:.1f}",
            str(by_item["1A"]), str(by_item["1"]), str(by_item["7"]),
        )
    pq.write_table(pa.Table.from_pylist(rows), CLAIMS_PATH)
    console.print(table)
    console.print(f"[green]wrote {len(rows)} claims to {CLAIMS_PATH}[/green]")


if __name__ == "__main__":
    app()
