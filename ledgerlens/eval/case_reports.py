"""The per case reports of the verifier and of the evaluation of the agent.

Why the per case report exists: an aggregate hides the cases that failed, and a release that publishes only
the aggregate publishes a tendency and calls it a significance. The per case report of the verifier names the
claim, the evidence, the expected verdict, the verdict that came out, the false supported, the false
contradicted and the case without a verdict, so a reader can open the case that failed and check it.

Why the correctness of the agent and the accuracy of the verifier are kept apart: they are two different
measurements over two different sets, and a sentence that mixes them publishes a number that means nothing.
Every sentence of the report of the agent names the agent, and no sentence of it carries the accuracy of the
verifier.

Why a change of the prompt parser is a change of the extraction: the parser turns the output of the model into
the result, and a parser that moved with the output unchanged moves the numbers without the model moving. The
report names the change of the extraction, and the reports of the past are never rewritten.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ledgerlens.verify.nli import Nli, verification_status

__all__ = [
    "VerifierCase",
    "extraction_change",
    "extraction_digest",
    "render_agent_report",
    "render_verifier_report",
    "verifier_cases",
]

# The verdicts of the per case report: the three labels of the verifier and the case without a verdict.
WITHOUT_VERDICT = "without_verdict"


def _evidence_text(evidence: Any) -> str:
    """The text of the evidence of a row: the string of the text sets, or the content of the live set.

    The rows of the live set carry the evidence as the repr of the list of the records of the run, and the
    report reads the content of each record, because the content is the premise the verifier reads.
    """
    if not isinstance(evidence, str):
        return str(evidence)
    text = evidence.strip()
    if text.startswith("[") and text.endswith("]"):
        import ast

        try:
            records = ast.literal_eval(text)
        except (SyntaxError, ValueError):
            return evidence
        if isinstance(records, list) and all(isinstance(record, dict) for record in records):
            return " ".join(str(record.get("content", "")) for record in records)
    return evidence


@dataclass(frozen=True)
class VerifierCase:
    """One case of the per case report of the verifier: the claim, the evidence and the two verdicts."""

    case_id: str
    claim: str
    evidence: str
    expected: str
    got: str
    outcome: str


def _label_of(scores: Mapping[str, float], thresholds: Mapping[str, Any]) -> str:
    """The label the thresholds give to the scores of the model, the rule of the calibration."""
    if scores["entailment"] >= float(thresholds["entailment_min"]):
        return "supported"
    if scores["contradiction"] >= float(thresholds["contradiction_min"]):
        return "contradicted"
    return "not_enough_evidence"


def verifier_cases(
    rows: Sequence[Mapping[str, Any]], nli: Nli, thresholds: Mapping[str, Any]
) -> tuple[VerifierCase, ...]:
    """The per case measurement of the verifier over the text rows of a verification set.

    The report covers the text cases, the ones the NLI judges: the numeric and the coherence cases are
    decided by the code of the verifier and are not in this report. A case whose verification is unavailable,
    because the real model is missing and the stand-in would decide by word rules, is a case without a
    verdict: a missing model is not a pass, and the case is never counted as one.
    """
    status = verification_status(nli)
    cases: list[VerifierCase] = []
    for row in rows:
        if "claim" not in row or "evidence" not in row:
            continue
        claim = str(row["claim"])
        evidence = _evidence_text(row["evidence"])
        expected = str(row.get("expected") or row.get("label") or "")
        if status == "unavailable":
            cases.append(VerifierCase(str(row["id"]), claim, evidence, expected, WITHOUT_VERDICT, WITHOUT_VERDICT))
            continue
        got = _label_of(nli.predict(evidence, claim), thresholds)
        if got == expected:
            outcome = "correct"
        elif got == "supported":
            outcome = "false_supported"
        elif got == "contradicted":
            outcome = "false_contradicted"
        else:
            outcome = "wrong"
        cases.append(VerifierCase(str(row["id"]), claim, evidence, expected, got, outcome))
    return tuple(cases)


def render_verifier_report(
    cases: Sequence[VerifierCase], *, set_name: str, role: str, status: str
) -> str:
    """The per case report of the verifier: the case that failed, with the claim and the evidence.

    The summary counts the passes only over the cases that have a verdict, and the report says out loud that
    a missing model is not a pass, because a verification that did not run is not a verification that passed.
    """
    scored = [case for case in cases if case.outcome != WITHOUT_VERDICT]
    correct = sum(1 for case in scored if case.outcome == "correct")
    false_supported = sum(1 for case in scored if case.outcome == "false_supported")
    false_contradicted = sum(1 for case in scored if case.outcome == "false_contradicted")
    lines = [
        f"# The per case report of the verifier over {set_name} (role {role})",
        "",
        f"The verification status is {status}. A missing model is not a pass: a case whose verification is "
        "unavailable is a case without a verdict, and it is never counted as a pass.",
        "",
        f"Cases with a verdict: {len(scored)} of {len(cases)}. Correct: {correct}. "
        f"False supported: {false_supported}. False contradicted: {false_contradicted}. "
        f"Without a verdict: {len(cases) - len(scored)}.",
        "",
        "| case | expected | got | outcome | claim | evidence |",
        "|---|---|---|---|---|---|",
    ]
    for case in cases:
        lines.append(
            f"| {case.case_id} | {case.expected} | {case.got} | {case.outcome} | {case.claim} | {case.evidence} |"
        )
    return "\n".join(lines) + "\n"


def render_agent_report(per_case: Sequence[Mapping[str, Any]], *, set_name: str, role: str) -> str:
    """The per case report of the evaluation of the agent, with the correctness of the agent and nothing else.

    Every sentence that publishes a number names the agent, and no sentence carries the accuracy of the
    verifier: the correctness of the agent and the accuracy of the verifier are two different measurements
    over two different sets, and a sentence that mixes them publishes a number that means nothing.
    """
    lines = [
        f"# The per case report of the agent over {set_name} (role {role})",
        "",
        "The correctness of the agent and the accuracy of the verifier are two different measurements over "
        "two different sets. This report publishes the correctness of the agent, and the accuracy of the "
        "verifier lives in the per case report of the verifier.",
        "",
        "| case | scenario | correctness of the agent | trajectory | tools of the agent |",
        "|---|---|---|---|---|",
    ]
    for case in per_case:
        scores = case.get("scores", {})
        correctness = scores.get("correctness", "0")
        trajectory = scores.get("trajectory_unordered_match", "0")
        tools = ", ".join(str(tool) for tool in case.get("tools", []))
        lines.append(
            f"| {case.get('case', '')} | {case.get('scenario', '')} | {correctness} | {trajectory} | {tools} |"
        )
    return "\n".join(lines) + "\n"


def extraction_digest(parser_path: Path) -> str:
    """The digest of the parser of the prompt: the version of the extraction, from the bytes of the parser."""
    return hashlib.sha256(parser_path.read_bytes()).hexdigest()


def extraction_change(old_report: Mapping[str, Any], new_report: Mapping[str, Any]) -> str | None:
    """The sentence that names a change of the extraction, or None when the extraction did not move.

    A change of the prompt parser with the model output unchanged is a change of the extraction, and the
    report names it as one. The reports of the past are never rewritten: the change is named in the new
    report, and the old report stays as it was.
    """
    old_extraction = str(old_report.get("extraction", ""))
    new_extraction = str(new_report.get("extraction", ""))
    if old_extraction == new_extraction:
        return None
    old_answers = [str(case.get("answer", "")) for case in old_report.get("per_case", [])]
    new_answers = [str(case.get("answer", "")) for case in new_report.get("per_case", [])]
    if old_answers == new_answers:
        return (
            f"the extraction changed: the parser moved from {old_extraction} to {new_extraction} "
            "and the output of the model did not change"
        )
    return None
