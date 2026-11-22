"""The sweep of the NLI thresholds: the cases that go to the model, the rule of ADR-007 and the table of it.

Why it exists: ADR-007 chose `entailment_min` and `contradiction_min` over the text cases of the verification set
and over the live sentences, and the slow test `tests/verify/test_verification_live.py` redoes that sweep with the
real model to prove that the thresholds of `thresholds.json` still follow the rule. The script
`scripts/sweep_nli_thresholds.py` does the same sweep over the datasets the manifest declares with the role
`tuning`, so the logic of the sweep lives here and the script and the test share it. There is one definition of the
cases of the sweep and one definition of the rule, and not two that can drift apart.

The module reads the datasets with the role `tuning` and nothing else. A dataset that may not be tuned against
never reaches the sweep, because the door of `ledgerlens.eval.manifest` says no before the file is opened.

The model is never chosen here. The caller gives the scores, or gives the model, and the module only decides the
thresholds.
"""

from __future__ import annotations

import itertools
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ledgerlens.eval.manifest import TUNING_ROLE, EvalDatasetManifest, require_tuning_dataset
from ledgerlens.schemas import Claim, Evidence
from ledgerlens.verify.checks import label_from_scores, load_thresholds, text_premise
from ledgerlens.verify.nli import Nli

__all__ = [
    "GRID",
    "NliCase",
    "SweepRow",
    "nli_cases",
    "pick_thresholds",
    "score_cases",
    "sweep_rows",
]

# The grid of the sweep: the thresholds from 0.30 to 0.99, by 0.01. It is the grid the sweep of ADR-007 used.
GRID: tuple[float, ...] = tuple(round(0.30 + 0.01 * index, 2) for index in range(70))

# The moment of the calibration, the moment the sets of the repository were read. The premise does not depend on
# it, and a fixed moment keeps the sweep of two runs the same.
CALIBRATION_MOMENT = datetime(2026, 11, 8, tzinfo=UTC)

# The kind of the evidence of a case, by the prefix of its id. The verifier uses the same names.
_SOURCE_TOOL = {
    "sql": ("sql", "query_ledger"),
    "api": ("ledger_api", "get_ledger_record"),
    "policy": ("policy", "search_policies"),
    "fx": ("fx", "get_reference_fx"),
    "calc": ("calc", "calculate"),
    "case": ("case", "recall_cases"),
}


@dataclass(frozen=True)
class NliCase:
    """One case that goes to the NLI model: the set it comes from, its id, the label, the premise and the claim.

    Why it exists: the sweep measures the labels the model gives against the labels a person gave, so a case has to
    carry both the premise the verifier builds and the label of the set it comes from. The record is frozen because
    it is a fact about a set that was measured once.
    """

    set_name: str
    case_id: str
    label: str
    premise: str
    claim: str


@dataclass(frozen=True)
class SweepRow:
    """One line of the sweep: the two thresholds and what they give over the cases.

    Why it exists: the table of ADR-007 is the reading of these lines. The row carries the accuracy over every
    case, the false `supported`, the false `contradicted` and the accuracy of each set, so a reader can see which
    thresholds cost which case.
    """

    entailment_min: float
    contradiction_min: float
    accuracy: float
    false_supported: int
    false_contradicted: int
    by_set: Mapping[str, float]


def _rows(path: Path) -> list[dict[str, Any]]:
    """The records of a JSONL file, one per nonblank line.

    Why it exists: a dataset of the repository is a JSONL file and the sweep reads the datasets the manifest
    declares. A line that does not parse is a data problem and not a case.
    """
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"The line {number} of the file {path} is not valid JSON: {error.msg}.") from error
        if not isinstance(row, dict):
            raise ValueError(f"The line {number} of the file {path} is not a JSON object, so it is not a case.")
        rows.append(row)
    return rows


def _evidence(evidence_id: str, content: str) -> Evidence:
    """The evidence of a case, with the kind of the tool the id names.

    Why it exists: the premise the verifier builds comes from the evidence, so the sweep has to build the same
    evidence the verifier builds. The moment of the read is the one of the calibration: the premise does not depend
    on it.
    """
    prefix = evidence_id.split(":")[0]
    source_type, tool = _SOURCE_TOOL.get(prefix, (prefix, prefix))
    return Evidence(
        id=evidence_id,
        source_type=source_type,
        tool=tool,
        content=content,
        ref=evidence_id,
        retrieved_at=CALIBRATION_MOMENT,
    )


def _case(set_name: str, row: Mapping[str, Any], limit: int) -> NliCase | None:
    """The case of a row, or None when the row does not go to the NLI model.

    Why it exists: only the text claims go to the model. The numeric ones are decided by code and the coherence
    ones by the rules, so a row without a claim of text is not a case of the sweep and counting it would make the
    accuracy of the sweep a number over something the model never saw.
    """
    claim = row.get("claim")
    if not isinstance(claim, str):
        return None

    if "label" in row:  # the live set: the evidence comes with the row, one entry per id
        label = str(row["label"])
        by_id = {str(item["id"]): _evidence(str(item["id"]), str(item["content"])) for item in row["evidence"]}
        evidence_ids = [str(item) for item in row["evidence_ids"]]
    elif row.get("type") == "text":  # the verification set: one text of evidence, read as a row of a query
        label = str(row["expected"])
        text = str(row["evidence"])
        evidence_id = "policy:1" if text.startswith("Policy") else "sql:1"
        by_id = {evidence_id: _evidence(evidence_id, text)}
        evidence_ids = [evidence_id]
    else:
        return None

    statement = Claim(id="CL1", text=claim, kind="fact", evidence_ids=evidence_ids)
    premise = text_premise(statement, by_id, limit)
    if premise is None:
        return None
    return NliCase(set_name=set_name, case_id=str(row.get("id", "")), label=label, premise=premise, claim=claim)


def nli_cases(root: Path, manifests: Sequence[EvalDatasetManifest]) -> tuple[NliCase, ...]:
    """The cases that go to the NLI model, taken from the datasets with the role `tuning`.

    Why it exists: the sweep of ADR-007 was measured over the text cases of the verification set and over the live
    sentences, and both need the premise the verifier builds. The script and the slow test share this function, so
    the cases of the sweep are the same in both and a change of one is a change of the other.

    Only the datasets with the role `tuning` are read, and the door of `ledgerlens.eval.manifest` says no before a
    file of any other role is opened. A dataset with the role `validation` and a dataset with the role `held_out`
    never reach the model.

    Raises `ValueError` when a file of a tuning dataset cannot be read or holds a line that is not a JSON object.
    """
    limit = int(load_thresholds()["max_premise_chars"])
    cases: list[NliCase] = []
    for entry in sorted(manifests, key=lambda item: item.dataset_id):
        if entry.split_role != TUNING_ROLE:
            continue
        require_tuning_dataset(entry.dataset_id, manifests)  # the door, for the case the role of the entry changed
        for row in _rows(root / entry.path):
            case = _case(entry.dataset_id, row, limit)
            if case is not None:
                cases.append(case)
    return tuple(cases)


def score_cases(cases: Sequence[NliCase], nli: Nli) -> tuple[dict[str, float], ...]:
    """The scores of the model for each case, in the order of the cases.

    Why it exists: the sweep is a function of the scores and of nothing else, so the module that decides the
    thresholds never calls the model itself and the caller decides which model measures.
    """
    return tuple(nli.predict(case.premise, case.claim) for case in cases)


def pick_thresholds(scored: Sequence[tuple[str, Mapping[str, float]]]) -> tuple[float, float]:
    """The thresholds the rule of ADR-007 chooses: no false `supported` and no false `contradicted`, the highest
    accuracy, and on a tie the middle of the plateau.

    Why it exists: the rule is the decision of ADR-007 and it lives here, so the slow test and the script of the
    sweep cannot choose different thresholds over the same scores. The false `supported` is the costly error: it
    lets through a sentence with no backing.
    """
    results: dict[tuple[float, float], tuple[int, int, int]] = {}
    for entailment, contradiction in itertools.product(GRID, GRID):
        thresholds = {"entailment_min": entailment, "contradiction_min": contradiction}
        labels = [(label, label_from_scores(scores, thresholds)) for label, scores in scored]
        false_supported = sum(predicted == "supported" and label != "supported" for label, predicted in labels)
        false_contradicted = sum(predicted == "contradicted" and label != "contradicted" for label, predicted in labels)
        results[(entailment, contradiction)] = (
            false_supported,
            false_contradicted,
            sum(predicted == label for label, predicted in labels),
        )
    safe = {key: value for key, value in results.items() if value[0] == 0 and value[1] == 0}
    if not safe:
        raise ValueError("no pair of thresholds has no false `supported` and no false `contradicted` over these cases.")
    best = max(value[2] for value in safe.values())
    plateau = [key for key, value in safe.items() if value[2] == best]
    return (
        round(sum(key[0] for key in plateau) / len(plateau), 2),
        round(sum(key[1] for key in plateau) / len(plateau), 2),
    )


def sweep_rows(
    cases: Sequence[NliCase],
    scores: Sequence[Mapping[str, float]],
) -> tuple[SweepRow, ...]:
    """One row of the sweep for every pair of thresholds of the grid.

    Why it exists: the table of ADR-007 is the reading of these rows, and a reader of the thresholds asks what the
    other pairs give. The row carries the accuracy over every case, the false `supported`, the false `contradicted`
    and the accuracy of each set.
    """
    rows: list[SweepRow] = []
    for entailment, contradiction in itertools.product(GRID, GRID):
        thresholds = {"entailment_min": entailment, "contradiction_min": contradiction}
        predicted = [label_from_scores(item, thresholds) for item in scores]
        false_supported = sum(
            prediction == "supported" and case.label != "supported"
            for case, prediction in zip(cases, predicted, strict=True)
        )
        false_contradicted = sum(
            prediction == "contradicted" and case.label != "contradicted"
            for case, prediction in zip(cases, predicted, strict=True)
        )
        correct = sum(
            prediction == case.label for case, prediction in zip(cases, predicted, strict=True)
        )
        by_set: dict[str, float] = {}
        for name in sorted({case.set_name for case in cases}):
            of_set = [
                (case, prediction)
                for case, prediction in zip(cases, predicted, strict=True)
                if case.set_name == name
            ]
            by_set[name] = round(sum(prediction == case.label for case, prediction in of_set) / len(of_set), 3)
        rows.append(
            SweepRow(
                entailment_min=entailment,
                contradiction_min=contradiction,
                accuracy=round(correct / len(cases), 3) if cases else 0.0,
                false_supported=false_supported,
                false_contradicted=false_contradicted,
                by_set=by_set,
            )
        )
    return tuple(rows)
