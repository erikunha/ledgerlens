"""The published verdict, redone with the published evidence: the bundle a reader can check.

What they prove, and why: (a) every published scenario shows a verdict that the code of the repository gives
again for the evidence the bundle publishes, so a reader can redo the verdict of the recording and not only
read it; (b) the values of a record and the names of the columns of a result are published whole, so the
evidence of the signature scenario, the one where a number would be easy to make up, is published with the
values that sustain it; (c) every value the answer of a published scenario states is in the evidence that
scenario publishes, so the reader finds the number of the answer in the evidence of the run; (d) the recording of
the scripted model states the rate the ledger applied and the day it applied it, the two values that the verdict of
the first claim of the signature scenario rests on.

Why the check reads both catalogs: the site publishes the recordings of the scripted model and the recordings of
a real model, and a check that read only the first one would let the second carry a verdict nobody redid. The
two catalogs hold the same ten scenarios, so the same check runs on the two of them.

Why the check of the values is a general one and not a pair of hardcoded numbers: the answer of the scripted model
is written by this repository and is the same in every recording, while the answer of a real model is written by the
model and changes with every recording. The promise that holds for the two of them is the same one: the values the
answer states are in the evidence the bundle publishes (ADR-073).

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from ledgerlens.replay.verdict import differences

ROOT = Path(__file__).resolve().parents[2]

# The two catalogs the site publishes: the recordings of the scripted model and the recordings of a real model.
PUBLISHED = ROOT / "site" / "replay"
PUBLISHED_REAL = ROOT / "site" / "replay-real"

# The ten scenarios the catalog publishes, in the order of the index.
SCENARIOS = ("s01", "s02", "s03", "s04", "s07", "s08", "s09", "s10", "s11", "s13")

# The marker of a cut, the one the old rule of the cut left in the published evidence.
_CUT_MARKER = "…"

# The shape of what an answer of a run states: an amount or a rate, and a day.
_VALUE = re.compile(r"\d+\.\d+")
_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")

__all__ = [
    "test_the_published_evidence_carries_the_values_the_answer_cites",
    "test_the_published_records_are_whole_and_keep_their_columns",
    "test_the_published_verdict_is_reproduced_from_the_published_evidence",
    "test_the_scripted_recording_states_the_rate_the_ledger_applied",
]


def _events(slug: str, published: Path = PUBLISHED) -> list[dict[str, Any]]:
    """The recorded events of a published scenario."""
    text = (published / slug / "events.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _answer_and_evidence(slug: str, published: Path = PUBLISHED) -> tuple[str, str]:
    """The answer the run verified and the evidence the bundle publishes, as the two texts.

    Why the answer of the verifier and not the final answer of the investigation: the escalation may add a notice
    to the answer after the verification, and the notice was never a claim of the run (ADR-077).
    """
    answer = ""
    verified = ""
    evidence = ""
    for event in _events(slug, published):
        payload = event.get("payload") or {}
        outputs = payload.get("outputs") or {}
        inputs = payload.get("inputs") or {}
        if payload.get("name") == "verify" and event.get("event_type") == "span.started":
            verified = str(inputs.get("answer") or "")
        if payload.get("name") == "investigate" and event.get("event_type") == "span.ended":
            answer = str(outputs.get("answer") or answer)
        if payload.get("run_type") == "tool" and outputs.get("ok"):
            evidence += json.dumps(outputs.get("data") or {}, ensure_ascii=False)
    return verified or answer, evidence


def _reads(slug: str, published: Path = PUBLISHED) -> list[dict[str, Any]]:
    """The reads of the ledger of a published scenario, with the data they returned."""
    reads: list[dict[str, Any]] = []
    for event in _events(slug, published):
        payload = event.get("payload") or {}
        outputs = payload.get("outputs") or {}
        if payload.get("name") == "query_ledger" and outputs.get("ok"):
            data = outputs.get("data") or {}
            if isinstance(data, dict):
                reads.append(data)
    return reads


@pytest.mark.parametrize("published", [PUBLISHED, PUBLISHED_REAL], ids=["sandbox", "real"])
@pytest.mark.parametrize("slug", SCENARIOS)
def test_the_published_verdict_is_reproduced_from_the_published_evidence(slug: str, published: Path):
    """The label the bundle publishes is the label the code gives for the published evidence.

    Why the evidence and not the label alone: a label without the evidence that sustains it is a claim, and the
    reader of the bundle has to be able to redo it with the code of the repository, which is what this does.
    """
    assert differences(published / slug) == [], (
        f"the published verdict of {slug} in {published.name} is not reachable from its evidence"
    )


@pytest.mark.parametrize("published", [PUBLISHED, PUBLISHED_REAL], ids=["sandbox", "real"])
@pytest.mark.parametrize("slug", SCENARIOS)
def test_the_published_records_are_whole_and_keep_their_columns(slug: str, published: Path):
    """The records the bundle publishes are whole and every value of them keeps its column.

    Why the alignment matters: a cut that takes the values of a record away leaves a record whose values no
    reader can put under a column, and the evidence of the claim with it.
    """
    for data in _reads(slug, published):
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


@pytest.mark.parametrize("published", [PUBLISHED, PUBLISHED_REAL], ids=["sandbox", "real"])
@pytest.mark.parametrize("slug", SCENARIOS)
def test_the_published_evidence_carries_the_values_the_answer_cites(slug: str, published: Path):
    """Every value the answer of a published scenario states is in the evidence that scenario publishes.

    Why every scenario and not only the signature one: the reader of a bundle looks for the number of the answer in
    the evidence of the run, and a value that no published evidence carries is a number nobody can check. The cut of
    the trace is the way a value goes missing, and the rule of the cut that keeps the records whole (ADR-079) is
    what this proves for every scenario and not for one of them.
    """
    answer, evidence = _answer_and_evidence(slug, published)

    for value in sorted(set(_VALUE.findall(answer))):
        assert value in evidence, (
            f"the answer of {slug} in {published.name} states {value} and the published evidence does not carry it"
        )
    for day in sorted(set(_DAY.findall(answer))):
        assert day in evidence, (
            f"the answer of {slug} in {published.name} states {day} and the published evidence does not carry it"
        )


def test_the_scripted_recording_states_the_rate_the_ledger_applied():
    """The recording of the scripted model states the rate the ledger applied and the day it applied it.

    Why this scenario and why these values: the scenario S11 is the scenario S01 with the reference rate in
    fault, and the answer of the scripted model cites the rate applied by the ledger and the day it was applied.
    Those two values are what the verdict of the first claim rests on, and a bundle that cut them away publishes a
    verdict that cannot be redone.

    Why the scripted catalog and not the other one: the answer of the scripted model is written by this repository
    and is the same in every recording, while the answer of a real model is written by the model and changes with
    every recording. The promise of the real catalog is the general one of the test above.
    """
    answer, evidence = _answer_and_evidence("s11", PUBLISHED)

    assert "5.4931" in answer and "2026-10-20" in answer, "the answer of the scripted S11 cites no rate"
    assert "5.4931" in evidence, "the published evidence of the scripted S11 does not carry the rate"
    assert "2026-10-20" in evidence, "the published evidence of the scripted S11 does not carry the day"
