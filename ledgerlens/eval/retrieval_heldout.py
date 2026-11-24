"""The generator of the held out set of the retrieval: the questions a person reads and the recipes they never see.

Why it exists: the twelve questions of `data/eval/policy_questions.jsonl` are a tuning set, because ADR-006
chose the embedding and the query transform with the recall over them, and a comparison of the retrieval over a
set that every decision was taken against is a comparison that measures nothing. The held out set of the
retrieval has the three properties of the held out set of the verification: the questions are written by a
generator, the relevance labels are read by a person blind to the recipe, and the guard refuses a tuning
script that reads the set.

The split is the point of the module. The generator writes the questions and keeps the recipe of each question
in a second file. The person who labels the relevance reads the questions and the policies, instructed to be
blind to the recipe. The recipe and the label are allowed to disagree, and the disagreement counts: it is the
measure of the set.

The questions come in two shapes. The easy question is a template over the heading of the section, and the
hard question is a paraphrase written over the section with a vocabulary that does not repeat it. The sections
of the held out set are never the sections of the tuning set: the gold chunks of the tuning questions are read
from the tuning file when the set is built, so a question of the set can never be a question of the tuning
material with another name.

Usage:

```python
from ledgerlens.eval.retrieval_heldout import build_cases, build_recipes, write_retrieval_held_out

cases = build_cases()      # the 16 questions, in the order of the file
recipes = build_recipes()  # the recipe of each question, in the same order
write_retrieval_held_out()  # the two files of the folder
```
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ledgerlens.eval.heldout import TOKEN_OVERLAP_CEILING, token_overlap

__all__ = [
    "HELDOUT_DIR",
    "build_cases",
    "build_recipes",
    "novelty_problems",
    "write_retrieval_held_out",
]

ROOT = Path(__file__).resolve().parents[2]
POLICIES_DIR = ROOT / "data" / "policies"
HELDOUT_DIR = ROOT / "data" / "eval" / "heldout"
TUNING_QUESTIONS = ROOT / "data" / "eval" / "policy_questions.jsonl"

# The easy question of a section: a template over the heading of the section, with the words of the policy.
_EASY_TEMPLATE = "What does the policy of Acme Payments say about {heading}?"

# The hard questions, written by hand over the section, with a vocabulary that does not repeat it. The recipe
# of each one names the section it was written over, and the paraphrase is the reason the question is hard.
_HARD_QUESTIONS: dict[tuple[str, str], str] = {
    ("chargeback-handling", "evidence-frd"): (
        "What should the store gather when the customer says the card was stolen?"
    ),
    ("cross-currency-refunds", "reading-the-difference"): (
        "The customer got less back than expected in another currency, how do I explain the gap?"
    ),
    ("duplicate-charges", "retries-after-failure"): (
        "The first attempt was declined and the shop tried again, is the second charge a copy?"
    ),
    ("escalation-and-review", "suspicious-text"): (
        "A note inside the order tells the analyst to approve everything, what should happen?"
    ),
    ("fees-and-pricing", "fx-markup-is-not-a-fee"): (
        "The shop adds a little on top of the exchange rate: is that a charge of the house?"
    ),
    ("fx-reference-rates", "unsupported-currency-handling"): (
        "What happens when a payment arrives in a currency the platform cannot price?"
    ),
    ("refund-policy", "rejection-reasons"): "Why would a shop say no to giving the money back?",
    ("settlement-schedule", "payout-calendars"): (
        "Do Brazilian and European stores receive their money on the same days?"
    ),
}

# The easy questions, one per policy, over a section that is not the section of the hard question and not a
# section of the tuning set.
_EASY_SECTIONS: dict[str, str] = {
    "chargeback-handling": "reason-codes",
    "cross-currency-refunds": "charge-fx-at-capture",
    "duplicate-charges": "time-gap",
    "escalation-and-review": "deadline-within-2-days",
    "fees-and-pricing": "rounding",
    "fx-reference-rates": "weekends-holidays",
    "refund-policy": "full-and-partial",
    "settlement-schedule": "components",
}

_SECTION = re.compile(r"^## (.+?) \{#([^}]+)\}", re.M)


def _sections_of(policy: Path) -> dict[str, str]:
    """The sections of a policy: the anchor and the heading of each one."""
    return {anchor: heading for heading, anchor in _SECTION.findall(policy.read_text(encoding="utf-8"))}


def _tuning_gold_chunks() -> set[str]:
    """The gold chunks of the tuning questions, read from the tuning file when the set is built."""
    chunks: set[str] = set()
    for line in TUNING_QUESTIONS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            chunks.update(json.loads(line)["gold_chunk_ids"])
    return chunks


def _tuning_questions() -> list[str]:
    """The text of the tuning questions, for the novelty check of the set."""
    return [
        str(json.loads(line)["question"])
        for line in TUNING_QUESTIONS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _plan() -> list[tuple[str, str, str, str]]:
    """The plan of the set: the policy, the anchor, the question and the template of each case, in order.

    The sections of the tuning set are excluded here, and not by hand: a section that is a gold chunk of the
    tuning questions is never a section of the held out set.
    """
    tuning = _tuning_gold_chunks()
    plan: list[tuple[str, str, str, str]] = []
    for policy in sorted(POLICIES_DIR.glob("*.md")):
        sections = _sections_of(policy)
        easy_anchor = _EASY_SECTIONS[policy.stem]
        hard_anchor = next(anchor for (name, anchor) in _HARD_QUESTIONS if name == policy.stem)
        for anchor in (easy_anchor, hard_anchor):
            chunk = f"{policy.stem}#{anchor}"
            if chunk in tuning:
                raise ValueError(f"the section {chunk} is a gold chunk of the tuning set")
            if anchor not in sections:
                raise ValueError(f"the section {chunk} is not in the policy")
        heading = sections[easy_anchor]
        plan.append((policy.stem, easy_anchor, _EASY_TEMPLATE.format(heading=heading[0].lower() + heading[1:]), "easy"))
        plan.append((policy.stem, hard_anchor, _HARD_QUESTIONS[(policy.stem, hard_anchor)], "hard"))
    return plan


def build_cases() -> list[dict[str, str]]:
    """The questions of the held out set, in the order of the file, with no label and no recipe."""
    return [
        {"id": f"RH-{index:02d}", "question": question}
        for index, (_policy, _anchor, question, _template) in enumerate(_plan(), start=1)
    ]


def build_recipes() -> list[dict[str, str]]:
    """The recipe of each question, in the same order: the gold chunk and the template of the question."""
    return [
        {"id": f"RH-{index:02d}", "gold_chunk_id": f"{policy}#{anchor}", "template": template}
        for index, (policy, anchor, _question, template) in enumerate(_plan(), start=1)
    ]


def novelty_problems(cases: list[dict[str, str]]) -> list[str]:
    """The questions of the set that are too close to a question of the tuning material, one line each.

    The ceiling of the token overlap is the one of the held out set of the verification: a question of the set
    that repeats the words of a question of the tuning material is a question of the tuning material with
    another name.
    """
    problems: list[str] = []
    tuning = _tuning_questions()
    for case in cases:
        for question in tuning:
            overlap = token_overlap(case["question"], question)
            if overlap >= TOKEN_OVERLAP_CEILING:
                problems.append(
                    f"the question {case['id']} is too close to a question of the tuning material: {overlap}"
                )
    return problems


def write_retrieval_held_out() -> None:
    """The two files of the folder: the questions the person reads and the recipes the person never sees."""
    cases = build_cases()
    problems = novelty_problems(cases)
    if problems:
        raise ValueError("; ".join(problems))
    HELDOUT_DIR.mkdir(parents=True, exist_ok=True)
    with (HELDOUT_DIR / "retrieval_cases.jsonl").open("w", encoding="utf-8") as handle:
        for case in cases:
            handle.write(json.dumps(case, ensure_ascii=False) + "\n")
    with (HELDOUT_DIR / "retrieval_recipes.jsonl").open("w", encoding="utf-8") as handle:
        for recipe in build_recipes():
            handle.write(json.dumps(recipe, ensure_ascii=False) + "\n")
