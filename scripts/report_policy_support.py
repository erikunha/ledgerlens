"""Measure support for synthetic claims using fixed evidence and the existing verifier."""

from __future__ import annotations

import json
from collections.abc import Sequence

from ledgerlens.eval.case_reports import WITHOUT_VERDICT, VerifierCase, verifier_cases
from ledgerlens.retrieval import load_policy_documents
from ledgerlens.verify.nli import THRESHOLDS_PATH, get_nli

SUPPORTED = "supported"
UNSUPPORTED = "not_enough_evidence"


def controls() -> list[dict[str, str]]:
    passages = {doc.metadata["chunk_id"]: doc.page_content for doc in load_policy_documents()}
    deadline = passages["chargeback-handling#response-deadline"]
    refund_record = "The recorded refund amount for transaction TX-0001 is BRL 25.00."
    rows = [
        (
            "chargeback-cutoff",
            "Acme requires evidence one business day before the dispute deadline.",
            deadline,
            SUPPORTED,
        ),
        (
            "neighboring-policy",
            "Refund requests must arrive one business day before the dispute deadline.",
            deadline,
            UNSUPPORTED,
        ),
        ("out-of-scope", "Acme covers pet insurance claims up to BRL 500.", deadline, UNSUPPORTED),
        ("mixed-amount", "The recorded refund amount is BRL 25.00.", refund_record, SUPPORTED),
        ("mixed-deadline", "The refund will arrive within two days.", refund_record, UNSUPPORTED),
    ]
    return [dict(id=key, claim=claim, evidence=evidence, expected=expected) for key, claim, evidence, expected in rows]


def summarize(cases: Sequence[VerifierCase]) -> dict:
    measured = [case for case in cases if case.got != WITHOUT_VERDICT]
    supported = [case for case in measured if case.expected == SUPPORTED]
    unsupported = [case for case in measured if case.expected != SUPPORTED]

    def support_count(rows: list[VerifierCase]) -> dict[str, int]:
        return {"count": sum(case.got == SUPPORTED for case in rows), "eligible": len(rows)}

    return {
        "without_verdict": len(cases) - len(measured),
        "false_support": support_count(unsupported),
        "supported_recall": support_count(supported),
        "cases": [{"id": case.case_id, "expected": case.expected, "observed": case.got} for case in cases],
    }


def main() -> None:
    thresholds = json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))
    cases = verifier_cases(controls(), get_nli(require_real=True), thresholds)
    print(json.dumps(summarize(cases), indent=2))


if __name__ == "__main__":
    main()
