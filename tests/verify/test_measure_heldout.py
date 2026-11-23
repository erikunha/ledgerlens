"""The measurement of the verifier over the held out set of the verification.

Why this file exists: the number this script publishes is the first one of the repository that is measured over data
no decision was taken against, and such a number is only worth reading when the test says where it comes from. The
test builds a set of three cases with an answer known in advance, it injects a predictor of its own so the model is
never downloaded and no key is ever needed, and it checks every part of the report: the denominators of the
accuracies, the false supported, the case that the code decides and the model never sees, the refusals, the line
that names the model and the table by template.

Every fixture is written under `tmp_path` and no test writes a file outside it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from measure_heldout import (  # noqa: E402  (the path is set up before the import)
    MeasureRefusal,
    main,
    measure_heldout,
    model_name,
    render_report,
    select_nli,
)

LABELS = ("supported", "contradicted", "not_enough_evidence")


class FakeNli:
    """A predictor of fixed scores, so the test never downloads the model."""

    def __init__(self, entailment: float = 0.9, contradiction: float = 0.05) -> None:
        self.scores = {
            "entailment": entailment,
            "neutral": round(1 - entailment - contradiction, 6),
            "contradiction": contradiction,
        }
        self.calls: list[tuple[str, str]] = []

    def predict(self, premise: str, hypothesis: str) -> dict[str, float]:
        self.calls.append((premise, hypothesis))
        return dict(self.scores)


def _case(case_id: str, claim: str, label: str, *, with_evidence: bool = True, note: str = "") -> dict:
    """One line of the labelled file, in the shape the reading session builds."""
    evidence = (
        [{"id": "sql:1", "content": f"ledger/chargebacks | {case_id} | transaction TX-1 | stage won"}]
        if with_evidence
        else []
    )
    return {
        "id": case_id,
        "claim": claim,
        "evidence_ids": ["sql:1"] if with_evidence else [],
        "evidence": evidence,
        "label": label,
        "origin": "held out: blind reading v1 by one reader, ADR-053",
        "note": note,
    }


def _recipe(case_id: str, template: str, label: str) -> dict:
    """One line of the recipes of the generator, the private input of the report."""
    return {"id": case_id, "template": template, "label": label, "pair_id": "hp-01"}


def _write_jsonl(path: Path, records: list[dict]) -> Path:
    """The records of a file, one per line."""
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    return path


@pytest.fixture
def three_cases(tmp_path):
    """A set of three cases with an answer known in advance, written under tmp_path.

    The first case is supported and the second is contradicted, and the fake predictor supports both, so the second
    is a false supported. The third cites no evidence at all: the verifier decides it by code.
    """
    labelled = _write_jsonl(
        tmp_path / "verification_heldout.jsonl",
        [
            _case("ho-001", "The dispute CB-0005 was in stage won.", "supported"),
            _case(
                "ho-002",
                "The dispute CB-0005 was in stage lost.",
                "contradicted",
                note="the evidence says the stage is won",
            ),
            _case("ho-003", "The dispute CB-0009 was in stage lost.", "not_enough_evidence", with_evidence=False),
        ],
    )
    recipes = _write_jsonl(
        tmp_path / "recipes.jsonl",
        [
            _recipe("ho-001", "range_shape", "supported"),
            _recipe("ho-002", "range_shape", "contradicted"),
            _recipe("ho-003", "hedge_shape", "not_enough_evidence"),
        ],
    )
    return labelled, recipes


def test_the_accuracy_comes_with_its_denominator(three_cases):
    """The accuracy over the set and the accuracy over the cases the model judged both name their denominator."""
    labelled, recipes = three_cases
    measurement = measure_heldout(labelled, recipes, nli=FakeNli())

    assert measurement.total == 3
    assert measurement.correct == 2
    assert measurement.model_total == 2
    assert measurement.model_correct == 1

    report = render_report(measurement, model=model_name(FakeNli()))
    assert "over the set: 2/3" in report
    assert "over the cases the model judged: 1/2" in report
    assert "2/3" in report and "1/2" in report


def test_the_false_supported_is_counted_and_not_hidden(three_cases):
    """The false supported is the costly error, so it is in the report and not folded into another number."""
    labelled, recipes = three_cases
    measurement = measure_heldout(labelled, recipes, nli=FakeNli())

    assert measurement.false_supported == 1
    assert measurement.false_contradicted == 0

    report = render_report(measurement, model=model_name(FakeNli()))
    assert "the false supported: 1" in report


def test_the_case_without_evidence_is_decided_by_code(three_cases):
    """The case that cites no evidence is decided by the code and the model never sees it."""
    labelled, recipes = three_cases
    nli = FakeNli()
    measurement = measure_heldout(labelled, recipes, nli=nli)

    outcome = next(item for item in measurement.cases if item.case_id == "ho-003")
    assert outcome.method == "none"
    assert outcome.verdict_label == "not_enough_evidence"
    assert outcome.correct is True
    assert measurement.code_total == 1
    assert [hypothesis for _premise, hypothesis in nli.calls] == [
        "The dispute CB-0005 was in stage won.",
        "The dispute CB-0005 was in stage lost.",
    ]


def test_the_refusal_over_a_missing_file(tmp_path):
    """A file that does not exist is a sentence and never a traceback."""
    with pytest.raises(MeasureRefusal) as error:
        measure_heldout(tmp_path / "missing.jsonl", tmp_path / "recipes.jsonl", nli=FakeNli())

    assert "does not exist" in str(error.value)


def test_the_refusal_over_an_incomplete_reading(tmp_path):
    """A reading that left a case out is refused, and the refusal names the case that is missing."""
    labelled = _write_jsonl(
        tmp_path / "verification_heldout.jsonl",
        [_case("ho-001", "The dispute CB-0005 was in stage won.", "supported")],
    )
    recipes = _write_jsonl(
        tmp_path / "recipes.jsonl",
        [
            _recipe("ho-001", "range_shape", "supported"),
            _recipe("ho-002", "range_shape", "contradicted"),
        ],
    )

    with pytest.raises(MeasureRefusal) as error:
        measure_heldout(labelled, recipes, nli=FakeNli())

    assert "ho-002" in str(error.value)
    assert "not complete" in str(error.value)


def test_the_report_names_the_model_and_the_thresholds(three_cases):
    """A number without the model that produced it is not a number of this repository."""
    labelled, recipes = three_cases
    nli = FakeNli()
    measurement = measure_heldout(labelled, recipes, nli=nli)

    report = render_report(measurement, model=model_name(nli))

    assert "the model that produced the verdicts" in report
    assert "FakeNli" in report
    assert "entailment_min 0.81" in report
    assert "contradiction_min 0.91" in report


def test_the_table_by_template(three_cases):
    """The table by template holds the cases, the labels of the reader and the cases the verifier got right."""
    labelled, recipes = three_cases
    measurement = measure_heldout(labelled, recipes, nli=FakeNli())

    rows = {row.template: row for row in measurement.by_template}
    assert rows["range_shape"].total == 2
    assert rows["range_shape"].reader_counts["supported"] == 1
    assert rows["range_shape"].reader_counts["contradicted"] == 1
    assert rows["range_shape"].reader_counts["not_enough_evidence"] == 0
    assert rows["range_shape"].correct == 1
    assert rows["hedge_shape"].total == 1
    assert rows["hedge_shape"].correct == 1

    report = render_report(measurement, model=model_name(FakeNli()))
    assert "range_shape" in report
    assert "hedge_shape" in report


def test_the_disagreements_of_the_reader_with_the_generator(tmp_path):
    """The count of the disagreements between the reading and the recipes is the noise of a label."""
    labelled = _write_jsonl(
        tmp_path / "verification_heldout.jsonl",
        [_case("ho-001", "The dispute CB-0005 was in stage won.", "supported")],
    )
    recipes = _write_jsonl(tmp_path / "recipes.jsonl", [_recipe("ho-001", "range_shape", "contradicted")])

    measurement = measure_heldout(labelled, recipes, nli=FakeNli())

    assert measurement.disagreements == 1
    assert measurement.disagreement_ids == ("ho-001",)


def test_the_per_case_list_carries_the_note_of_the_wrong_cases(three_cases):
    """The per case list is the part a reader uses to disagree with the number, so it carries the note."""
    labelled, recipes = three_cases
    measurement = measure_heldout(labelled, recipes, nli=FakeNli())

    report = render_report(measurement, model=model_name(FakeNli()))

    assert "ho-001" in report
    assert "ho-002" in report
    assert "the evidence says the stage is won" in report


def test_the_stub_is_named_when_it_is_used():
    """A number measured with the stand-in of the rules says so."""
    nli = select_nli("stub")

    assert "StubNli" in model_name(nli)
    assert "not the model" in model_name(nli)


def test_the_refusal_when_the_real_model_is_asked_for_and_only_the_stub_is_there():
    """The caller that insists on the real model is not given the stand-in, and is told why."""
    with pytest.raises(MeasureRefusal) as error:
        select_nli("real")

    assert "offline" in str(error.value)
    assert "stand-in" in str(error.value)


def test_the_refusal_when_the_extra_of_the_real_model_is_not_installed(monkeypatch):
    """The caller that insists on the real model is told that the extra is not there."""

    def missing(*_args, **_kwargs):
        raise RuntimeError("the real NLI model needs `transformers` and `torch`")

    monkeypatch.setattr(sys.modules["measure_heldout"], "offline_mode", lambda: False)
    monkeypatch.setattr(sys.modules["measure_heldout"], "get_nli", missing)

    with pytest.raises(MeasureRefusal) as error:
        select_nli("real")

    assert "transformers" in str(error.value)


def test_the_command_prints_the_report_and_writes_it_as_markdown(three_cases, tmp_path, capsys):
    """The command prints the report and writes the same report as Markdown when it is asked to."""
    labelled, recipes = three_cases
    out = tmp_path / "report.md"

    code = main(
        [
            "--labelled",
            str(labelled),
            "--recipes",
            str(recipes),
            "--model",
            "stub",
            "--out",
            str(out),
        ]
    )

    printed = capsys.readouterr().out
    assert code == 0
    assert "the model that produced the verdicts" in printed
    assert out.exists()
    assert "the model that produced the verdicts" in out.read_text(encoding="utf-8")


def test_the_command_refuses_a_missing_file_with_a_code_that_is_not_zero(tmp_path, capsys):
    """The refusal of the command is a sentence on the error output and a code that is not zero."""
    code = main(
        [
            "--labelled",
            str(tmp_path / "missing.jsonl"),
            "--recipes",
            str(tmp_path / "recipes.jsonl"),
            "--model",
            "stub",
        ]
    )

    captured = capsys.readouterr()
    assert code != 0
    assert "does not exist" in captured.err
    assert "Traceback" not in captured.err
