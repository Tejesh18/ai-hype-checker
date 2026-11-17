"""The TF-IDF classifier without scikit-learn, for AWS Lambda.

Production uses the TF-IDF model rather than the embedding model:
it ties on macro F1 (0.73), its weights are a 183 KB JSON file, and it
needs no numpy, onnxruntime or model download, so a cold start takes
milliseconds. The embedding model is a little better on concrete vs vague
but would mean a ~130 MB container for every filing.

This reproduces sklearn's TfidfVectorizer(ngram_range=(1, 2),
sublinear_tf=True) + LogisticRegression exactly; tests/test_lite.py checks
it against sklearn on every labeled sentence.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

_TOKEN = re.compile(r"(?u)\b\w\w+\b")  # sklearn's default token_pattern


class LiteClassifier:
    def __init__(self, model: dict):
        self.classes = model["classes"]
        self.index = {w: i for i, w in enumerate(model["vocab"])}
        self.idf = model["idf"]
        self.coef = model["coef"]
        self.intercept = model["intercept"]

    @classmethod
    def load(cls, path: str | Path) -> "LiteClassifier":
        return cls(json.loads(Path(path).read_text()))

    def _features(self, text: str) -> dict[int, float]:
        toks = _TOKEN.findall(text.lower())
        grams = toks + [f"{a} {b}" for a, b in zip(toks, toks[1:])]
        counts: dict[int, int] = {}
        for g in grams:
            j = self.index.get(g)
            if j is not None:
                counts[j] = counts.get(j, 0) + 1
        x = {j: (1 + math.log(n)) * self.idf[j] for j, n in counts.items()}
        norm = math.sqrt(sum(v * v for v in x.values())) or 1.0
        return {j: v / norm for j, v in x.items()}

    def predict(self, text: str) -> str:
        x = self._features(text)
        scores = [b + sum(row[j] * v for j, v in x.items()) for row, b in zip(self.coef, self.intercept)]
        return self.classes[max(range(len(scores)), key=scores.__getitem__)]
