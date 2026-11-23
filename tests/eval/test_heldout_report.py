"""The published measurement of the held out set: the aggregate, the predictions and what is not published.

Why it exists: the number over the held out set is the only number of this repository that is not a measurement of the
fit, and a number nobody can check is a number nobody can trust. The report of the measurement was published in
Markdown, which a reader can read but not compute with, and the file that holds the answer key of the generator is not
published, so the reader cannot run the measurement either. The machine readable report of the measurement answers
that: it carries the aggregate, the predictions of the model and the identifiers of the cases where the reading
disagreed with the recipes, and it carries no expected label of any case, because the expected label of a case is the
answer key and the set has to stay reserved for the changes that come after.

These tests read the published files and the manifest of the datasets, and they prove three things: that the two
reports agree, that the published report carries no expected label, and that the guard of the tuning refuses the
published report as a tuning target. The last one is red until the reservation of the guard names the published
report, and the refusal it waits for is the one of the reserved path and the one of the reserved digest.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

import pytest

from ledgerlens.eval.manifest import (
    HELD_OUT_RESERVED_DIGESTS,
    EvalDatasetManifest,
    TuningRefusal,
    require_tuning_path,
)

ROOT = Path(__file__).resolve().parents[2]
REPORT_JSON_PATH = ROOT / "data" / "eval" / "report_heldout.json"
REPORT_MARKDOWN_PATH = ROOT / "data" / "eval" / "report_heldout.md"
MANIFEST_PATH = ROOT / "data" / "eval" / "datasets.json"
LABELLED_PATH = "data/eval/verification_heldout.jsonl"

# The keys that may carry a label in the published report: the label the model predicted and the vocabulary of the
# matrix. Any other key that names a label is a leak of the truth of a case.
ALLOWED_LABEL_KEYS = {"predicted_label", "labels"}

# The names that would carry the expected label of a case, in any spelling.
FORBIDDEN_KEYS = {
    "answer_key",
    "expected",
    "expected_label",
    "expected_labels",
    "gold",
    "gold_label",
    "label",
    "labels_of_the_cases",
    "recipe",
    "recipe_label",
    "recipes",
    "reader_label",
    "adjudicated_label",
    "truth",
}

__all__ = [
    "test_the_identifiers_of_the_two_cases_where_the_reading_disagreed_are_published_without_a_label",
    "test_the_limitations_of_the_number_come_from_the_manifest_in_both_reports",
    "test_the_published_json_agrees_with_the_markdown_report",
    "test_the_published_json_carries_no_expected_label",
    "test_the_published_json_names_the_dataset_the_denominator_and_the_pinned_weights",
    "test_the_published_report_is_refused_as_a_tuning_target",
    "test_the_published_report_is_refused_under_another_name",
]


def _published() -> dict:
    """The published report of the measurement, read from the disk."""
    assert REPORT_JSON_PATH.exists(), (
        f"The file {REPORT_JSON_PATH} does not exist: the measurement writes it, and a published number that a "
        f"reader cannot read is not a published number."
    )
    return json.loads(REPORT_JSON_PATH.read_text(encoding="utf-8"))


def _markdown() -> str:
    """The Markdown report of the measurement, read from the disk."""
    assert REPORT_MARKDOWN_PATH.exists(), f"The file {REPORT_MARKDOWN_PATH} does not exist."
    return REPORT_MARKDOWN_PATH.read_text(encoding="utf-8")


def _manifest_entry() -> dict:
    """The entry of the manifest that declares the held out set."""
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    entries = [entry for entry in payload["datasets"] if entry["path"] == LABELLED_PATH]
    assert len(entries) == 1, f"the manifest does not declare {LABELLED_PATH} exactly once"
    return entries[0]


def _section(markdown: str, title: str) -> str:
    """The text of a section of the Markdown report, without the title and without the next one."""
    pattern = re.compile(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)
    found = pattern.search(markdown)
    assert found is not None, f"The report has no section '{title}'."
    return found.group(1)


def _cells(row: str) -> list[str]:
    """The cells of a row of a Markdown table, with the escaped bars kept inside their cell."""
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", row.strip())][1:-1]


def _rows(section: str) -> list[list[str]]:
    """The rows of the table of a section, without the header and without the separator."""
    rows = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = _cells(stripped)
        if set(cells[0]) <= {"-"}:
            continue
        rows.append(cells)
    return rows[1:]


def test_the_published_json_names_the_dataset_the_denominator_and_the_pinned_weights() -> None:
    """The report says which set it is, over how many cases, and with which weights.

    Why it matters: a number over a set is honest only when its denominator is known, and a number that does not name
    the weights is a number of a moving target. The role `held_out` says what the number may claim.
    """
    published = _published()
    entry = _manifest_entry()

    assert published["dataset"]["dataset_id"] == entry["dataset_id"]
    assert published["dataset"]["path"] == entry["path"]
    assert published["dataset"]["split_role"] == entry["split_role"] == "held_out"
    assert published["dataset"]["cases"] == entry["records_count"] == 48
    assert published["dataset"]["denominator"] == 48

    thresholds = json.loads((ROOT / "ledgerlens" / "verify" / "thresholds.json").read_text(encoding="utf-8"))
    recorded = thresholds["calibration"]["nli_model"]
    assert published["model"]["name"] == recorded["model"]
    assert published["model"]["revision"] == recorded["revision"], (
        "the report does not name the revision of the weights that produced it, and a measurement of one day is not "
        "the measurement of another day"
    )


def test_the_published_json_agrees_with_the_markdown_report() -> None:
    """The two reports of the measurement carry the same numbers, and a reader can check one against the other.

    Why it matters: the Markdown is what a person reads and the JSON is what a program reads. A number that is only in
    one of them is a number that a reader of the repository cannot check, and the point of publishing the aggregate is
    that it can be checked.
    """
    published = _published()
    markdown = _markdown()

    accuracy = re.search(r"- over the set: (\d+)/(\d+) \(([0-9.]+)\)", _section(markdown, "Accuracy"))
    assert accuracy is not None
    assert published["accuracy"]["correct"] == int(accuracy.group(1))
    assert published["accuracy"]["cases"] == int(accuracy.group(2))
    assert published["accuracy"]["value"] == accuracy.group(3)

    model = re.search(r"- over the cases the model judged: (\d+)/(\d+) \(([0-9.]+)\)", _section(markdown, "Accuracy"))
    assert model is not None
    assert published["accuracy_of_the_model_cases"]["correct"] == int(model.group(1))
    assert published["accuracy_of_the_model_cases"]["cases"] == int(model.group(2))
    assert published["accuracy_of_the_model_cases"]["value"] == model.group(3)

    code = re.search(r"- decided by the code, without the model: (\d+)", _section(markdown, "Accuracy"))
    assert code is not None
    assert published["cases_decided_by_the_code"] == int(code.group(1))

    matrix = _rows(_section(markdown, "The confusion matrix"))
    header = _cells(
        "| the reader \\ the verifier | " + " | ".join(published["confusion_matrix"]["labels"]) + " | total |"
    )
    labels = published["confusion_matrix"]["labels"]
    assert header[1:-1] == labels
    for row in matrix:
        if row[0] == "total":
            for index, label in enumerate(labels):
                assert published["counts"]["verifier"][label] == int(row[1 + index])
            continue
        counts = published["confusion_matrix"]["counts"][row[0]]
        for index, label in enumerate(labels):
            assert counts[label] == int(row[1 + index])
        assert published["counts"]["reader"][row[0]] == int(row[-1])

    templates = _rows(_section(markdown, "The table by template"))
    assert len(templates) == len(published["by_template"])
    for row, published_row in zip(templates, published["by_template"], strict=True):
        assert published_row["template"] == row[0]
        assert published_row["cases"] == int(row[1])
        for index, label in enumerate(labels):
            assert published_row["reader_counts"][label] == int(row[2 + index])
        assert published_row["right"] == int(row[-1])

    predictions = {case["id"]: case["predicted_label"] for case in published["cases"]}
    assert len(predictions) == published["dataset"]["cases"]
    for row in _rows(_section(markdown, "The cases")):
        assert predictions[row[0]] == row[3], f"the report of the case {row[0]} says another label"

    disagreement = re.search(
        r"the reading disagrees with the recipe of (\d+) case\(s\) of (\d+): ([a-z0-9,\- ]*)",
        _section(markdown, "The reader and the recipes"),
    )
    assert disagreement is not None
    assert published["reading_against_the_recipes"]["count"] == int(disagreement.group(1))
    assert published["dataset"]["cases"] == int(disagreement.group(2))
    identifiers = [name.strip() for name in disagreement.group(3).split(",") if name.strip()]
    assert published["reading_against_the_recipes"]["case_ids"] == identifiers


def test_the_published_json_carries_no_expected_label() -> None:
    """The published report carries the label the model predicted and never the label the case expects.

    Why it matters: the expected label of a case is the answer key of the generator, and a published key ends the
    reservation of the set for every change that comes after. A hash would publish it just as badly: there are only
    three labels, so a hash of the expected label is brute forceable in three tries.
    """
    published = _published()

    def walk(node: object, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                where = f"{path}.{key}" if path else key
                assert key.lower() not in FORBIDDEN_KEYS, f"the published report carries the field '{where}'"
                if "label" in key.lower():
                    assert key in ALLOWED_LABEL_KEYS, f"the published report carries the field '{where}'"
                walk(value, where)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")

    walk(published, "")

    for case in published["cases"]:
        assert set(case) == {"id", "predicted_label", "method"}, (
            f"the published record of the case {case.get('id')} carries more than the prediction of the model"
        )


def test_the_identifiers_of_the_two_cases_where_the_reading_disagreed_are_published_without_a_label() -> None:
    """The two cases where the reading disagreed with the recipes are named, and their labels are not.

    Why it matters: the count of the disagreement is the noise a label of this set carries, and a reader has to be
    able to see which cases carry it. The label of the reading and the label of the recipe are the truth of the case,
    and the truth of the case is not published.
    """
    published = _published()
    reading = published["reading_against_the_recipes"]

    assert reading["count"] == 2
    assert reading["case_ids"] == ["ho-002", "ho-013"]

    published_ids = {case["id"] for case in published["cases"]}
    assert set(reading["case_ids"]) <= published_ids
    for case in published["cases"]:
        if case["id"] in reading["case_ids"]:
            assert set(case) == {"id", "predicted_label", "method"}, (
                f"the published record of the case {case['id']} carries a label of the case that is not a prediction"
            )


def test_the_limitations_of_the_number_come_from_the_manifest_in_both_reports() -> None:
    """Both reports carry the sentences that qualify the number, and they take them from the same place.

    Why it matters: the sentences that limit a number live in the manifest of the datasets, and a report that copies
    them by hand drifts from them. The two reports read the manifest, so the qualification of the number is the same
    in both of them and in the manifest.
    """
    published = _published()
    entry = _manifest_entry()
    markdown = _markdown()

    assert published["limitations"]["contamination_policy"] == entry["contamination_policy"]
    assert published["limitations"]["caveat"] == entry["notes"]

    section = _section(markdown, "The limitations of this number")
    assert entry["contamination_policy"] in section
    assert entry["notes"] in section


def _tuning_entry(path: str, sha256: str) -> EvalDatasetManifest:
    """An entry of the manifest that declares the published report with the role `tuning`, as a bypass would."""
    return EvalDatasetManifest(
        dataset_id="report_heldout",
        path=path,
        sha256=sha256,
        records_count=48,
        source="The predictions of the measurement of the held out set.",
        labeling_version="v1",
        split_role="tuning",
        scenario_seed=None,
        contamination_policy="A tuning script reads only the datasets whose split_role is 'tuning'.",
        notes="",
    )


def test_the_published_report_is_refused_as_a_tuning_target() -> None:
    """The guard of the tuning refuses the published report, whatever role the manifest gives it.

    Why it matters: the published report carries the predictions of the model over the cases of the held out set, and
    a script that tunes a threshold against the predictions is tuning against the held out set. The reservation lives
    in the code of the guard, because the role of an entry is a line of JSON that a hand edit changes.

    This test is red until the reservation of the guard names the published report.
    """
    published = _published()
    assert published["dataset"]["cases"] == 48

    digest = hashlib.sha256(REPORT_JSON_PATH.read_bytes()).hexdigest()
    entry = _tuning_entry("data/eval/report_heldout.json", digest)

    with pytest.raises(TuningRefusal) as caught:
        require_tuning_path("data/eval/report_heldout.json", [entry], root=ROOT)

    message = str(caught.value)
    assert "reserved for the held out set" in message, (
        f"the published report of the measurement was refused by another door than the reservation: {message}"
    )


def test_the_published_report_is_refused_under_another_name(tmp_path: Path) -> None:
    """A copy of the published report under another name is refused too.

    Why it matters: a path names a file and a copy of the file under another name has another path, so a reservation
    by the path alone stops at the name. The bytes of the published report are the same under any name, and the digest
    is what the guard compares with the file on the disk.

    This test is red until the reservation of the guard holds the digest of the published report.
    """
    digest = hashlib.sha256(REPORT_JSON_PATH.read_bytes()).hexdigest()
    assert digest in HELD_OUT_RESERVED_DIGESTS, (
        "the digest of the published report is not reserved, so a copy of it under another name may be tuned against"
    )

    copy = tmp_path / "data" / "eval" / "my_report.json"
    copy.parent.mkdir(parents=True)
    shutil.copyfile(REPORT_JSON_PATH, copy)
    entry = _tuning_entry("data/eval/my_report.json", digest)

    with pytest.raises(TuningRefusal) as caught:
        require_tuning_path("data/eval/my_report.json", [entry], root=tmp_path)

    message = str(caught.value)
    assert "held out set" in message, f"the copy of the published report was refused by another door: {message}"
