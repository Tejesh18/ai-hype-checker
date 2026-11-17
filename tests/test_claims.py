from aiwash.claims import ai_mentions, extract_claims
from aiwash.model import Example, rules


def test_ai_acronym_is_case_sensitive():
    assert ai_mentions("We use AI in our stores.") == 1
    assert ai_mentions("We maintain our said aims.") == 0
    assert ai_mentions("large language models and LLMs") == 2
    assert ai_mentions("Artificial Intelligence and machine learning") == 2


def _block(text, item="1", is_table=False):
    return {"ticker": "TEST", "fiscal_year": 2025, "url": "u", "page": 3, "item": item, "is_table": is_table, "text": text}


def test_extracts_only_ai_sentences_once():
    blocks = [
        _block("We sell drinks. We use AI to forecast demand across our bottlers."),
        _block("We use AI to forecast demand across our bottlers."),  # repeated later in the filing
        _block("Exhibit list mentioning AI tools in a filing index.", item="15"),
        _block("AI | 2024 | 2025", is_table=True),
    ]
    claims = extract_claims(blocks)
    assert [c.sentence for c in claims] == ["We use AI to forecast demand across our bottlers."]
    assert claims[0].section == "Item 1. Business"
    assert claims[0].page == 3


def test_rules_baseline_examples():
    ex = [
        Example("NVIDIA NIM delivers a 2.5x increase in token throughput.", "Item 1. Business", ""),
        Example("We use AI across our operations.", "Item 1. Business", ""),
        Example("AI may increase cybersecurity risks.", "Item 1A. Risk Factors", ""),
        Example("These forward-looking statements include our plans for AI.", "Cover", ""),
    ]
    assert rules(ex) == ["concrete", "vague", "risk", "context"]
