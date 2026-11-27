"""Keep the public classifier score reproducible without private generator recipes."""

import shutil
from unittest.mock import Mock

import pytest

from ledgerlens.verify.nli import StubNli
from scripts import measure_heldout as scorer


def test_public_scorer_requires_only_the_manifest_and_adjudications(tmp_path, monkeypatch):
    for relative in (scorer.LABELLED_SET_RELATIVE, scorer.MANIFEST_RELATIVE):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(scorer.ROOT / relative, target)
    monkeypatch.setattr(scorer, "ROOT", tmp_path)
    result = scorer.score_fixed_classifier(StubNli())
    assert len(result["predictions"]) == result["total"] == 48

    with (tmp_path / scorer.LABELLED_SET_RELATIVE).open("ab") as cases:
        cases.write(b"\n")
    classifier = Mock()
    with pytest.raises(scorer.MeasureRefusal, match="manifest"):
        scorer.score_fixed_classifier(classifier)
    classifier.predict.assert_not_called()
