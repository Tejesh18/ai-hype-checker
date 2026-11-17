"""Turn 10-K HTML into an ordered list of text blocks.

Each block remembers which page it's on and which Item (section) of the
10-K it belongs to. Both matter later: the section helps retrieval, and the
page is what makes a citation checkable.

A few things about 10-K HTML that drive the design:
- Most filings are inline XBRL. The XBRL header sits in a display:none div
  and is pure noise, so hidden elements are skipped.
- Page breaks are CSS (page-break-before/after), not real pages, so we count
  them as we walk the document.
- The table of contents also contains "Item 1A ..." lines. We label blocks
  as we go, so a TOC line just opens a tiny section that the real heading
  replaces a few pages later.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from selectolax.lexbor import LexborHTMLParser as HTMLParser
from selectolax.lexbor import LexborNode as Node

ITEM_NAMES = {
    "1": "Business",
    "1A": "Risk Factors",
    "1B": "Unresolved Staff Comments",
    "1C": "Cybersecurity",
    "2": "Properties",
    "3": "Legal Proceedings",
    "4": "Mine Safety Disclosures",
    "5": "Market for Common Equity",
    "6": "Reserved",
    "7": "Management's Discussion and Analysis",
    "7A": "Market Risk Disclosures",
    "8": "Financial Statements",
    "9": "Changes in and Disagreements with Accountants",
    "9A": "Controls and Procedures",
    "9B": "Other Information",
    "9C": "Foreign Jurisdictions that Prevent Inspections",
    "10": "Directors and Corporate Governance",
    "11": "Executive Compensation",
    "12": "Security Ownership",
    "13": "Related Transactions and Director Independence",
    "14": "Principal Accountant Fees",
    "15": "Exhibits and Schedules",
    "16": "Form 10-K Summary",
}

ITEM_RE = re.compile(r"^item\s*(\d{1,2}[abc]?)\b\s*[.:\-–—]?", re.IGNORECASE)
BLOCK_TAGS = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "section"}
SKIP_TAGS = {"script", "style", "head", "title", "ix:header"}
PAGE_NUMBER_RE = re.compile(r"^(page\s*)?[ivx\d]{1,4}$", re.IGNORECASE)


@dataclass
class Block:
    text: str
    page: int
    item: str  # e.g. "1A", or "" before the first Item heading
    is_table: bool = False

    @property
    def section(self) -> str:
        if not self.item:
            return "Cover"
        return f"Item {self.item}. {ITEM_NAMES.get(self.item, '')}".strip()


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _style(node: Node) -> str:
    return (node.attributes.get("style") or "").replace(" ", "").lower()


def _table_text(table: Node) -> str:
    rows = []
    for tr in table.css("tr"):
        cells = [_clean(td.text(separator=" ")) for td in tr.css("td, th")]
        cells = [c for c in cells if c and c not in {"$", "%", ")"}]
        if cells:
            rows.append(" | ".join(cells))
    return "\n".join(rows)


class _Walker:
    def __init__(self) -> None:
        self.page = 1
        self.item = ""
        self.blocks: list[Block] = []

    def emit(self, text: str, is_table: bool = False) -> None:
        if not text or PAGE_NUMBER_RE.match(text):
            return
        if not is_table and len(text) < 160:
            m = ITEM_RE.match(text)
            if m:
                self.item = m.group(1).upper()
        self.blocks.append(Block(text, self.page, self.item, is_table))

    def walk(self, node: Node) -> None:
        tag = node.tag
        if tag in SKIP_TAGS:
            return
        style = _style(node)
        if "display:none" in style:
            return
        if "page-break-before:always" in style or "break-before:page" in style:
            self.page += 1

        if tag == "table":
            text = _table_text(node)
            if "\n" not in text and len(text) < 200:
                # one short row is layout, not data. Amazon and Walmart put
                # their "ITEM 1A. | Risk Factors" headings in tables like this.
                self.emit(text.replace(" | ", " "))
            else:
                self.emit(text, is_table=True)
        elif tag in BLOCK_TAGS and not any(c.tag in BLOCK_TAGS for c in node.iter()):
            self.emit(_clean(node.text(separator=" ")))
        else:
            for child in node.iter():
                self.walk(child)

        if "page-break-after:always" in style or "break-after:page" in style:
            self.page += 1


def parse_10k(html: str) -> list[Block]:
    tree = HTMLParser(html)
    body = tree.body or tree.root
    walker = _Walker()
    walker.walk(body)
    return walker.blocks
