"""The forensic export of a run: the parent of every span, the order of the events, the spend and the redaction.

What they guarantee, and why: (a) the export carries the spans of the run, the parent of every span, the order
of the events and the spend of every step, because a stranger reads the shape of the run from the export;
(b) the export redacts what looks like a key and says what it redacted, because an export that hid its
redaction would ask to be trusted blindly; (c) the export does not export the raw content of a prompt by
default, because the trace of the repository stays in the session of the person who asked (ADR-013).

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from decimal import Decimal

from ledgerlens.durability.export import forensic_export
from ledgerlens.durability.journal import JournalEntry
from ledgerlens.observability.trace_event import TraceEvent


def _events() -> list[TraceEvent]:
    """The events of a run, with a parent and a value that looks like a key."""
    return [
        TraceEvent(
            run_id="run-of-the-test",
            seq=1,
            at="2026-11-24T12:00:00+00:00",
            mode="deterministic_sandbox",
            event_type="span.started",
            span_id="root",
            payload={"name": "investigate"},
        ),
        TraceEvent(
            run_id="run-of-the-test",
            seq=2,
            at="2026-11-24T12:00:01+00:00",
            mode="deterministic_sandbox",
            event_type="span.started",
            span_id="tool-1",
            parent_span_id="root",
            payload={"name": "query_ledger", "note": "the key sk-fakefake1234 was here"},
        ),
        TraceEvent(
            run_id="run-of-the-test",
            seq=3,
            at="2026-11-24T12:00:02+00:00",
            mode="deterministic_sandbox",
            event_type="span.ended",
            span_id="tool-1",
            parent_span_id="root",
            payload={"name": "query_ledger", "prompt": "the raw prompt of the model"},
        ),
    ]


def _journal() -> list[JournalEntry]:
    """The journal of the run, with the spend of one step."""
    return [
        JournalEntry(
            number=1,
            kind="result",
            step_id="read",
            attempt=1,
            inputs_hash="a" * 64,
            snapshot="snapshot-of-the-run",
            idempotency_key="key-read",
            output_ref="out-read",
            status="ok",
            spend_usd=Decimal("0.002"),
        )
    ]


def test_the_export_carries_the_parent_of_every_span_the_order_and_the_spend() -> None:
    """The shape of the run: the spans, the parent of every span, the order of the events and the spend."""
    export = forensic_export(_events(), _journal())

    spans = {span["span_id"]: span for span in export["spans"]}
    assert spans["tool-1"]["parent_span_id"] == "root"
    assert [event["seq"] for event in export["events"]] == [1, 2, 3]
    assert export["spend"] == [{"step_id": "read", "spend_usd": "0.002"}]


def test_the_export_redacts_what_looks_like_a_key_and_says_what_it_redacted() -> None:
    """The value that looks like a key is replaced, and the export says how many it redacted."""
    export = forensic_export(_events(), _journal())

    assert export["redaction"]["count"] >= 1
    assert "redacted" in export["redaction"]["sentence"]
    text = str(export["events"])
    assert "sk-fakefake1234" not in text
    assert "[REDACTED]" in text


def test_the_export_does_not_export_the_raw_content_of_a_prompt_by_default() -> None:
    """The raw prompt is held back, and the export names it."""
    export = forensic_export(_events(), _journal())

    assert export["redaction"]["held_back_prompts"] == 1
    assert "the raw prompt of the model" not in str(export["events"])

    exported = forensic_export(_events(), _journal(), include_prompts=True)
    assert "the raw prompt of the model" in str(exported["events"])
