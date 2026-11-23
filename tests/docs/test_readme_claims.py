"""The published documents carry claims that the files of the repository can check.

Why it exists: three sentences of the published documents were false, and a false sentence in a published document is
worse than an admission of a gap. The first one put the number of a metric of the README under the wrong header of
the table, the second one counted the datasets of the manifest wrong in the readiness audit, and the third one said
that three releases of the roadmap were pending when the tasks of their specifications are all checked. A correction
that decays is a correction that is not a correction, so the three claims are read from the files that hold the truth
and compared here, and the comparison runs in the gate.

What it guarantees: the trajectory column of the results table of the two READMEs carries the value that the report
publishes under the column the header of the table names, the count of the datasets of every role in the readiness
audit is the count of the manifest, and no row of the roadmap of a release says that the release is pending when the
tasks of its specification are all checked.

What it does not do: it writes nothing, and it reads nothing but the files of the repository, so it runs offline and
in the first seconds of a checkout.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
README_PT = ROOT / "README.pt-BR.md"
REPORT = ROOT / "data" / "eval" / "report_online.md"
DATASETS = ROOT / "data" / "eval" / "datasets.json"
READINESS = ROOT / "docs" / "readiness-2027.md"
ROADMAP = ROOT / "docs" / "roadmap-v3.md"
ROADMAP_PT = ROOT / "docs" / "pt-BR" / "roadmap-v3.md"

# The words of the two languages that name a kind of trajectory, and the word of the report that carries it.
# Why the translation lives here: the report names its metrics with the name of the evaluator and the README names
# them in prose, so the header of the table is translated into the words of the report and the one column that
# carries every one of them is the column the README says it publishes.
TRAJECTORY_WORDS = {
    "en": {"equivalent": "equivalent", "unordered": "unordered", "strict": "strict"},
    "pt": {"equivalente": "equivalent", "sem ordem": "unordered", "estrito": "strict"},
}

# The words of the two languages that name the column of the trajectory in the header of the table.
TRAJECTORY_HEADER = {"en": "traject", "pt": "trajet"}

# The words of the two languages that say a release is waiting.
PENDING_WORDS = {"pending", "pendente"}

# The number words of the sentences of the audit that count the datasets of a role.
NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}

# A cell of a table of numbers: the mean, and the interval when the cell carries one.
_CELL = re.compile(r"^([0-9]+(?:\.[0-9]+)?)(?:\s*\[([0-9]+(?:\.[0-9]+)?),\s*([0-9]+(?:\.[0-9]+)?)\])?$")

# A row of a table of the roadmap, and the folder of the specification it names.
_ROADMAP_ROW = re.compile(r"^\|\s*(LL-V3-R\d-\d+)\s*\|")
_SPEC_FOLDER = re.compile(r"specs/(\d{3}-[a-z0-9-]+)/")

# A task of a specification, checked or not.
_CHECKED = re.compile(r"^\s*-\s*\[x\]", re.IGNORECASE)
_UNCHECKED = re.compile(r"^\s*-\s*\[ \]")

# The claim of the audit that counts the datasets of a role, and the number word that carries the count.
# Why the verb of the pattern carries two forms: "carry" and "carries" are the ways the sentence can say it, and
# a pattern that only knows "carry" cannot count a claim about a single dataset, because the only grammatical
# form of that sentence says "carries".
_ROLE_CLAIM = re.compile(
    r"(\w+)\s+(?:datasets?\s+)?carr(?:y|ies)\s+the\s+role\s+`(tuning|held_out)`",
)


@pytest.fixture(scope="module")
def report() -> tuple[list[str], dict[str, list[str]]]:
    """The header and the rows of the table of the scores of the report, by variant."""
    return _table(REPORT.read_text(encoding="utf-8"), "| Variant | correctness |")


@pytest.fixture(scope="module")
def manifest() -> dict[str, int]:
    """The count of the datasets of the manifest, by the role each one carries."""
    data = json.loads(DATASETS.read_text(encoding="utf-8"))
    counts: dict[str, int] = {}
    for dataset in data["datasets"]:
        role = dataset["split_role"]
        counts[role] = counts.get(role, 0) + 1
    return counts


def _table(text: str, header: str) -> tuple[list[str], dict[str, list[str]]]:
    """The header of a Markdown table and its rows, keyed by the first letter of the variant.

    Why the rows are keyed by one letter: the report names a variant "B: ReAct agent (legacy_react)" and the README
    names the same variant "B: ReAct agent", so the letter is the one thing the two documents share.
    """
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not line.startswith(header):
            continue
        headers = _cells(line)
        rows: dict[str, list[str]] = {}
        for candidate in lines[index + 1 :]:
            if not candidate.startswith("|"):
                break
            cells = _cells(candidate)
            if set("".join(cells)) <= {"-", " "}:
                continue
            rows[cells[0].split(":")[0].strip()] = cells
        return headers, rows
    raise AssertionError(f"the table that starts with {header!r} is not in the document")


def _cells(line: str) -> list[str]:
    """The cells of a row of a Markdown table, without the pipes and without the spaces around them."""
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _value(cell: str) -> tuple[Decimal, tuple[Decimal, Decimal] | None]:
    """The mean of a cell of numbers and the interval of the cell, when it carries one.

    Why the interval is optional: the README writes the interval only when it says something the mean does not, and
    a cell that carries no interval says the mean.
    """
    found = _CELL.match(cell.strip())
    if found is None:
        raise AssertionError(f"the cell {cell!r} is not a number")
    mean = Decimal(found.group(1))
    if found.group(2) is None:
        return mean, None
    return mean, (Decimal(found.group(2)), Decimal(found.group(3)))


def _trajectory_column(headers: list[str], language: str) -> tuple[int, set[str]]:
    """The index of the column of the trajectory in a header and the kinds of trajectory it names.

    Why the kinds are returned and not only the index: the header is the claim of the document, and the test has to
    know which column of the report the claim names, or it would compare the numbers of two different metrics.
    """
    words = TRAJECTORY_WORDS[language]
    marker = TRAJECTORY_HEADER[language]
    for index, cell in enumerate(headers):
        lowered = cell.lower()
        if marker not in lowered:
            continue
        required = {value for word, value in words.items() if word in lowered}
        if required:
            return index, required
    raise AssertionError("the table has no column of the trajectory")


def _report_column(headers: list[str], required: set[str]) -> int:
    """The index of the column of the report that carries every kind of trajectory the README names."""
    found = [
        index
        for index, name in enumerate(headers)
        if name != "Variant" and all(kind in name for kind in required)
    ]
    if len(found) != 1:
        raise AssertionError(
            f"the kinds {sorted(required)} name {len(found)} columns of the report and the README names one of them"
        )
    return found[0]


def test_the_readme_carries_the_value_of_the_report_that_its_header_names(
    report: tuple[list[str], dict[str, list[str]]],
) -> None:
    """The results table of both READMEs carries the value of the report under the header the table names.

    Why the header matters: the report publishes the trajectory under several names, and the table of the README
    says which one it publishes. The cell of a variant is compared with the cell of the report under the column the
    header names, so a number that belongs to another metric of the report fails here.
    """
    report_headers, report_rows = report
    for path, language in ((README, "en"), (README_PT, "pt")):
        readme_headers, readme_rows = _table(
            path.read_text(encoding="utf-8"), "| Variant |" if language == "en" else "| Variante |"
        )
        index, required = _trajectory_column(readme_headers, language)
        column = _report_column(report_headers, required)
        for variant in ("A", "B", "C"):
            readme_mean, readme_interval = _value(readme_rows[variant][index])
            report_mean, report_interval = _value(report_rows[variant][column])
            assert readme_mean == report_mean, (
                f"{path.name} publishes {readme_mean} for the variant {variant} and the report publishes "
                f"{report_mean} under the column {report_headers[column]!r} that the header of the table names"
            )
            if readme_interval is not None:
                assert readme_interval == report_interval, (
                    f"{path.name} publishes the interval {readme_interval} for the variant {variant} and the report "
                    f"publishes {report_interval} under the column {report_headers[column]!r}"
                )


def test_the_audit_counts_the_datasets_of_the_manifest_as_the_manifest_counts_them(
    manifest: dict[str, int],
) -> None:
    """The readiness audit counts the datasets of every role the way the manifest counts them.

    Why the count is checked and not the sentence: the sentence of the audit is a claim about a number, and the
    number is in the manifest. A sentence that claims a count the manifest does not hold is a sentence that says
    something false about the repository.
    """
    text = READINESS.read_text(encoding="utf-8")
    claims = _ROLE_CLAIM.findall(text)
    assert claims, "the audit does not count the datasets of any role"
    for word, role in claims:
        count = NUMBER_WORDS.get(word.lower())
        assert count is not None, f"the audit counts the datasets of the role {role!r} with the word {word!r}"
        assert count == manifest[role], (
            f"the audit says that {count} datasets carry the role {role!r} and the manifest holds "
            f"{manifest[role]} of them"
        )
    for role in ("tuning", "held_out"):
        assert any(claimed == role for _, claimed in claims), (
            f"the audit does not count the datasets of the role {role!r}"
        )


def test_the_roadmap_does_not_wait_for_a_specification_whose_tasks_are_all_checked() -> None:
    """No row of the roadmap says that a release is pending when the tasks of its specification are all checked.

    Why the tasks and not the state of the row: a state that says "pending" over a specification whose tasks are all
    checked is a state that contradicts the specification, and the specification is the file a reader can check.
    """
    for path in (ROADMAP, ROADMAP_PT):
        for line in path.read_text(encoding="utf-8").splitlines():
            found = _ROADMAP_ROW.match(line)
            if found is None:
                continue
            cells = _cells(line)
            if cells[-1].strip().lower() not in PENDING_WORDS:
                continue
            folder = _SPEC_FOLDER.search(line)
            assert folder is not None, (
                f"{path.name} says that {found.group(1)} is pending and names no specification, so nothing can "
                "check the claim"
            )
            tasks = (ROOT / "specs" / folder.group(1) / "tasks.md").read_text(encoding="utf-8")
            checked = len(_CHECKED.findall(tasks))
            unchecked = len(_UNCHECKED.findall(tasks))
            assert unchecked > 0, (
                f"{path.name} says that {found.group(1)} is pending and every task of "
                f"{folder.group(1)} is checked ({checked} of them)"
            )
