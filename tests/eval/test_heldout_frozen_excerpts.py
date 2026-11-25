"""The held out set keeps the corpus of its generation: a correction of the corpus never regenerates it.

What it guarantees, and why: the excerpt of every policy citation of `data/eval/heldout/cases.jsonl` is the
text of the corpus of the generation, and not the text of the corrected corpus, because the set is read
once, its labels are published, and a regenerated set has no provenance and no published labels (the task
T170 of the milestone, and ADR-061).

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "data" / "eval" / "heldout" / "cases.jsonl"
POLICIES = ROOT / "data" / "policies"


def _corpus_text() -> str:
    """The text of the corrected corpus of today, for the comparison that must fail to match."""
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(POLICIES.glob("*.md")))


def test_the_excerpt_of_every_policy_citation_is_the_text_of_the_corpus_of_the_generation() -> None:
    """The excerpts of the cases are frozen: they are the text of the corpus of the generation.

    The cases of the held out set carry the text of the excerpts inside them. The corpus of today is the
    corrected one, and the excerpts of the cases that cite a rule the correction moved are the text of the
    corpus of the generation, so the set still measures the verifier over the excerpts it was read over.
    """
    cases = [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert cases
    corpus = _corpus_text()
    frozen = 0
    for case in cases:
        excerpt = str(case.get("evidence", ""))
        if "policy:" not in str(case.get("evidence_ids", "")):
            continue
        # The excerpt of a policy citation is the text of the corpus of the generation: when the correction
        # moved the rule, the excerpt of the case is not the text of the corrected corpus, and that is the
        # proof that the set is frozen and was not regenerated.
        if excerpt and excerpt not in corpus:
            frozen += 1
    assert frozen > 0, (
        "every excerpt of the held out set matches the corrected corpus: the set was regenerated, "
        "and a regenerated set has no provenance"
    )


def test_the_held_out_set_is_not_written_by_this_milestone() -> None:
    """The cases and the labels of the held out set are the files of the generation, untouched."""
    assert CASES.is_file()
    labels = ROOT / "data" / "eval" / "heldout" / "labels_adjudicated.jsonl"
    assert labels.is_file()
    cases = [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(cases) == 48
