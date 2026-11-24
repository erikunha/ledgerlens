"""The published result, rebuilt from the published events: the text the claims of the run came from.

What they prove, and why: (a) the rebuild takes the answer the run verified, and not the final answer of the
investigation, because the escalation may add a notice to the answer after the verification and the claims of the
run were extracted from the text the verifier saw (ADR-077); (b) a bundle without a span of the verifier falls back
to the final answer, so a recording without a verification still rebuilds something the reader can read.

Why it matters: the check of ADR-073 compares the label the bundle publishes with the label the code gives for
the published evidence. A rebuild that reads the wrong text finds claims the run never had, and the difference
looks like a broken recording when it is a broken rebuild.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ledgerlens.replay.verdict import published_result

__all__ = [
    "test_the_rebuild_takes_the_answer_the_run_verified",
    "test_the_rebuild_falls_back_to_the_final_answer_when_there_is_no_verification",
]


def _event(seq: int, name: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """One event of a bundle, with the shape the trace writes."""
    return {
        "schema_version": "1",
        "run_id": "run-1",
        "seq": seq,
        "at": f"2026-11-24T10:0{seq}:00.000+00:00",
        "event_type": event_type,
        "payload": {"name": name, **payload},
    }


def _bundle(tmp_path: Path, events: list[dict[str, Any]]) -> Path:
    """A folder with the events of a bundle, which is what the rebuild reads."""
    directory = tmp_path / "bundle"
    directory.mkdir()
    text = "\n".join(json.dumps(event, ensure_ascii=False, sort_keys=True) for event in events) + "\n"
    (directory / "events.jsonl").write_text(text, encoding="utf-8")
    return directory


def test_the_rebuild_takes_the_answer_the_run_verified(tmp_path: Path):
    """The claims of the run came from the answer the verifier saw, and the rebuild uses that text.

    Why the two answers differ here: the escalation adds a notice to the answer when the reference source could
    not give a rate, and the notice comes after the verification. A rebuild that reads the final answer would
    find sentences the run never turned into claims (ADR-077).
    """
    verified = "The refund came to BRL 549.31 [sql:1]."
    final = verified + " The reference rate could not be obtained and the case went to a person."
    directory = _bundle(
        tmp_path,
        [
            _event(1, "investigate", "span.started", {"inputs": {"question": "why?"}}),
            _event(2, "verify", "span.started", {"inputs": {"answer": verified}}),
            _event(3, "investigate", "span.ended", {"outputs": {"answer": final}}),
        ],
    )

    result = published_result(directory)

    assert result.answer == verified


def test_the_rebuild_falls_back_to_the_final_answer_when_there_is_no_verification(tmp_path: Path):
    """A recording without a verification has no claims to rebuild, and the rebuild still reads the answer."""
    final = "The refund came to BRL 549.31 [sql:1]."
    directory = _bundle(
        tmp_path,
        [
            _event(1, "investigate", "span.started", {"inputs": {"question": "why?"}}),
            _event(2, "investigate", "span.ended", {"outputs": {"answer": final}}),
        ],
    )

    result = published_result(directory)

    assert result.answer == final
