"""Live set: claims in the real agent's shape, with the real evidence, and the NLI thresholds.

The verification set has short sentences the NLI model splits into 0.0 or 1.0, whatever the threshold. This
one carries sentences in the shape `gpt-4.1-mini` wrote, against the evidence the tools returned, labeled by
reading the evidence (see `data/eval/verification_live.jsonl`). The slow test scores both sets with the real
model and checks that the thresholds in `thresholds.json` follow the rule in `calibration.rule`.
"""

from __future__ import annotations

import importlib.util
import itertools
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ledgerlens.schemas import Claim, Evidence
from ledgerlens.verify.checks import label_from_scores, load_thresholds, text_premise
from ledgerlens.verify.nli import MODEL_ID, HuggingFaceNli

DATA = Path(__file__).resolve().parents[2] / "data" / "eval"
NOW = datetime(2026, 11, 8, tzinfo=UTC)
SOURCE_TOOL = {
    "sql": ("sql", "query_ledger"),
    "api": ("ledger_api", "get_ledger_record"),
    "policy": ("policy", "search_policies"),
    "fx": ("fx", "get_reference_fx"),
    "calc": ("calc", "calculate"),
    "case": ("case", "recall_cases"),
}
LABELS = {"supported", "contradicted", "not_enough_evidence"}


def read(name: str) -> list[dict]:
    return [json.loads(line) for line in (DATA / name).read_text().splitlines() if line.strip()]


def evidence(evidence_id: str, content: str) -> Evidence:
    source, tool = SOURCE_TOOL[evidence_id.split(":")[0]]
    return Evidence(id=evidence_id, source_type=source, tool=tool, content=content, ref=evidence_id, retrieved_at=NOW)


def text_cases() -> list[tuple[str, str, str, str]]:
    """(set, id, label, premise, claim) of the cases that go to the NLI model, with the premise the verifier builds."""
    limit = int(load_thresholds()["max_premise_chars"])
    cases = []
    for case in read("verification_set.jsonl"):
        if case["type"] != "text":
            continue
        evidence_id = "policy:1" if case["evidence"].startswith("Policy") else "sql:1"
        claim = Claim(id="CL1", text=case["claim"], kind="fact", evidence_ids=[evidence_id])
        premise = text_premise(claim, {evidence_id: evidence(evidence_id, case["evidence"])}, limit)
        cases.append(("verification", case["id"], case["expected"], premise, case["claim"]))
    for case in read("verification_live.jsonl"):
        by_id = {e["id"]: evidence(e["id"], e["content"]) for e in case["evidence"]}
        claim = Claim(id="CL1", text=case["claim"], kind="fact", evidence_ids=case["evidence_ids"])
        cases.append(("live", case["id"], case["label"], text_premise(claim, by_id, limit), case["claim"]))
    return cases


def test_the_live_set_has_both_classes_and_every_claim_has_its_evidence() -> None:
    rows = read("verification_live.jsonl")
    assert len(rows) >= 20
    assert {r["label"] for r in rows} == LABELS
    assert len({r["id"] for r in rows}) == len(rows)
    for row in rows:
        assert row["evidence"] and {e["id"] for e in row["evidence"]} == set(row["evidence_ids"]), row["id"]
        assert row["origin"] and row["note"], row["id"]


def pick_thresholds(scored: list[tuple[str, dict[str, float]]]) -> tuple[float, float]:
    """The rule: no false `supported` or `contradicted`, the highest accuracy; on a tie, the middle of the plateau."""
    grid = [round(0.30 + 0.01 * i, 2) for i in range(70)]
    results = {}
    for entailment, contradiction in itertools.product(grid, grid):
        t = {"entailment_min": entailment, "contradiction_min": contradiction}
        labels = [(label, label_from_scores(scores, t)) for label, scores in scored]
        false_supported = sum(p == "supported" and label != "supported" for label, p in labels)
        false_contradicted = sum(p == "contradicted" and label != "contradicted" for label, p in labels)
        results[(entailment, contradiction)] = (false_supported, false_contradicted, sum(p == lb for lb, p in labels))
    safe = {k: v for k, v in results.items() if v[0] == 0 and v[1] == 0}
    best = max(v[2] for v in safe.values())
    plateau = [k for k, v in safe.items() if v[2] == best]
    return (
        round(sum(k[0] for k in plateau) / len(plateau), 2),
        round(sum(k[1] for k in plateau) / len(plateau), 2),
    )


@pytest.mark.slow
@pytest.mark.skipif(importlib.util.find_spec("transformers") is None, reason="extra `verify` is not installed")
def test_the_chosen_thresholds_follow_the_calibration_rule_on_both_sets() -> None:
    thresholds = load_thresholds()
    nli = HuggingFaceNli(MODEL_ID)
    cases = text_cases()
    scored = [(label, nli.predict(premise, claim)) for _, _, label, premise, claim in cases]
    predicted = [label_from_scores(scores, thresholds) for _, scores in scored]
    false_supported = [c[1] for c, p in zip(cases, predicted, strict=True) if p == "supported" and c[2] != "supported"]
    false_contradicted = [
        c[1] for c, p in zip(cases, predicted, strict=True) if p == "contradicted" and c[2] != "contradicted"
    ]
    assert false_supported == [] and false_contradicted == []
    # no threshold pair without false `supported` and `contradicted` gets more right than the chosen one
    chosen = sum(p == c[2] for c, p in zip(cases, predicted, strict=True))
    best_entailment, best_contradiction = pick_thresholds(scored)
    t = {"entailment_min": best_entailment, "contradiction_min": best_contradiction}
    assert chosen >= sum(label_from_scores(s, t) == label for label, s in scored)
    assert thresholds["entailment_min"] == best_entailment
    assert thresholds["contradiction_min"] == best_contradiction
