"""Exercise the evidence diagnostic with synthetic public-trace records."""

import json

import pytest

from ledgerlens.observability.trace import compact, envelope_of
from ledgerlens.observability.trace_event import TraceEvent
from ledgerlens.tools.envelope import error, ok
from scripts.report_evidence_stages import main, observe_stages

TARGET = "policy:refunds#deadline"
OTHER = "policy:refunds#fees"


def _trace(candidates, messages, answer):
    records = []
    if candidates is not None:
        records.append(("span.ended", {"name": "search_policies", "outputs": ok(candidates, {})}))
    if messages is not None:
        records.append(("span.started", {"name": "model", "inputs": {"messages": messages}}))
    if answer is not None:
        records.append(("span.ended", {"name": "investigate", "outputs": {"answer": answer}}))
    return [
        TraceEvent("control", index, "2026-01-01T00:00:00Z", kind, payload)
        for index, (kind, payload) in enumerate(records, start=1)
    ]


def _tool_message(ids):
    return {"type": "tool", "content": json.dumps(ok(ids, {}))}


@pytest.mark.parametrize(
    ("candidates", "delivered", "answer", "expected"),
    [
        ([OTHER], [OTHER], "A refund can have fees.", "missing_candidate"),
        ([TARGET, OTHER], [OTHER], "A refund can have fees.", "candidate_dropped"),
        ([TARGET], [TARGET], "Refunds depend on the policy.", "delivered_uncited"),
        ([TARGET], [TARGET], f"Refunds have a deadline [sql:1, {TARGET}].", "cited"),
    ],
)
def test_locates_the_first_observed_loss_of_a_target(candidates, delivered, answer, expected):
    stages = observe_stages(_trace(candidates, [_tool_message(delivered)], answer))

    assert stages.outcome_for(TARGET) == expected
    assert (TARGET in stages.candidate_dropped) == (expected == "candidate_dropped")
    assert (TARGET in stages.delivered_uncited) == (expected == "delivered_uncited")


@pytest.mark.parametrize(
    ("candidates", "messages", "answer", "stage"),
    [
        (None, [_tool_message([])], "A refund is possible.", "candidate"),
        ([TARGET], None, "A refund is possible.", "delivered"),
        ([TARGET], [_tool_message([TARGET])], None, "cited"),
    ],
)
def test_unavailable_stage_is_unknown(candidates, messages, answer, stage):
    stages = observe_stages(_trace(candidates, messages, answer))

    assert getattr(stages, stage) is None
    assert stages.outcome_for(TARGET) == "unknown"


def test_last_model_input_can_record_no_evidence():
    earlier = _trace([TARGET], [_tool_message([TARGET])], None)
    final = _trace(None, [], "Refunds depend on the policy.")

    stages = observe_stages(earlier + final)

    assert stages.outcome_for(TARGET) == "candidate_dropped"


@pytest.mark.parametrize(
    ("output", "expected_candidate", "expected_delivered"),
    [
        (envelope_of("unreadable tool result"), "unknown", "unknown"),
        ({"ok": False}, "unknown", "unknown"),
        (error("INDEX_SEARCH_FAILED", "The index did not respond", False), "missing_candidate", "candidate_dropped"),
    ],
)
def test_distinguishes_unreadable_tool_results_from_recorded_failures(output, expected_candidate, expected_delivered):
    events = _trace([TARGET], [_tool_message([OTHER])], "A refund can have fees.")
    events[0].payload["outputs"] = output
    assert observe_stages(events).outcome_for(TARGET) == expected_candidate

    message = {"type": "tool", "content": json.dumps(output)}
    assert (
        observe_stages(_trace([TARGET], [message], "A refund can have fees.")).outcome_for(TARGET) == expected_delivered
    )


def test_unfamiliar_message_does_not_support_asserting_absence():
    messages = [_tool_message([OTHER]), {"type": "unfamiliar"}]
    stages = observe_stages(_trace([TARGET, OTHER], messages, "Refunds depend on the policy."))

    assert stages.outcome_for(TARGET) == "unknown"
    assert stages.delivered.ids == {OTHER}


def test_compacted_id_array_only_supports_presence_of_visible_ids():
    events = _trace([OTHER], [_tool_message([OTHER])], "Refunds depend on the policy.")
    events[0].payload["outputs"]["evidence_ids"].append("…+2 items")
    stages = observe_stages(events)

    assert stages.outcome_for(TARGET) == "unknown"
    assert stages.candidate.ids == {OTHER}


def test_truncated_answer_preserves_visible_citations_without_asserting_omissions():
    stages = observe_stages(
        _trace([TARGET, OTHER], [_tool_message([TARGET, OTHER])], f"Recent refunds [{TARGET}]…+4 chars")
    )

    assert stages.outcome_for(TARGET) == "cited"
    assert stages.outcome_for(OTHER) == "unknown"
    assert stages.delivered_uncited is None


def test_recovers_visible_model_ids_and_marks_omitted_messages(tmp_path, capsys):
    bundle = tmp_path / "control"
    bundle.mkdir()
    long_output = json.dumps(ok([TARGET], {"text": "policy text " * 100}))
    messages = [{"type": "tool", "content": long_output}] + ["omitted"] * 9
    events = _trace([TARGET, OTHER], compact(messages), f"Refunds are subject to [sql:1, {TARGET}].")
    (bundle / "events.jsonl").write_text("\n".join(event.to_json() for event in events), encoding="utf-8")
    (tmp_path / "index.json").write_text(
        json.dumps([{"id": "control", "bundle_path": "control", "capture_kind": "scripted_fixture"}]),
        encoding="utf-8",
    )

    assert main([str(tmp_path)]) == 0

    [report] = json.loads(capsys.readouterr().out)
    assert report["runs"] == [
        {
            "id": "control",
            "capture_kind": "scripted_fixture",
            "candidate": {"ids": sorted([TARGET, OTHER]), "complete": True},
            "delivered": {"ids": [TARGET], "complete": False},
            "cited": {"ids": [TARGET], "complete": True},
            "candidate_dropped": None,
            "delivered_uncited": None,
        }
    ]
    assert report["coverage"] == {
        "candidate": {"complete": 1, "partial": 0, "unknown": 0},
        "delivered": {"complete": 0, "partial": 1, "unknown": 0},
        "cited": {"complete": 1, "partial": 0, "unknown": 0},
    }
