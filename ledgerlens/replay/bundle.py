"""The replay bundle: the trace of an execution, written to a file, redacted and with the manifest that says what it is.

Why it exists: the phase R2 will repeat an execution without calling any model. For that it needs a recorded trace, in
the public contract format (`TraceEvent`), that anyone can read, play in a browser and check by hash. The bundle is that
file: the events as JSON lines, plus a manifest that declares the mode, the origin, the count and the hash of each part.

What the bundle carries is always a deterministic execution: scripted model, recorded exchange rate, no key and no
network. The `mode` in the manifest is `deterministic_sandbox`, and the `mode` of each event is the same. Nothing here
is a live execution, and the manifest says so in words, so that nobody has to infer it from the format.

The redaction happens at the event boundary, in `ledgerlens.observability.trace_event`. The bundle does not trust that
and checks again when it reads: if the text of the file changes with the redaction, there is a key inside it and the
bundle does not open. It is the same `redact` function the trace uses, so there is a single source of pattern.

The integrity check is by hash: the manifest keeps the sha256 of each file, and `load_bundle` refuses a tampered
bundle. It is what allows the bundle hash to be cited as proof that the replay is the same one as always.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ledgerlens.observability.callbacks import redact
from ledgerlens.observability.trace_event import TraceEvent, TraceMode, TraceSink

BUNDLE_SCHEMA_VERSION = "1"
EVENTS_FILE = "events.jsonl"
MANIFEST_FILE = "manifest.json"
DEFAULT_NOTE = (
    "Deterministic execution, with the scripted model and the recorded exchange rate. "
    "This is not a live execution and it calls no model."
)


class BundleError(Exception):
    """The bundle does not open: the hash is wrong, there is a secret inside or an event is invalid."""


@dataclass(frozen=True)
class BundleManifest:
    """What the bundle says about itself."""

    run_id: str
    mode: TraceMode
    scenario: str
    events: int
    files: dict[str, str] = field(default_factory=dict)
    snapshot_sha256: str | None = None
    created_at: str = ""
    note: str = DEFAULT_NOTE

    def to_dict(self) -> dict[str, Any]:
        """The manifest as a dictionary, with what the reader needs to check it."""
        data: dict[str, Any] = {
            "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
            "run_id": self.run_id,
            "mode": self.mode,
            "scenario": self.scenario,
            "events": self.events,
            "files": self.files,
            "created_at": self.created_at,
            "note": self.note,
        }
        if self.snapshot_sha256:
            data["snapshot_sha256"] = self.snapshot_sha256
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BundleManifest:
        """The manifest back, from the dictionary read from the file."""
        return cls(
            run_id=str(data["run_id"]),
            mode=data["mode"],
            scenario=str(data["scenario"]),
            events=int(data["events"]),
            files=dict(data.get("files") or {}),
            snapshot_sha256=data.get("snapshot_sha256"),
            created_at=str(data.get("created_at") or ""),
            note=str(data.get("note") or DEFAULT_NOTE),
        )


def _sha256(path: Path) -> str:
    """The hash of the file, for the manifest."""
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_bundle(
    directory: Path,
    events: list[TraceEvent],
    *,
    scenario: str,
    snapshot_sha256: str | None = None,
    note: str = DEFAULT_NOTE,
) -> BundleManifest:
    """Writes the bundle and returns the manifest.

    The events go out in sequence order, one per line. The manifest is written afterwards, with the hash of each file,
    and it is what closes the package.
    """
    if not events:
        raise BundleError("a bundle with no event at all serves nothing")
    directory.mkdir(parents=True, exist_ok=True)
    events_path = directory / EVENTS_FILE
    ordered = sorted(events, key=lambda item: item.seq)
    lines = [event.to_json() for event in ordered]
    events_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest = BundleManifest(
        run_id=ordered[0].run_id,
        mode=ordered[0].mode,
        scenario=scenario,
        events=len(events),
        files={EVENTS_FILE: _sha256(events_path)},
        snapshot_sha256=snapshot_sha256,
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        note=note,
    )
    (directory / MANIFEST_FILE).write_text(
        json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def load_bundle(directory: Path) -> tuple[BundleManifest, list[TraceEvent]]:
    """Reads the bundle, checking the hash, the secret and the order. It refuses when something is out of place."""
    manifest_path = directory / MANIFEST_FILE
    events_path = directory / EVENTS_FILE
    if not manifest_path.exists() or not events_path.exists():
        raise BundleError(f"incomplete bundle in {directory}")

    raw_events = events_path.read_text(encoding="utf-8")
    if redact(raw_events) != raw_events:
        raise BundleError("the bundle has something that looks like a key inside")

    manifest = BundleManifest.from_dict(json.loads(manifest_path.read_text(encoding="utf-8")))
    for name, digest in manifest.files.items():
        path = directory / name
        if not path.exists():
            raise BundleError(f"the manifest cites {name}, which is not in the bundle")
        if _sha256(path) != digest:
            raise BundleError(f"the hash of {name} does not match the manifest")

    events = [TraceEvent.from_dict(json.loads(line)) for line in raw_events.splitlines() if line.strip()]
    if len(events) != manifest.events:
        raise BundleError("the manifest says one number of events and the file has another")
    if [event.seq for event in events] != list(range(1, len(events) + 1)):
        raise BundleError("the sequence of the bundle has a gap or a repetition")
    modes = {event.mode for event in events}
    if modes != {manifest.mode}:
        raise BundleError("the events of the bundle do not have the same mode the manifest declares")
    return manifest, events


def replay(directory: Path, sink: TraceSink) -> list[TraceEvent]:
    """Repeats the bundle into a sink, the way a trace read would.

    The replay is not an execution: the events that come out here are the recorded ones, with the `mode` the manifest
    declares.
    """
    manifest, events = load_bundle(directory)
    for event in events:
        sink.append(event)
    return events


def bundle_digest(directory: Path) -> str:
    """The sha256 of the manifest, which is the summary of the whole bundle."""
    return _sha256(directory / MANIFEST_FILE)
