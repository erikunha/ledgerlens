"""The published verdict, redone with the published evidence: the bundle a reader can check.

What they prove, and why: (a) every published scenario shows a verdict that the code of the repository gives
again for the evidence the bundle publishes, so a reader can redo the verdict of the recording and not only
read it; (b) the values of a record and the names of the columns of a result are published whole, so the
evidence of the signature scenario, the one where a number would be easy to make up, is published with the
values that sustain it; (c) the values the signature scenario cites are in the evidence it publishes.

Why the check reads the published set and not one scenario: the catalog publishes nine recordings and a check
that only read the first one would let the other eight carry a verdict nobody redid.

Why the check is red before the bundles are captured again: the published bundles were recorded with the cut
that took the values of a record and the names of the columns away, so the evidence they publish does not
sustain the verdict they show. The bundles have to be captured again with the rule of the cut that keeps them,
and then this check reads them and goes green.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ledgerlens.replay.verdict import differences

ROOT = Path(__file__).resolve().parents[2]
PUBLISHED = ROOT / "site" / "replay"

# The nine scenarios the catalog publishes, in the order of the index.
SCENARIOS = ("s01", "s02", "s03", "s04", "s07", "s08", "s09", "s10", "s11")

# The marker of a cut, the one the old rule of the cut left in the published evidence.
_CUT_MARKER = "…"

__all__ = [
    "test_the_published_evidence_carries_the_values_the_answer_cites",
    "test_the_published_records_are_whole_and_keep_their_columns",
    "test_the_published_verdict_is_reproduced_from_the_published_evidence",
]


def _events(slug: str) -> list[dict[str, Any]]:
    """The recorded events of a published scenario."""
    text = (PUBLISHED / slug / "events.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _reads(slug: str) -> list[dict[str, Any]]:
    """The reads of the ledger of a published scenario, with the data they returned."""
    reads: list[dict[str, Any]] = []
    for event in _events(slug):
        payload = event.get("payload") or {}
        outputs = payload.get("outputs") or {}
        if payload.get("name") == "query_ledger" and outputs.get("ok"):
            data = outputs.get("data") or {}
            if isinstance(data, dict):
                reads.append(data)
    return reads


@pytest.mark.parametrize("slug", SCENARIOS)
def test_the_published_verdict_is_reproduced_from_the_published_evidence(slug: str):
    """The label the bundle publishes is the label the code gives for the published evidence.

    Why the evidence and not the label alone: a label without the evidence that sustains it is a claim, and the
    reader of the bundle has to be able to redo it with the code of the repository, which is what this does.
    """
    assert differences(PUBLISHED / slug) == [], f"the published verdict of {slug} is not reachable from its evidence"


@pytest.mark.parametrize("slug", SCENARIOS)
def test_the_published_records_are_whole_and_keep_their_columns(slug: str):
    """The records the bundle publishes are whole and every value of them keeps its column.

    Why the alignment matters: a cut that takes the values of a record away leaves a record whose values no
    reader can put under a column, and the evidence of the claim with it.
    """
    for data in _reads(slug):
        columns = data.get("columns") or []
        assert not any(str(column).startswith(_CUT_MARKER) for column in columns), (
            f"the bundle of {slug} publishes cut names of columns"
        )
        for row in data.get("rows") or []:
            if not isinstance(row, list):
                continue  # the marker of a cut of the number of the records, not a record
            assert len(row) == len(columns), f"the bundle of {slug} publishes a record that lost its columns"
            assert not any(str(value).startswith(_CUT_MARKER) for value in row), (
                f"the bundle of {slug} publishes cut values of a record"
            )


def test_the_published_evidence_carries_the_values_the_answer_cites():
    """The values the answer of the signature scenario cites are in the evidence the bundle publishes.

    Why this scenario and why these values: the scenario S11 is the scenario S01 with the reference rate in
    fault, and the answer cites the rate applied by the ledger and the day it was applied. Those two values are
    what the verdict of the first claim rests on, and a bundle that cut them away publishes a verdict that
    cannot be redone.
    """
    evidence = ""
    answer = ""
    for event in _events("s11"):
        payload = event.get("payload") or {}
        outputs = payload.get("outputs") or {}
        if payload.get("name") == "investigate" and outputs.get("answer"):
            answer = str(outputs["answer"])
        if payload.get("run_type") == "tool" and outputs.get("ok"):
            evidence += json.dumps(outputs.get("data") or {}, ensure_ascii=False)

    assert "5.4931" in answer and "2026-10-20" in answer
    assert "5.4931" in evidence, "the published evidence of S11 does not carry the rate the answer cites"
    assert "2026-10-20" in evidence, "the published evidence of S11 does not carry the day the answer cites"
