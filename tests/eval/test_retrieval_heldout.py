"""The held out set of the retrieval: the generator, the exclusion of the tuning material and the novelty.

What they guarantee, and why: the questions of the set are written by the generator, the file the person reads
holds no label and no recipe, the gold chunks of the set are never the gold chunks of the tuning questions,
and no question of the set is closer to a question of the tuning material than the ceiling of the token
overlap, because a held out set that repeats the tuning material is a tuning set with another name.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import json
from pathlib import Path

from ledgerlens.eval.heldout import TOKEN_OVERLAP_CEILING, token_overlap
from ledgerlens.eval.retrieval_heldout import (
    HELDOUT_DIR,
    build_cases,
    build_recipes,
    novelty_problems,
)

ROOT = Path(__file__).resolve().parents[2]


def test_the_file_the_person_reads_holds_no_label_and_no_recipe() -> None:
    """The cases file holds the question and nothing else, because the person reads it blind."""
    cases = build_cases()

    assert cases
    for case in cases:
        assert set(case) == {"id", "question"}


def test_the_gold_chunks_of_the_set_are_never_the_gold_chunks_of_the_tuning_questions() -> None:
    """A section of the tuning set is never a section of the held out set."""
    tuning: set[str] = set()
    for line in (ROOT / "data" / "eval" / "policy_questions.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            tuning.update(json.loads(line)["gold_chunk_ids"])

    for recipe in build_recipes():
        assert recipe["gold_chunk_id"] not in tuning


def test_no_question_of_the_set_is_too_close_to_a_question_of_the_tuning_material() -> None:
    """The novelty of the set is measured, and the ceiling is the one of the verification held out."""
    assert novelty_problems(build_cases()) == []


def test_every_gold_chunk_of_the_recipes_exists_in_the_policies() -> None:
    """A recipe that names a section that is not in the policy is a recipe that cannot be checked."""
    import re

    for recipe in build_recipes():
        policy_stem, anchor = recipe["gold_chunk_id"].split("#")
        policy = ROOT / "data" / "policies" / f"{policy_stem}.md"
        assert policy.is_file(), f"the policy {policy_stem} is not on the disk"
        anchors = re.findall(r"^## .+? \{#([^}]+)\}", policy.read_text(encoding="utf-8"), re.M)
        assert anchor in anchors, f"the anchor {anchor} is not in {policy_stem}"


def test_the_recipes_are_not_in_the_cases_file() -> None:
    """The file the person reads holds no recipe, and the recipe lives in its own file."""
    cases_text = (HELDOUT_DIR / "retrieval_cases.jsonl").read_text(encoding="utf-8")

    for recipe in build_recipes():
        assert recipe["gold_chunk_id"] not in cases_text


def test_the_questions_of_the_set_are_not_the_questions_of_the_tuning_material() -> None:
    """No question of the set is a question of the tuning material with another name."""
    tuning_questions = [
        json.loads(line)["question"]
        for line in (ROOT / "data" / "eval" / "policy_questions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for case in build_cases():
        for question in tuning_questions:
            assert token_overlap(case["question"], question) < TOKEN_OVERLAP_CEILING
