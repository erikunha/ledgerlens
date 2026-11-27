"""Check that the classifier sees only evidence and its claim and rejects invalid labels."""

import json

import pytest

from ledgerlens.offline import ScriptedChatModel
from ledgerlens.schemas import NliScores
from scripts.measure_openai_verifier import EvidenceClassifier


@pytest.mark.parametrize("label", NliScores.model_fields)
def test_classifier_passes_only_the_pair_and_returns_a_class(label):
    model = ScriptedChatModel(script=[label])
    scores = EvidenceClassifier(model).predict("A train arrived.", "A train arrived.")
    assert scores[label] == sum(scores.values()) == 1
    assert json.loads(model.calls[0][-1].content) == {"evidence": "A train arrived.", "claim": "A train arrived."}


def test_unrecognized_class_stops_the_evaluation():
    with pytest.raises(ValueError, match="unknown class"):
        EvidenceClassifier(ScriptedChatModel(script=["unknown"])).predict("a", "b")


def test_published_report_matches_frozen_adjudicated_cases():
    from hashlib import sha256

    from ledgerlens.config import PROJECT_ROOT
    from ledgerlens.eval.heldout_reader import read_heldout_cases
    from scripts.measure_heldout import LABELLED_SET_RELATIVE
    from scripts.measure_openai_verifier import MODEL, OUTPUT, PROMPT

    labelled = PROJECT_ROOT / LABELLED_SET_RELATIVE
    cases = read_heldout_cases(labelled)
    report = json.loads(OUTPUT.read_text())
    assert report["model"] == MODEL
    assert report["prompt"] == PROMPT
    assert report["input_sha256"] == sha256(labelled.read_bytes()).hexdigest()
    predictions = report["predictions"]
    assert [row["id"] for row in predictions] == [case.case_id for case in cases]
    assert report["total"] == len(cases)
    assert report["correct"] == sum(
        row["prediction"] == case.label for row, case in zip(predictions, cases, strict=True)
    )
    for label in ("supported", "contradicted"):
        assert report[f"false_{label}"] == sum(
            row["prediction"] == label and case.label != label for row, case in zip(predictions, cases, strict=True)
        )


def test_policy_resolution_counts_the_original_questions_and_binds_the_review_to_its_answers():
    from hashlib import sha256

    from ledgerlens.config import PROJECT_ROOT

    reports = PROJECT_ROOT / "data/eval/reports"
    review = json.loads((reports / "policy-openai-verifier-review.json").read_text())
    source = PROJECT_ROOT / review["source_report"]
    answers = json.loads(source.read_bytes())["cases"]
    baseline = json.loads((PROJECT_ROOT / review["baseline_review"]).read_text())["cases"]
    assert review["source_sha256"] == sha256(source.read_bytes()).hexdigest()
    assert [c["case_id"] for c in answers] == [c["case_id"] for c in baseline] == [
        c["case_id"] for c in review["cases"]
    ]
    assert review["total_cases"] == len(answers)
    assert review["resolved_cases"] == sum(c["resolved"] for c in review["cases"])
