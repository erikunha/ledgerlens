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
import subprocess
import sys
from pathlib import Path

import pytest

from ledgerlens.replay.bundle import load_bundle
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
