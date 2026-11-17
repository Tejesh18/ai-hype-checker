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

app = typer.Typer(help="Score the AI claims in SEC 10-K filings.", no_args_is_help=True)
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


@app.command()
def sample(
    per_filing: int = typer.Option(10, help="Max claims to draw from each filing."),
    seed: int = typer.Option(7),
    out: Path = typer.Option(Path("labels/to_label.csv")),
) -> None:
    """Draw a labeling sample spread evenly across filings.

    A plain random sample would be mostly Microsoft, NVIDIA and Google, who
    together write over a third of all AI sentences. Capping per filing keeps
    banks, retailers and Exxon in the set.
    """
    import csv
    import random

    rows = pq.read_table(CLAIMS_PATH).to_pylist()
    by_filing: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for r in rows:
        by_filing[(r["ticker"], r["fiscal_year"])].append(r)
    rng = random.Random(seed)
    picked = []
    for key in sorted(by_filing):
        group = by_filing[key]
        picked.extend(rng.sample(group, min(per_filing, len(group))))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, ["claim_id", "ticker", "fiscal_year", "section", "page", "sentence", "label"])
        w.writeheader()
        for r in picked:
            w.writerow({k: r.get(k, "") for k in w.fieldnames})
    console.print(f"[green]{len(picked)} claims from {len(by_filing)} filings -> {out}[/green]")


@app.command()
def evaluate(
    methods: str = typer.Option("rules,tfidf,embed,finetune", help="Comma-separated."),
    out: Path = typer.Option(Path("results/metrics.json")),
) -> None:
    """Compare classifiers with 5-fold cross-validation on the labeled set."""
    import json

    from .model import LABELS, cross_validate, load_labels

    examples = load_labels()
    names = [m.strip() for m in methods.split(",")]
    results = cross_validate(examples, names)
    table = Table("method", "macro F1", "accuracy", *[f"F1 {l}" for l in LABELS])
    for m, r in results.items():
        table.add_row(m, f"{r['macro_f1']:.3f}", f"{r['accuracy']:.3f}", *[f"{r['per_class_f1'][l]:.2f}" for l in LABELS])
    console.print(f"{len(examples)} labeled sentences, 5-fold stratified CV")
    console.print(table)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"n": len(examples), "folds": 5, "results": results}, indent=2))


@app.command()
def score(
    method: str = typer.Option("", help="Classifier to use. Default: best macro-F1 in results/metrics.json."),
) -> None:
    """Label every claim and score each company's AI substance."""
    import csv
    import json

    from .model import Example, load_labels, train_full

    if not method:
        metrics = json.loads(Path("results/metrics.json").read_text())["results"]
        method = max(metrics, key=lambda m: metrics[m]["macro_f1"])
    labeled = load_labels()
    gold = {e.sentence: e.label for e in labeled}
    predict = train_full(labeled, method)

    claims = pq.read_table(CLAIMS_PATH).to_pylist()
    preds = predict([Example(c["sentence"], c["section"], "") for c in claims])
    for c, p in zip(claims, preds):
        c["label"] = gold.get(c["sentence"], p)
        c["label_source"] = "human" if c["sentence"] in gold else method

    out = Path("results")
    out.mkdir(exist_ok=True)
    fields = ["claim_id", "ticker", "fiscal_year", "section", "page", "label", "label_source", "sentence", "url"]
    with (out / "claims_scored.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(claims)

    by_filing: dict[tuple[str, int], Counter] = defaultdict(Counter)
    for c in claims:
        by_filing[(c["ticker"], c["fiscal_year"])][c["label"]] += 1
    rows = []
    for (t, y), n in sorted(by_filing.items()):
        own = n["concrete"] + n["vague"]
        total = sum(n.values())
        rows.append({
            "ticker": t, "fiscal_year": y, "ai_sentences": total,
            "concrete": n["concrete"], "vague": n["vague"], "risk": n["risk"], "context": n["context"],
            "substance": round(n["concrete"] / own, 3) if own else None,
            "risk_share": round(n["risk"] / total, 3) if total else None,
        })
    with (out / "companies.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, rows[0].keys())
        w.writeheader()
        w.writerows(rows)

    table = Table("ticker", "FY", "AI sentences", "concrete", "vague", "risk", "context", "substance")
    for r in rows:
        table.add_row(r["ticker"], str(r["fiscal_year"]), str(r["ai_sentences"]), str(r["concrete"]), str(r["vague"]),
                      str(r["risk"]), str(r["context"]), "-" if r["substance"] is None else f"{r['substance']:.0%}")
    console.print(f"labeled with [bold]{method}[/bold] ({sum(c['label_source'] == 'human' for c in claims)} human labels kept)")
    console.print(table)


@app.command()
def site(out: Path = typer.Option(Path("docs/data.json"))) -> None:
    """Export results for the static site in docs/."""
    import csv
    import json

    companies = list(csv.DictReader(Path("results/companies.csv").open()))
    claims = list(csv.DictReader(Path("results/claims_scored.csv").open()))
    metrics = json.loads(Path("results/metrics.json").read_text())
    payload = {
        "companies": companies,
        "claims": [
            {k: c[k] for k in ("ticker", "fiscal_year", "section", "page", "label", "label_source", "sentence", "url")}
            for c in claims
        ],
        "metrics": metrics,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, separators=(",", ":")))
    console.print(f"[green]wrote {out} ({out.stat().st_size // 1024} KB)[/green]")

    # The draft checker on the site runs the TF-IDF model in the browser.
    # Export exactly what sklearn computes: vocabulary, idf, and the
    # logistic-regression weights, so the JS can reproduce predictions.
    from .model import fit_tfidf_pipeline, load_labels

    pipe = fit_tfidf_pipeline(load_labels())
    vec, clf = pipe.steps[0][1], pipe.steps[1][1]
    vocab = sorted(vec.vocabulary_, key=vec.vocabulary_.get)
    model = {
        "classes": [str(c) for c in clf.classes_],
        "vocab": vocab,
        "idf": [round(float(x), 5) for x in vec.idf_],
        "coef": [[round(float(x), 5) for x in row] for row in clf.coef_],
        "intercept": [round(float(x), 5) for x in clf.intercept_],
    }
    mpath = out.parent / "model.json"
    mpath.write_text(json.dumps(model, separators=(",", ":")))
    console.print(f"[green]wrote {mpath} ({mpath.stat().st_size // 1024} KB, {len(vocab)} features)[/green]")


if __name__ == "__main__":
    app()
