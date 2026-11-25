"""The forensic export of a run: the shape of the run that a stranger can read and check.

Why the export exists: a reader of a run that was not there has to see the shape of the run: the spans, the
parent of every span, the order of the events and what each step spent. The export is that shape, and it is
redacted: a value that looks like a key is replaced, and the export says what it redacted and how many values
it redacted.

Why the raw content of a prompt is not exported by default: the trace of the repository stays in the session
of the person who asked (ADR-013), and a published export is read by strangers. The export names the prompts
it did not export, so a reader knows they exist and were held back, and not that they never happened.

Why the export uses the conventions of the repository and not a standard: the trace of the repository is a
published contract (ADR-013), and a contract that is replaced by a standard is a contract that breaks.
"""

from __future__ import annotations

from typing import Any

from ledgerlens.durability.journal import JournalEntry
from ledgerlens.observability.callbacks import redact
from ledgerlens.observability.trace_event import TraceEvent

__all__ = ["export_or_record", "forensic_export"]


def export_or_record(
    events: list[TraceEvent],
    journal: list[JournalEntry],
    *,
    record: list[str],
    include_prompts: bool = False,
) -> dict[str, Any] | None:
    """The export of a run, and the record of the error when the export fails.

    Why the failure of the export is recorded locally and the run finishes with an answer: the export is a
    convenience of the run, and a run that ended with the error of the exporter instead of an answer for the
    visitor would be a run that failed for a reason that is not the reason of the visitor. The error of the
    exporter is recorded locally, and the answer of the run stands.
    """
    try:
        return forensic_export(events, journal, include_prompts=include_prompts)
    except Exception as exc:
        record.append(f"the export of the run failed: {type(exc).__name__}: {exc}")
        return None


def forensic_export(
    events: list[TraceEvent],
    journal: list[JournalEntry],
    *,
    include_prompts: bool = False,
) -> dict[str, Any]:
    """The forensic export of a run: the spans, the order of the events, the spend of every step and the redaction.

    Why the redaction is counted and named: a reader of the export has to know that values were redacted and
    how many, because an export that hid its redaction would be an export that asks to be trusted blindly.
    """
    redacted_count = 0
    held_back_prompts = 0

    def clean(value: Any) -> Any:
        nonlocal redacted_count
        if isinstance(value, str):
            cleaned = redact(value)
            if cleaned != value:
                redacted_count += 1
            return cleaned
        if isinstance(value, dict):
            return {key: clean(item) for key, item in value.items()}
        if isinstance(value, list):
            return [clean(item) for item in value]
        return value

    spans: dict[str, dict[str, Any]] = {}
    order: list[dict[str, Any]] = []
    for event in sorted(events, key=lambda item: item.seq):
        payload = dict(event.payload)
        if not include_prompts and "prompt" in payload:
            # The raw content of a prompt is not exported by default: the export names it and holds it back.
            payload.pop("prompt")
            held_back_prompts += 1
        order.append(
            {
                "seq": event.seq,
                "event_type": event.event_type,
                "span_id": event.span_id,
                "payload": clean(payload),
            }
        )
        if event.span_id:
            span = spans.setdefault(
                event.span_id,
                {"span_id": event.span_id, "parent_span_id": event.parent_span_id, "events": 0},
            )
            span["events"] += 1
            if event.parent_span_id and not span.get("parent_span_id"):
                span["parent_span_id"] = event.parent_span_id

    spend = [
        {"step_id": entry.step_id, "spend_usd": None if entry.spend_usd is None else str(entry.spend_usd)}
        for entry in journal
        if entry.kind == "result"
    ]

    redaction_sentence = (
        f"the export redacted {redacted_count} value(s) that looked like a key"
        + (
            f", and held back the raw content of {held_back_prompts} prompt(s)"
            if held_back_prompts
            else ""
        )
    )
    return {
        "spans": list(spans.values()),
        "events": order,
        "spend": spend,
        "redaction": {"sentence": redaction_sentence, "count": redacted_count, "held_back_prompts": held_back_prompts},
    }
