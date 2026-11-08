"""Verification of the agent's answer: claims, numbers by code, coherence and NLI.

After the agent answers, `verify_result` gives each claim a verdict (`supported`,
`contradicted` or `not_enough_evidence`), checks the coherence of the whole and flags the result for
human review when there is a contradiction or too much missing evidence. Numbers never go through the
NLI model: code compares them, with `Decimal`, against what the `calculate` tool returned.
Escalation (deadline, high amount) and the recommended action come from the evidence, in `escalation.py`.
"""

from datetime import date
from pathlib import Path

from ledgerlens.schemas import InvestigationResult
from ledgerlens.verify.checks import verify_result as verify_claims
from ledgerlens.verify.escalation import apply_escalation
from ledgerlens.verify.nli import Nli


def verify_result(
    result: InvestigationResult,
    *,
    nli: Nli | None = None,
    as_of: date | None = None,
    ledger_db: Path | str | None = None,
) -> InvestigationResult:
    """Verifies the claims and applies the escalation and the recommended action, decided by code.

    `as_of` is the reference day for dispute deadlines (default: the day the evidence was read). `ledger_db` is the
    ledger from which the deadline and the free text of cited records the model's query did not bring are read,
    read-only (default: the configured one, the same the tools read).
    """
    return apply_escalation(verify_claims(result, nli=nli), as_of=as_of, ledger_db=ledger_db)


__all__ = ["verify_result"]
