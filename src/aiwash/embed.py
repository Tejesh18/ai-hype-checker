"""Local text embeddings. No API key, runs on CPU.

bge-small is 33M parameters: small enough to embed a few thousand
paragraphs on a laptop in under a minute, and good enough on retrieval
benchmarks that it's a fair baseline to beat later with fine-tuning.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


@lru_cache(maxsize=2)
def _model(name: str):
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=name, cache_dir="models")


def embed(texts: list[str], model: str = DEFAULT_MODEL) -> np.ndarray:
    """Returns unit-length vectors, so a dot product is cosine similarity."""
    if not texts:
        return np.zeros((0, 384), dtype=np.float32)
    vecs = np.array(list(_model(model).embed(texts, batch_size=32)), dtype=np.float32)
    return vecs / np.linalg.norm(vecs, axis=1, keepdims=True)
