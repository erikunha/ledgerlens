"""Replay archived dated policy answers against the offline claim verifier."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ledgerlens.schemas import Claim, Coherence, Evidence, InvestigationResult, ToolCallRecord
from ledgerlens.verify.checks import verify_result
from ledgerlens.verify.nli import StubNli

ARCHIVE = Path(__file__).resolve().parents[1] / "data/eval/reports/policy-journeys-openai.json"
DATED_CASES = ("july-cutoff-usd", "july-cutoff-eur", "unseen-usd")
ARCHIVE_TIMESTAMP = datetime(1970, 1, 1, tzinfo=UTC)
MISSING_EVIDENCE_PREFIX = "Missing evidence for: "
POLICY_PREFIX = "policy:"
VERIFY_STAGE = "verify"
ALREADY_FLAGGED = "already_flagged"
SEARCH_OK = "ok"
UNSUPPORTED = "not_enough_evidence"


def reconstruct_archived_case(case: dict[str, Any]) -> InvestigationResult:
    """Rebuild claim verifier inputs. The archive omits timing and a combined tool order."""
    evidence: list[Evidence] = []
    trace: list[ToolCallRecord] = []
    for search in case["searches"]:
        ids = search["candidate_ids"]
        searched = search["status"] == SEARCH_OK and ids is not None
        trace.append(
            ToolCallRecord(
                step=len(trace) + 1,
                tool="search_policies",
                input=deepcopy(search["input"]),
                ok=searched,
                evidence_ids=ids if searched else [],
                duration_ms=0,
            )
        )
    for citation in case["policy_citations"]:
        if citation["passage"] is None:
            continue
        chunk_id = citation["id"].removeprefix(POLICY_PREFIX)
        evidence.append(
            Evidence(
                id=citation["id"],
                source_type="policy",
                tool="search_policies",
                ref=chunk_id,
                content=json.dumps({"chunk_id": chunk_id, "text": citation["passage"]}),
                retrieved_at=ARCHIVE_TIMESTAMP,
            )
        )
    for calculation in case["calculations"]:
        output = calculation["outputs"]
        calculated = output.get("ok") is True
        ids = output.get("evidence_ids", []) if calculated else []
        trace.append(
            ToolCallRecord(
                step=len(trace) + 1,
                tool="calculate",
                input=deepcopy(calculation["inputs"]),
                ok=calculated,
                evidence_ids=ids,
                duration_ms=0,
            )
        )
        for evidence_id in ids:
            data = output["data"]
            evidence.append(
                Evidence(
                    id=evidence_id,
                    source_type="calc",
                    tool="calculate",
                    ref=data["formula"],
                    content=json.dumps(data),
                    retrieved_at=ARCHIVE_TIMESTAMP,
                )
            )
    claims = [Claim.model_validate(claim) for claim in case["claims"]]
    unsupported = {verdict["claim_id"] for verdict in case["verdicts"] if verdict["label"] == UNSUPPORTED}
    verifier_messages = {MISSING_EVIDENCE_PREFIX + claim.text for claim in claims if claim.id in unsupported}
    return InvestigationResult(
        session_id=case["case_id"],
        question=case["question"],
        answer=case["answer"],
        claims=claims,
        evidence=evidence,
        verdicts=[],
        coherence=Coherence(passed=True),
        missing_information=[message for message in case["missing_information"] if message not in verifier_messages],
        requires_human_review=any(
            condition["stage"] == VERIFY_STAGE and condition["condition"] == ALREADY_FLAGGED
            for condition in case["review_conditions"]
        ),
        recommended_action="none",
        tool_trace=trace,
    )


def compare_archived_cases(archive: Path) -> dict[str, Any]:
    """Compare claim verification on the three archived dated policy questions."""
    cases = {case["case_id"]: case for case in json.loads(archive.read_text())["cases"]}
    comparisons = []
    nli = StubNli()
    for case_id in DATED_CASES:
        source = cases[case_id]
        reconstructed = reconstruct_archived_case(source)
        baseline = verify_result(reconstructed, nli=nli)
        candidate = verify_result(reconstructed, nli=nli, use_cutoff_receipts=True)
        preflagged = reconstructed.model_copy(update={"requires_human_review": True})
        preflagged_candidate = verify_result(preflagged, nli=nli, use_cutoff_receipts=True)
        comparisons.append(
            {
                "case_id": case_id,
                "baseline_requires_review": baseline.requires_human_review,
                "candidate_requires_review": candidate.requires_human_review,
                "independent_review_flag_preserved": (
                    preflagged_candidate.requires_human_review and preflagged_candidate.verdicts == candidate.verdicts
                ),
                "baseline_matches_archive": (
                    baseline.requires_human_review == source["requires_human_review"]
                    and baseline.missing_information == source["missing_information"]
                    and [verdict.model_dump(mode="json") for verdict in baseline.verdicts] == source["verdicts"]
                ),
                "changed_claims": [
                    {
                        "claim_id": after.claim_id,
                        "baseline": before.label,
                        "candidate": after.label,
                        "method": after.method,
                        "evidence_ids": after.evidence_ids,
                    }
                    for before, after in zip(baseline.verdicts, candidate.verdicts, strict=True)
                    if before != after
                ],
            }
        )
    return {"scope": "offline claim verifier only", "cases": comparisons}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
    args = parser.parse_args()
    print(json.dumps(compare_archived_cases(args.archive), indent=2))


if __name__ == "__main__":
    main()
