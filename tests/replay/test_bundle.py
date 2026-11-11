"""The replay bundle: the recorded trace, with manifest, hash and the promise that it is not a live execution.

What they guarantee, and why: (a) the versioned canonical bundle opens, and the hash of each part matches what the
manifest declares; (b) every event of the bundle satisfies the public contract schema, so whoever reads it in the
browser does not have to guess the format; (c) the sequence is complete, with no gap and no repetition; (d) the
manifest and every event say the execution is deterministic, and the text of the manifest says it is not a live
execution, because a replay read as a live execution is the worst failure this repository can have; (e) a bundle with a
key inside does not open, even when the hash matches; (f) a tampered bundle does not open; (g) repeating the bundle in
a sink gives back exactly the recorded events.

The canonical bundle is the one of the S01 scenario, recorded by the offline path of the product, with the scripted
model and the recorded exchange rate. It calls no model at all.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from ledgerlens.observability.trace_event import InMemoryTraceSink
from ledgerlens.replay.bundle import (
    EVENTS_FILE,
    MANIFEST_FILE,
    BundleError,
    bundle_digest,
    load_bundle,
    replay,
    write_bundle,
)

ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "data" / "eval" / "replay" / "s01"
SCHEMA = ROOT / "docs" / "v3" / "contracts" / "schemas" / "trace-event.schema.json"
FAKE_KEY = "sk-fakefake1234"


def _validator() -> Draft202012Validator:
    """The validator of the public schema, read from the versioned file in the repository."""
    return Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))


def test_the_canonical_bundle_opens_and_its_hashes_match():
    """The versioned bundle opens, and the manifest matches what is in the file."""
    manifest, events = load_bundle(CANONICAL)
    assert manifest.events == len(events)
    assert manifest.mode == "deterministic_sandbox"
    for name, digest in manifest.files.items():
        import hashlib

        assert hashlib.sha256((CANONICAL / name).read_bytes()).hexdigest() == digest


def test_every_event_of_the_canonical_bundle_follows_the_public_schema():
    """Every event of the bundle satisfies the public schema, field by field."""
    validator = _validator()
    _, events = load_bundle(CANONICAL)
    for event in events:
        errors = sorted(validator.iter_errors(event.to_dict()), key=lambda error: error.path)
        assert not errors, f"{event.event_type} outside the schema: {[error.message for error in errors]}"


def test_the_sequence_of_the_canonical_bundle_is_complete():
    """The sequence of the bundle goes from 1 to 1, with no gap and no repetition."""
    _, events = load_bundle(CANONICAL)
    assert [event.seq for event in events] == list(range(1, len(events) + 1))


def test_the_bundle_says_it_is_not_a_live_run():
    """The manifest and every event say the execution is deterministic, and the text says it is not live."""
    manifest, events = load_bundle(CANONICAL)
    assert manifest.mode == "deterministic_sandbox"
    assert {event.mode for event in events} == {"deterministic_sandbox"}
    assert "live execution" in manifest.note
    assert "deterministic" in manifest.note.lower()


def test_a_secret_never_reaches_the_file_even_outside_the_coordinator(tmp_path: Path):
    """The key is redacted at the boundary: whoever assembles the event outside the coordinator does not write it
    either."""
    from ledgerlens.observability.trace_event import TraceEvent

    event = TraceEvent(
        run_id="r1",
        seq=1,
        at="2026-11-11T12:00:00.000+00:00",
        event_type="span.ended",
        payload={"api_key": FAKE_KEY, "error": f"401 unauthorized {FAKE_KEY}", "question": "hello"},
    )
    directory = tmp_path / "bundle"
    write_bundle(directory, [event], scenario="S99")

    text = (directory / EVENTS_FILE).read_text(encoding="utf-8")
    assert FAKE_KEY not in text
    assert "api_key" not in text
    assert "REDACTED" in text


def test_a_bundle_with_a_secret_inside_does_not_open(tmp_path: Path):
    """A key inside the bundle stops the read, even with the hash in order."""
    import hashlib

    from ledgerlens.observability.trace_event import TraceEvent

    event = TraceEvent(
        run_id="r1",
        seq=1,
        at="2026-11-11T12:00:00.000+00:00",
        event_type="span.ended",
        payload={"error": "nothing"},
    )
    directory = tmp_path / "bundle"
    write_bundle(directory, [event], scenario="S99")

    # The key is injected after it was written, and the manifest is redone so the hash keeps matching.
    events_path = directory / EVENTS_FILE
    events_path.write_text(events_path.read_text(encoding="utf-8").replace("nothing", FAKE_KEY), encoding="utf-8")
    manifest_path = directory / MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][EVENTS_FILE] = hashlib.sha256(events_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    with pytest.raises(BundleError):
        load_bundle(directory)


def test_a_tampered_bundle_does_not_open(tmp_path: Path):
    """A tampered bundle does not open: the hash of the manifest does not match."""
    sink = InMemoryTraceSink()
    from ledgerlens.observability.trace_event import TraceEvent

    event = TraceEvent(
        run_id="r1",
        seq=1,
        at="2026-11-11T12:00:00.000+00:00",
        event_type="span.ended",
        payload={"error": "nothing"},
    )
    sink.append(event)
    directory = tmp_path / "bundle"
    write_bundle(directory, [event], scenario="S99")

    events_path = directory / EVENTS_FILE
    events_path.write_text(events_path.read_text(encoding="utf-8").replace("nothing", "other"), encoding="utf-8")
    with pytest.raises(BundleError):
        load_bundle(directory)


def test_replaying_a_bundle_gives_back_the_same_events():
    """Repeating the bundle in a sink gives back exactly the recorded events."""
    sink = InMemoryTraceSink()
    replayed = replay(CANONICAL, sink)
    stored = sink.read_from(replayed[0].run_id, after_seq=0, limit=10000)
    assert [event.to_dict() for event in stored] == [event.to_dict() for event in replayed]


def test_a_bundle_with_mixed_modes_does_not_open(tmp_path: Path):
    """Events with a mode different from the manifest do not open: the label has to be a single one."""
    from ledgerlens.observability.trace_event import TraceEvent

    events = [
        TraceEvent(
            run_id="r1",
            seq=1,
            at="2026-11-11T12:00:00.000+00:00",
            event_type="span.ended",
            payload={"error": "nothing"},
            mode="deterministic_sandbox",
        ),
        TraceEvent(
            run_id="r1",
            seq=2,
            at="2026-11-11T12:00:01.000+00:00",
            event_type="span.ended",
            payload={"error": "nothing"},
            mode="live_agent",
        ),
    ]
    directory = tmp_path / "bundle"
    write_bundle(directory, events, scenario="S99")
    with pytest.raises(BundleError):
        load_bundle(directory)


def test_the_bundle_without_events_is_refused(tmp_path: Path):
    """A bundle with no event at all is not written."""
    with pytest.raises(BundleError):
        write_bundle(tmp_path / "empty", [], scenario="S99")


def test_the_manifest_and_the_events_file_are_the_only_parts(tmp_path: Path):
    """The bundle has two parts: the events and the manifest. Nothing else gets in."""
    from ledgerlens.observability.trace_event import TraceEvent

    event = TraceEvent(
        run_id="r1",
        seq=1,
        at="2026-11-11T12:00:00.000+00:00",
        event_type="span.ended",
        payload={"error": "nothing"},
    )
    directory = tmp_path / "bundle"
    write_bundle(directory, [event], scenario="S99")
    assert sorted(path.name for path in directory.iterdir()) == [EVENTS_FILE, MANIFEST_FILE]
    assert len(bundle_digest(directory)) == 64
