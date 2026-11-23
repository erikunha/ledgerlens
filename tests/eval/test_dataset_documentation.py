"""The public numbers of the repository have to name the dataset they come from.

Why it exists: the milestone that pinned the eval datasets decided that a number without its dataset is a claim
about nothing in particular, and that a number without its restriction is a claim about more than the measurement
supports. The manifest and the check enforce the pin on the data; this file enforces it on the words, so that the
README and the canonical document of the numbers cannot drift away from the decision that wrote them.

What it guarantees: the README, in both languages, and `docs/verification_sets.md` name the dataset behind the
accuracy of the verifier and the dataset behind the correctness of the agent, they name the role of those datasets,
and the README says that the 43 case number is the whole verifier and not the accuracy of the NLI, which is measured
over 70 NLI cases. A number that was renamed without its dataset fails here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
README_PT = ROOT / "README.pt-BR.md"
VERIFICATION_SETS = ROOT / "docs" / "verification_sets.md"

# The decision that says what a role means and what may be done with a dataset.
ADR = "docs/decisions/ADR-052-the-manifest-of-the-eval-datasets.md"

# The dataset of the accuracy of the verifier and the dataset of the correctness of the agent.
VERIFICATION_DATASET = "data/eval/verification_set.jsonl"
EVALUATION_DATASET = "data/eval/eval_cases.jsonl"


@pytest.fixture(scope="module")
def readme() -> str:
    """The English README."""
    return README.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def readme_pt() -> str:
    """The Portuguese README, the translation of the English one."""
    return README_PT.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def verification_sets() -> str:
    """The canonical document of the numbers of the verifier."""
    return VERIFICATION_SETS.read_text(encoding="utf-8")


def _bullet(text: str, needle: str) -> str:
    """The line of the document that holds the needle, or a failure that says what is missing."""
    for line in text.splitlines():
        if needle in line:
            return line
    raise AssertionError(f"the document does not name {needle!r}")


def test_the_readme_names_the_dataset_of_the_accuracy_of_the_verifier(readme: str) -> None:
    """The 43 case number of the README names the file the 43 cases live in."""
    assert VERIFICATION_DATASET in readme


def test_the_readme_names_the_dataset_of_the_correctness_of_the_agent(readme: str) -> None:
    """The correctness of the three variants names the file the 30 cases live in."""
    assert EVALUATION_DATASET in readme


def test_the_readme_points_at_the_decision_that_says_what_a_role_means(readme: str) -> None:
    """The README points at the decision, so the reader can read what the restriction is."""
    assert ADR in readme


def test_the_readme_says_that_the_43_cases_are_the_whole_verifier(readme: str) -> None:
    """The 43 case number is the whole verifier, and the README says so next to it.

    The reason is that the two numbers are easy to confuse: the accuracy of the NLI of the calibration is measured
    over 70 NLI cases, while the number of the README is the whole verifier over the 43 records of the set. A
    reader who reads one as the other reads a number that is not there.
    """
    line = _bullet(readme, "43-case verification set")
    assert "70 NLI cases" in line
    assert "WHOLE verifier" in line


def test_the_readme_says_that_the_correctness_of_the_agent_is_a_measure_of_the_fit(readme: str) -> None:
    """The 30 cases of the evaluation are named as a tuning set, with the restriction."""
    line = _bullet(readme, EVALUATION_DATASET)
    assert "tuning set" in line
    assert "not a generalization to unseen data" in line


def test_the_two_readmes_name_the_same_datasets(readme: str, readme_pt: str) -> None:
    """The translation names the same datasets as the English one."""
    for dataset in (VERIFICATION_DATASET, EVALUATION_DATASET):
        assert dataset in readme_pt, f"the Portuguese README does not name {dataset}"
    assert ADR in readme_pt


def test_the_canonical_document_names_the_dataset_and_the_role(verification_sets: str) -> None:
    """The canonical document of the numbers names the datasets and their roles."""
    assert VERIFICATION_DATASET in verification_sets
    assert "tuning" in verification_sets
    # The document lives in `docs/`, so it links the decision with the path that is relative to it.
    assert "decisions/ADR-052-the-manifest-of-the-eval-datasets.md" in verification_sets


def test_the_canonical_document_names_the_denominator_of_every_accuracy(verification_sets: str) -> None:
    """Every accuracy of the document states the denominator it is measured over.

    The numbers of the calibration are 1.000 over 30 cases, 0.625 over 40 cases and 0.786 over 70 cases, and the
    document has to say which is which. The check looks for each number next to the set it belongs to.
    """
    assert re.search(r"1\.000", verification_sets)
    assert re.search(r"0\.625", verification_sets)
    assert re.search(r"0\.786", verification_sets)
    assert "70 NLI cases" in verification_sets


def test_the_public_numbers_do_not_carry_a_dash_that_the_guard_forbids(
    readme: str, readme_pt: str, verification_sets: str
) -> None:
    """The numbers live in documents without an em dash and without an en dash.

    The repository has a guard for the two characters, and this file reads the same documents the guard does, so a
    dash that reaches them fails the gate with a sentence that names the file.
    """
    for name, text in (
        ("README.md", readme),
        ("README.pt-BR.md", readme_pt),
        ("docs/verification_sets.md", verification_sets),
    ):
        assert "\u2014" not in text, f"{name} carries an em dash"
        assert "\u2013" not in text, f"{name} carries an en dash"
