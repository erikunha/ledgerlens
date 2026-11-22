"""Tests of the tool that runs the blind reading of the held out set.

Why they exist: ADR-053 decides that the labels of the held out set come from one person who reads the cases one at a
time, blind to the recipe of each case, and that the label of the reader wins over the recipe. The tool is the
instrument of that reading, so every promise of the decision needs a test: one case at a time, no recipe on a screen,
the rule of ADR-007 on every screen, the evidence the way the model reads it, the case without evidence, the session
that resumes, the labels file, the report of the disagreements, the build that keeps the label of the reader, and the
malformed line that is a sentence and not a traceback.

Every test here runs against a temporary tree: the tool takes the root as an argument, so nothing in this file writes
in the repository and nothing in it reads the cases of the repository.

These tests were written before the script and were seen failing without it.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "label_heldout.py"

# The markers the recipes of the fixtures carry. None of them may ever reach a screen.
TEMPLATE_MARKER = "TEMPLATE-MARKER"
PAIR_MARKER = "PAIR-MARKER-07"
FACT_MARKER = "FACT-MARKER"


@pytest.fixture()
def tool():
    """The script under test, loaded as a module so the test can drive its functions."""
    spec = importlib.util.spec_from_file_location("label_heldout", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ---- fixtures --------------------------------------------------------------------------------------


def _envelope(row_id: str = "TX-9001", status: str = "captured") -> dict:
    """One evidence of a case: the JSON envelope of a tool, the shape the live set uses."""
    return {
        "id": "sql:1",
        "content": json.dumps(
            {
                "sql": f"SELECT id, status FROM transactions WHERE id = '{row_id}'",
                "columns": ["id", "status"],
                "rows": [[row_id, status]],
            }
        ),
    }


def _case(index: int, claim: str, evidence: list[dict] | None = None) -> dict:
    """One case of the set: the id, the claim, the ids the claim cites and the evidence itself."""
    items = evidence if evidence is not None else []
    return {
        "id": f"ho-{index:03d}",
        "claim": claim,
        "evidence_ids": [item["id"] for item in items],
        "evidence": items,
    }


def _recipe(index: int, expected: str) -> dict:
    """One recipe of the set: the template, the expected label, the pair and the fact that differs."""
    return {
        "id": f"ho-{index:03d}",
        "template": TEMPLATE_MARKER,
        "expected_label": expected,
        "pair_id": PAIR_MARKER,
        "differing_fact": FACT_MARKER,
    }


def _write_jsonl(path: Path, records: list[dict]) -> Path:
    """A JSONL file of the temporary tree, one record per line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    return path


def _tree(root: Path, cases: list[dict], recipes: list[dict] | None = None) -> Path:
    """A temporary tree with the cases of the set and, when asked for, the recipes."""
    _write_jsonl(root / "data" / "eval" / "heldout" / "cases.jsonl", cases)
    if recipes is not None:
        _write_jsonl(root / "data" / "eval" / "heldout" / "recipes.jsonl", recipes)
    return root


def _three_cases() -> list[dict]:
    """Three cases of the set, each with its own claim and its own evidence."""
    return [
        _case(1, "The payment TX-9001 was captured.", [_envelope("TX-9001", "captured")]),
        _case(2, "The refund R-9002 was paid.", [_envelope("R-9002", "paid")]),
        _case(3, "The charge CB-9003 was won.", [_envelope("CB-9003", "won")]),
    ]


def _session(tool, root: Path, answers: list[str]) -> str:
    """Runs the reading session over the tree and returns everything the reader saw."""
    out = io.StringIO()
    tool.read_session(root, iter(answers), out)
    return out.getvalue()


def _labels(root: Path) -> list[dict]:
    """The records of the labels file of the tree."""
    path = root / "data" / "eval" / "heldout" / "labels_v1.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ---- one case at a time ------------------------------------------------------------------------------


def test_the_session_shows_one_case_at_a_time(tool, tmp_path: Path) -> None:
    """The first screen holds the first case and says nothing about the two that come after it."""
    root = _tree(tmp_path, _three_cases())
    seen = _session(
        tool,
        root,
        ["supported", "the ledger says so", "contradicted", "the ledger says another", "not_enough_evidence", "silent"],
    )

    first = seen.split("CASE ho-002")[0]
    assert "ho-001" in first
    assert "The payment TX-9001 was captured." in first
    assert "The refund R-9002 was paid." not in first
    assert "The charge CB-9003 was won." not in first


def test_no_screen_shows_the_recipe_of_a_case(tool, tmp_path: Path) -> None:
    """The template, the expected label, the pair and the fact that differs never reach a screen."""
    root = _tree(tmp_path, _three_cases(), [_recipe(index, "contradicted") for index in (1, 2, 3)])
    seen = _session(
        tool,
        root,
        ["supported", "one", "supported", "two", "supported", "three"],
    )

    assert TEMPLATE_MARKER not in seen
    assert PAIR_MARKER not in seen
    assert FACT_MARKER not in seen
    # the screen never names an expected label of any case
    assert "expected" not in seen.lower()


# ---- the rule on every screen ------------------------------------------------------------------------


def test_every_screen_carries_the_rule_of_adr_007(tool, tmp_path: Path) -> None:
    """The rule of ADR-007 is in the header of every screen, and so is the rule ADR-053 adds."""
    root = _tree(tmp_path, _three_cases())
    seen = _session(tool, root, ["supported", "one", "supported", "two", "supported", "three"])

    assert seen.count(tool.RULE_ADR_007) == 3
    assert seen.count(tool.RULE_SELF_CONTRADICTION) == 3
    assert "Evidence that contradicts itself says two things and so says nothing" in seen


# ---- the evidence as the model reads it ----------------------------------------------------------------


def test_the_evidence_is_shown_as_the_model_will_read_it(tool, tmp_path: Path) -> None:
    """The screen shows the rendered premise, never the JSON envelope of the tool."""
    root = _tree(tmp_path, [_case(1, "The payment TX-9001 was captured.", [_envelope()])])
    seen = _session(tool, root, ["supported", "the ledger says so"])

    assert "id: TX-9001; status: captured." in seen
    assert '"columns"' not in seen
    assert '"rows"' not in seen
    assert "SELECT id, status FROM" not in seen


def test_the_case_without_evidence_is_shown_and_is_not_an_error(tool, tmp_path: Path) -> None:
    """The case with no evidence at all is a case of the set: it is shown, and it is not skipped."""
    root = _tree(
        tmp_path,
        [_case(1, "A claim that cites nothing at all."), _case(2, "The payment TX-9001 was captured.", [_envelope()])],
    )
    seen = _session(tool, root, ["not_enough_evidence", "there is no evidence", "supported", "the ledger says so"])

    assert "(no evidence)" in seen
    records = _labels(root)
    assert [record["id"] for record in records] == ["ho-001", "ho-002"]
    assert records[0]["label"] == "not_enough_evidence"


# ---- the session resumes -----------------------------------------------------------------------------


def test_an_interrupted_session_resumes_where_it_stopped(tool, tmp_path: Path) -> None:
    """A session that stops after two cases asks nothing about them again."""
    root = _tree(tmp_path, _three_cases())
    _session(tool, root, ["supported", "one", "contradicted", "two"])
    assert len(_labels(root)) == 2

    resumed = _session(tool, root, ["not_enough_evidence", "three"])

    assert "ho-001" not in resumed
    assert "ho-002" not in resumed
    assert "ho-003" in resumed
    assert "The payment TX-9001 was captured." not in resumed
    assert len(_labels(root)) == 3


# ---- the labels file ---------------------------------------------------------------------------------


def test_the_labels_file_holds_the_label_and_the_note_and_no_recipe(tool, tmp_path: Path) -> None:
    """The labels file carries what the reader said and nothing of the recipe."""
    root = _tree(tmp_path, [_case(1, "The payment TX-9001 was captured.", [_envelope()])], [_recipe(1, "contradicted")])
    _session(tool, root, ["supported", "the ledger says the payment was captured"])

    records = _labels(root)
    assert records == [{"id": "ho-001", "label": "supported", "note": "the ledger says the payment was captured"}]
    text = (root / "data" / "eval" / "heldout" / "labels_v1.jsonl").read_text(encoding="utf-8")
    assert TEMPLATE_MARKER not in text
    assert "expected_label" not in text


# ---- the report of the disagreements -------------------------------------------------------------------


def test_the_report_prints_the_disagreements_and_their_count(tool, tmp_path: Path) -> None:
    """The report names the cases where the reader disagreed with the recipe, and counts them."""
    root = _tree(
        tmp_path,
        _three_cases(),
        [_recipe(1, "contradicted"), _recipe(2, "supported"), _recipe(3, "supported")],
    )
    _session(tool, root, ["supported", "one", "supported", "two", "supported", "three"])

    out = io.StringIO()
    tool.report_session(root, out)
    text = out.getvalue()

    assert "ho-001" in text
    assert "Disagreements: 1 of 3." in text


def test_the_report_counts_zero_when_the_reading_agrees_with_every_recipe(tool, tmp_path: Path) -> None:
    """A reading with no disagreement says so, and says the count of zero."""
    root = _tree(tmp_path, _three_cases(), [_recipe(index, "supported") for index in (1, 2, 3)])
    _session(tool, root, ["supported", "one", "supported", "two", "supported", "three"])

    out = io.StringIO()
    tool.report_session(root, out)
    text = out.getvalue()

    assert "Disagreements: 0 of 3." in text


def test_the_report_reads_a_recipe_whose_field_names_are_the_ones_of_the_other_specialist(tool, tmp_path: Path) -> None:
    """The report finds the disagreement of a recipe that names its fields in another way."""
    recipes = [
        {
            "id": "ho-001",
            "template_name": TEMPLATE_MARKER,
            "label": "contradicted",
            "pair": PAIR_MARKER,
            "fact": FACT_MARKER,
        }
    ]
    root = _tree(tmp_path, [_case(1, "The payment TX-9001 was captured.", [_envelope()])], recipes)
    _session(tool, root, ["supported", "the ledger says so"])

    out = io.StringIO()
    tool.report_session(root, out)

    assert "Disagreements: 1 of 1." in out.getvalue()


def test_the_report_writes_the_note_of_the_disagreement_into_the_labelled_set(tool, tmp_path: Path) -> None:
    """The note of a disagreement is on the record, in the labelled set."""
    root = _tree(tmp_path, [_case(1, "The payment TX-9001 was captured.", [_envelope()])], [_recipe(1, "contradicted")])
    _session(tool, root, ["supported", "the ledger says the payment was captured"])

    out = io.StringIO()
    tool.report_session(root, out)

    path = root / "data" / "eval" / "verification_heldout.jsonl"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(records) == 1
    note = records[0]["note"]
    assert "the ledger says the payment was captured" in note
    assert "disagrees with the recipe" in note


# ---- the build ---------------------------------------------------------------------------------------


def test_the_build_keeps_the_label_of_the_reader(tool, tmp_path: Path) -> None:
    """The line carries the label the reader gave, even when the recipe expected another one."""
    root = _tree(tmp_path, [_case(1, "The payment TX-9001 was captured.", [_envelope()])], [_recipe(1, "contradicted")])
    _session(tool, root, ["supported", "the ledger says the payment was captured"])

    path = tool.build_labelled_set(root)
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert len(records) == 1
    record = records[0]
    assert record["id"] == "ho-001"
    assert record["claim"] == "The payment TX-9001 was captured."
    assert record["evidence_ids"] == ["sql:1"]
    assert record["evidence"][0]["id"] == "sql:1"
    assert record["label"] == "supported"
    assert record["origin"] == tool.ORIGIN
    assert "the ledger says the payment was captured" in record["note"]


def test_the_build_refuses_an_incomplete_session_with_a_plain_sentence(tool, tmp_path: Path) -> None:
    """The build refuses, and it says how many cases are missing and which ones."""
    root = _tree(tmp_path, _three_cases())
    _session(tool, root, ["supported", "one"])

    with pytest.raises(tool.HeldoutIncompleteError) as failure:
        tool.build_labelled_set(root)

    message = str(failure.value)
    assert "2" in message
    assert "ho-002" in message
    assert "ho-003" in message


def test_the_command_line_prints_the_refusal_and_no_traceback(tool, tmp_path: Path, capsys) -> None:
    """The command line turns the refusal into a sentence and a non zero exit code."""
    root = _tree(tmp_path, _three_cases())
    _session(tool, root, ["supported", "one"])

    code = tool.main(["build", "--root", str(root)])
    captured = capsys.readouterr()

    assert code == 1
    assert "Traceback" not in captured.err
    assert "ho-002" in captured.err


# ---- the malformed line -------------------------------------------------------------------------------


def test_a_malformed_line_is_a_sentence_that_names_the_file_and_the_line(tool, tmp_path: Path) -> None:
    """A line that is not JSON is a data problem of the file, and never a traceback."""
    path = tmp_path / "data" / "eval" / "heldout" / "cases.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_case(1, "a claim")) + "\n" + "{not json}\n", encoding="utf-8")

    with pytest.raises(tool.HeldoutDataError) as failure:
        tool.load_cases(tmp_path)

    message = str(failure.value)
    assert "cases.jsonl" in message
    assert "2" in message
    assert isinstance(failure.value, tool.HeldoutError)


def test_the_error_of_a_bad_line_survives_the_command_line(tool, tmp_path: Path, capsys) -> None:
    """The command line prints the sentence of the malformed line and exits with a non zero code."""
    path = tmp_path / "data" / "eval" / "heldout" / "cases.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json}\n", encoding="utf-8")

    code = tool.main(["read", "--root", str(tmp_path)])
    captured = capsys.readouterr()

    assert code == 1
    assert "Traceback" not in captured.err
    assert "cases.jsonl" in captured.err
