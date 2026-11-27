"""Run a paired verification experiment with frozen inputs and identical answer writers."""

import argparse
import hashlib
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ledgerlens.config import PROJECT_ROOT, get_chat_model, get_settings
from ledgerlens.verify.atomic_classifier import PROMPT as ATOMIC_PROMPT
from ledgerlens.verify.atomic_classifier import AtomicEvidenceClassifier
from ledgerlens.verify.openai_classifier import PROMPT, EvidenceClassifier
from scripts.measure_heldout import score_regression_classifier
from scripts.measure_openai_verifier import MODEL
from scripts.measure_openai_verifier import OUTPUT as BASELINE_REPORT

DATA = PROJECT_ROOT / "data/eval/atomic_verifier_pairs.json"
WRITER = (
    "Explain the verification decision to a payments analyst using the supplied evidence. "
    "Name the relevant facts and distinguish what is established from what remains uncertain. "
    "Use the verifier result and do not introduce unsupported facts. Answer in English."
)
ARMS = ("baseline", "candidate")


def evaluate(case, model):
    evidence, claim = case["evidence"], case["claim"]
    results = {}
    try:
        baseline = EvidenceClassifier(model).predict(evidence, claim)
        results["baseline"] = {"label": max(baseline, key=baseline.get)}
    except ValueError as exc:
        results["baseline"] = {"label": "invalid", "error": str(exc)}
    try:
        results["candidate"] = AtomicEvidenceClassifier(model).assess(evidence, claim)
    except ValueError as exc:
        # Invalid structured output counts as a failed case and an incomplete answer.
        results["candidate"] = {"label": "invalid", "error": str(exc)}
    for arm in ARMS:
        verdict = results[arm]
        if "error" in verdict:
            continue
        payload = {"claim": claim, "evidence": evidence, "verification": verdict}
        reply = model.invoke([("system", WRITER), ("human", json.dumps(payload))])
        results[arm] = {**verdict, "written_answer": reply.text.strip()}
    return {"id": case["id"], **results}


def summarize(cases, rows, arm):
    pairs = defaultdict(list)
    by_slice = defaultdict(list)
    slice_pairs = defaultdict(set)
    slice_false_supported = defaultdict(int)
    false_supported = 0
    for case, row in zip(cases, rows, strict=True):
        assert case["id"] == row["id"]
        label = row[arm]["label"]
        correct = label == case["expected"]
        pairs[case["pair_id"]].append(correct)
        by_slice[case["slice"]].append(correct)
        slice_pairs[case["slice"]].add(case["pair_id"])
        slice_false_supported[case["slice"]] += label == "entailment" and not correct
        false_supported += label == "entailment" and not correct
    if any(len(pair) != 2 for pair in pairs.values()):
        raise ValueError("Each contrast or invariance pair needs two cases.")
    return {
        "correct": sum(sum(v) for v in pairs.values()),
        "total": len(rows),
        "correct_pairs": sum(all(v) for v in pairs.values()),
        "pairs": len(pairs),
        "false_supported": false_supported,
        "by_slice": {
            k: {
                "correct": sum(v),
                "total": len(v),
                "pairs": len(slice_pairs[k]),
                "correct_pairs": sum(all(pairs[pair]) for pair in slice_pairs[k]),
                "false_supported": slice_false_supported[k],
            }
            for k, v in by_slice.items()
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    settings = get_settings()
    if settings.offline or not settings.openai_api_key:
        parser.error("Online mode and a configured OpenAI key are required.")
    model = get_chat_model(settings, model=MODEL, temperature=0)
    data = DATA.read_bytes()
    cases = json.loads(data)
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(lambda case: evaluate(case, model), cases))
    report = {
        "model": MODEL,
        "temperature": 0,
        "baseline_prompt": PROMPT,
        "candidate_prompt": ATOMIC_PROMPT,
        "writer_prompt": WRITER,
        "dataset_sha256": hashlib.sha256(data).hexdigest(),
        "summary": {arm: summarize(cases, rows, arm) for arm in ARMS},
        "cases": rows,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    baseline = json.loads(BASELINE_REPORT.read_bytes())
    report["regression"] = score_regression_classifier(AtomicEvidenceClassifier(model), baseline)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
