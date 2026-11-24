"""The page of the routing: the cascade, the nine fields of the decision, the rules and the numbers.

What they guarantee, and why: (a) the page exists even when the comparison was never run, because the cascade
and the rules of the routing are published before any number of the comparison exists; (b) the page names the
nine fields of the decision, so a reader knows what the router writes down; (c) the page states the rules that
keep the routing honest; (d) the numbers of the page are the numbers of the measurement, cell by cell and not as
strings that a page may carry anywhere, because a number without its dataset is a claim about nothing in
particular; (e) the digests of the page are the digests of the files on the disk, recomputed here and not read
from the report; (f) the prose of the measurement is the prose the module writes.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from ledgerlens.eval.routing_comparison import render_markdown

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "docs" / "routing.md"
MEASUREMENT = ROOT / "data" / "eval" / "routing_comparison.json"
PROSE = ROOT / "data" / "eval" / "routing_comparison.md"
CASES_PATH = ROOT / "data" / "eval" / "eval_cases.jsonl"

# The nine fields of the decision of the router, as the decision of ADR-078 names them.
NINE_FIELDS = (
    "case_id",
    "case_type",
    "risk_tier",
    "allowed_provider_models",
    "chosen_model",
    "reason",
    "budget",
    "price_snapshot",
    "confidence_kind",
)

# The rules that keep the routing honest, one phrase of the page for each one.
HONESTY_RULES = (
    "never silently replaced",
    "only runs a task when the capability",
    "unknown, and unknown is never zero",
    "written once",
)


def _table_of(page: str, header: str) -> list[list[str]]:
    """The rows of the table of the page whose header carries the header, as lists of cells.

    Why the table and not the text of the page: a number of the page that is read as a string anywhere in the
    page passes with any number in the wrong place, and a table with a header has a place for every number.
    """
    rows: list[list[str]] = []
    inside = False
    for line in page.splitlines():
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if not inside:
                inside = header in cells
                continue
            if all(set(cell) <= {"-", ":"} for cell in cells):
                continue
            rows.append(cells)
        else:
            inside = False
    return rows


def test_the_page_exists_even_when_the_comparison_was_never_run() -> None:
    """The cascade and the rules are published before any number of the comparison exists."""
    assert PAGE.is_file(), "the page of the routing is missing"
    assert PAGE.read_text("utf-8").strip()


def test_the_page_names_the_cascade_and_the_nine_fields_of_the_decision() -> None:
    """A reader knows what the router writes down and what the deployment declares."""
    text = PAGE.read_text("utf-8")
    for field in NINE_FIELDS:
        assert field in text, f"the page does not name the field {field}"
    assert "gpt-4.1-mini" in text and "gpt-4.1" in text


def test_the_page_states_the_rules_that_keep_the_routing_honest() -> None:
    """The four rules of ADR-078 are in the page, in the words of the page."""
    text = PAGE.read_text("utf-8")
    for rule in HONESTY_RULES:
        assert rule in text, f"the page does not state the rule {rule!r}"


def test_the_page_says_that_a_number_without_its_dataset_is_a_claim_about_nothing() -> None:
    """The sentence that makes the numbers of the page readable is in the page."""
    assert "a claim about nothing in particular" in PAGE.read_text("utf-8")


def test_the_page_states_the_rules_of_the_fallback() -> None:
    """A reader of the page knows that a fallback needs a consent and a budget that covers it.

    Why it matters: the fallback is the one place of a run where a call happens that the plan did not ask for,
    and a page that does not say so leaves the reader to assume that the router spends what it wants.
    """
    text = PAGE.read_text("utf-8")

    assert "The fallback of a run" in text
    assert "LEDGERLENS_FALLBACK_ATTEMPTS" in text
    assert "LEDGERLENS_FALLBACK_DIRECTION" in text
    assert "the check happens before the call" in text
    assert "no retry at all" in text


def test_the_measurement_is_published() -> None:
    """The comparison was measured and the measurement is on the disk.

    Why it is not a skip: the measurement is committed, and a file that went missing is a file that nobody
    noticed going missing.
    """
    assert MEASUREMENT.is_file(), "the measurement of the routes is missing"
    assert PROSE.is_file(), "the prose of the measurement is missing"


def test_the_numbers_of_the_page_are_the_numbers_of_the_measurement() -> None:
    """The table of the page carries the accuracy of each arm, the right arm and the right number."""
    report = json.loads(MEASUREMENT.read_text("utf-8"))
    page = PAGE.read_text("utf-8")
    rows = _table_of(page, "The measure")

    measured = {}
    for name, arm in report["arms"].items():
        measured[name] = {
            f"the accuracy over {report['cohort']['cases']} cases": str(arm["accuracy"]["accuracy"]),
            "the cases that carried every expected fact": (
                f"{arm['correct_cases']['cases']} of {arm['accuracy']['cases']}"
            ),
            "the tokens per correct case": str(arm["cost_per_correct_case"]["tokens"]),
            "the money per correct case": (
                f"{arm['cost_per_correct_case']['usd']} dollars"
                if arm["cost_per_correct_case"]["usd"] is not None
                else "unknown"
            ),
            "the p95 of the latency": f"{arm['latency_p95_ms']['value']} ms",
            "the calls": str(arm["fallback_rate"]["calls"]),
        }

    for line in rows:
        label = line[0]
        if label not in measured["one_model"]:
            continue
        for arm in ("one_model", "cascade"):
            assert measured[arm][label] == line[1 if arm == "one_model" else 2], f"the page is wrong about {label}"


def test_the_intents_of_the_page_are_the_intents_of_the_measurement() -> None:
    """The table of the intents carries the accuracy of each arm, per intent, with the cases behind it."""
    report = json.loads(MEASUREMENT.read_text("utf-8"))
    page = PAGE.read_text("utf-8")
    rows = _table_of(page, "Intent")

    for name, arm in report["arms"].items():
        for intent, values in arm["accuracy_by_intent"].items():
            row = next((cells for cells in rows if cells[0] == f"`{intent}`"), None)
            assert row is not None, f"the page has no row for the intent {intent}"
            assert row[1] == str(values["cases"])
            column = 2 if name == "one_model" else 3
            assert row[column] == str(values["accuracy"]), f"the page is wrong about the intent {intent}"


def test_the_digests_of_the_page_are_the_digests_of_the_files_on_the_disk() -> None:
    """The cohort and the ledger of the page are recomputed here, and not read from the report."""
    report = json.loads(MEASUREMENT.read_text("utf-8"))
    page = PAGE.read_text("utf-8")

    cohort_digest = hashlib.sha256(CASES_PATH.read_bytes()).hexdigest()
    assert report["cohort"]["digest"] == cohort_digest
    assert cohort_digest in page
    assert report["ledger"]["sha256"] in page
    assert str(report["cohort"]["cases"]) in page


def test_the_prose_of_the_measurement_is_the_prose_the_module_writes() -> None:
    """The published prose is the prose of the module, so a number of the report and a number of the prose agree."""
    report = json.loads(MEASUREMENT.read_text("utf-8"))

    assert PROSE.read_text("utf-8") == render_markdown(report)


def test_the_measurement_names_the_judge_that_scored_the_arms() -> None:
    """A reader of the measurement alone knows what judged the arms and what the numbers are comparable with."""
    report = json.loads(MEASUREMENT.read_text("utf-8"))

    assert report["judge"]["correctness"]
    assert report["judge"]["runs_per_case"] == 1
    assert "the other arm" in report["judge"]["comparable_with"]


@pytest.mark.parametrize("arm", ["one_model", "cascade"])
def test_every_case_of_the_cohort_has_a_row_in_every_arm(arm: str) -> None:
    """The row of every case is published, so a reader can check a total against the cases behind it."""
    report = json.loads(MEASUREMENT.read_text("utf-8"))
    rows = report["arms"][arm]["cases"]

    assert [row["case"] for row in rows] == report["cohort"]["ids"]
