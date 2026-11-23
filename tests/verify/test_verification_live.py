"""Live set: claims in the real agent's shape, with the real evidence, and the NLI thresholds.

The verification set has short sentences the NLI model splits into 0.0 or 1.0, whatever the threshold. This
one carries sentences in the shape `gpt-4.1-mini` wrote, against the evidence the tools returned, labeled by
reading the evidence (see `data/eval/verification_live.jsonl`). The slow test scores both sets with the real
model and checks that the thresholds in `thresholds.json` follow the rule in `calibration.rule`.

The cases of the sweep and the rule that chooses the thresholds live in `ledgerlens/verify/sweep.py`, so this test
and the script `scripts/sweep_nli_thresholds.py` measure over the same cases and choose with the same rule.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from ledgerlens.config import PROJECT_ROOT
from ledgerlens.eval.manifest import load_manifests
from ledgerlens.verify.checks import label_from_scores, load_thresholds
from ledgerlens.verify.nli import MODEL_ID, HuggingFaceNli
from ledgerlens.verify.sweep import nli_cases, pick_thresholds

DATA = Path(__file__).resolve().parents[2] / "data" / "eval"
LABELS = {"supported", "contradicted", "not_enough_evidence"}


def read(name: str) -> list[dict]:
    """The records of a dataset of the evaluation."""
    return [json.loads(line) for line in (DATA / name).read_text().splitlines() if line.strip()]


def test_the_live_set_has_both_classes_and_every_claim_has_its_evidence() -> None:
    rows = read("verification_live.jsonl")
    assert len(rows) >= 20
    assert {r["label"] for r in rows} == LABELS
    assert len({r["id"] for r in rows}) == len(rows)
    for row in rows:
        assert row["evidence"] and {e["id"] for e in row["evidence"]} == set(row["evidence_ids"]), row["id"]
        assert row["origin"] and row["note"], row["id"]


@pytest.mark.slow
@pytest.mark.skipif(importlib.util.find_spec("transformers") is None, reason="extra `verify` is not installed")
def test_the_chosen_thresholds_follow_the_calibration_rule_on_both_sets() -> None:
    thresholds = load_thresholds()
    nli = HuggingFaceNli(MODEL_ID)
    cases = nli_cases(PROJECT_ROOT, load_manifests())
    scored = [(case.label, nli.predict(case.premise, case.claim)) for case in cases]
    predicted = [label_from_scores(scores, thresholds) for _, scores in scored]
    false_supported = [
        c.case_id for c, p in zip(cases, predicted, strict=True) if p == "supported" and c.label != "supported"
    ]
    false_contradicted = [
        c.case_id for c, p in zip(cases, predicted, strict=True) if p == "contradicted" and c.label != "contradicted"
    ]
    assert false_supported == [] and false_contradicted == []
    # no threshold pair without false `supported` and `contradicted` gets more right than the chosen one
    chosen = sum(p == c.label for c, p in zip(cases, predicted, strict=True))
    best_entailment, best_contradiction = pick_thresholds(scored)
    t = {"entailment_min": best_entailment, "contradiction_min": best_contradiction}
    assert chosen >= sum(label_from_scores(s, t) == label for label, s in scored)
    assert thresholds["entailment_min"] == best_entailment
    assert thresholds["contradiction_min"] == best_contradiction
