"""The baseline of the orchestration studio is frozen.

What they guarantee, and why: (a) the page of the baseline names a commit that exists in the repository, because a
baseline that names a commit that was never pushed is a baseline of nothing; (b) the page names the six tools of the
shipped agent and the repository still declares those six, because the arm of the comparison is the shipped path and
a shipped path that lost a tool is not the arm that was measured; (c) the page names the snapshot of the comparison
and the files of the disk still carry those digests, because a comparison whose arms read different ledgers is not a
comparison.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "docs" / "orchestration" / "baseline.md"

# The six tools of the shipped agent, in the order of the contract of `build_investigation_tools`.
THE_SIX_TOOLS = (
    "query_ledger",
    "get_ledger_record",
    "search_policies",
    "get_reference_fx",
    "calculate",
    "recall_cases",
)


def _the_page() -> str:
    """The text of the page of the baseline, and a failure with a reason when the page is not there.

    Why the failure is a sentence and not an error of the file system: the reader of the test wants to know that the
    page is missing and not that a path was not found.
    """
    if not BASELINE.is_file():
        pytest.fail(
            f"the baseline of the studio is not there: {BASELINE} does not exist, and the arm of the comparison is "
            "the path that the repository ships"
        )
    return BASELINE.read_text(encoding="utf-8")


def _flat(text: str) -> str:
    """The text with the line breaks of the page replaced by spaces.

    Why it exists: a sentence of the page is wrapped over several lines, and a test that looks for it has to look for
    the sentence and not for the line that happens to hold it.
    """
    return " ".join(text.split())


def _section(text: str, title: str) -> str:
    """The section of the page, from its title to the next title."""
    start = text.find(f"## {title}")
    assert start >= 0, f"the baseline has no section titled {title!r}"
    rest = text[start + len(title) + 3 :]
    end = rest.find("\n## ")
    return rest if end < 0 else rest[:end]


def _digests_of_the_page(text: str) -> list[str]:
    """The digests the page names, every sha256 that it holds."""
    digests: list[str] = []
    for word in text.replace("`", " ").split():
        candidate = word.strip(".,;:()")
        if len(candidate) == 64 and all(character in "0123456789abcdef" for character in candidate):
            digests.append(candidate)
    return digests


def test_the_page_of_the_baseline_exists() -> None:
    """The page exists, and a baseline that is not written is not a baseline."""
    assert BASELINE.is_file(), f"the baseline of the studio is missing: {BASELINE}"


def test_the_baseline_names_a_commit_that_exists_in_the_repository() -> None:
    """The commit of the baseline is a commit of the repository and not a name that was written down."""
    text = _the_page()
    section = _section(text, "The commit of the baseline")

    commits = [word.strip("`") for word in section.split() if len(word.strip("`")) == 40]
    assert commits, "the baseline names no commit"
    commit = commits[0]

    done = subprocess.run(
        ["git", "-C", str(ROOT), "cat-file", "-e", f"{commit}^{{commit}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, f"the commit {commit} of the baseline is not a commit of the repository"

    ancestor = subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", commit, "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert ancestor.returncode == 0, f"the commit {commit} of the baseline is not an ancestor of the head"


def test_the_baseline_names_the_six_tools_of_the_shipped_agent() -> None:
    """The page names the six tools and the repository still declares those six."""
    text = _the_page()
    section = _section(text, "The six tools of the agent")

    named = tuple(tool for tool in THE_SIX_TOOLS if f"`{tool}`" in section)
    assert named == THE_SIX_TOOLS, f"the baseline names the tools {named} and not the six of the contract"

    sources = sorted((ROOT / "ledgerlens").rglob("*.py"))
    for tool in THE_SIX_TOOLS:
        declared = any(f'name="{tool}"' in source.read_text(encoding="utf-8") for source in sources)
        assert declared, f"the shipped path no longer declares the tool {tool!r}"


def test_the_baseline_names_the_snapshot_of_the_comparison() -> None:
    """The page names the digest of the set and the digest of the ledger, and the disk still carries them."""
    text = _the_page()
    section = _section(text, "The snapshot of the comparison")

    set_path = ROOT / "data" / "eval" / "eval_cases.jsonl"
    set_digest = hashlib.sha256(set_path.read_bytes()).hexdigest()
    assert set_digest in _digests_of_the_page(section), "the baseline does not name the digest of the set"

    # The ledger of the set is rebuilt at run time and stays out of git, so the digest the page names is the one of
    # the canonical ledger that the scenarios file publishes.
    scenarios = json.loads((ROOT / "data" / "scenarios.json").read_text(encoding="utf-8"))
    ledger_digest = str(scenarios["db_canonical_sha256"])
    assert ledger_digest in _digests_of_the_page(section), "the baseline does not name the digest of the ledger"


def test_the_baseline_says_that_the_studio_is_not_the_default() -> None:
    """The page says what the studio has to beat, and it never says that it wins."""
    text = _the_page()

    assert "ADR-P007" in text
    flat = _flat(text).lower()
    assert "does not say that the studio is better" in flat
    assert "off in the shipped configuration" in flat
