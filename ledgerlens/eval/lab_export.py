"""The export of the Eval Lab: the numbers of the verification and of the evaluation, with their restrictions.

Why the export exists: the site is a static export, so the numbers of the Eval Lab have to exist as a file
before anyone opens the page. The export reads the reports of the repository and writes one file,
`site/eval/index.json`, with the numbers of the verification and of the evaluation, each one with the dataset
it comes from and the restriction that applies to it, the list of the cases that failed with the claim and
the evidence of each one, and the confusion matrix of the verifier with its denominator.

Why every number names its dataset and its restriction: a number without the dataset it was measured over is
a number a reader cannot check, and a number without the restriction that applies to it is a number that
reads as a generalization when it is not one. The restriction of a tuning set says that the decisions of the
repository were taken against it, and the restriction of a held out set says that it is reserved for the
final scoring.

Why the note of the missing model is part of the export: a missing NLI model is not a pass, and the page of
the Eval Lab says so next to the confusion matrix, because a verification that did not run is not a
verification that passed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

__all__ = ["build_eval_lab_export", "check_eval_lab_export", "write_eval_lab_export"]

HELDOUT_REPORT = Path("data/eval/report_heldout.json")
ONLINE_REPORT = Path("data/eval/report_online.json")
VERIFIER_CASES = (
    Path("data/eval/reports/verifier-cases-verification_set.json"),
    Path("data/eval/reports/verifier-cases-verification_live.json"),
)
DATASETS = Path("data/eval/datasets.json")

# The restriction of each role, in one sentence: the restriction of a tuning set is that the decisions of the
# repository were taken against it, and the restriction of a held out set is that it is reserved.
RESTRICTION_BY_ROLE = {
    "tuning": (
        "the thresholds, the prompts and the hyperparameters of the repository were tuned against this set, "
        "so no number over it is a generalization to unseen data"
    ),
    "validation": "this set may be scored but never tuned against",
    "held_out": "this set is reserved for the final scoring, and no decision of the repository was taken against it",
}

# The notes of the page: the two rules a reader of the numbers has to know.
NOTES = (
    "a missing model is not a pass: a case whose verification is unavailable is a case without a verdict",
    "the correctness of the agent and the accuracy of the verifier are two different measurements over two "
    "different sets",
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _role_of(datasets: dict[str, Any], dataset_id: str) -> str:
    for entry in datasets["datasets"]:
        if entry["dataset_id"] == dataset_id:
            return str(entry["split_role"])
    raise ValueError(f"the dataset {dataset_id} is not declared by the manifest")


def build_eval_lab_export(root: Path) -> dict[str, bytes]:
    """The file of the Eval Lab, built from the reports of the repository.

    Every number names the dataset it comes from and the restriction that applies to it, and the confusion
    matrix carries its denominator. The failed cases of the verifier carry the claim and the evidence, and
    the failed cases of the agent carry the scenario and the correctness of the agent.
    """
    heldout = _read_json(root / HELDOUT_REPORT)
    online = _read_json(root / ONLINE_REPORT)
    verifier_case_files = [_read_json(root / path) for path in VERIFIER_CASES]
    datasets = _read_json(root / DATASETS)

    verification_dataset = heldout["dataset"]["dataset_id"]
    verification_role = _role_of(datasets, verification_dataset)
    accuracy = heldout["accuracy"]
    variant_c = online["variants"]["C"]
    agent_dataset = "eval_cases"
    agent_role = _role_of(datasets, agent_dataset)
    correctness = variant_c["metrics"]["correctness"]

    failed_cases: list[dict[str, Any]] = []
    # The failed cases of the verifier over the tuning sets: the per case verdicts over a held out set are
    # never published, because a reading of the held out set that a tuning script can use is the set itself.
    for verifier_cases in verifier_case_files:
        for case in verifier_cases["cases"]:
            if case["outcome"] == "correct":
                continue
            failed_cases.append(
                {
                    "kind": "verifier",
                    "id": case["case_id"],
                    "set_name": verifier_cases["set_name"],
                    "claim": case["claim"],
                    "evidence": case["evidence"],
                    "expected": case["expected"],
                    "got": case["got"],
                    "outcome": case["outcome"],
                }
            )
    # The evaluation runs every case more than once, and a case is failed when the mean of its correctness
    # over the repeats is below one: a case that failed once in three runs is a case that is not resolved.
    runs_by_case: dict[str, list[dict[str, Any]]] = {}
    for case in online["per_case"]:
        if case["variant"] != "C":
            continue
        runs_by_case.setdefault(case["case"], []).append(case)
    for case_id, runs in runs_by_case.items():
        mean = sum(float(run["scores"]["correctness"]) for run in runs) / len(runs)
        if mean >= 1.0:
            continue
        first = runs[0]
        failed_cases.append(
            {
                "kind": "agent",
                "id": case_id,
                "set_name": agent_dataset,
                "scenario": first["scenario"],
                "claim": first["answer"],
                "evidence": "",
                "expected": "the answer the case expects",
                "got": first["answer"],
                "outcome": (
                    f"the agent did not resolve the case "
                    f"(the mean of the correctness over {len(runs)} runs is {mean:.4f})"
                ),
            }
        )

    export = {
        "verification": {
            "dataset_id": verification_dataset,
            "role": verification_role,
            "restriction": RESTRICTION_BY_ROLE[verification_role],
            "denominator": heldout["dataset"]["denominator"],
            "accuracy": str(accuracy["value"]),
            "correct": accuracy["correct"],
            "cases": accuracy["cases"],
        },
        "confusion_matrix": {
            **heldout["confusion_matrix"],
            "denominator": heldout["dataset"]["denominator"],
        },
        "evaluation": {
            "dataset_id": agent_dataset,
            "role": agent_role,
            "restriction": RESTRICTION_BY_ROLE[agent_role],
            "denominator": len(runs_by_case),
            "repeats": online.get("repeats", 1),
            "correctness_mean": str(correctness["mean"]) if isinstance(correctness, dict) else str(correctness),
        },
        "failed_cases": failed_cases,
        "notes": list(NOTES),
    }
    text = json.dumps(export, indent=2, sort_keys=True) + "\n"
    return {"index.json": text.encode("utf-8")}


def write_eval_lab_export(files: dict[str, bytes], out_dir: Path) -> None:
    """The write of the export of the Eval Lab."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (out_dir / name).write_bytes(content)


def check_eval_lab_export(files: dict[str, bytes], out_dir: Path) -> list[str]:
    """The differences between the rebuilt export and the published one, one line each. The check writes nothing."""
    problems: list[str] = []
    for name, content in sorted(files.items()):
        published = out_dir / name
        if not published.is_file():
            problems.append(f"the published eval lab file {name} is not on the disk")
        elif published.read_bytes() != content:
            problems.append(f"the published eval lab file {name} does not match the reports")
    return problems
