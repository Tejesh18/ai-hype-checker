from pathlib import Path

import pytest

from aiwash.lite import LiteClassifier
from aiwash.model import fit_tfidf_pipeline, load_labels


@pytest.mark.skipif(not Path("labels/labels.csv").exists(), reason="needs the labeled set")
def test_lite_matches_sklearn_on_every_labeled_sentence(tmp_path):
    import json

    examples = load_labels()
    pipe = fit_tfidf_pipeline(examples)
    vec, clf = pipe.steps[0][1], pipe.steps[1][1]
    model = {
        "classes": [str(c) for c in clf.classes_],
        "vocab": sorted(vec.vocabulary_, key=vec.vocabulary_.get),
        "idf": vec.idf_.tolist(),
        "coef": clf.coef_.tolist(),
        "intercept": clf.intercept_.tolist(),
    }
    path = tmp_path / "model.json"
    path.write_text(json.dumps(model))
    lite = LiteClassifier.load(path)

    texts = [e.text for e in examples]
    assert [lite.predict(t) for t in texts] == list(pipe.predict(texts))
