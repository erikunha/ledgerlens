"""The capture of the replay bundle: the commit it names, the provenance it declares and the refusal to lie.

What they guarantee, and why: (a) the capture names the commit it ran from, so anybody can find the code that
produced the recording; (b) the capture refuses to run on a dirty tracked tree, because the recording claims a commit
and the claim has to be true; (c) an untracked file never blocks the capture, because the repository keeps untracked
material on purpose and the commit named is the commit of the tracked code; (d) the capture declares the provenance it
can state honestly, the capture kind, the moment of the capture, the model profile, the policy version and the
commit, and it declares nothing it cannot compute, so no hash of a prompt and no version of a redaction are invented;
(e) the bundle the first capture wrote does not block a second capture into the same folder.

Everything here runs offline, with no key and no network. The capture runs in a tiny repository built under the
temporary folder, so the real repository of the machine is never written to and never touched by a test.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from ledgerlens.replay.bundle import load_bundle
from ledgerlens.replay.verdict import differences
from ledgerlens.run_context import POLICY_VERSION

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "capture_replay.py"


def _load_script():
    """The capture script, loaded as a module so the test can drive its functions."""
    spec = importlib.util.spec_from_file_location("capture_replay", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


capture_replay = _load_script()


def _git(repository: Path, *args: str) -> str:
    """The output of a git command in the tiny repository of the test."""
    done = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return done.stdout.strip()


def _tiny_repository(path: Path) -> Path:
    """A repository with one commit and nothing else, so the capture has a commit to name."""
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "capture@example.invalid")
    _git(path, "config", "user.name", "Capture Test")
    (path / "README.md").write_text("a tiny repository\n", encoding="utf-8")
    _git(path, "add", "README.md")
    _git(path, "commit", "-q", "-m", "chore: first commit")
    return path


@pytest.fixture(scope="module")
def captured(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path, str]:
    """One capture in a tiny repository, with the bundle inside the repository.

    The commit the capture ran from is kept, because the bundle is tracked afterwards and that moves the head of the
    repository. The bundle is changed the way a second capture into the same folder changes it: the canonical bundle
    of the repository is tracked as well, so it shows up as a modification of the tracked tree.
    """
    repository = _tiny_repository(tmp_path_factory.mktemp("capture") / "repository")
    commit = _git(repository, "rev-parse", "HEAD")
    out = repository / "bundle"
    capture_replay.capture("S01", out, root=repository)
    _git(repository, "add", "bundle")
    _git(repository, "commit", "-q", "-m", "chore: the bundle of the capture")
    manifest_path = out / "manifest.json"
    manifest_path.write_text(manifest_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    return repository, out, commit


def test_the_capture_writes_the_commit_of_the_repository_into_the_manifest(captured: tuple[Path, Path, str]):
    """The recording names the commit it ran from, and the provenance it can state honestly.

    The fields it cannot compute, the hash of the prompt and the version of the redaction, stay absent: a value
    that is invented is worse than a value that is missing.
    """
    repository, out, commit = captured
    manifest, _ = load_bundle(out)

    assert manifest.code_sha == commit
    assert manifest.capture_kind == "scripted_fixture"
    assert manifest.model_profile == "scripted-fixture"
    assert manifest.policy_version == POLICY_VERSION
    assert manifest.recorded_at
    assert manifest.prompt_hash is None
    assert manifest.redaction_version is None


def test_the_capture_accepts_a_clean_tree_and_ignores_the_bundle_of_a_previous_capture(
    captured: tuple[Path, Path, str],
):
    """A capture into the same folder twice is not blocked by the bundle the first one wrote.

    The bundle is tracked in the repository of the test and changed by the second capture, so it shows up as a
    modification of the tracked tree. That report is about the output of the capture, not about the code, and the
    claim of the commit stays true without it.
    """
    repository, out, _commit = captured

    assert (out / "manifest.json").is_file()
    assert capture_replay.dirty_paths(repository, None) != []
    assert capture_replay.dirty_paths(repository, out) == []
    # The tree of the capture is clean for the code, so a second capture into the same folder is not refused.
    capture_replay.ensure_clean_tree(repository, out)


def test_an_untracked_file_does_not_block_the_capture(tmp_path: Path):
    """The repository keeps untracked material on purpose, so it never blocks the capture.

    The commit the recording names is the commit of the tracked code, and an untracked file is not part of it.
    """
    repository = _tiny_repository(tmp_path / "repository")
    (repository / "scratch.txt").write_text("material the repository keeps on purpose\n", encoding="utf-8")

    out = tmp_path / "bundle"
    capture_replay.capture("S01", out, root=repository)

    manifest, _ = load_bundle(out)
    assert manifest.code_sha == _git(repository, "rev-parse", "HEAD")
    assert capture_replay.dirty_paths(repository, out) == []
    assert capture_replay.dirty_paths(repository, None) == []


def test_the_capture_signs_in_as_the_account_that_holds_the_records_of_the_question(tmp_path: Path):
    """A question about the payout of a merchant is recorded with the merchant signed in.

    Why the account is not the first of the scenario: the scenario S08 names a customer and a merchant, and the
    question is about the payout of the merchant. Signing in as the customer reads nothing, and the recording
    would publish an answer that cites evidence the run never saw.
    """
    repository = _tiny_repository(tmp_path / "repository")
    out = tmp_path / "bundle"

    capture_replay.capture("S08", out, root=repository)

    manifest, _ = load_bundle(out)
    assert "M-03" in manifest.note
    assert "C-0900" not in manifest.note


def test_the_capture_of_a_scenario_that_names_no_account_uses_the_first_customer(tmp_path: Path):
    """A scenario whose question is about an id that does not exist still runs, on the first customer.

    Why the scenario names no account: the question of the scenario S04 is about a transaction that is not in the
    ledger, so there is no customer of the scenario to scope the ledger to. The run still needs an account to sign
    in, because the agent reads the ledger of one account, so the first customer of the ledger is used and the note
    of the bundle says which account it was.
    """
    repository = _tiny_repository(tmp_path / "repository")
    out = tmp_path / "bundle"

    capture_replay.capture("S04", out, root=repository)

    manifest, _ = load_bundle(out)
    assert manifest.scenario == "S04"
    assert "C-0001" in manifest.note


def test_the_capture_refuses_to_run_on_a_dirty_tree(tmp_path: Path):
    """A change in the tracked tree stops the capture, because the recording names a commit and the claim has to be
    true."""
    repository = _tiny_repository(tmp_path / "repository")
    (repository / "README.md").write_text("a change that was never committed\n", encoding="utf-8")

    out = tmp_path / "bundle"
    with pytest.raises(SystemExit) as refused:
        capture_replay.capture("S01", out, root=repository)

    message = str(refused.value)
    assert "dirty" in message
    assert "commit" in message
    # The paths of the status are read as they are, so the one that is dirty is named whole.
    assert "README.md" in message
    assert not out.exists()


def test_the_capture_refuses_to_run_when_the_commit_cannot_be_read(tmp_path: Path):
    """A repository with no commit has no commit to name, so the capture refuses with a clear message."""
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init", "-q")

    with pytest.raises(SystemExit) as refused:
        capture_replay.capture("S01", tmp_path / "bundle", root=repository)

    assert "commit" in str(refused.value)


def test_the_capture_refuses_to_run_in_a_folder_that_is_not_a_repository(tmp_path: Path):
    """A folder that is not a repository has no tracked tree to check, so the capture refuses with a clear message."""
    with pytest.raises(SystemExit) as refused:
        capture_replay.capture("S01", tmp_path / "bundle", root=tmp_path)

    assert "working tree" in str(refused.value)


def _case_id_of(bundle_dir: Path) -> str:
    """The id of the case the recording wrote, read from the bundle.

    Why the span of the memory and not the store of the machine: the bundle is what the repository publishes,
    and the id of the case is what the reader of the bundle sees.
    """
    for line in (bundle_dir / "events.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line).get("payload") or {}
        if payload.get("name") == "CaseMemory.write_case":
            outputs = payload.get("outputs") or {}
            if outputs.get("case_id"):
                return str(outputs["case_id"])
    return ""


def test_two_captures_of_the_same_scenario_write_the_same_case(tmp_path: Path):
    """Two captures of the same scenario write the same case, so the published bundle is reproducible.

    Why the id of the case matters: the bundle names the case the run wrote, and a reader who wants to find
    that case again has to be able to. The id used to come from a counter over a store that lives outside the
    repository, so two captures of the same commit gave two different ids, and the same commit published two
    different bundles.

    Why the id names the scenario: a counter is a number of one afternoon of one machine, and a number of that
    kind cannot be looked up. The scenario is in the bundle, and the case that names it can.
    """
    first = _tiny_repository(tmp_path / "first")
    second = _tiny_repository(tmp_path / "second")

    capture_replay.capture("S01", tmp_path / "first-bundle", root=first)
    capture_replay.capture("S01", tmp_path / "second-bundle", root=second)

    assert _case_id_of(tmp_path / "first-bundle") == "CASE-S01"
    assert _case_id_of(tmp_path / "first-bundle") == _case_id_of(tmp_path / "second-bundle")


def test_a_fresh_capture_publishes_a_verdict_that_its_own_evidence_reaches(tmp_path: Path):
    """The bundle a capture writes now carries the evidence that sustains the verdict it shows.

    Why this test and not only the one over the published set: the published set is captured by the release,
    and this one proves the rule of the capture itself, on a bundle the test writes in a throwaway repository.
    The scenario S11 is the one with the reference rate in fault, and its answer cites the rate the ledger
    applied: a bundle that cuts that rate away publishes a verdict that nobody can redo.
    """
    repository = _tiny_repository(tmp_path / "repository")
    out = tmp_path / "bundle"

    capture_replay.capture("S11", out, root=repository)

    assert differences(out) == [], "the verdict of the fresh capture is not reachable from its own evidence"

    events = [
        json.loads(line)
        for line in (out / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    evidence = ""
    for event in events:
        payload = event.get("payload") or {}
        outputs = payload.get("outputs") or {}
        if payload.get("run_type") == "tool" and outputs.get("ok"):
            evidence += json.dumps(outputs.get("data") or {}, ensure_ascii=False)

    assert "5.4931" in evidence, "the fresh capture does not publish the rate the answer cites"
    assert "2026-10-20" in evidence, "the fresh capture does not publish the day the answer cites"
