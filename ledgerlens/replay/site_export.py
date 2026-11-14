"""Turns a recorded replay bundle into the static artifacts the public web site reads.

Why it exists: the site is a static export, so the browser cannot ask a backend for a trace. It needs the recorded
events, a manifest that says what they are, and a provenance file that proves what is being shown. This module
produces those three things per scenario, plus one index that tells the catalog which scenarios exist. It runs
offline, with no key and with no network, and it never changes the recorded content: it copies, it hashes and it
labels.

The shapes are the ones the interface already reads, transcribed field by field from `apps/web/lib/api/schemas.ts` and
`apps/web/lib/replay/validate.ts`: the exported manifest is the manifest of the core, the provenance carries the
fields of the provenance panel, and the index holds one card per scenario with the identifier, the name, the
question, the concepts, the origin of the data as a string, the status, the kind of the capture and the path of the
bundle. The export adds its own names under names of their own (`bundle_digest`, `artifacts`, `dataset_sha256`), so
that nothing the interface reads is renamed and nothing of the export invents a field of the contract.

The export is a pure function of two inputs: the bundle and the public dataset. Every timestamp comes from the
manifest of the bundle, never from the clock, and the state of the repository is never read, so running the export
twice leaves the same bytes on the disk and a third party can confirm the result with a hash. The commit that
appears in the provenance is the one the capture wrote in the bundle: the export never looks at the repository, so
the published artifacts stay valid across commits.

The labels are the point of the module. The mode it writes is always `deterministic_sandbox`, because the published
bundles are deterministic recordings made with the scripted model and the recorded exchange rate. A bundle that
declares any other mode is refused rather than relabelled: a live execution published under a sandbox label would be
a lie, and a lie in a manifest is worse than a missing file. The note that goes with the manifest says the same
thing in words, so nobody has to read the format to know what the recording is.

The export refuses what it cannot prove. Every recorded line is validated against the versioned public schema, as it
was recorded and not as the core re-derives it, because a re-derivation coerces a wrong type into a right one. The
moment of the event is checked against the ISO 8601 shape the interface accepts, and the scenario of the bundle is
checked against the shape of the contract, so that the card and the manifest can never disagree. A bundle that does
not hold up is refused before anything is written, and a refusal is an `ExportError`, never a traceback.

The write publishes exactly the set that was exported, and it removes only the artifacts of the export: the folder
of a scenario that left the set goes away, and a file of somebody else stays. The files it left behind are named, so
that the reason the check is red is visible. A dotfile is exempt everywhere, because the desktop writes Finder
metadata into any folder a human opens and that is not content of the export.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ledgerlens.replay.bundle import (
    EVENTS_FILE,
    MANIFEST_FILE,
    PROVENANCE_FIELDS,
    BundleError,
    BundleManifest,
    bundle_digest,
    load_bundle,
)

ROOT = Path(__file__).resolve().parents[2]
TRACE_EVENT_SCHEMA = ROOT / "docs" / "v3" / "contracts" / "schemas" / "trace-event.schema.json"
DATASET_FILE = ROOT / "data" / "scenarios.json"

# The only mode the site publishes. A recorded sandbox is what the visitor sees, and the label never says live.
SITE_MODE = "deterministic_sandbox"

# The name of the file that holds the provenance of a scenario, next to the events and the manifest.
PROVENANCE_FILE = "provenance.json"

# The name of the file that lists every exported scenario, at the root of the export.
INDEX_FILE = "index.json"

# The status a published scenario card carries: the recording exists and it is a recording.
SCENARIO_STATUS = "Recorded"

# The shape of an ISO 8601 moment with a time zone, the same one the interface accepts for the moment of an event
# and of a capture. The schema of the trace event declares the format `date-time`, but a validator does not check a
# format on its own, and the environment is offline, so the moment is checked here against the shape the browser
# will read.
ISO8601_MOMENT_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")

# The shape of the identifier of a scenario, the same one the interface accepts for the card and for the manifest.
# A bundle that declares anything else is refused, so that the card and the manifest can never disagree.
SCENARIO_ID_PATTERN = re.compile(r"^[S][0-9]{2}$")

# The name of a scenario folder inside the output, the lower case of the identifier of the contract. Only a folder
# with this name is a scenario folder, so the write never removes a folder of somebody else.
SCENARIO_SLUG_PATTERN = re.compile(r"^[sS][0-9]{2}$")

# The three files of a scenario. They are the only files the export writes inside a scenario folder, and therefore
# the only files the write may delete: a file outside this list is not an artifact of the export.
SCENARIO_ARTIFACT_NAMES = (EVENTS_FILE, MANIFEST_FILE, PROVENANCE_FILE)

# The concept each tool of the agent demonstrates, in the words a visitor of the site understands.
TOOL_CONCEPTS = {
    "query_ledger": "read_only_ledger_query",
    "search_policies": "policy_retrieval",
    "get_reference_fx": "exchange_rate_reference",
    "calculate": "decimal_calculation",
    "recall_cases": "case_memory",
}

# The concept of the case that needs a person to decide.
HUMAN_REVIEW_CONCEPT = "human_review"


class ExportError(Exception):
    """The export refuses: the bundle does not hold up, or an event is outside the public schema."""


@dataclass(frozen=True)
class ExportedArtifact:
    """One file the export wrote, with the hash that proves what it holds."""

    path: Path
    sha256: str
    size: int


@dataclass(frozen=True)
class ExportOutcome:
    """What the write did: the files it wrote, and the foreign files it left behind.

    The foreign files are named, because they are the reason the check stays red: the write never deletes a file of
    somebody else, so the operator has to be told which one is in the way.
    """

    written: list[ExportedArtifact]
    foreign: list[Path]


def _is_dotfile(path: Path) -> bool:
    """Whether a file is a dotfile, which is not content of the export.

    The desktop writes Finder metadata (`.DS_Store`) into any folder a human opens, and that is not something the
    export published. The rule is the same one `load_bundle` of the core uses in a bundle, for the same reason.
    """
    return path.name.startswith(".")


def _sha256_bytes(payload: bytes) -> str:
    """The hash of the bytes, so the manifest and the provenance can cite the file exactly."""
    return hashlib.sha256(payload).hexdigest()


def _json_bytes(payload: Any) -> bytes:
    """The JSON of a payload, in the format the repository uses everywhere: sorted keys, two spaces, a final line."""
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    return (text + "\n").encode("utf-8")


def discover_bundles(folder: Path) -> list[Path]:
    """The bundles of a folder, in a stable order.

    A folder that is itself a bundle gives that bundle. A folder that holds bundles gives every bundle it holds,
    sorted by name, so the export never depends on the order the filesystem lists things in.
    """
    if (folder / MANIFEST_FILE).is_file() and (folder / EVENTS_FILE).is_file():
        return [folder]
    if not folder.is_dir():
        raise ExportError(f"the bundle folder does not exist: {folder}")
    found = sorted(
        child for child in folder.iterdir() if child.is_dir() and (child / MANIFEST_FILE).is_file()
    )
    if not found:
        raise ExportError(f"there is no bundle in {folder}")
    return found


def _load_dataset(path: Path = DATASET_FILE) -> tuple[dict[str, Any], str]:
    """The public dataset and its digest.

    The dataset is the second input of the export: the cards of the catalog come from it, and its digest goes into
    the provenance, so that a change of the dataset is visible in the published artifacts.
    """
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ExportError(f"the public dataset cannot be read: {path}") from exc
    try:
        dataset = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExportError(f"the public dataset is not valid JSON: {path}") from exc
    return dataset, _sha256_bytes(raw)


def _scenario_metadata(dataset: dict[str, Any], scenario: str) -> dict[str, Any]:
    """What the public dataset says about a scenario: its name, its question, its concepts and its data origin.

    It comes from the versioned dataset of the repository, not from the recording, so the catalog of the site and
    the dataset always agree. A scenario that the dataset does not know is refused: publishing a card without its
    question would be publishing an empty promise.
    """
    entries = {str(entry["id"]): entry for entry in dataset.get("scenarios", [])}
    entry = entries.get(scenario.upper())
    if entry is None:
        raise ExportError(f"the scenario {scenario} is not in the public dataset")

    questions = entry.get("questions") or []
    if not questions:
        raise ExportError(f"the scenario {scenario} has no question in the public dataset")

    concepts: list[str] = []
    for tool in entry.get("expected_tools") or []:
        concept = TOOL_CONCEPTS.get(str(tool))
        if concept and concept not in concepts:
            concepts.append(concept)
    if entry.get("requires_human_review") and HUMAN_REVIEW_CONCEPT not in concepts:
        concepts.append(HUMAN_REVIEW_CONCEPT)

    origin = _data_origin(dataset)
    return {
        "name": str(entry.get("name", "")),
        "question": str(questions[0]),
        "concepts": concepts,
        "data_origin": origin["data_origin"],
        "data_origin_detail": origin["detail"],
    }


def _data_origin(dataset: dict[str, Any]) -> dict[str, Any]:
    """Where the data of the ledger comes from: the name of the dataset, and the detail behind the name.

    The card shows a name, so `data_origin` is a string. The kind, the seed, the license and the reference travel
    with it under `data_origin_detail`, for the panel that shows the whole origin. When there is no public source
    behind the dataset, the origin is simulated and the name says so.
    """
    transform = dataset.get("transform") or {}
    sample = transform.get("sample_meta") or {}
    derived_from = str(sample.get("derived_from") or "")
    name, _, reference = derived_from.partition(", ")
    detail: dict[str, Any] = {
        "kind": "public-derived" if derived_from else "simulated",
        "seed": dataset.get("seed"),
    }
    if name:
        detail["dataset"] = name
    if reference:
        detail["reference"] = reference
    if sample.get("license"):
        detail["license"] = str(sample["license"])
    return {"data_origin": name or "simulated", "detail": detail}


def _recorded_lines(bundle_dir: Path) -> tuple[bytes, list[dict[str, Any]]]:
    """The bytes of the recorded events and the lines as they were recorded, parsed.

    The bytes are kept verbatim, because the exported events file has to be the file the bundle sealed, so that the
    digest of the manifest of the core still describes it.
    """
    try:
        raw = (bundle_dir / EVENTS_FILE).read_bytes()
    except FileNotFoundError as exc:
        raise ExportError(f"the bundle in {bundle_dir.name} has no {EVENTS_FILE}") from exc
    except OSError as exc:
        raise ExportError(f"the events of {bundle_dir.name} cannot be read") from exc

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExportError(f"the events of {bundle_dir.name} are not text") from exc

    lines: list[dict[str, Any]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ExportError(f"the event {number} of {bundle_dir.name} is not valid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ExportError(f"the event {number} of {bundle_dir.name} is not an object")
        lines.append(payload)
    return raw, lines


def _validate_recorded_events(lines: list[dict[str, Any]], schema_path: Path) -> None:
    """Checks every recorded line against the versioned public schema, before anything is written.

    The line is validated as it was recorded, and not the event the core re-derives from it: a re-derivation would
    coerce a wrong type into a right one, and the export would publish an event the bundle never had.

    The schema is the contract the interface reads, so an event outside it would break the site in the browser. The
    moment is checked here because a validator does not check the `format` of a field on its own, and the interface
    refuses a moment that is not an ISO 8601 moment with a time zone.
    """
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:  # jsonschema is a development dependency, and the export refuses without it
        raise ExportError("the export needs jsonschema, which the development extra installs") from exc

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExportError(f"the trace event schema cannot be read: {schema_path}") from exc
    validator = Draft202012Validator(schema)
    for number, line in enumerate(lines, start=1):
        errors = sorted(validator.iter_errors(line), key=lambda error: list(error.path))
        if errors:
            messages = "; ".join(error.message for error in errors)
            raise ExportError(f"the event {number} is outside the public schema: {messages}")
        moment = line.get("at")
        if not isinstance(moment, str) or not ISO8601_MOMENT_PATTERN.match(moment):
            raise ExportError(
                f"the event {number} has a moment that is not an ISO 8601 moment with a time zone: {moment!r}"
            )


def _load_manifest(bundle_dir: Path) -> BundleManifest:
    """The manifest of a bundle, after the core checked the hash, the secret and the order of the events.

    A bundle that does not hold up does not get exported, and the refusal is an `ExportError`: the export never
    lets a traceback out.
    """
    try:
        manifest, _events = load_bundle(bundle_dir)
    except BundleError as exc:
        raise ExportError(f"the bundle in {bundle_dir.name} does not hold up: {exc}") from exc
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise ExportError(f"the bundle in {bundle_dir.name} does not hold up: {exc}") from exc
    return manifest


def _scenario_artifacts(
    bundle_dir: Path,
    dataset: dict[str, Any],
    dataset_sha256: str,
    schema_path: Path,
) -> tuple[str, dict[str, bytes], dict[str, Any]]:
    """The three files of one scenario, and the card the index holds for it.

    The bundle is read with the loader of the core, which checks the hashes, the secret and the order of the
    events, and its recorded lines are checked against the versioned public schema.
    """
    events_bytes, lines = _recorded_lines(bundle_dir)
    _validate_recorded_events(lines, schema_path)
    manifest = _load_manifest(bundle_dir)

    if manifest.mode != SITE_MODE:
        raise ExportError(
            f"the bundle in {bundle_dir.name} declares the mode {manifest.mode} and the site publishes only "
            f"{SITE_MODE}"
        )

    scenario = str(manifest.scenario)
    if not SCENARIO_ID_PATTERN.match(scenario):
        # The card and the manifest have to agree, and the interface refuses an identifier outside the contract.
        raise ExportError(
            f"the bundle in {bundle_dir.name} declares the scenario {manifest.scenario!r}, which is not in the "
            f"shape of the contract: a letter S and two digits"
        )
    metadata = _scenario_metadata(dataset, scenario)
    slug = scenario.lower()

    # The exported manifest is the manifest of the core: the same keys, the same values, and the provenance fields
    # the bundle declares. Nothing is added and nothing is renamed.
    manifest_bytes = _json_bytes(manifest.to_dict())

    provenance_payload: dict[str, Any] = {
        "mode": manifest.mode,
        "files": dict(manifest.files),
        "created_at": manifest.created_at,
        "note": manifest.note,
        "bundle_digest": bundle_digest(bundle_dir),
        "artifacts": {
            EVENTS_FILE: _sha256_bytes(events_bytes),
            MANIFEST_FILE: _sha256_bytes(manifest_bytes),
        },
        "dataset_sha256": dataset_sha256,
    }
    if manifest.snapshot_sha256:
        provenance_payload["snapshot_sha256"] = manifest.snapshot_sha256
    # The provenance is declared field by field: a field the bundle does not declare never reaches the artifact,
    # because a claim that cannot be checked is worse than no claim.
    for name in PROVENANCE_FIELDS:
        value = getattr(manifest, name)
        if value:
            provenance_payload[name] = value
    provenance_bytes = _json_bytes(provenance_payload)

    files = {
        f"{slug}/{EVENTS_FILE}": events_bytes,
        f"{slug}/{MANIFEST_FILE}": manifest_bytes,
        f"{slug}/{PROVENANCE_FILE}": provenance_bytes,
    }
    card: dict[str, Any] = {
        "id": scenario,
        "name": metadata["name"],
        "question": metadata["question"],
        "concepts": metadata["concepts"],
        "data_origin": metadata["data_origin"],
        "data_origin_detail": metadata["data_origin_detail"],
        "status": SCENARIO_STATUS,
        "bundle_path": slug,
        "bundle_digest": provenance_payload["bundle_digest"],
        "provenance_sha256": _sha256_bytes(provenance_bytes),
    }
    if manifest.capture_kind:
        card["capture_kind"] = manifest.capture_kind
    if manifest.code_sha:
        # The card is what the visitor reads first, so it says which commit produced the recording.
        card["code_sha"] = manifest.code_sha
    return slug, files, card


def build_export(
    bundles: list[Path],
    *,
    schema_path: Path = TRACE_EVENT_SCHEMA,
    dataset_path: Path = DATASET_FILE,
) -> dict[str, bytes]:
    """The bytes of every file the export would write, keyed by the path relative to the output folder.

    Nothing is written here. The same function serves the write and the check, so the check compares the disk with
    exactly what the write would have produced. The result depends only on the bundles and on the public dataset.
    """
    dataset, dataset_sha256 = _load_dataset(dataset_path)
    files: dict[str, bytes] = {}
    cards: list[dict[str, Any]] = []
    for bundle_dir in bundles:
        _slug, scenario_files, card = _scenario_artifacts(bundle_dir, dataset, dataset_sha256, schema_path)
        files.update(scenario_files)
        cards.append(card)

    cards.sort(key=lambda card: str(card["id"]))
    files[INDEX_FILE] = _json_bytes(cards)
    return files


def _is_artifact_of_the_export(relative: Path) -> bool:
    """Whether a file of the output folder is one of the artifacts the export writes.

    The export writes the index at the root and three files inside each scenario folder, and a scenario folder is a
    folder whose name is the slug of the contract. A file outside this list belongs to somebody else, so the write
    never deletes it.
    """
    if _is_dotfile(relative):
        return False
    if len(relative.parts) == 1:
        return relative.name == INDEX_FILE
    if len(relative.parts) == 2:
        is_scenario_folder = SCENARIO_SLUG_PATTERN.match(relative.parts[0]) is not None
        return is_scenario_folder and relative.parts[1] in SCENARIO_ARTIFACT_NAMES
    return False


def write_export(files: dict[str, bytes], out_dir: Path) -> ExportOutcome:
    """Writes the files, removes the artifacts of a scenario that left the set, and returns what it did.

    What is published is exactly what was exported: the folder of a scenario that left the set is removed, so the
    site never shows a scenario the export does not cover. Only the artifacts of the export are removed, so a wrong
    output folder cannot cost anything, and the foreign files that were left behind are named, so the operator can
    see why the check stays red.
    """
    written: list[ExportedArtifact] = []
    for name in sorted(files):
        path = out_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = files[name]
        path.write_bytes(payload)
        written.append(ExportedArtifact(path=path, sha256=_sha256_bytes(payload), size=len(payload)))

    foreign: list[Path] = []
    if out_dir.is_dir():
        stale: list[Path] = []
        for path in sorted(out_dir.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(out_dir)
            if relative.as_posix() in files:
                continue
            if _is_dotfile(relative):
                # A dotfile is metadata of the desktop, not content of the export: it is left alone everywhere.
                continue
            if _is_artifact_of_the_export(relative):
                stale.append(path)
            else:
                foreign.append(path)
        folders = set()
        for path in stale:
            path.unlink()
            folders.add(path.parent)
        # A scenario folder that lost its last file is a folder of a scenario that left the set.
        for folder in sorted(folders, reverse=True):
            if folder != out_dir and folder.is_dir() and not any(folder.iterdir()):
                folder.rmdir()
    return ExportOutcome(written=written, foreign=foreign)


def check_export(files: dict[str, bytes], out_dir: Path) -> list[str]:
    """The differences between what would be written and what is on the disk, one line per difference.

    A missing file, a file with other bytes and a file that should not be there are all differences: the export is
    verified, not assumed. A dotfile is exempt, because the desktop writes it into any folder a human opens and it
    is not content of the export.
    """
    differences: list[str] = []
    for name in sorted(files):
        path = out_dir / name
        if not path.is_file():
            differences.append(f"missing: {name}")
            continue
        if path.read_bytes() != files[name]:
            differences.append(f"differs: {name}")
    if out_dir.is_dir():
        for path in sorted(out_dir.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(out_dir)
            if _is_dotfile(relative):
                continue
            name = relative.as_posix()
            if name not in files:
                differences.append(f"unexpected: {name}")
    return differences
