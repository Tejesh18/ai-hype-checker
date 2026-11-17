from __future__ import annotations

from collections import Counter
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import typer
from rich.console import Console
from rich.table import Table

from .chunk import chunk_filing
from .edgar import Edgar
from .parse import parse_10k

app = typer.Typer(help="Ask questions about SEC 10-K filings.", no_args_is_help=True)
console = Console()

# Large companies across tech, finance, energy, health and retail, so the
# eval set isn't all one industry's vocabulary.
DEFAULT_TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA",
    "JPM", "GS", "BAC", "XOM:34088", "JNJ", "WMT", "KO", "NFLX",
]  # XOM is pinned: the ticker file now points at a new holding company
CHUNKS_PATH = Path("data/chunks.parquet")


@app.command()
def ingest(
    tickers: list[str] = typer.Argument(None, help="Tickers to fetch. Defaults to 15 large caps."),
    years: int = typer.Option(1, help="How many recent 10-Ks per company."),
) -> None:
    """Download 10-Ks, split them into sections, and write data/chunks.parquet."""
    edgar = Edgar()
    rows = []
    for ticker in tickers or DEFAULT_TICKERS:
        for filing in edgar.ten_ks(ticker, limit=years):
            blocks = parse_10k(edgar.html(filing))
            chunks = chunk_filing(filing, blocks)
            sections = len({c.item for c in chunks if c.item})
            pages = max((b.page for b in blocks), default=0)
            console.print(
                f"{filing.ticker} FY{filing.fiscal_year}: {len(chunks):>4} chunks, "
                f"{sections:>2} sections, {pages:>3} pages"
            )
            rows.extend(c.to_row() for c in chunks)
    CHUNKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), CHUNKS_PATH)
    console.print(f"[green]wrote {len(rows)} chunks to {CHUNKS_PATH}[/green]")


@app.command()
def stats() -> None:
    """Summarize what's been ingested."""
    rows = pq.read_table(CHUNKS_PATH).to_pylist()
    table = Table("ticker", "FY", "chunks", "tables", "avg words", "sections")
    by_ticker: dict[str, list[dict]] = {}
    for r in rows:
        by_ticker.setdefault(r["ticker"], []).append(r)
    for t, rs in by_ticker.items():
        words = sum(len(r["text"].split()) for r in rs) / len(rs)
        table.add_row(
            t,
            str(rs[0]["fiscal_year"]),
            str(len(rs)),
            str(sum(r["is_table"] for r in rs)),
            f"{words:.0f}",
            str(len({r["item"] for r in rs if r["item"]})),
        )
    console.print(table)
    top = Counter(r["section"] for r in rows).most_common(8)
    console.print("most common sections: " + ", ".join(f"{s} ({n})" for s, n in top))


if __name__ == "__main__":
    app()
