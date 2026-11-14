"""The static export of a recorded bundle: the files the public site reads, and the promises they keep.

What they guarantee, and why: (a) the export writes the events, the manifest, the provenance and the index, so the
site has everything it needs to open a recorded case; (b) every exported event satisfies the versioned public
schema, so the browser never has to guess the format; (c) the export is byte identical when it runs twice, because
every timestamp comes from the bundle and not from the clock, and the digest of every published file is pinned in
this file, so a change of the export cannot land without the artifacts being regenerated; (d) the exported mode is
`deterministic_sandbox` and the note says the execution is not a live one, because a replay read as a live run is
the worst failure this repository can have; (e) a bundle whose manifest was tampered with is refused, so a broken
recording never reaches the site; (f) the provenance carries the digest of each artifact, the commit the capture
wrote and the digest of the dataset, so the interface can prove what it is showing; (g) the check reports a
difference when a file on the disk is not what the bundle says it is.

Everything here runs offline, with no key and no network. The bundle used is the canonical one of the S01 scenario,
recorded by the offline path of the product, with the scripted model and the recorded exchange rate. The bundles a
test needs a different one of are built under `tmp_path`, by copying the canonical one and changing it there: the
canonical bundle is an input of the export and is never written to.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

from ledgerlens.replay.site_export import (
    ExportError,
    build_export,
    check_export,
    discover_bundles,
    write_export,
)

ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "data" / "eval" / "replay" / "s01"
DATASET = ROOT / "data" / "scenarios.json"
SCHEMA = ROOT / "docs" / "v3" / "contracts" / "schemas" / "trace-event.schema.json"
SCRIPT = ROOT / "scripts" / "export_replay_site.py"
PUBLISHED = ROOT / "site" / "replay"

# The digest of every file the export publishes, pinned here so that a change of the export cannot land without the
# artifacts of `site/replay` being regenerated. The bundle and the dataset are the only inputs of these digests.
EXPECTED_DIGESTS = {
    "index.json": "9117f8bbb3df7f12d2c95c7de7cb9f967cc4596ba6f7652e5de743e435a3c868",
    "s01/events.jsonl": "577939e532327f3af1a3897612f622d96edc27a620646437fb02c5fa5318de13",
    "s01/manifest.json": "bbbe1e54fcae712df66a3a6096838ab5b7f8c938e2e47b7ef6681e43cafa84ac",
    "s01/provenance.json": "c879b10e32cc1f889cac717141da83da78bd3ac2497ebaf774a05090a73d06e5",
}


def _load_script():
    """The export script, loaded as a module so the test can drive its command line."""
    spec = importlib.util.spec_from_file_location("export_replay_site", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


export_replay_site = _load_script()


def _sha256(path: Path) -> str:
    """The hash of a file, the way the provenance records it."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bundle_manifest(bundle: Path = CANONICAL) -> dict:
    """The manifest of a bundle, as it was written."""
    return json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))


def _events(bundle: Path) -> list[dict]:
    """The recorded events of a bundle, parsed."""
    text = (bundle / "events.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _copy_bundle(tmp_path: Path, name: str = "bundle") -> Path:
    """A copy of the canonical bundle, so a test can change it without touching the canonical one."""
    bundle = tmp_path / name
    shutil.copytree(CANONICAL, bundle)
    return bundle


def _rewrite_events(bundle: Path, events: list[dict]) -> None:
    """Writes the events back and re-seals the manifest.

    The manifest carries the digest of the events file, so a bundle whose events were changed without resealing is
    refused by the hash of the core. The test wants the refusal of the export itself, so the bundle stays coherent.
    """
    text = "\n".join(json.dumps(event, ensure_ascii=False, sort_keys=True) for event in events) + "\n"
    (bundle / "events.jsonl").write_text(text, encoding="utf-8")
    manifest = _bundle_manifest(bundle)
    manifest["files"]["events.jsonl"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    (bundle / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def test_the_export_writes_the_events_the_manifest_the_provenance_and_the_index(tmp_path: Path):
    """The export leaves on the disk everything the site needs to open a recorded case."""
    out = tmp_path / "replay"
    artifacts = build_export([CANONICAL])
    written = write_export(artifacts, out).written

    assert (out / "index.json").is_file()
    assert (out / "s01" / "events.jsonl").is_file()
    assert (out / "s01" / "manifest.json").is_file()
    assert (out / "s01" / "provenance.json").is_file()
    assert {artifact.path.relative_to(out).as_posix() for artifact in written} == {
        "index.json",
        "s01/events.jsonl",
        "s01/manifest.json",
        "s01/provenance.json",
    }
    assert all(len(artifact.sha256) == 64 for artifact in written)


def test_the_exported_manifest_carries_exactly_the_keys_of_the_manifest_of_the_core(tmp_path: Path):
    """The exported manifest is the manifest of the core, key for key, with the provenance the bundle declares."""
    out = tmp_path / "replay"
    write_export(build_export([CANONICAL]), out)

    core = _bundle_manifest()
    exported = json.loads((out / "s01" / "manifest.json").read_text(encoding="utf-8"))
    assert set(exported) == set(core)
    assert exported["bundle_schema_version"] == core["bundle_schema_version"]
    assert exported["run_id"] == core["run_id"]
    assert exported["mode"] == core["mode"]
    assert exported["scenario"] == core["scenario"]
    assert exported["events"] == core["events"]
    assert exported["files"] == core["files"]
    assert exported["snapshot_sha256"] == core["snapshot_sha256"]
    assert exported["note"] == core["note"]
    for name in ("capture_kind", "recorded_at", "model_profile", "code_sha", "policy_version"):
        assert exported[name] == core[name]


def test_the_exported_provenance_carries_the_fields_the_interface_reads(tmp_path: Path):
    """The provenance says what the interface shows, and names the bundle and the dataset it came from."""
    out = tmp_path / "replay"
    write_export(build_export([CANONICAL]), out)

    provenance = json.loads((out / "s01" / "provenance.json").read_text(encoding="utf-8"))
    for name in (
        "mode",
        "capture_kind",
        "recorded_at",
        "model_profile",
        "code_sha",
        "snapshot_sha256",
        "policy_version",
        "files",
        "created_at",
        "note",
    ):
        assert name in provenance, name
    assert provenance["mode"] == "deterministic_sandbox"
    assert provenance["snapshot_sha256"] == _bundle_manifest()["snapshot_sha256"]
    assert provenance["files"]["events.jsonl"] == _sha256(CANONICAL / "events.jsonl")
    assert provenance["created_at"] == _bundle_manifest()["created_at"]
    assert provenance["note"] == _bundle_manifest()["note"]
    assert provenance["bundle_digest"] == _sha256(CANONICAL / "manifest.json")
    assert provenance["artifacts"]["events.jsonl"] == _sha256(out / "s01" / "events.jsonl")
    assert provenance["artifacts"]["manifest.json"] == _sha256(out / "s01" / "manifest.json")
    assert provenance["dataset_sha256"] == _sha256(DATASET)


def test_the_commit_of_the_exported_provenance_is_the_commit_the_capture_wrote(tmp_path: Path):
    """The commit comes from the recording, and the export never reads the state of the repository."""
    out = tmp_path / "replay"
    write_export(build_export([CANONICAL]), out)

    core = _bundle_manifest()
    provenance = json.loads((out / "s01" / "provenance.json").read_text(encoding="utf-8"))
    assert provenance["code_sha"] == core["code_sha"]
    assert len(provenance["code_sha"]) == 40
    assert provenance["recorded_at"] == core["recorded_at"]
    assert provenance["capture_kind"] == core["capture_kind"]
    assert provenance["model_profile"] == core["model_profile"]
    assert provenance["policy_version"] == core["policy_version"]


def test_the_index_card_carries_the_fields_the_interface_reads(tmp_path: Path):
    """The card of the catalog carries what the interface reads, and the digest of the provenance of the scenario."""
    out = tmp_path / "replay"
    write_export(build_export([CANONICAL]), out)

    index = json.loads((out / "index.json").read_text(encoding="utf-8"))
    assert isinstance(index, list)
    card = index[0]
    assert card["id"] == "S01"
    assert card["name"]
    assert card["question"]
    assert card["concepts"]
    assert isinstance(card["data_origin"], str)
    assert card["data_origin"]
    assert card["status"] == "Recorded"
    assert card["capture_kind"] == "scripted_fixture"
    assert card["bundle_path"] == "s01"
    assert card["bundle_digest"] == _sha256(CANONICAL / "manifest.json")
    assert card["provenance_sha256"] == _sha256(out / "s01" / "provenance.json")


def test_the_card_carries_the_commit_the_capture_wrote(tmp_path: Path):
    """The card of the catalog says which commit produced it, next to the digest of the bundle."""
    out = tmp_path / "replay"
    write_export(build_export([CANONICAL]), out)

    card = json.loads((out / "index.json").read_text(encoding="utf-8"))[0]
    assert card["code_sha"] == _bundle_manifest()["code_sha"]
    assert len(card["code_sha"]) == 40


def test_every_exported_event_follows_the_versioned_public_schema(tmp_path: Path):
    """Every exported event satisfies the public schema, field by field."""
    from jsonschema import Draft202012Validator

    out = tmp_path / "replay"
    write_export(build_export([CANONICAL]), out)

    validator = Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
    lines = (out / "s01" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert lines
    for line in lines:
        event = json.loads(line)
        errors = sorted(validator.iter_errors(event), key=lambda error: list(error.path))
        assert not errors, f"{event.get('event_type')} outside the schema: {[error.message for error in errors]}"


def test_the_export_is_byte_identical_when_it_runs_twice(tmp_path: Path):
    """Running the export twice gives the same bytes, because no timestamp comes from the clock."""
    first = build_export([CANONICAL])
    second = build_export([CANONICAL])
    assert first == second

    write_export(first, tmp_path / "one")
    write_export(second, tmp_path / "two")
    for name in first:
        assert (tmp_path / "one" / name).read_bytes() == (tmp_path / "two" / name).read_bytes(), name


def test_the_digest_of_every_exported_file_is_pinned():
    """The bytes of the export are pinned, so a change of the export cannot land without a regeneration."""
    files = build_export([CANONICAL])
    digests = {name: hashlib.sha256(payload).hexdigest() for name, payload in files.items()}
    assert digests == EXPECTED_DIGESTS


def test_the_export_does_not_read_the_clock(tmp_path: Path):
    """The moment of the exported manifest is the moment of the bundle, not the moment of the export."""
    out = tmp_path / "replay"
    write_export(build_export([CANONICAL]), out)

    exported = json.loads((out / "s01" / "manifest.json").read_text(encoding="utf-8"))
    assert exported["created_at"] == _bundle_manifest()["created_at"]

    provenance = json.loads((out / "s01" / "provenance.json").read_text(encoding="utf-8"))
    assert provenance["created_at"] == _bundle_manifest()["created_at"]
    assert provenance["recorded_at"] == _bundle_manifest()["recorded_at"]


def test_a_bundle_with_an_event_whose_moment_is_not_a_moment_is_refused(tmp_path: Path):
    """An event whose moment is not an ISO 8601 moment is refused, because the interface could not read it."""
    bundle = _copy_bundle(tmp_path)
    events = _events(bundle)
    events[0]["at"] = "yesterday afternoon"
    _rewrite_events(bundle, events)

    with pytest.raises(ExportError):
        build_export([bundle])


def test_a_bundle_with_an_event_whose_sequence_is_a_string_is_refused(tmp_path: Path):
    """A sequence number that is a string is refused, and not coerced into a number."""
    bundle = _copy_bundle(tmp_path)
    events = _events(bundle)
    events[0]["seq"] = str(events[0]["seq"])
    _rewrite_events(bundle, events)

    with pytest.raises(ExportError):
        build_export([bundle])


def test_an_event_beyond_the_first_one_is_validated(tmp_path: Path):
    """The sixth event is checked too, and not only the first line of the file."""
    bundle = _copy_bundle(tmp_path)
    events = _events(bundle)
    events[5]["seq"] = str(events[5]["seq"])
    _rewrite_events(bundle, events)

    with pytest.raises(ExportError) as refusal:
        build_export([bundle])
    assert "event 6" in str(refusal.value)


def test_a_bundle_with_a_malformed_payload_is_refused(tmp_path: Path):
    """A payload that is not an object is a refusal, and never a traceback."""
    bundle = _copy_bundle(tmp_path)
    events = _events(bundle)
    events[0]["payload"] = ["not", "an", "object"]
    _rewrite_events(bundle, events)

    with pytest.raises(ExportError):
        build_export([bundle])


def test_a_bundle_with_an_event_that_is_not_json_is_refused(tmp_path: Path):
    """A line that is not JSON at all is a refusal, and never a traceback."""
    bundle = _copy_bundle(tmp_path)
    (bundle / "events.jsonl").write_text("{not json\n", encoding="utf-8")
    manifest = _bundle_manifest(bundle)
    manifest["files"]["events.jsonl"] = hashlib.sha256(b"{not json\n").hexdigest()
    (bundle / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    with pytest.raises(ExportError):
        build_export([bundle])


def test_a_bundle_that_declares_another_mode_is_refused_and_never_relabelled(tmp_path: Path):
    """A bundle that is not a deterministic sandbox is refused, and the export does not call it one."""
    bundle = _copy_bundle(tmp_path)
    events = _events(bundle)
    for event in events:
        event["mode"] = "recorded_replay"
    _rewrite_events(bundle, events)
    manifest = _bundle_manifest(bundle)
    manifest["mode"] = "recorded_replay"
    (bundle / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    with pytest.raises(ExportError):
        build_export([bundle])


def test_a_bundle_whose_scenario_is_not_in_the_shape_of_the_contract_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """A scenario that is not a letter S and two digits is refused, and nothing is written."""
    bundle = _copy_bundle(tmp_path)
    manifest = _bundle_manifest(bundle)
    manifest["scenario"] = "s01"
    (bundle / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    out = tmp_path / "replay"
    with pytest.raises(ExportError):
        build_export([bundle])
    assert export_replay_site.main([str(bundle), "--out", str(out)]) == 1
    capsys.readouterr()
    assert not out.exists() or not any(out.iterdir())


def test_a_bundle_with_a_tampered_manifest_is_refused(tmp_path: Path):
    """A bundle whose manifest was changed does not get exported."""
    bundle = _copy_bundle(tmp_path)
    manifest = _bundle_manifest(bundle)
    manifest["events"] = manifest["events"] + 1
    (bundle / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    with pytest.raises(ExportError):
        build_export([bundle])


def test_a_schema_that_is_missing_or_broken_is_a_refusal_and_not_a_traceback(tmp_path: Path):
    """The schema is read once and a schema that does not hold up is a refusal, never a crash."""
    with pytest.raises(ExportError):
        build_export([CANONICAL], schema_path=tmp_path / "missing.schema.json")

    broken = tmp_path / "broken.schema.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(ExportError):
        build_export([CANONICAL], schema_path=broken)


def test_the_check_reports_a_missing_file_and_an_unexpected_file(tmp_path: Path):
    """The check says what is missing and what should not be there, one line per difference."""
    out = tmp_path / "replay"
    files = build_export([CANONICAL])
    write_export(files, out)
    assert check_export(files, out) == []

    (out / "s01" / "events.jsonl").unlink()
    (out / "s01" / "stray.json").write_text("{}", encoding="utf-8")
    differences = check_export(files, out)
    assert "missing: s01/events.jsonl" in differences
    assert "unexpected: s01/stray.json" in differences


def test_the_write_removes_the_folder_of_a_scenario_that_left_the_set(tmp_path: Path):
    """What is published is exactly what was exported: the folder of a scenario that left the set is removed."""
    out = tmp_path / "replay"
    files = build_export([CANONICAL])
    write_export(files, out)
    assert (out / "s01" / "manifest.json").is_file()

    remaining = {name: payload for name, payload in files.items() if not name.startswith("s01/")}
    write_export(remaining, out)

    assert not (out / "s01").exists()
    assert (out / "index.json").is_file()


def test_a_dotfile_in_the_output_folder_is_exempt_and_survives_the_write(tmp_path: Path):
    """A dotfile is not content of the export: the check ignores it and the write never deletes it."""
    out = tmp_path / "replay"
    files = build_export([CANONICAL])
    write_export(files, out)

    finder = out / ".DS_Store"
    finder.write_bytes(b"\x00")
    assert check_export(files, out) == []

    outcome = write_export(files, out)
    assert finder.is_file()
    assert outcome.foreign == []


def test_a_foreign_file_that_is_not_a_dotfile_is_reported_and_is_not_deleted(tmp_path: Path):
    """A file of somebody else is reported by the check, never deleted, and named by the write."""
    out = tmp_path / "replay"
    files = build_export([CANONICAL])
    write_export(files, out)

    stranger = out / "notes.md"
    stranger.write_text("keep me", encoding="utf-8")
    assert "unexpected: notes.md" in check_export(files, out)

    outcome = write_export(files, out)
    assert stranger.is_file()
    assert stranger.read_text(encoding="utf-8") == "keep me"
    assert outcome.foreign == [stranger]


def test_an_unrelated_folder_inside_the_output_is_never_touched(tmp_path: Path):
    """Only the folder of a scenario is removed: a folder named `docs` inside the output is not one."""
    out = tmp_path / "replay"
    files = build_export([CANONICAL])
    write_export(files, out)

    docs = out / "docs"
    docs.mkdir()
    (docs / "manifest.json").write_text("{}", encoding="utf-8")

    remaining = {name: payload for name, payload in files.items() if not name.startswith("s01/")}
    write_export(remaining, out)

    assert (docs / "manifest.json").is_file()
    assert not (out / "s01").exists()


def test_the_write_refuses_to_delete_a_file_that_is_not_an_artifact_of_the_export(tmp_path: Path):
    """A file that the export never wrote is never deleted, so a wrong output folder cannot cost anything."""
    out = tmp_path / "replay"
    files = build_export([CANONICAL])
    write_export(files, out)

    stranger = out / "notes.md"
    stranger.write_text("keep me", encoding="utf-8")
    remaining = {name: payload for name, payload in files.items() if not name.startswith("s01/")}
    write_export(remaining, out)

    assert stranger.is_file()
    assert stranger.read_text(encoding="utf-8") == "keep me"


def test_the_default_output_of_the_script_is_the_folder_the_repository_publishes():
    """The default output is `site/replay`, and it is not inside the paused frontend tree."""
    assert export_replay_site.DEFAULT_OUT == ROOT / "site" / "replay"
    assert "apps" not in export_replay_site.DEFAULT_OUT.relative_to(ROOT).parts


def test_the_script_exits_1_when_the_disk_differs_and_0_when_it_matches(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """The command line check fails when the disk differs and passes when it matches, writing nothing."""
    out = tmp_path / "replay"
    assert export_replay_site.main([str(CANONICAL), "--out", str(out)]) == 0
    capsys.readouterr()

    assert export_replay_site.main([str(CANONICAL), "--out", str(out), "--check"]) == 0
    capsys.readouterr()

    (out / "s01" / "events.jsonl").write_text("tampered\n", encoding="utf-8")
    assert export_replay_site.main([str(CANONICAL), "--out", str(out), "--check"]) == 1
    assert "s01/events.jsonl" in capsys.readouterr().err


def test_the_artifacts_published_in_the_repository_match_the_bundle():
    """The published artifacts are the ones the bundle says, so the gate can prove they never drifted."""
    files = build_export([CANONICAL])
    assert check_export(files, PUBLISHED) == []


def test_a_folder_of_bundles_gives_one_scenario_per_bundle():
    """A folder with bundle folders inside it gives one scenario for each of them."""
    found = discover_bundles(ROOT / "data" / "eval" / "replay")
    assert [path.name for path in found] == ["s01"]

    assert discover_bundles(CANONICAL) == [CANONICAL]
