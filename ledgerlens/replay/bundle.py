"""The replay bundle: the trace of an execution, written to a file, redacted and with the manifest that says what it is.

Why it exists: the phase R2 will repeat an execution without calling any model. For that it needs a recorded trace, in
the public contract format (`TraceEvent`), that anyone can read, play in a browser and check by hash. The bundle is that
file: the events as JSON lines, plus a manifest that declares the mode, the origin, the count and the hash of each part.

What the bundle carries is never a live execution: no key and no network, and one single mode from the first line to
the last. The write path checks that before any file exists: a set with a `live_agent` event is refused, because a live
execution never becomes a bundle, and a set with more than one mode is refused, because there is no honest single
label for the manifest. The `mode` in the manifest is then the one mode every event carries, and the note says in
words that it is not a live execution, so that nobody has to infer it from the format.

The redaction happens at the event boundary, in `ledgerlens.observability.trace_event`. The bundle does not trust that
and checks again when it reads: if the text of the events file or of the manifest changes with the redaction, there is
a key inside it and the bundle does not open. The `note` and the `scenario` are free text from the caller, so they go
through the same `redact` on the way in. There is a single source of pattern.

The integrity check is by hash: the manifest keeps the sha256 of each file, and `load_bundle` refuses a tampered
bundle. It is what allows the bundle hash to be cited as proof that the replay is the same one as always. What the
manifest declares is also checked against what the events say: the run id has to be the run id of the events, and the
directory has to hold exactly the files the manifest declares, with nothing smuggled beside them.

The manifest also declares the provenance of the recording: the kind of the capture, the moment of the capture, the
model profile, the commit of the code, the hash of the prompt, the policy version and the version of the redaction.
Every one of those fields is optional and it is written only when the bundle declares it, because a field that
cannot be computed is better absent than invented. A bundle that declares no provenance keeps the manifest of the
previous version, key for key, so the files of the two versions are the same bytes.
"""

from __future__ import annotations

import json
import re
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

# The commit of the code, in the shape the bundle contract of the design package demands: forty lowercase
# hexadecimal characters, so that anybody can check the claim against the repository.
CODE_SHA_PATTERN = re.compile(r"^[a-f0-9]{40}$")

# The two kinds of capture the bundle contract of the design package accepts: a real model run and a fixture.
CAPTURE_KINDS = ("real_model_recorded", "scripted_fixture")

# The shape of an ISO 8601 moment with a time zone, the same one the interface accepts for the moment of the
# capture. It lives here so the bundle refuses a moment the interface would not be able to read.
RECORDED_AT_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")

# The optional fields of the contract, in the order the manifest declares them.
PROVENANCE_FIELDS = (
    "capture_kind",
    "recorded_at",
    "model_profile",
    "code_sha",
    "prompt_hash",
    "policy_version",
    "redaction_version",
)


class BundleError(Exception):
    """The bundle does not open or does not get written: the hash is wrong, there is a secret inside, an event is
    invalid, the events have no honest single mode or the provenance is outside the contract."""


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
    capture_kind: str | None = None
    recorded_at: str | None = None
    model_profile: str | None = None
    code_sha: str | None = None
    prompt_hash: str | None = None
    policy_version: str | None = None
    redaction_version: str | None = None

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
        # The provenance is declared field by field: a field the bundle does not declare never reaches the file.
        for name in PROVENANCE_FIELDS:
            value = getattr(self, name)
            if value:
                data[name] = value
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
            capture_kind=_optional_text(data.get("capture_kind")),
            recorded_at=_optional_text(data.get("recorded_at")),
            model_profile=_optional_text(data.get("model_profile")),
            code_sha=_optional_text(data.get("code_sha")),
            prompt_hash=_optional_text(data.get("prompt_hash")),
            policy_version=_optional_text(data.get("policy_version")),
            redaction_version=_optional_text(data.get("redaction_version")),
        )


def _optional_text(value: Any) -> str | None:
    """A field of the manifest that is either a text or nothing at all."""
    if value is None:
        return None
    return str(value) or None


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
    capture_kind: str | None = None,
    recorded_at: str | None = None,
    model_profile: str | None = None,
    code_sha: str | None = None,
    prompt_hash: str | None = None,
    policy_version: str | None = None,
    redaction_version: str | None = None,
) -> BundleManifest:
    """Writes the bundle and returns the manifest.

    The events are validated before any file is written: a set with a `live_agent` event is refused, because a live
    execution never becomes a bundle, and a set with more than one mode is refused, because the manifest can carry
    only one honest label. The events go out in sequence order, one per line, and the manifest declares the single
    mode they all share. The manifest is written afterwards, with the hash of each file, and it is what closes the
    package.

    The provenance of the contract is optional and it is checked before anything is written: a commit hash outside
    the shape of a commit, a capture kind outside the contract and a moment outside the shape the interface accepts
    are refused, because a claim that cannot be checked is worse than no claim.

    The moment of the capture, `recorded_at`, defaults to the moment the bundle was written, which is `created_at`,
    as soon as the bundle declares any provenance at all. A bundle that declares no provenance keeps the manifest of
    the previous version, key for key, so the files of the two versions are the same bytes.
    """
    _check_provenance(capture_kind=capture_kind, recorded_at=recorded_at, code_sha=code_sha)
    if not events:
        raise BundleError("a bundle with no event at all serves nothing")
    modes = {event.mode for event in events}
    if "live_agent" in modes:
        raise BundleError("a live execution never becomes a bundle: the events carry mode live_agent")
    if len(modes) != 1:
        raise BundleError("the events do not have a single mode, so the manifest has no honest label")
    mode = modes.pop()
    run_ids = {event.run_id for event in events}
    if len(run_ids) != 1:
        raise BundleError("the events do not have a single run id, so the manifest has no honest run id")
    # The note and the scenario are free text from the caller, the same as a payload value: they pass through the
    # single redaction source before they reach the manifest.
    scenario = redact(scenario)
    note = redact(note)
    directory.mkdir(parents=True, exist_ok=True)
    events_path = directory / EVENTS_FILE
    ordered = sorted(events, key=lambda item: item.seq)
    lines = [event.to_json() for event in ordered]
    events_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    created_at = datetime.now(UTC).isoformat(timespec="seconds")
    # The capture happened when the bundle was written, so the moment of the capture is the moment of the write,
    # unless the caller states another one. A bundle that declares no provenance at all keeps the manifest of the
    # previous version, key for key, and then the moment stays only in created_at.
    if recorded_at is None and any(
        value is not None
        for value in (capture_kind, model_profile, code_sha, prompt_hash, policy_version, redaction_version)
    ):
        recorded_at = created_at

    manifest = BundleManifest(
        run_id=ordered[0].run_id,
        mode=mode,
        scenario=scenario,
        events=len(events),
        files={EVENTS_FILE: _sha256(events_path)},
        snapshot_sha256=snapshot_sha256,
        created_at=created_at,
        note=note,
        capture_kind=capture_kind,
        recorded_at=recorded_at,
        model_profile=model_profile,
        code_sha=code_sha,
        prompt_hash=prompt_hash,
        policy_version=policy_version,
        redaction_version=redaction_version,
    )
    (directory / MANIFEST_FILE).write_text(
        json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def _check_provenance(*, capture_kind: str | None, recorded_at: str | None, code_sha: str | None) -> None:
    """The provenance of the bundle, checked against the contract before any file exists."""
    if code_sha is not None and not CODE_SHA_PATTERN.match(code_sha):
        raise BundleError("the code_sha is not the shape of a commit: forty lowercase hexadecimal characters")
    if capture_kind is not None and capture_kind not in CAPTURE_KINDS:
        raise BundleError(f"the capture_kind is not one of the kinds of the contract: {list(CAPTURE_KINDS)}")
    if recorded_at is not None and not RECORDED_AT_PATTERN.match(recorded_at):
        raise BundleError("the recorded_at is not an ISO 8601 moment with a time zone")


def load_bundle(directory: Path) -> tuple[BundleManifest, list[TraceEvent]]:
    """Reads the bundle, checking the hash, the secret and the order. It refuses when something is out of place."""
    manifest_path = directory / MANIFEST_FILE
    events_path = directory / EVENTS_FILE
    if not manifest_path.exists() or not events_path.exists():
        raise BundleError(f"incomplete bundle in {directory}")

    raw_events = events_path.read_text(encoding="utf-8")
    if redact(raw_events) != raw_events:
        raise BundleError("the bundle has something that looks like a key inside")

    # The manifest is not hashed by anything inside the directory, so its own text goes through the same secret
    # check as the events file.
    raw_manifest = manifest_path.read_text(encoding="utf-8")
    if redact(raw_manifest) != raw_manifest:
        raise BundleError("the manifest has something that looks like a key inside")

    manifest = BundleManifest.from_dict(json.loads(raw_manifest))
    for name, digest in manifest.files.items():
        path = directory / name
        if not path.exists():
            raise BundleError(f"the manifest cites {name}, which is not in the bundle")
        if _sha256(path) != digest:
            raise BundleError(f"the hash of {name} does not match the manifest")

    # The bundle is a sealed package: what the manifest cites, the manifest itself, and nothing else. Dotfiles are
    # exempt because the desktop writes Finder metadata into folders, and that is not bundle content.
    expected = {MANIFEST_FILE, *manifest.files}
    present = {path.name for path in directory.iterdir() if not path.name.startswith(".")}
    if present != expected:
        extra = sorted(present - expected)
        raise BundleError(f"the bundle has extra files the manifest does not declare: {extra}")

    events = [TraceEvent.from_dict(json.loads(line)) for line in raw_events.splitlines() if line.strip()]
    if len(events) != manifest.events:
        raise BundleError("the manifest says one number of events and the file has another")
    if [event.seq for event in events] != list(range(1, len(events) + 1)):
        raise BundleError("the sequence of the bundle has a gap or a repetition")
    modes = {event.mode for event in events}
    if modes != {manifest.mode}:
        raise BundleError("the events of the bundle do not have the same mode the manifest declares")
    run_ids = {event.run_id for event in events}
    if run_ids != {manifest.run_id}:
        raise BundleError("the run id of the manifest is not the run id of the events")
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
