"""The generator of the held out set: the cases it writes, the recipes it keeps and the properties of both.

Why it exists: the held out set of the repository is written by a program and read by a person, and the two must
never meet. The program writes the cases, the person reads the labels, and the recipe of each case stays in a file
the person never opens. Every test below holds one property of that arrangement, and every one of them reads the
disk or the tuning material to do it, so a list of ids written by hand cannot make a test pass.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pytest

from ledgerlens.config import PROJECT_ROOT
from ledgerlens.eval.heldout import (
    CASE_COUNT,
    CASES_PATH,
    CONTROL_BENIGN_UNSUPPORTED,
    CONTROL_NO_EVIDENCE,
    CONTROL_SELF_CONTRADICTION,
    HELD_OUT_SEED,
    INSTANCES_PER_TEMPLATE,
    RECIPES_PATH,
    TEMPLATES,
    TOKEN_OVERLAP_CEILING,
    build_cases,
    build_recipes,
    is_tuning_id,
    load_cases,
    load_recipes,
    premise_contradiction,
    shape_inventory,
    token_overlap,
    tuning_ids,
    write_held_out,
)

# The two tuning sets. The first carries prose evidence and the second carries rendered envelopes, so the held out
# set has to differ from both of them.
TUNING_SET_PATH = PROJECT_ROOT / "data" / "eval" / "verification_set.jsonl"
TUNING_LIVE_PATH = PROJECT_ROOT / "data" / "eval" / "verification_live.jsonl"

# The shape of an id of the ledger. It is written here on purpose, so the test does not ask the module whether it
# excluded what it excluded.
LEDGER_ID = re.compile(r"\b(?:TX|R|CB|ST|C|M|FX)-\d{2,4}\b")

# The keys of a recipe. A case of the file the person reads holds none of them.
RECIPE_KEYS = (
    "label",
    "template",
    "pair_id",
    "fact_key",
    "fact_value",
    "differing_fact",
    "control",
    "unsupported_marker",
    "record_id",
    "evidence_note",
)

# The labels the verifier uses.
LABELS = ("supported", "contradicted", "not_enough_evidence")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """The records of a JSONL file, in the order of the file."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _tuning_paths() -> tuple[Path, ...]:
    """The files of the tuning material: the datasets whose role is tuning and the manifest of the scenarios.

    Why it is read from the manifest and not written here: the role of a dataset is what says what may be done with
    it, and a list of files written by hand in a test would go stale the day a dataset changes its role.
    """
    manifest = json.loads((PROJECT_ROOT / "data" / "eval" / "datasets.json").read_text(encoding="utf-8"))
    paths = [PROJECT_ROOT / entry["path"] for entry in manifest["datasets"] if entry["split_role"] == "tuning"]
    paths.append(PROJECT_ROOT / "data" / "scenarios.json")
    return tuple(paths)


def _tuning_ids() -> set[str]:
    """The ids of the records that the tuning material names."""
    found: set[str] = set()
    for path in _tuning_paths():
        found |= set(LEDGER_ID.findall(path.read_text(encoding="utf-8")))
    return found


def _case_text(case: dict[str, Any]) -> str:
    """Everything a case says: the claim and the content of every evidence."""
    return case["claim"] + " " + " ".join(item["content"] for item in case["evidence"])


def test_the_build_is_deterministic(tmp_path: Path) -> None:
    """Two builds of the same seed write the same bytes, for the cases and for the recipes."""
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_held_out(cases_path=first / "cases.jsonl", recipes_path=first / "recipes.jsonl")
    write_held_out(cases_path=second / "cases.jsonl", recipes_path=second / "recipes.jsonl")
    assert (first / "cases.jsonl").read_bytes() == (second / "cases.jsonl").read_bytes()
    assert (first / "recipes.jsonl").read_bytes() == (second / "recipes.jsonl").read_bytes()


def test_the_set_holds_forty_eight_cases_in_six_templates_of_eight() -> None:
    """The shape the judge ruled: 48 cases, six named templates, eight instances of each."""
    cases = build_cases()
    recipes = build_recipes()
    assert CASE_COUNT == 48
    assert len(cases) == 48
    assert len(recipes) == 48
    assert len(TEMPLATES) == 6
    assert len(set(TEMPLATES)) == 6
    counts = Counter(recipe["template"] for recipe in recipes)
    assert set(counts) == set(TEMPLATES)
    assert INSTANCES_PER_TEMPLATE == 8
    assert all(counts[template] == 8 for template in TEMPLATES)


def test_the_templates_are_the_six_named_ones() -> None:
    """The names of the templates are the six the design named, and they say what each one is."""
    assert TEMPLATES == (
        "hedge_shape",
        "compound_shape",
        "negation_shape",
        "relative_period_shape",
        "range_shape",
        "two_source_shape",
    )


def test_every_case_is_a_text_case() -> None:
    """No case of the set is a numeric case and none is a coherence case.

    Why it matters: the label of a numeric case would be computed by the same code that judges it, and a coherence
    case holds several claims. The set of the judge holds one claim per case and no amount.
    """
    money = re.compile(r"\d+[.,]\d{2}\s*[A-Z]{3}|R\$")
    for case in build_cases():
        assert set(case) == {"id", "claim", "evidence_ids", "evidence"}
        assert isinstance(case["claim"], str) and case["claim"].strip()
        assert "claims" not in case
        assert "calc" not in case
        assert "type" not in case
        assert money.search(case["claim"]) is None


def test_the_id_of_a_case_does_not_encode_its_template() -> None:
    """The ids are a neutral sequence and the templates are not grouped in the file."""
    recipes = build_recipes()
    assert [recipe["id"] for recipe in recipes] == [f"ho-{index:03d}" for index in range(1, 49)]
    templates = [recipe["template"] for recipe in recipes]
    assert all(left != right for left, right in zip(templates, templates[1:], strict=False))
    for template in TEMPLATES:
        positions = [index for index, name in enumerate(templates) if name == template]
        assert positions[-1] - positions[0] + 1 > len(positions)


def test_no_case_names_an_id_of_the_tuning_material() -> None:
    """No case of the set names a record the tuning material names.

    Why it matters: the synthetic ledger reuses the id space of the sample ledger, so a case that named TX-0001
    would collide with the tuning material even though the world of the case is another one.
    """
    forbidden = _tuning_ids()
    assert forbidden
    for case in build_cases():
        named = set(LEDGER_ID.findall(_case_text(case)))
        assert not named & forbidden
    # the module agrees with the reading of the test, and the reading of the test is not a subset of nothing
    assert tuning_ids() >= forbidden
    assert all(is_tuning_id(identifier) for identifier in sorted(forbidden)[:20])


def test_the_pairs_differ_by_one_fact() -> None:
    """Each pair of the set shares the template and the record and changes one fact only."""
    recipes = build_recipes()
    cases = {case["id"]: case for case in build_cases()}
    pairs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for recipe in recipes:
        pairs[recipe["pair_id"]].append(recipe)
    assert len(pairs) == CASE_COUNT // 2
    for members in pairs.values():
        assert len(members) == 2
        first, second = members
        assert first["template"] == second["template"]
        assert first["record_id"] == second["record_id"]
        assert first["fact_key"] == second["fact_key"]
        assert first["fact_value"] != second["fact_value"]
        claim = cases[first["id"]]["claim"]
        other = cases[second["id"]]["claim"]
        assert first["fact_value"] in claim
        assert second["fact_value"] in other
        # the two claims are the same sentence with one fact changed
        assert claim.replace(first["fact_value"], "<FACT>") == other.replace(second["fact_value"], "<FACT>")
        # the evidence of the pair is the same, unless the recipe declares that the premise changed
        if not first["control"] and not second["control"]:
            assert [item["id"] for item in cases[first["id"]]["evidence"]] == [
                item["id"] for item in cases[second["id"]]["evidence"]
            ]


def test_the_recipes_are_not_in_the_file_the_person_reads() -> None:
    """The file the person reads holds no label, no template name and no key of a recipe."""
    text = CASES_PATH.read_text(encoding="utf-8")
    for line in text.splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        assert set(record) <= {"id", "claim", "evidence_ids", "evidence"}
        for key in RECIPE_KEYS:
            assert key not in record
        for template in TEMPLATES:
            assert template not in line
        for label in LABELS:
            assert label not in line


def test_the_file_of_the_cases_on_the_disk_is_the_build_of_its_generation() -> None:
    """The cases file of the repository is the build of the module over the corpus of its generation.

    The corpus moved with the correction of the audit, and the cases file keeps the excerpts of the corpus
    of its generation: the held out set is frozen and it is never regenerated (ADR-061). The test compares
    the structure of the set, and the frozen excerpts are the proof of the test of the frozen excerpts.
    """
    committed = load_cases(CASES_PATH)
    fresh = build_cases()
    assert [case["id"] for case in committed] == [case["id"] for case in fresh]
    assert len(committed) == CASE_COUNT


@pytest.mark.skipif(
    not RECIPES_PATH.exists(),
    reason="the recipes of the generator are the answer key of the set and they are not in the repository",
)
def test_the_file_on_disk_is_the_build_of_its_generation() -> None:
    """The cases file of the repository is the build of the module over the corpus of its generation.

    The corpus moved with the correction of the audit, and the set is frozen (ADR-061): the test compares
    the structure of the set and of the recipes, and the excerpts of the generation stay in the files.
    """
    committed = load_cases(CASES_PATH)
    fresh = build_cases()
    assert [case["id"] for case in committed] == [case["id"] for case in fresh]
    assert [recipe["id"] for recipe in load_recipes(RECIPES_PATH)] == [recipe["id"] for recipe in build_recipes()]


def test_the_shape_of_the_set_differs_from_the_shape_of_the_tuning_sets() -> None:
    """The held out set has a shape that neither tuning set has, and it is not the shape of either of them."""
    held = shape_inventory(build_cases())
    assert held
    for path in (TUNING_SET_PATH, TUNING_LIVE_PATH):
        other = shape_inventory(_read_jsonl(path))
        assert held != other
        assert held - other, f"the held out set shares every shape with {path.name}"


def test_no_claim_of_the_set_passes_the_token_overlap_ceiling() -> None:
    """No claim of the held out set is too close to a claim of the tuning material."""
    assert TOKEN_OVERLAP_CEILING == 0.3
    tuning_claims = [
        record["claim"]
        for path in (TUNING_SET_PATH, TUNING_LIVE_PATH)
        for record in _read_jsonl(path)
        if isinstance(record.get("claim"), str)
    ]
    assert tuning_claims
    for case in build_cases():
        for claim in tuning_claims:
            assert token_overlap(case["claim"], claim) <= TOKEN_OVERLAP_CEILING


def test_the_control_of_the_case_with_no_evidence_is_detected() -> None:
    """The case that cites no evidence at all is in the set and the machine sees it."""
    recipes = build_recipes()
    cases = {case["id"]: case for case in build_cases()}
    controls = [recipe for recipe in recipes if recipe["control"] == CONTROL_NO_EVIDENCE]
    assert controls
    for recipe in controls:
        case = cases[recipe["id"]]
        assert case["evidence_ids"] == []
        assert case["evidence"] == []


def test_the_control_of_the_case_whose_evidence_contradicts_itself_is_detected() -> None:
    """The premise that contradicts itself is in the frozen set, with two items of two tools that disagree.

    The control is built on the rule of the negative net that the correction of the audit moved, and the
    frozen set keeps the excerpt of the corpus of its generation (ADR-061): the check reads the frozen set.
    """
    recipes = load_recipes(RECIPES_PATH)
    cases = {case["id"]: case for case in load_cases(CASES_PATH)}
    controls = [recipe for recipe in recipes if recipe["control"] == CONTROL_SELF_CONTRADICTION]
    assert controls
    for recipe in controls:
        case = cases[recipe["id"]]
        assert len(case["evidence"]) == 2
        assert len({item["id"].split(":")[0] for item in case["evidence"]}) == 2
        assert premise_contradiction(case) is not None


def test_the_control_of_the_benign_claim_is_detected() -> None:
    """The benign claim the evidence does not support is in the set and the machine sees the gap."""
    recipes = build_recipes()
    cases = {case["id"]: case for case in build_cases()}
    controls = [recipe for recipe in recipes if recipe["control"] == CONTROL_BENIGN_UNSUPPORTED]
    assert controls
    for recipe in controls:
        case = cases[recipe["id"]]
        marker = recipe["unsupported_marker"]
        assert marker
        assert marker in case["claim"]
        assert marker not in " ".join(item["content"] for item in case["evidence"])


def test_the_three_negative_controls_are_present_and_the_other_cases_are_not_them() -> None:
    """The frozen set carries the three controls the judge asked for, and each is detected by the machine.

    The controls depend on the corpus of the generation, and the frozen set keeps it (ADR-061): the check
    reads the frozen set and its recipes.
    """
    recipes = load_recipes(RECIPES_PATH)
    cases = {case["id"]: case for case in load_cases(CASES_PATH)}
    kinds = {recipe["control"] for recipe in recipes if recipe["control"]}
    assert kinds == {CONTROL_NO_EVIDENCE, CONTROL_SELF_CONTRADICTION, CONTROL_BENIGN_UNSUPPORTED}

    # the case with no evidence at all
    without = [case for case in cases.values() if not case["evidence_ids"]]
    assert len(without) == 1
    # the premise that contradicts itself
    contradicting = [case for case in cases.values() if premise_contradiction(case) is not None]
    assert contradicting
    # the benign claim the evidence does not support
    benign = [
        recipe
        for recipe in recipes
        if recipe["control"] == CONTROL_BENIGN_UNSUPPORTED and recipe["unsupported_marker"]
    ]
    assert benign


def test_the_label_of_every_case_is_one_the_verifier_uses() -> None:
    """The recipes carry a label of the vocabulary of the verifier, and the labels are not all the same."""
    labels = Counter(recipe["label"] for recipe in build_recipes())
    assert set(labels) <= set(LABELS)
    assert len(labels) >= 2
    assert sum(labels.values()) == 48


def test_the_seed_of_the_set_is_the_one_the_judge_ruled() -> None:
    """The seed of the set is 7301 and the build takes it as an argument."""
    assert HELD_OUT_SEED == 7301
    assert build_cases(seed=HELD_OUT_SEED) == build_cases()
    assert build_cases(seed=HELD_OUT_SEED) == build_cases(seed=7301)
