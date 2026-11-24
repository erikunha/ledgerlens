"""The journal of a run: what it records and what it refuses.

What they guarantee, and why: (a) the journal refuses an entry whose output does not match the digest it was given,
because the journal is what a resume trusts and a resume that trusts a replaced output answers with the result of
another run; (b) the entry keeps the digest of the inputs of the step, because a resume reuses an output only when
the inputs are the same as they were; (c) the history of the journal is append only, because the journal is the proof
of what a run already did.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import pytest

from ledgerlens.orchestration.journal import Journal, JournalRefused, digest_of


def test_the_journal_refuses_an_output_that_does_not_match_the_digest_it_was_given() -> None:
    """The journal is what a resume trusts, and it refuses what it cannot vouch for."""
    journal = Journal()

    with pytest.raises(JournalRefused, match="does not match the digest"):
        journal.record(
            step_id="read",
            inputs={"account": "M-01"},
            output={"rate": "5.41"},
            output_digest="0" * 64,
            status="ok",
            snapshot="a" * 64,
            config_version="v1",
        )

    assert journal.entries == []


def test_an_entry_keeps_the_digest_of_the_inputs_of_the_step() -> None:
    """The inputs are what the digest of the entry binds the output to."""
    journal = Journal()
    output = {"rate": "5.41"}

    entry = journal.record(
        step_id="read",
        inputs={"account": "M-01"},
        output=output,
        output_digest=digest_of(output),
        status="ok",
        snapshot="a" * 64,
        config_version="v1",
    )

    assert entry.inputs_digest == digest_of({"account": "M-01"})
    assert entry.output_digest == digest_of(output)
    assert entry.output == output


def test_the_journal_counts_the_attempts_of_a_step() -> None:
    """A step that failed and was tried again is two attempts."""
    journal = Journal()
    for _ in range(2):
        output = {"rate": "5.41"}
        journal.record(
            step_id="read",
            inputs={"account": "M-01"},
            output=output,
            output_digest=digest_of(output),
            status="ok",
            snapshot="a" * 64,
            config_version="v1",
        )

    assert [entry.attempt for entry in journal.attempts_of("read")] == [1, 2]
    assert len(journal.entries) == 2


def test_the_journal_finds_the_entry_of_a_step_that_completed() -> None:
    """A resume looks for the last entry of the step that completed."""
    journal = Journal()
    output = {"rate": "5.41"}
    journal.record(
        step_id="read",
        inputs={},
        output=output,
        output_digest=digest_of(output),
        status="ok",
        snapshot="a" * 64,
        config_version="v1",
    )

    entry = journal.completed("read")

    assert entry is not None
    assert entry.output == output
    assert journal.completed("other") is None


def test_the_journal_of_a_step_that_failed_has_no_completed_entry() -> None:
    """A step that failed is not work that a resume may reuse."""
    journal = Journal()
    output = {"error": "the source did not answer"}
    journal.record(
        step_id="read",
        inputs={},
        output=output,
        output_digest=digest_of(output),
        status="failed",
        snapshot="a" * 64,
        config_version="v1",
    )

    assert journal.completed("read") is None


def test_the_journal_survives_the_round_trip_of_its_records() -> None:
    """The journal that is written and read back is the journal that was written."""
    journal = Journal()
    output = {"rate": "5.41"}
    journal.record(
        step_id="read",
        inputs={"account": "M-01"},
        output=output,
        output_digest=digest_of(output),
        status="ok",
        snapshot="a" * 64,
        config_version="v1",
    )

    rebuilt = Journal.from_records(journal.to_records())

    assert rebuilt.to_records() == journal.to_records()
