"""Group parsed blocks into retrieval chunks.

Rules, and why:
- Never cross a section boundary. "Risk Factors" text mixed with "MD&A"
  text makes both worse at retrieval and muddies citations.
- Tables stay whole (split by rows only if huge). Half a table is useless.
- ~300 words per chunk: big enough to hold a full thought, small enough
  that the embedding isn't an average of five different topics.
- Each chunk gets a short header (company, year, section). It's prepended
  only for search, so a chunk that says "we" still knows who "we" is.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .edgar import Filing
from .parse import Block

TARGET_WORDS = 300
MAX_TABLE_WORDS = 600


@dataclass
class Chunk:
    chunk_id: str
    ticker: str
    company: str
    fiscal_year: int
    section: str
    item: str
    page_start: int
    page_end: int
    is_table: bool
    text: str
    url: str

    @property
    def header(self) -> str:
        return f"{self.company} ({self.ticker}) FY{self.fiscal_year} 10-K, {self.section}"

    def for_search(self) -> str:
        return f"{self.header}\n{self.text}"

    def to_row(self) -> dict:
        return asdict(self)


def _words(text: str) -> int:
    return len(text.split())


def _split_table(text: str) -> list[str]:
    parts, cur = [], []
    for row in text.split("\n"):
        cur.append(row)
        if _words("\n".join(cur)) >= MAX_TABLE_WORDS:
            parts.append("\n".join(cur))
            cur = []
    if cur:
        parts.append("\n".join(cur))
    return parts


def chunk_filing(filing: Filing, blocks: list[Block]) -> list[Chunk]:
    chunks: list[Chunk] = []

    def add(group: list[Block], text: str | None = None, is_table: bool = False) -> None:
        body = text if text is not None else "\n".join(b.text for b in group)
        if _words(body) < 8:  # stray headers, "Table of Contents" links, etc.
            return
        chunks.append(
            Chunk(
                chunk_id=f"{filing.ticker}-{filing.fiscal_year}-{len(chunks):04d}",
                ticker=filing.ticker,
                company=filing.company,
                fiscal_year=filing.fiscal_year,
                section=group[0].section,
                item=group[0].item,
                page_start=group[0].page,
                page_end=group[-1].page,
                is_table=is_table,
                text=body,
                url=filing.url,
            )
        )

    buf: list[Block] = []
    for block in blocks:
        if buf and block.item != buf[0].item:
            add(buf)
            buf = []
        if block.is_table:
            if buf:
                add(buf)
                buf = []
            for part in _split_table(block.text):
                add([block], part, is_table=True)
            continue
        buf.append(block)
        if _words("\n".join(b.text for b in buf)) >= TARGET_WORDS:
            add(buf)
            buf = []
    if buf:
        add(buf)
    return chunks
