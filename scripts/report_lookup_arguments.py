#!/usr/bin/env python3
"""Compare structured transaction arguments and tool trajectories on six synthetic controls.

A complete trace earns argument credit when it contains a structured lookup and
every structured lookup has the expected kind and ID. Missing traces and traces
with only a free-text alternative are excluded from the argument denominator.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from enum import StrEnum

from langsmith import tracing_context

from ledgerlens.eval.dataset import RECORD_LOOKUP_TOOLS
from ledgerlens.eval.evaluators import reference_messages, trace_to_messages, trajectory_evaluator
from ledgerlens.schemas import ToolCallRecord, ToolName
from ledgerlens.tools.ledger_api import GetLedgerRecordInput
from ledgerlens.tools.sql import QueryLedgerInput

RECORD_LOOKUP, QUERY_LOOKUP = RECORD_LOOKUP_TOOLS
STRICT_MODE = "strict"
TRANSACTION_KIND = "transaction"
EXPECTED_LOOKUP = GetLedgerRecordInput(kind=TRANSACTION_KIND, id="TX-0001")


class ArgumentStatus(StrEnum):
    CORRECT = "correct"
    INCORRECT = "incorrect"
    MISSING_LOOKUP = "missing_lookup"
    MIXED = "mixed"
    MISSING_TRACE = "missing_trace"
    UNMEASURABLE_ALTERNATIVE = "unmeasurable_alternative"


def _trace(*calls: tuple[ToolName, GetLedgerRecordInput | QueryLedgerInput]) -> list[ToolCallRecord]:
    return [
        ToolCallRecord(step=step, tool=tool, input=args.model_dump(exclude_unset=True), ok=True, duration_ms=0)
        for step, (tool, args) in enumerate(calls, start=1)
    ]


def _controls() -> dict[str, list[ToolCallRecord] | None]:
    correct = (RECORD_LOOKUP, EXPECTED_LOOKUP)
    swapped = (RECORD_LOOKUP, GetLedgerRecordInput(kind=TRANSACTION_KIND, id="TX-0002"))
    wrong_kind = (RECORD_LOOKUP, GetLedgerRecordInput(kind="event_replay", id=EXPECTED_LOOKUP.id))
    alternative = (QUERY_LOOKUP, QueryLedgerInput(question=f"What is the status of {EXPECTED_LOOKUP.id}?"))
    return {
        "expected_id": _trace(correct),
        "swapped_id": _trace(swapped),
        "missing_lookup": [],
        "alternative_tool": _trace(alternative),
        "missing_trace": None,
        "mixed_lookups": _trace(correct, swapped, wrong_kind),
    }


def _arguments(trace: list[ToolCallRecord] | None) -> tuple[ArgumentStatus, int | None, int | None]:
    if trace is None:
        return ArgumentStatus.MISSING_TRACE, None, None

    lookups = [GetLedgerRecordInput.model_validate(call.input) for call in trace if call.tool == RECORD_LOOKUP]
    if not lookups:
        if any(call.tool == QUERY_LOOKUP for call in trace):
            return ArgumentStatus.UNMEASURABLE_ALTERNATIVE, None, None
        return ArgumentStatus.MISSING_LOOKUP, 0, 0

    correct = sum(lookup.kind == EXPECTED_LOOKUP.kind and lookup.id == EXPECTED_LOOKUP.id for lookup in lookups)
    incorrect = len(lookups) - correct
    if correct and incorrect:
        return ArgumentStatus.MIXED, correct, incorrect
    status = ArgumentStatus.CORRECT if correct else ArgumentStatus.INCORRECT
    return status, correct, incorrect


def summarize_lookup_arguments() -> dict:
    reference = {
        "trajectory": reference_messages([RECORD_LOOKUP]),
        "equivalent_tools": [list(RECORD_LOOKUP_TOOLS)],
    }
    evaluators = (trajectory_evaluator(STRICT_MODE), trajectory_evaluator(STRICT_MODE, equivalent=True))
    rows = []
    cases: Counter[ArgumentStatus] = Counter()
    eligible = correct_calls = incorrect_calls = 0

    with tracing_context(enabled=False):
        for control, trace in _controls().items():
            status, correct, incorrect = _arguments(trace)
            cases[status] += 1
            argument_score = None
            if correct is not None and incorrect is not None:
                eligible += 1
                correct_calls += correct
                incorrect_calls += incorrect
                argument_score = float(status == ArgumentStatus.CORRECT)

            trajectory_scores = dict.fromkeys(evaluator.__name__ for evaluator in evaluators)
            if trace is not None:
                outputs = {"trajectory": trace_to_messages(trace)}
                for evaluator in evaluators:
                    result = evaluator(outputs=outputs, reference_outputs=reference)
                    trajectory_scores[result["key"]] = result["score"]
            rows.append(
                {
                    "control": control,
                    "argument_status": status,
                    "argument_score": argument_score,
                    "correct_lookup_calls": correct,
                    "incorrect_lookup_calls": incorrect,
                    **trajectory_scores,
                }
            )

    return {
        "counts": {
            "declared": len(rows),
            "eligible": eligible,
            **{status.value: cases[status] for status in ArgumentStatus},
        },
        "lookup_calls": {
            "eligible": correct_calls + incorrect_calls,
            "correct": correct_calls,
            "incorrect": incorrect_calls,
        },
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(summarize_lookup_arguments(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
