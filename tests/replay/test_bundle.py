"""The replay bundle: the recorded trace, with manifest, hash and the promise that it is not a live execution.

What they guarantee, and why: (a) the versioned canonical bundle opens, and the hash of each part matches what the
manifest declares; (b) every event of the bundle satisfies the public contract schema, so whoever reads it in the
browser does not have to guess the format; (c) the sequence is complete, with no gap and no repetition; (d) the
manifest and every event say the execution is deterministic, and the text of the manifest says it is not a live
execution, because a replay read as a live execution is the worst failure this repository can have; (e) a bundle with a
key inside does not open, even when the hash matches; (f) a tampered bundle does not open; (g) repeating the bundle in
a sink gives back exactly the recorded events; (h) the write path refuses a live execution and a mixed set before any
file is written, and the manifest carries the single mode every event carries; (i) a manifest whose event count was
changed does not open.

The canonical bundle is the one of the S01 scenario, recorded by the offline path of the product, with the scripted
model and the recorded exchange rate. It calls no model at all.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from ledgerlens.observability.trace_event import InMemoryTraceSink, TraceEvent, TraceMode
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


def _event(seq: int, mode: TraceMode = "deterministic_sandbox") -> TraceEvent:
    """One valid event of a bundle, with the given sequence and mode."""
    return TraceEvent(
        run_id="r1",
        seq=seq,
        at=f"2026-11-11T12:00:{seq - 1:02d}.000+00:00",
        event_type="span.ended",
        payload={"error": "nothing"},
        mode=mode,
    )


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


def test_the_canonical_bundle_opens_with_its_fifty_seven_events():
    """The versioned S01 recording opens whole: fifty seven events, every one of them a deterministic sandbox."""
    manifest, events = load_bundle(CANONICAL)
    assert len(events) == 57
    assert manifest.events == 57
    assert {event.mode for event in events} == {"deterministic_sandbox"}


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


def test_a_manifest_with_a_changed_event_count_does_not_open(tmp_path: Path):
    """Only the count in the manifest changes, everything else stays as written: the reader refuses the lie.

    The hash of the events file still matches, because the file was not touched: what is wrong is the number the
    manifest declares, and the reader has to catch that on its own.
    """
    directory = tmp_path / "bundle"
    write_bundle(directory, [_event(1)], scenario="S99")

    manifest_path = directory / MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["events"] = manifest["events"] + 1
    rewritten = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    manifest_path.write_text(rewritten, encoding="utf-8")

    with pytest.raises(BundleError, match="number of events"):
        load_bundle(directory)


def test_a_manifest_with_a_forged_run_id_does_not_open(tmp_path: Path):
    """The run id of the manifest has to be the run id of the events: a forged one does not open.

    The manifest is not hashed by anything inside the directory, so the run id it declares is a claim. The reader
    checks the claim against the events themselves.
    """
    directory = tmp_path / "bundle"
    write_bundle(directory, [_event(1)], scenario="S99")

    manifest_path = directory / MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["run_id"] = "someone-else"
    rewritten = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    manifest_path.write_text(rewritten, encoding="utf-8")

    with pytest.raises(BundleError, match="run id"):
        load_bundle(directory)


def test_a_manifest_with_a_secret_inside_does_not_open(tmp_path: Path):
    """The read path checks the manifest too, not only the events file.

    The events file is guarded by its hash, but the manifest is not hashed by anything inside the directory, so a key
    injected into the note would travel with the bundle. The reader refuses it.
    """
    directory = tmp_path / "bundle"
    write_bundle(directory, [_event(1)], scenario="S99")

    manifest_path = directory / MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["note"] = f"recorded with {FAKE_KEY}"
    rewritten = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    manifest_path.write_text(rewritten, encoding="utf-8")

    with pytest.raises(BundleError, match="manifest"):
        load_bundle(directory)


def test_an_extra_file_in_the_bundle_does_not_open(tmp_path: Path):
    """A file the manifest does not cite, beside the manifest itself, does not open.

    The bundle is a sealed package: the events file, the manifest, and nothing else. Dotfiles are exempt, because the
    desktop writes Finder metadata into directories and that is not bundle content.
    """
    directory = tmp_path / "bundle"
    write_bundle(directory, [_event(1)], scenario="S99")
    (directory / "extra.txt").write_text("smuggled", encoding="utf-8")

    with pytest.raises(BundleError, match="extra"):
        load_bundle(directory)


def test_the_note_and_the_scenario_are_redacted_on_write(tmp_path: Path):
    """A note or a scenario that carries a key is redacted before it reaches the manifest.

    Both are free text from the caller, the same as a payload value, so they go through the single redaction source
    on the way in.
    """
    directory = tmp_path / "bundle"
    manifest = write_bundle(
        directory,
        [_event(1)],
        scenario=f"S99 {FAKE_KEY}",
        note=f"recorded by {FAKE_KEY}",
    )

    manifest_text = (directory / MANIFEST_FILE).read_text(encoding="utf-8")
    assert FAKE_KEY not in manifest_text
    assert manifest.scenario == "S99 [REDACTED]"
    assert manifest.note == "recorded by [REDACTED]"
    again, _ = load_bundle(directory)
    assert again.scenario == "S99 [REDACTED]"


def test_replaying_a_bundle_gives_back_the_same_events():
    """Repeating the bundle in a sink gives back exactly the recorded events."""
    sink = InMemoryTraceSink()
    replayed = replay(CANONICAL, sink)
    stored = sink.read_from(replayed[0].run_id, after_seq=0, limit=10000)
    assert [event.to_dict() for event in stored] == [event.to_dict() for event in replayed]


def test_write_bundle_refuses_a_live_execution(tmp_path: Path):
    """A live execution never becomes a bundle, and the refusal comes before any file is written.

    A manifest that said `live_agent` while its note says the execution is not a live one would be a contradiction,
    so the write path does not even start.
    """
    events = [_event(1, "live_agent"), _event(2, "live_agent")]
    directory = tmp_path / "bundle"
    with pytest.raises(BundleError, match="live_agent"):
        write_bundle(directory, events, scenario="S99")
    assert not directory.exists()


def test_write_bundle_refuses_events_with_mixed_modes(tmp_path: Path):
    """A set with two modes has no honest single label for the manifest, so it is refused before any file is written."""
    events = [_event(1, "deterministic_sandbox"), _event(2, "recorded_replay")]
    directory = tmp_path / "bundle"
    with pytest.raises(BundleError, match="single mode"):
        write_bundle(directory, events, scenario="S99")
    assert not directory.exists()


def test_write_bundle_refuses_events_with_more_than_one_run_id(tmp_path: Path):
    """A bundle is the trace of one execution: two run ids have no honest manifest, and no file is written."""
    other = TraceEvent(
        run_id="r2",
        seq=2,
        at="2026-11-11T12:00:01.000+00:00",
        event_type="span.ended",
        payload={"error": "nothing"},
    )
    directory = tmp_path / "bundle"
    with pytest.raises(BundleError, match="single run id"):
        write_bundle(directory, [_event(1), other], scenario="S99")
    assert not directory.exists()


def test_the_manifest_carries_the_single_mode_of_the_events(tmp_path: Path):
    """Sandbox events make a sandbox manifest and replay events make a replay manifest: the label is the common mode."""
    sandbox = write_bundle(tmp_path / "sandbox", [_event(1, "deterministic_sandbox")], scenario="S99")
    assert sandbox.mode == "deterministic_sandbox"

    replay = write_bundle(tmp_path / "replay", [_event(1, "recorded_replay")], scenario="S99")
    assert replay.mode == "recorded_replay"
    manifest, events = load_bundle(tmp_path / "replay")
    assert manifest.mode == "recorded_replay"
    assert [event.mode for event in events] == ["recorded_replay"]


def test_a_bundle_with_mixed_modes_does_not_open(tmp_path: Path):
    """Events with two modes do not open on the read path either: the label has to be a single one.

    The write path refuses a mixed set before any file exists, so the only way to meet a mixed bundle is to assemble
    it on disk: the second line is switched to `live_agent` after the write and the manifest hash is redone, which
    leaves the mix as the only thing that is wrong.
    """
    import hashlib

    directory = tmp_path / "bundle"
    write_bundle(directory, [_event(1), _event(2)], scenario="S99")

    lines = (directory / EVENTS_FILE).read_text(encoding="utf-8").splitlines()
    switched = json.loads(lines[1])
    switched["mode"] = "live_agent"
    lines[1] = json.dumps(switched, ensure_ascii=False, sort_keys=True)
    (directory / EVENTS_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest_path = directory / MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][EVENTS_FILE] = hashlib.sha256((directory / EVENTS_FILE).read_bytes()).hexdigest()
    rewritten = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    manifest_path.write_text(rewritten, encoding="utf-8")

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
