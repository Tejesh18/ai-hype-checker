"""Find every sentence in a 10-K that talks about AI.

Matching is deliberately simple and high-recall: acronyms (AI, GenAI, LLM)
case-sensitive so "said" or "maintain" never match, and the long phrases
case-insensitive. Precision problems get handled downstream by labeling,
not by making this regex clever.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from .parse import ITEM_NAMES

_AI_ACRONYM = re.compile(r"\b(?:AI|GenAI|LLMs?)\b")
_AI_PHRASE = re.compile(
    r"artificial intelligence|machine learning|large language models?|generative AI|neural network",
    re.IGNORECASE,
)

# Sections that list exhibits or legal boilerplate rather than say anything
SKIP_ITEMS = {"15", "16"}


def ai_mentions(text: str) -> int:
    return len(_AI_ACRONYM.findall(text)) + len(_AI_PHRASE.findall(text))


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z(“\"])", text.replace("\n", " "))
    return [p.strip() for p in parts if len(p.split()) >= 5]


@dataclass
class Claim:
    claim_id: str
    ticker: str
    fiscal_year: int
    item: str
    section: str
    page: int
    sentence: str
    context: str  # the paragraph it came from, for labeling
    url: str


def extract_claims(blocks: list[dict]) -> list[Claim]:
    """blocks: one filing's rows from data/blocks.parquet, in document order."""
    claims: list[Claim] = []
    seen: set[str] = set()
    for b in blocks:
        if b["is_table"] or b["item"] in SKIP_ITEMS or not ai_mentions(b["text"]):
            continue
        for sentence in split_sentences(b["text"]):
            if not ai_mentions(sentence):
                continue
            key = re.sub(r"\W+", " ", sentence.lower()).strip()
            if key in seen:  # filings repeat themselves; count a claim once
                continue
            seen.add(key)
            digest = hashlib.sha1(key.encode()).hexdigest()[:8]
            claims.append(
                Claim(
                    claim_id=f"{b['ticker']}-{b['fiscal_year']}-{digest}",
                    ticker=b["ticker"],
                    fiscal_year=b["fiscal_year"],
                    item=b["item"],
                    section=f"Item {b['item']}. {ITEM_NAMES.get(b['item'], '')}" if b["item"] else "Cover",
                    page=b["page"],
                    sentence=sentence,
                    context=b["text"][:1500],
                    url=b["url"],
                )
            )
    return claims
