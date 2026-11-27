"""Keep the published behavioral study tied to its inputs, model prompts and adjudications."""

import hashlib
import json

from scripts.compare_atomic_verifier import ARMS, ATOMIC_PROMPT, DATA, MODEL, PROJECT_ROOT, PROMPT, WRITER, summarize


def test_paired_results_and_review_match_the_frozen_inputs():
    reports = PROJECT_ROOT / "data/eval/reports"
    raw = (reports / "atomic-verifier-comparison.json").read_bytes()
    report = json.loads(raw)
    review = json.loads((reports / "atomic-verifier-answer-review.json").read_bytes())
    cases = json.loads(DATA.read_bytes())
    assert report["dataset_sha256"] == hashlib.sha256(DATA.read_bytes()).hexdigest()
    assert review["comparison_sha256"] == hashlib.sha256(raw).hexdigest()
    assert (report["model"], report["temperature"]) == (MODEL, 0)
    assert (report["baseline_prompt"], report["candidate_prompt"], report["writer_prompt"]) == (
        PROMPT,
        ATOMIC_PROMPT,
        WRITER,
    )
    assert len(cases) == len({c["id"] for c in cases}) == 24
    for arm in ARMS:
        assert report["summary"][arm] == summarize(cases, report["cases"], arm)
        decisions = review["cases"]
        assert [r["id"] for r in decisions] == [c["id"] for c in cases]
        assert review["complete"][arm] == sum(not d[arm]["missing"] and not d[arm]["unsupported"] for d in decisions)


def test_regression_predictions_match_the_published_cases():
    from scripts.compare_atomic_verifier import BASELINE_REPORT
    from scripts.measure_heldout import LABELLED_SET_RELATIVE

    report = json.loads((PROJECT_ROOT / "data/eval/reports/atomic-verifier-comparison.json").read_bytes())["regression"]
    baseline = json.loads(BASELINE_REPORT.read_bytes())
    data = (PROJECT_ROOT / LABELLED_SET_RELATIVE).read_bytes()
    cases = [json.loads(line) for line in data.splitlines()]
    assert report["input_sha256"] == baseline["input_sha256"] == hashlib.sha256(data).hexdigest()
    assert report["published_baseline_correct"] == baseline["correct"]
    assert report["total"] == len(cases)
    assert [r["id"] for r in report["predictions"]] == [c["id"] for c in cases]
    assert report["correct"] == sum(
        c["label"] == r["prediction"] for c, r in zip(cases, report["predictions"], strict=True)
    )


def test_invalid_replies_count_as_failures_for_both_arms():
    from ledgerlens.offline import ScriptedChatModel
    from scripts.compare_atomic_verifier import evaluate

    model = ScriptedChatModel(script=["unsupported-format", "unsupported-format"])
    row = evaluate({"id": "invalid", "claim": "Claim.", "evidence": "Evidence."}, model)
    for arm in ARMS:
        assert row[arm]["label"] == "invalid"
        assert "written_answer" not in row[arm]
