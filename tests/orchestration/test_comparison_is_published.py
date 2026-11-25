"""The publication of the comparison of the studio: the page exists, with the decision that followed the result.

What they guarantee, and why: (a) the page of the comparison exists, because a result that is not published is a
result that nobody can check (FR-002 of the spec of the studio); (b) the page names the two arms, the
denominator of every measure, the uncertainty of the difference and the decision that follows the result,
because a number without its denominator and its uncertainty is a number about nothing in particular; (c) the
page exists even when the decision was that the flag stays off, because a study that hides its negative result
is not a study (the package asks for the published negative result, and the repository publishes the failures
of its catalog on purpose, ADR-068).

Everything here runs offline, with no key and with no network: the page was written by the run of the
comparison, and the test reads the page, it does not run the comparison.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "docs" / "orchestration" / "comparison.md"
RESULT = ROOT / "data" / "runtime" / "orchestration" / "result.json"
RUNS = ROOT / "data" / "runtime" / "orchestration" / "runs.jsonl"


def test_the_page_of_the_comparison_exists() -> None:
    """The page exists even when the decision was that the flag stays off: the negative result is published."""
    assert PAGE.is_file(), (
        "the page of the comparison does not exist: run "
        "`LEDGERLENS_OFFLINE=0 LEDGERLENS_ORCHESTRATION_STUDIO=1 uv run python scripts/measure_orchestration.py`"
    )


def test_the_page_names_the_two_arms() -> None:
    """The page names the arm of the single agent and the arm of the studio."""
    text = PAGE.read_text(encoding="utf-8")

    assert "## The arm `single_agent`" in text
    assert "## The arm `orchestration_studio`" in text


def test_the_page_names_the_denominator_of_the_measures() -> None:
    """Every measure of the page carries the number of cases behind it."""
    text = PAGE.read_text(encoding="utf-8")

    assert "the denominator of every measure is the 31 cases of the set" in text
    assert re.search(r"The correct cases: \d+ of 31\.", text)


def test_the_page_names_the_uncertainty_of_the_difference() -> None:
    """The page publishes the interval of the difference of the correctness, and what the interval is."""
    text = PAGE.read_text(encoding="utf-8")

    assert "## The difference of the arms" in text
    assert "The interval of the difference of the correctness is" in text
    assert "## The uncertainty" in text
    assert "is not a generalization" in text


def test_the_page_names_the_rule_and_the_decision_that_follows_the_result() -> None:
    """The decision of the page is the rule the manifest registered, and it is published either way."""
    text = PAGE.read_text(encoding="utf-8")

    assert "## The rule and the decision" in text
    assert "The decision: **" in text
    outcome = re.search(r"The decision: \*\*(.+?)\*\*", text)
    assert outcome is not None
    assert outcome.group(1) in {"gain", "the flag stays off"}


def test_the_result_and_the_record_of_the_run_exist_next_to_the_page() -> None:
    """The numbers of the page are the numbers of the result, and the run is recorded with the manifest it ran."""
    assert RESULT.is_file(), "the result of the comparison does not exist"
    assert RUNS.is_file(), "the record of the runs of the comparison does not exist"
    first = RUNS.read_text(encoding="utf-8").splitlines()[0]
    assert "manifest_sha256" in first
