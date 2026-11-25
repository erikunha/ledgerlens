"""Only what was verified gets in: the refusal of a proposal without a verified source.

What they guarantee, and why: (a) a proposal without a verified source is refused, because a record that
entered the memory without a verification would come back as a claim in the next session with the authority of
a memory; (b) the case memory of `ledgerlens/memory/long_term.py` keeps refusing an investigation whose verdict
is not `supported`, because the rule of the versioned memory is the rule of the case memory read from the other
side.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import pytest

from ledgerlens.memory.long_term import CaseMemory
from ledgerlens.memory.proposal import ProposalRefused, propose
from ledgerlens.schemas import Coherence, InvestigationResult, Verdict


def test_a_proposal_without_a_verified_source_is_refused() -> None:
    """A proposal that asks the memory to trust it blindly is refused."""
    with pytest.raises(ProposalRefused, match="not verified"):
        propose(
            scope="session-a",
            assertion="the markup of M-17 is inside the limit",
            source="CASE-0001",
            source_verdict="not_enough_evidence",
        )


def test_a_proposal_with_no_source_is_refused() -> None:
    """A proposal with no source is a proposal of nothing."""
    with pytest.raises(ProposalRefused, match="no source"):
        propose(
            scope="session-a",
            assertion="the markup of M-17 is inside the limit",
            source="",
            source_verdict="supported",
        )


def test_a_proposal_with_a_verified_source_is_accepted() -> None:
    """The proposal that names a verified source enters the memory."""
    proposal = propose(
        scope="session-a",
        assertion="the markup of M-17 is inside the limit",
        source="CASE-0001",
        source_verdict="supported",
    )

    assert proposal.assertion == "the markup of M-17 is inside the limit"
    assert proposal.source == "CASE-0001"


def test_the_case_memory_keeps_refusing_an_investigation_that_was_not_verified(tmp_path) -> None:
    """The rule of the case memory does not move: an unverified investigation never becomes memory."""
    result = InvestigationResult(
        session_id="session-a",
        question="q",
        answer="a",
        claims=[],
        evidence=[],
        verdicts=[Verdict(claim_id="CL1", label="not_enough_evidence", method="nli")],
        coherence=Coherence(passed=True),
        recommended_action="none",
        requires_human_review=False,
    )

    outcome = CaseMemory(tmp_path).write_case(result)

    assert outcome["written"] is False
    assert outcome["reason"] == "verdict_not_supported"
