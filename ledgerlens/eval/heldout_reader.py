"""The reader of the held out file: its cases, the NLI cases the sweep judges and the counts of the set.

Why it exists: the held out file has a shape the readers of the tuning sets do not understand. Its cases may cite
two tools at once, the premise of a case may hold five to twelve rows of evidence and one case of the set cites
no evidence at all. The reader of the sweep (`ledgerlens.verify.sweep`) understands the two shapes of the tuning
sets and drops a case whose premise is empty, so that case would have vanished from the set and every number over
the set would have been a number over fewer cases than the file holds.

This module is the reader of that file. It reads the file, it builds the cases in the shape the verifier consumes
(`Claim` and `Evidence` of `ledgerlens.schemas`) and it builds the `NliCase` of the sweep, with the case that
cites no evidence kept in the list and marked, so that a caller cannot count the set wrong and cannot read a
premise that does not exist. The verifier decides that case by itself, as `not_enough_evidence` with the method
`none`, and the reader says so in its counts.

The reader reads the file and nothing else. It does not import the module that writes the file, so the two may be
written and reviewed apart and a file written by hand is read like one written by the generator.

A line that is not valid JSON, a line that is not a JSON object, a line that misses a field of the shape and an
evidence the verifier cannot read are refused with one sentence that names the file and the line, as
`ledgerlens.eval.manifest` refuses. The refusal is a `HeldoutError` and never a traceback.

Usage:

```python
from ledgerlens.eval.heldout_reader import heldout_counts, heldout_nli_cases, read_heldout_cases

cases = read_heldout_cases(path)      # the cases of the file
built = heldout_nli_cases(cases)      # the cases the sweep judges, the empty one included
counts = heldout_counts(path)         # how many cases the file holds and how many the model reads
```
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ledgerlens.eval.manifest import safe_text
from ledgerlens.schemas import Claim, Coherence, Evidence, InvestigationResult
from ledgerlens.verify.checks import load_thresholds, text_premise
from ledgerlens.verify.sweep import CALIBRATION_MOMENT, NliCase

__all__ = [
    "HELDOUT_SET_NAME",
    "HeldoutCase",
    "HeldoutCounts",
    "HeldoutError",
    "HeldoutNliCase",
    "heldout_counts",
    "heldout_nli_cases",
    "heldout_result",
    "read_heldout_cases",
]

# The name of the set in the sweep. It is the role the set plays in the split, and the reader never tunes against
# it: the set is read once, by the final scoring step.
HELDOUT_SET_NAME = "held_out"

# The verdicts a case of the set may carry. They are the verdicts of the verifier, so a label that is not one of
# them is a data problem of the file.
_LABELS: tuple[str, ...] = ("supported", "contradicted", "not_enough_evidence")

# The fields every case of the file holds. The note is the only one that may be left out.
_REQUIRED_FIELDS: tuple[str, ...] = ("id", "claim", "evidence_ids", "evidence", "label")

# The kind of the evidence of a case, by the prefix of its id. The rule is the one of the verifier, and the test
# of the module checks that the two do not drift apart.
_SOURCE_TOOL: dict[str, tuple[str, str]] = {
    "sql": ("sql", "query_ledger"),
    "api": ("ledger_api", "get_ledger_record"),
    "policy": ("policy", "search_policies"),
    "fx": ("fx", "get_reference_fx"),
    "calc": ("calc", "calculate"),
    "case": ("case", "recall_cases"),
}


class HeldoutError(Exception):
    """The held out file does not have the shape the reader expects, and the message says why.

    Why it exists: the reader of a file that a person wrote must get one sentence that names the file and the line,
    not a stack trace. The style is the one of `ledgerlens.eval.manifest`, and the class is its own so that a
    caller can catch the refusal of this file without catching every error of the repository.
    """


@dataclass(frozen=True)
class HeldoutCase:
    """One case of the held out file: its id, its claim, its label, its evidence and its note.

    Why it exists: the file of the set is JSONL and every line is one sentence under judgement. The record keeps
    the evidence as the verifier reads it, so the premise of the case is the premise the verifier builds and not a
    second rendering of it. It is frozen because it is a fact about a file that was written once.
    """

    case_id: str
    claim: str
    label: str
    evidence_ids: tuple[str, ...]
    evidence: tuple[Evidence, ...]
    note: str = ""

    @property
    def cited_evidence(self) -> tuple[Evidence, ...]:
        """The evidence the claim cites, in the order of the citations and without the ones the file does not hold.

        Why it exists: the premise of a case is built from the evidence it cites, in the order of the citations,
        so a citation that names an evidence the file does not hold contributes nothing to the premise.
        """
        by_id = {item.id: item for item in self.evidence}
        return tuple(by_id[item] for item in self.evidence_ids if item in by_id)

    @property
    def has_evidence(self) -> bool:
        """Whether the case cites evidence that the file holds.

        Why it exists: the set has one case that cites no evidence. It is a control of the set and the verifier
        decides it by code, so a reader that cannot tell it apart from a case that was skipped would count the set
        wrong.
        """
        return bool(self.cited_evidence)


@dataclass(frozen=True)
class HeldoutNliCase:
    """One case of the held out file in the shape the sweep builds, with the mark of the cases the model never sees.

    Why it exists: the sweep sends a premise and a claim to the model and drops the cases that have no premise.
    The set has a case that cites no evidence and it must not be dropped, so the record carries `needs_model`:
    `False` says that the verifier decides the case by code, as `not_enough_evidence` with the method `none`, and
    that the premise of the case is empty because the model never reads it.
    """

    case: NliCase
    needs_model: bool

    @property
    def case_id(self) -> str:
        """The id of the case, so a caller can name it without unwrapping the record."""
        return self.case.case_id

    @property
    def label(self) -> str:
        """The label the file expects for the case."""
        return self.case.label

    @property
    def claim(self) -> str:
        """The sentence under judgement."""
        return self.case.claim

    @property
    def premise(self) -> str:
        """The premise the model reads, empty for a case that cites no evidence because the model never reads it."""
        return self.case.premise


@dataclass(frozen=True)
class HeldoutCounts:
    """How many cases the held out file holds and how many of them the model reads.

    Why it exists: a number over the set is honest only when its denominator is known before the model runs.
    `total` is the denominator of the accuracy over the set, `nli` is the denominator of the accuracy over the
    cases the model judged and `decided_by_code` counts the cases the verifier decides by itself, the ones that
    cite no evidence.
    """

    total: int
    nli: int
    decided_by_code: int


def read_heldout_cases(path: Path) -> tuple[HeldoutCase, ...]:
    """The cases of the held out file, in the order of the file.

    Why it exists: the file of the set is the source of every number published over it, and the shape of a case
    is not the shape of the tuning sets: the evidence comes with the case, one item per id, and the ids the claim
    cites are named apart. The reader turns every line into a case the verifier can judge.

    A blank line is not a case. Raises `HeldoutError` when the file cannot be read, when a line is not valid
    JSON, when a line is not a JSON object, when a case misses a field of the shape or when an evidence of the
    case is not an evidence the verifier can read. Every message names the file and the line.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        reason = getattr(error, "strerror", None) or str(error) or type(error).__name__
        raise HeldoutError(f"The file {safe_text(path)} could not be read: {reason}.") from error

    cases: list[HeldoutCase] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise HeldoutError(
                f"The line {number} of the file {safe_text(path)} is not valid JSON: {error.msg}."
            ) from error
        if not isinstance(record, dict):
            raise HeldoutError(
                f"The line {number} of the file {safe_text(path)} is not a JSON object, so it is not a case."
            )
        cases.append(_case(record, number, path))
    return tuple(cases)


def heldout_nli_cases(cases: Sequence[HeldoutCase], *, limit: int | None = None) -> tuple[HeldoutNliCase, ...]:
    """The cases of the held out file in the shape the sweep builds, the case without evidence included.

    Why it exists: the sweep of the thresholds builds an `NliCase` per case it sends to the model and drops the
    ones that have no premise. The set has a case that cites no evidence, and it is a control of the set: the
    verifier decides it by code, as `not_enough_evidence` with the method `none`. The reader keeps it in the list
    and marks it with `needs_model=False`, so a caller cannot count the set as one case short and cannot read a
    premise that does not exist.

    The premise of a case is the premise the verifier builds: the cited evidence rendered as text, focused on the
    ids of the claim by the rule of `focus_premise` and truncated to `max_premise_chars` of `thresholds.json`,
    unless `limit` says otherwise.

    Raises `ValueError` when `limit` is not a positive number of characters.
    """
    if limit is None:
        limit = int(load_thresholds()["max_premise_chars"])
    if limit <= 0:
        raise ValueError(f"The limit of the premise must be a positive number of characters, and it is {limit}.")

    built: list[HeldoutNliCase] = []
    for case in cases:
        statement = Claim(id="CL1", text=case.claim, kind="fact", evidence_ids=list(case.evidence_ids))
        by_id = {item.id: item for item in case.evidence}
        premise = text_premise(statement, by_id, limit)
        built.append(
            HeldoutNliCase(
                case=NliCase(
                    set_name=HELDOUT_SET_NAME,
                    case_id=case.case_id,
                    label=case.label,
                    premise=premise if premise is not None else "",
                    claim=case.claim,
                ),
                needs_model=premise is not None,
            )
        )
    return tuple(built)


def heldout_counts(path: Path) -> HeldoutCounts:
    """How many cases the held out file holds and how many of them the model reads.

    Why it exists: a number over the set is honest only when its denominator is known before the model runs. The
    file holds `total` cases, `nli` of them go to the model and `decided_by_code` are decided by the verifier
    without it, the ones that cite no evidence.

    Raises `HeldoutError` when the file cannot be read or holds a line that is not a case.
    """
    built = heldout_nli_cases(read_heldout_cases(path))
    nli = sum(1 for item in built if item.needs_model)
    return HeldoutCounts(total=len(built), nli=nli, decided_by_code=len(built) - nli)


def heldout_result(case: HeldoutCase) -> InvestigationResult:
    """The investigation result the verifier judges for a case of the held out file.

    Why it exists: the verifier judges an `InvestigationResult`, so a case of the set has to become one. The
    result holds the claim and the evidence of the case and nothing else, so the code of `ledgerlens/verify/**`
    judges the case without knowing that the set exists.
    """
    return InvestigationResult(
        session_id=f"heldout-{case.case_id}",
        question=case.claim,
        answer=case.claim,
        claims=[Claim(id="CL1", text=case.claim, kind="fact", evidence_ids=list(case.evidence_ids))],
        evidence=list(case.evidence),
        verdicts=[],
        coherence=Coherence(passed=True),
        recommended_action="none",
        requires_human_review=False,
    )


def _case(record: Mapping[str, Any], number: int, path: Path) -> HeldoutCase:
    """The case of a line of the file, or a refusal that names the file and the line.

    Why it exists: the reader refuses the same way the repository refuses elsewhere: one sentence that says what
    is wrong with the line, never a traceback.
    """
    for name in _REQUIRED_FIELDS:
        if name not in record:
            raise HeldoutError(
                f"The case in the line {number} of the file {safe_text(path)} is missing the field '{name}'."
            )

    case_id = record["id"]
    if not isinstance(case_id, str) or not case_id.strip():
        raise HeldoutError(
            f"The case in the line {number} of the file {safe_text(path)} has no id that is a nonempty string."
        )

    claim = record["claim"]
    if not isinstance(claim, str) or not claim.strip():
        raise HeldoutError(
            f"The case '{safe_text(case_id)}' in the line {number} of the file {safe_text(path)} has no claim that "
            f"is a nonempty string."
        )

    label = record["label"]
    if label not in _LABELS:
        raise HeldoutError(
            f"The case '{safe_text(case_id)}' in the line {number} of the file {safe_text(path)} has the label "
            f"'{safe_text(label)}', and a label must be supported, contradicted or not_enough_evidence."
        )

    evidence_ids = record["evidence_ids"]
    if not isinstance(evidence_ids, list) or not all(isinstance(item, str) for item in evidence_ids):
        raise HeldoutError(
            f"The case '{safe_text(case_id)}' in the line {number} of the file {safe_text(path)} has an "
            f"evidence_ids that is not a list of strings."
        )

    raw_evidence = record["evidence"]
    if not isinstance(raw_evidence, list):
        raise HeldoutError(
            f"The case '{safe_text(case_id)}' in the line {number} of the file {safe_text(path)} has an evidence "
            f"that is not a list."
        )
    evidence = tuple(
        _evidence(item, case_id, number, path) for item in raw_evidence
    )

    note = record.get("note", "")
    if not isinstance(note, str):
        raise HeldoutError(
            f"The case '{safe_text(case_id)}' in the line {number} of the file {safe_text(path)} has a note that "
            f"is not a string."
        )

    return HeldoutCase(
        case_id=case_id,
        claim=claim,
        label=str(label),
        evidence_ids=tuple(evidence_ids),
        evidence=evidence,
        note=note,
    )


def _evidence(item: Any, case_id: str, number: int, path: Path) -> Evidence:
    """The evidence of a case, with the kind of the tool the id names, or a refusal that names the file and the line.

    Why it exists: the verifier reads the evidence as the object of `ledgerlens.schemas`, and the prefix of the id
    says which tool produced it. An id that names no tool the verifier knows is a data problem of the file, and it
    is refused here instead of failing inside the model of the data.
    """
    if not isinstance(item, dict) or "id" not in item or "content" not in item:
        raise HeldoutError(
            f"The case '{safe_text(case_id)}' in the line {number} of the file {safe_text(path)} has an evidence "
            f"without an id and a content."
        )
    evidence_id, content = item["id"], item["content"]
    if not isinstance(evidence_id, str) or not isinstance(content, str):
        raise HeldoutError(
            f"The case '{safe_text(case_id)}' in the line {number} of the file {safe_text(path)} has an evidence "
            f"whose id and content are not strings."
        )

    prefix = evidence_id.split(":")[0]
    if prefix not in _SOURCE_TOOL:
        raise HeldoutError(
            f"The evidence '{safe_text(evidence_id)}' of the case '{safe_text(case_id)}' in the line {number} of "
            f"the file {safe_text(path)} does not name a tool the verifier knows, and a tool is one of sql, api, "
            f"policy, fx, calc or case."
        )
    source_type, tool = _SOURCE_TOOL[prefix]
    try:
        return Evidence(
            id=evidence_id,
            source_type=source_type,
            tool=tool,
            content=content,
            ref=evidence_id,
            retrieved_at=CALIBRATION_MOMENT,
        )
    except ValidationError as error:
        raise HeldoutError(
            f"The evidence '{safe_text(evidence_id)}' of the case '{safe_text(case_id)}' in the line {number} of "
            f"the file {safe_text(path)} is not an evidence the verifier can read: {error}."
        ) from error
