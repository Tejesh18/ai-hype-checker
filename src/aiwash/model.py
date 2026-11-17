"""Classify AI sentences as concrete / vague / risk / context.

Four approaches, evaluated on the same stratified 5-fold split so the
numbers are comparable:

1. rules       hand-written keyword rules, the "do we even need ML?" baseline
2. tfidf       TF-IDF word n-grams + logistic regression
3. embed       frozen bge-small sentence embeddings + logistic regression
4. finetune    bge-small fine-tuned end to end on our labels, with a
               linear classification head. Needs the `finetune` extra.

With ~250 labels, cross-validation matters more than a single test split:
one unlucky split can swing macro-F1 by 10 points.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

LABELS = ["concrete", "vague", "risk", "context"]


@dataclass
class Example:
    sentence: str
    section: str
    label: str

    @property
    def text(self) -> str:
        # The section is a strong hint (Risk Factors vs Business), so the
        # learned models get to see it.
        return f"{self.section}: {self.sentence}"


def load_labels(path: Path = Path("labels/labels.csv")) -> list[Example]:
    with path.open() as f:
        return [Example(r["sentence"], r["section"], r["label"]) for r in csv.DictReader(f)]


# --- 1. rules ---------------------------------------------------------------

_CONTEXT = re.compile(
    r"forward-looking|competitors (?:include|to)|\bAI Act\b|Executive Order|Code of Practice"
    r"|training programs|educational|^[A-Z][\w ,&\-]{0,60}:?$",
)
_RISK = re.compile(
    r"\b(?:may|could|might|risks?|threats?|uncertain\w*|liabilit\w*|advers\w*|exacerbat\w*|malicious"
    r"|attack\w*|fraud|cyber\w*|regulat\w*|laws?|scrutiny|litigation|infring\w*|competition|competitors)\b",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"\$\s?\d|\b\d+(?:\.\d+)?\s?(?:%|x\b|percent|billion|million)|\b(?:19|20)\d{2}\b")
# Product-looking names: CamelCase (DGX, NeMo), or a capitalized brand word
# right before/after AI terms. Crude on purpose; it's a baseline.
_PRODUCT = re.compile(r"\b(?:[A-Z][a-z]+[A-Z]\w*|[A-Z]{2,}[a-z]*\d*)\b")
_NOT_PRODUCTS = {"AI", "EU", "US", "GPU", "GPUs", "LLM", "LLMs", "HPC", "CEO", "USG", "IFR", "FTC", "GDPR", "CCPA", "LRRs"}


def rules(examples: list[Example]) -> list[str]:
    out = []
    for e in examples:
        s = e.sentence
        products = [p for p in _PRODUCT.findall(s) if p not in _NOT_PRODUCTS]
        if _CONTEXT.search(s):
            out.append("context")
        elif e.section.startswith("Item 1A") or len(_RISK.findall(s)) >= 2:
            out.append("risk")
        elif _NUMBER.search(s) or products:
            out.append("concrete")
        else:
            out.append("vague")
    return out


# --- 2-4. learned models ----------------------------------------------------


def _logreg():
    from sklearn.linear_model import LogisticRegression

    # balanced: risk is ~60% of the data and would otherwise swallow the rest
    return LogisticRegression(max_iter=4000, class_weight="balanced", C=4.0)


def fit_tfidf_pipeline(train: list[Example]):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.pipeline import make_pipeline

    model = make_pipeline(TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True), _logreg())
    model.fit([e.text for e in train], [e.label for e in train])
    return model


def fit_tfidf(train: list[Example]):
    model = fit_tfidf_pipeline(train)
    return lambda xs: list(model.predict([e.text for e in xs]))


def fit_embed(train: list[Example]):
    from .embed import embed

    clf = _logreg().fit(embed([e.text for e in train]), [e.label for e in train])
    return lambda xs: list(clf.predict(embed([e.text for e in xs])))


def fit_finetune(train: list[Example], seed: int = 7, epochs: int = 4, batch_size: int = 16):
    """Fine-tune bge-small end to end with a linear head on top.

    Small learning rate for the pretrained encoder, a larger one for the new
    head, and class weights so the 60% "risk" majority doesn't dominate the
    loss. bge models are trained to use the [CLS] vector as the sentence
    embedding, so that's what the head reads.
    """
    import torch
    from torch import nn
    from transformers import AutoModel, AutoTokenizer

    torch.manual_seed(seed)
    torch.set_num_threads(max(torch.get_num_threads(), 2))
    name = "BAAI/bge-small-en-v1.5"
    tok = AutoTokenizer.from_pretrained(name, cache_dir="models")
    encoder = AutoModel.from_pretrained(name, cache_dir="models")
    head = nn.Linear(encoder.config.hidden_size, len(LABELS))

    texts = [e.text for e in train]
    y = torch.tensor([LABELS.index(e.label) for e in train])
    counts = torch.bincount(y, minlength=len(LABELS)).float().clamp(min=1)
    loss_fn = nn.CrossEntropyLoss(weight=counts.sum() / (len(LABELS) * counts))
    opt = torch.optim.AdamW(
        [{"params": encoder.parameters(), "lr": 3e-5}, {"params": head.parameters(), "lr": 1e-3}],
        weight_decay=0.01,
    )

    def cls(batch: list[str]) -> torch.Tensor:
        t = tok(batch, padding=True, truncation=True, max_length=128, return_tensors="pt")
        return encoder(**t).last_hidden_state[:, 0]

    encoder.train()
    g = torch.Generator().manual_seed(seed)
    for _ in range(epochs):
        for idx in torch.randperm(len(texts), generator=g).split(batch_size):
            loss = loss_fn(head(cls([texts[i] for i in idx])), y[idx])
            opt.zero_grad()
            loss.backward()
            opt.step()

    encoder.eval()

    def predict(xs: list[Example]) -> list[str]:
        out: list[str] = []
        with torch.no_grad():
            for i in range(0, len(xs), 64):
                logits = head(cls([e.text for e in xs[i : i + 64]]))
                out.extend(LABELS[j] for j in logits.argmax(-1).tolist())
        return out

    return predict


FITTERS = {"tfidf": fit_tfidf, "embed": fit_embed, "finetune": fit_finetune}


def cross_validate(examples: list[Example], methods: list[str], folds: int = 5, seed: int = 7) -> dict:
    from sklearn.metrics import confusion_matrix, f1_score
    from sklearn.model_selection import StratifiedKFold

    y = np.array([e.label for e in examples])
    preds = {m: np.empty(len(examples), dtype=object) for m in methods}
    skf = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
    for train_idx, test_idx in skf.split(np.zeros(len(y)), y):
        train = [examples[i] for i in train_idx]
        test = [examples[i] for i in test_idx]
        for m in methods:
            predict = rules if m == "rules" else FITTERS[m](train)
            preds[m][test_idx] = predict(test)

    results = {}
    for m in methods:
        p = preds[m].astype(str)
        per_class = f1_score(y, p, labels=LABELS, average=None, zero_division=0)
        results[m] = {
            "macro_f1": float(f1_score(y, p, labels=LABELS, average="macro", zero_division=0)),
            "accuracy": float((p == y).mean()),
            "per_class_f1": dict(zip(LABELS, map(float, per_class))),
            "confusion": confusion_matrix(y, p, labels=LABELS).tolist(),
        }
    return results


def export_embed_head(examples: list[Example], path: Path) -> None:
    """Train embeddings + logistic regression on every label and save the
    classifier weights as JSON. The scorer Lambda embeds with bge-small and
    applies these weights with a dot product, so it doesn't need sklearn."""
    import json

    from .embed import DEFAULT_MODEL, embed

    clf = _logreg().fit(embed([e.text for e in examples]), [e.label for e in examples])
    path.write_text(json.dumps({
        "embed_model": DEFAULT_MODEL,
        "classes": [str(c) for c in clf.classes_],
        "coef": clf.coef_.round(6).tolist(),
        "intercept": clf.intercept_.round(6).tolist(),
    }))


def train_full(examples: list[Example], method: str):
    return rules if method == "rules" else FITTERS[method](examples)
