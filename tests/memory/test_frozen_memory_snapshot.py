"""The frozen snapshot of the memory of a run: the digest travels with the run and with the published bundle.

What they guarantee, and why: (a) the digest of the snapshot of the generation is in the bundle of
`ledgerlens/replay/bundle.py`, because a replay of an old case reads the memory of its generation and the
reader of the bundle checks it; (b) the retrieval of a replay reads that snapshot, so the replay reads the
memory of the generation and not the memory of today; (c) the verifier of `ledgerlens/replay/verdict.py`
refuses a bundle whose digest does not match the snapshot it names, because a bundle that asks the reader to
trust the name and not the bytes is a bundle that lies.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import json

from ledgerlens.memory.snapshot import freeze, read_snapshot, write_snapshot
from ledgerlens.observability.trace_event import TraceEvent
from ledgerlens.replay.bundle import load_bundle, write_bundle
from ledgerlens.replay.verdict import memory_snapshot_differences

RECORDS = [
    {"case_id": "CASE-0002", "finding": "the payout of ST-0044 was late"},
    {"case_id": "CASE-0001", "finding": "the markup of M-17 is inside the limit"},
]


def _event() -> TraceEvent:
    """One event of a run, for the bundle of the test."""
    return TraceEvent(
        run_id="run-of-the-test",
        seq=1,
        at="2026-11-24T12:00:00+00:00",
        mode="deterministic_sandbox",
        event_type="run.completed",
        payload={"reason": "the run answered"},
    )


def test_the_digest_of_the_snapshot_of_the_generation_is_in_the_bundle(tmp_path) -> None:
    """The manifest of the bundle names the digest of the snapshot of the memory of the run."""
    snapshot = freeze(RECORDS)
    bundle = tmp_path / "bundle"
    write_bundle(bundle, [_event()], scenario="S01", memory_snapshot=snapshot)

    manifest, _events = load_bundle(bundle)
    assert manifest.memory_snapshot_sha256 == snapshot.digest
    assert (bundle / "memory_snapshot.json").is_file()


def test_the_retrieval_of_a_replay_reads_the_snapshot_of_the_generation(tmp_path) -> None:
    """The replay reads the memory of the generation, and not the memory of today."""
    snapshot = freeze(RECORDS)
    write_snapshot(tmp_path / "memory_snapshot.json", snapshot)

    read = read_snapshot(tmp_path / "memory_snapshot.json")

    assert read.digest == snapshot.digest
    assert [record["case_id"] for record in read.records] == ["CASE-0001", "CASE-0002"]


def test_the_digest_of_the_snapshot_does_not_depend_on_the_order_of_the_records() -> None:
    """The snapshot is of the set of the records, and not of the order they were written in."""
    assert freeze(RECORDS).digest == freeze(list(reversed(RECORDS))).digest


def test_the_verifier_refuses_a_bundle_whose_digest_does_not_match_the_snapshot(tmp_path) -> None:
    """A bundle that asks the reader to trust the name and not the bytes is refused."""
    snapshot = freeze(RECORDS)
    bundle = tmp_path / "bundle"
    write_bundle(bundle, [_event()], scenario="S01", memory_snapshot=snapshot)

    assert memory_snapshot_differences(bundle) == []

    tampered = dict(RECORDS[0])
    tampered["finding"] = "the payout of ST-0044 was on time"
    (bundle / "memory_snapshot.json").write_text(
        json.dumps({"records": [tampered, RECORDS[1]]}, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = memory_snapshot_differences(bundle)
    assert lines
    assert "the manifest names" in lines[0]


def test_a_bundle_of_the_versions_before_the_snapshot_is_checked_as_it_always_was(tmp_path) -> None:
    """A bundle that names no snapshot of the memory has no check of the snapshot."""
    bundle = tmp_path / "bundle"
    write_bundle(bundle, [_event()], scenario="S01")

    assert memory_snapshot_differences(bundle) == []
