#!/usr/bin/env python3
"""The blind reading session of the held out set: the modes read, report and build.

Why it exists: ADR-053 decides that the labels of the held out set come from one person who reads the cases one at a
time, blind to the recipe of each case, and that the label of the reader wins over the recipe. This script is the
instrument of that reading: it shows one case at a time, it shows the evidence the way the model will read it, it
saves every label as the reading goes so an interrupted session is never lost, and it compares the labels with the
recipes after the reading so that every disagreement is on the record.

Three modes:

- `read` runs the session. It shows ONE case at a time: the id, the claim, the ids the claim cites, the evidence
  rendered the way the model will read it, the rule of ADR-007 in the header of every screen and the three labels of
  the rule. It never shows the recipe, the template, the expected label, the pair, the case before or the case after.
  Every label is written to `data/eval/heldout/labels_v1.jsonl` as it is given, so a session that is interrupted
  resumes where it stopped.
- `report` compares the labels of the session with the recipes, prints the disagreements and their count, and writes
  the note of every disagreement into the labelled set.
- `build` builds `data/eval/verification_heldout.jsonl` from the cases and the labels. The label of the reader is the
  label of the line, the recipe never overwrites it, and the build refuses to run over an incomplete session.

The script reads the files of the set and never imports the module that writes them, so the two halves of the
milestone stay apart. It needs no model and no key: it runs offline. The tool moves text and never turns a number
into a float, so the amounts of a claim stay the text they are.

Usage:

```bash
uv run python scripts/label_heldout.py read --root .
uv run python scripts/label_heldout.py report --root .
uv run python scripts/label_heldout.py build --root .
```
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

from ledgerlens.config import PROJECT_ROOT
from ledgerlens.schemas import Claim, Evidence
from ledgerlens.verify.checks import load_thresholds, text_premise

__all__ = [
    "CASES_RELATIVE",
    "HELDOUT_DIR_RELATIVE",
    "LABELS_RELATIVE",
    "LABELLED_SET_RELATIVE",
    "LABELS",
    "ORIGIN",
    "ORIGIN_ONE_READER",
    "ORIGIN_TWO_READERS",
    "RECIPES_RELATIVE",
    "RULE_ADR_007",
    "RULE_SELF_CONTRADICTION",
    "SCREEN_CASE_MARKER",
    "Case",
    "Disagreement",
    "HeldoutDataError",
    "HeldoutError",
    "HeldoutIncompleteError",
    "ReaderLabel",
    "Recipe",
    "build_labelled_set",
    "cases_path",
    "compare_labels",
    "labels_path",
    "labelled_set_path",
    "load_cases",
    "load_labels",
    "load_recipes",
    "main",
    "premise_of",
    "read_session",
    "recipes_path",
    "render_screen",
    "report_session",
]

# The three labels of the rule of ADR-007, in the order of the screen.
LABELS: tuple[str, ...] = ("supported", "contradicted", "not_enough_evidence")

# The origin of every line of the labelled set: the reading was a blind one.
# The origin that goes into every line of the labelled set. It says WHO read the cases, because a label without a
# reader is a label without a provenance, and the reader is part of what the number over the set may claim.
ORIGIN_ONE_READER = "held out: blind reading v1 by one reader, ADR-053"
ORIGIN_TWO_READERS = (
    "held out: blind reading by two independent machine readers with adjudication, ADR-059"
)
ORIGIN = ORIGIN_ONE_READER

# The marker that opens the block of a case, so a screen can be found in the output of a session.
SCREEN_CASE_MARKER = "CASE "

# The rule of ADR-007, in the words the reading brief carries. It is in the header of every screen.
RULE_ADR_007 = "\n".join(
    [
        "You label verification cases. You are given ONE case at a time and nothing else: an id, a claim, the ids of "
        "the evidence the claim cites, and the content of that evidence. You are not given a label, a note, an "
        "origin, a recipe, the case before this one or the case after this one.",
        "Read the claim against the cited evidence and give exactly one label:",
        "- `supported`: every fact of the claim is in the cited evidence. A particular case of a general rule counts "
        "as in the evidence.",
        "- `contradicted`: the cited evidence says something else.",
        "- `not_enough_evidence`: the cited evidence does not say.",
        "Numeric claims are out of scope: they go to `check_numeric`, not to the NLI model.",
        "Answer with the label and ONE sentence naming the fact of the claim that decided it. If the claim carries a "
        "judgment the evidence does not state (for example, that a refusal is correct), the label is "
        "`not_enough_evidence` and the sentence says so. If you cannot separate `supported` from "
        "`not_enough_evidence`, answer `not_enough_evidence` and say why. Never state a fact that is not in the "
        "evidence.",
    ]
)

# The rule that ADR-007 does not have and that ADR-053 adds, because the set carries an evidence that contradicts
# itself. It is in the header of every screen, next to the rule of ADR-007.
RULE_SELF_CONTRADICTION = (
    "Evidence that contradicts itself says two things and so says nothing, therefore the label is "
    "`not_enough_evidence`."
)

# The files of the set, relative to the root of the tree.
HELDOUT_DIR_RELATIVE = Path("data") / "eval" / "heldout"
CASES_RELATIVE = HELDOUT_DIR_RELATIVE / "cases.jsonl"
RECIPES_RELATIVE = HELDOUT_DIR_RELATIVE / "recipes.jsonl"
LABELS_RELATIVE = HELDOUT_DIR_RELATIVE / "labels_v1.jsonl"
LABELLED_SET_RELATIVE = Path("data") / "eval" / "verification_heldout.jsonl"

# The words a reader may type for a label, and the label each of them means.
_LABEL_ALIASES: dict[str, str] = {
    "s": "supported",
    "1": "supported",
    "supported": "supported",
    "support": "supported",
    "c": "contradicted",
    "2": "contradicted",
    "contradicted": "contradicted",
    "contradiction": "contradicted",
    "n": "not_enough_evidence",
    "3": "not_enough_evidence",
    "not_enough_evidence": "not_enough_evidence",
    "nee": "not_enough_evidence",
}

# The fields a recipe may name each of its facts with. The file of the recipes is written by another half of the
# milestone, so the tool accepts the names it may find and takes the first one that is there.
_TEMPLATE_KEYS = ("template", "template_name", "case_template")
_EXPECTED_KEYS = ("expected_label", "expected", "label", "expected_verdict")
_PAIR_KEYS = ("pair_id", "pair", "pair_case_id")
_FACT_KEYS = (
    "differing_fact",
    "fact_that_differs",
    "changed_fact",
    "differing_field",
    "differs",
    "fact",
)

# The source and the tool of an evidence, by the prefix of its id. The premise of the model does not read them, but
# the evidence of the schema carries them.
_SOURCE_BY_PREFIX = {
    "sql": "sql",
    "api": "ledger_api",
    "policy": "policy",
    "fx": "fx",
    "calc": "calc",
    "case": "case",
}
_TOOL_BY_PREFIX = {
    "sql": "query_ledger",
    "api": "get_ledger_record",
    "policy": "search_policies",
    "fx": "get_reference_fx",
    "calc": "calculate",
    "case": "recall_cases",
}

# The moment the evidences of the set carry. Nothing of the reading depends on it: the set has no run behind it.
_RETRIEVED_AT = datetime(2026, 1, 1, tzinfo=UTC)


class HeldoutError(Exception):
    """The tool cannot go on, and the message says why in one plain English sentence."""


class HeldoutDataError(HeldoutError):
    """A file of the set does not have the shape the contract declares.

    Why it exists: a malformed line is a data problem of the file and not a crash of the tool. The message names the
    file and the line, the way the manifest of the datasets names them.
    """


class HeldoutIncompleteError(HeldoutError):
    """The reading session is not complete, and the message names the cases that are missing."""


@dataclass(frozen=True)
class Case:
    """One case of the set: the id, the claim, the ids the claim cites and the evidence itself.

    Why it exists: the case is the unit the reader sees and the unit the labelled set carries. It holds no label, no
    template and no recipe, because the reader must not see any of them.
    """

    id: str
    claim: str
    evidence_ids: tuple[str, ...]
    evidence: tuple[tuple[str, str], ...]  # the id and the content of each evidence, in the order of the file


@dataclass(frozen=True)
class Recipe:
    """The recipe of a case: how it was built and what it was built to be.

    Why it exists: the recipe is the answer key of the generator. The reader never sees it, and the report compares
    the labels of the reader with it after the reading, so that every disagreement is on the record.
    """

    id: str
    template: str
    expected_label: str
    pair_id: str
    differing_fact: str


@dataclass(frozen=True)
class ReaderLabel:
    """What the reader answered for one case: the label and the sentence that decided it."""

    id: str
    label: str
    note: str


@dataclass(frozen=True)
class Disagreement:
    """One case where the label of the reader and the label of the recipe do not agree."""

    id: str
    reader_label: str
    expected_label: str
    template: str
    pair_id: str
    differing_fact: str
    note: str


def cases_path(root: Path) -> Path:
    """The file of the cases of the set, inside the root."""
    return root / CASES_RELATIVE


def recipes_path(root: Path) -> Path:
    """The file of the recipes of the set, inside the root. The reader never opens it."""
    return root / RECIPES_RELATIVE


def labels_path(root: Path, override: Path | None = None) -> Path:
    """The file the reading writes, one line per case, inside the root.

    Why the override exists: two readers who never see each other need two files, and the comparison of the two is a
    measurement of the noise of a label that does not depend on the recipes of the generator.
    """
    if override is None:
        return root / LABELS_RELATIVE
    return override if override.is_absolute() else root / override


def labelled_set_path(root: Path) -> Path:
    """The file of the labelled set, inside the root. It is what the manifest will declare."""
    return root / LABELLED_SET_RELATIVE


def _read_records(path: Path) -> list[tuple[int, dict[str, Any]]]:
    """The records of a JSONL file, each with the number of its line.

    Why it exists: every read of the set goes through this door, so a file that the process cannot open and a line
    that does not parse are sentences and never tracebacks. The number of the line travels with the record because
    the message of a bad record has to name it.
    """
    if not path.exists():
        raise HeldoutDataError(f"The file {path} does not exist, so it holds nothing to read.")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise HeldoutDataError(f"The file {path} is not valid UTF-8: {error}.") from error
    except OSError as error:
        raise HeldoutDataError(f"The file {path} could not be read: {error}.") from error
    records: list[tuple[int, dict[str, Any]]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise HeldoutDataError(f"The line {number} of the file {path} is not valid JSON: {error.msg}.") from error
        if not isinstance(record, dict):
            raise HeldoutDataError(f"The line {number} of the file {path} is not a JSON object, so it is not a record.")
        records.append((number, record))
    return records


def _text_field(record: Mapping[str, Any], name: str, path: Path, number: int) -> str:
    """A field of a record that has to be a string, or a sentence that names the file and the line."""
    value = record.get(name)
    if not isinstance(value, str) or not value.strip():
        raise HeldoutDataError(
            f"The line {number} of the file {path} does not hold a usable record: the field {name} is missing or is "
            f"not a string."
        )
    return value


def _first_text(record: Mapping[str, Any], names: Sequence[str]) -> str:
    """The first of the given names that holds a text in the record, or an empty string.

    Why it exists: the file of the recipes is written by another half of the milestone, and the names of its fields
    are not pinned by this tool. The tool takes the first name it finds and never fails over a name it does not know.
    """
    for name in names:
        value = record.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _case_of(record: Mapping[str, Any], path: Path, number: int) -> Case:
    """The case of a record, or a sentence that names the file and the line."""
    identifier = _text_field(record, "id", path, number)
    claim = _text_field(record, "claim", path, number)
    raw_ids = record.get("evidence_ids", [])
    raw_evidence = record.get("evidence", [])
    if not isinstance(raw_ids, list) or not all(isinstance(item, str) for item in raw_ids):
        raise HeldoutDataError(
            f"The line {number} of the file {path} does not hold a usable case: the field evidence_ids is missing or "
            f"is not a list of strings."
        )
    if not isinstance(raw_evidence, list):
        raise HeldoutDataError(
            f"The line {number} of the file {path} does not hold a usable case: the field evidence is missing or is "
            f"not a list."
        )
    evidence: list[tuple[str, str]] = []
    for item in raw_evidence:
        if not isinstance(item, dict):
            raise HeldoutDataError(
                f"The line {number} of the file {path} does not hold a usable case: an item of the field evidence is "
                f"not an object."
            )
        item_id = _text_field(item, "id", path, number)
        content = _text_field(item, "content", path, number)
        evidence.append((item_id, content))
    return Case(
        id=identifier,
        claim=claim,
        evidence_ids=tuple(raw_ids),
        evidence=tuple(evidence),
    )


def load_cases(root: Path) -> list[Case]:
    """The cases of the set, in the order of the file.

    Why it exists: the file of the cases is what the reader sees. It carries no label, no template and no recipe, and
    the tool reads it as it is.
    """
    path = cases_path(root)
    return [_case_of(record, path, number) for number, record in _read_records(path)]


def load_recipes(root: Path) -> list[Recipe]:
    """The recipes of the set, in the order of the file. The reader never opens this file."""
    path = recipes_path(root)
    recipes: list[Recipe] = []
    for number, record in _read_records(path):
        identifier = _text_field(record, "id", path, number)
        recipes.append(
            Recipe(
                id=identifier,
                template=_first_text(record, _TEMPLATE_KEYS),
                expected_label=_first_text(record, _EXPECTED_KEYS),
                pair_id=_first_text(record, _PAIR_KEYS),
                differing_fact=_first_text(record, _FACT_KEYS),
            )
        )
    return recipes


def load_labels(root: Path, override: Path | None = None) -> list[ReaderLabel]:
    """The labels the reader has given so far, in the order of the file.

    Why it exists: the file of the labels is what makes the session resumable. A case with a label is a case that is
    done, and a case with two labels is a file that cannot be read, so it is refused with the file and the line.
    """
    path = labels_path(root, override)
    if not path.exists():
        return []
    labels: list[ReaderLabel] = []
    seen: dict[str, int] = {}
    for number, record in _read_records(path):
        identifier = _text_field(record, "id", path, number)
        label = _text_field(record, "label", path, number)
        if label not in LABELS:
            raise HeldoutDataError(
                f"The line {number} of the file {path} does not hold a usable label: {label} is not one of the "
                f"labels of the rule."
            )
        if identifier in seen:
            raise HeldoutDataError(
                f"The line {number} of the file {path} labels the case {identifier} a second time, and the first "
                f"label of that case is on the line {seen[identifier]}."
            )
        seen[identifier] = number
        note = record.get("note", "")
        if not isinstance(note, str):
            raise HeldoutDataError(
                f"The line {number} of the file {path} does not hold a usable label: the field note is not a string."
            )
        labels.append(ReaderLabel(id=identifier, label=label, note=note))
    return labels


def _append_label(path: Path, label: ReaderLabel) -> None:
    """The label of one case, appended to the file of the labels and flushed at once.

    Why it exists: a session that is interrupted loses nothing, because every label is on the disk before the next
    screen is shown.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"id": label.id, "label": label.label, "note": label.note}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        handle.flush()


def _evidence_of(identifier: str, content: str) -> Evidence:
    """The evidence of a case, as the schema of the repository holds it.

    Why it is built without the validation of the schema: the ids of the held out set are the ids of a synthetic
    world and the premise of the model reads only the content of the evidence. The ids and the moments of a run of
    the agent would say nothing here.
    """
    prefix = identifier.split(":", 1)[0]
    return Evidence.model_construct(
        id=identifier,
        source_type=_SOURCE_BY_PREFIX.get(prefix, "sql"),
        tool=_TOOL_BY_PREFIX.get(prefix, "query_ledger"),
        content=content,
        ref=identifier,
        retrieved_at=_RETRIEVED_AT,
    )


def premise_of(case: Case) -> str | None:
    """The premise the model will read for the case: the evidence rendered, focused and truncated.

    Why it exists: the reader has to judge the claim against the same text the NLI model will read, and not against
    the JSON envelope of the tool. The renderer of the repository builds it, so the reading is over the same premise.

    `None` when the case cites no evidence: there is no premise, and the reader is told so in words.
    """
    claim = Claim(id="CL1", text=case.claim, kind="fact", evidence_ids=list(case.evidence_ids))
    by_id = {identifier: _evidence_of(identifier, content) for identifier, content in case.evidence}
    max_chars = int(load_thresholds()["max_premise_chars"])
    return text_premise(claim, by_id, max_chars)


def render_screen(case: Case) -> str:
    """The screen of one case: the rule, the claim, the evidence as the model reads it and the three labels.

    Why it exists: the screen is everything the reader sees of the case. It never holds the recipe, the template, the
    expected label, the pair, the case before or the case after, because the reading is blind.
    """
    lines: list[str] = []
    lines.append("=" * 78)
    lines.append("THE RULE OF ADR-007 (it is the same on every screen)")
    lines.append("=" * 78)
    lines.append(RULE_ADR_007)
    lines.append("")
    lines.append(RULE_SELF_CONTRADICTION)
    lines.append("-" * 78)
    lines.append(f"{SCREEN_CASE_MARKER}{case.id}")
    lines.append("-" * 78)
    lines.append("CLAIM")
    lines.append(f"  {case.claim}")
    lines.append("")
    lines.append("EVIDENCE IDS THE CLAIM CITES")
    if case.evidence_ids:
        lines.extend(f"  {identifier}" for identifier in case.evidence_ids)
    else:
        lines.append("  (none)")
    lines.append("")
    lines.append("EVIDENCE AS THE MODEL WILL READ IT")
    premise = premise_of(case)
    if premise is None:
        lines.append("  (no evidence)")
    else:
        lines.extend(f"  {line}" for line in premise.splitlines())
    lines.append("")
    lines.append("LABELS (type one of them)")
    lines.extend(f"  [ ] {label}" for label in LABELS)
    return "\n".join(lines) + "\n"


class _Answers:
    """The lines the reader types, one at a time.

    Why it exists: the session has to run without a terminal, so the lines come from an iterable. The end of the
    iterable is the end of the session.
    """

    def __init__(self, lines: Iterable[str]) -> None:
        self._lines = iter(lines)

    def take(self) -> str | None:
        """The next line, or None when the reader typed nothing more."""
        try:
            return next(self._lines)
        except StopIteration:
            return None


def _parse_label(raw: str) -> str | None:
    """The label of a typed word, or None when the word is not a label of the rule."""
    key = raw.strip().lower().replace("-", "_").replace(" ", "_")
    return _LABEL_ALIASES.get(key)


def read_session(
    root: Path, answers: Iterable[str], out: TextIO, override: Path | None = None
) -> int:
    """Runs the reading session over the cases of the root and returns how many cases it labelled.

    Why it exists: this is the mode a person runs. It shows one case at a time, it saves every label as it is given,
    and it skips the cases that already carry a label, so a session that was interrupted resumes where it stopped.
    """
    cases = load_cases(root)
    done = {label.id for label in load_labels(root, override)}
    path = labels_path(root, override)
    typed = _Answers(answers)
    labelled = 0
    for case in cases:
        if case.id in done:
            continue
        out.write(render_screen(case))
        raw = _ask_label(typed, out)
        if raw is None:
            break
        label = _parse_label(raw)
        while label is None:
            out.write(
                "That is not a label of the rule. Type one of: supported, contradicted, not_enough_evidence.\n"
            )
            raw = _ask_label(typed, out)
            if raw is None:
                return labelled
            label = _parse_label(raw)
        out.write("Note (one sentence, an empty line is accepted): ")
        out.flush()
        note = typed.take()
        _append_label(path, ReaderLabel(id=case.id, label=label, note=(note or "").strip()))
        labelled += 1
        out.write("\n")
    out.write(f"The session stops here. {labelled} case(s) were labelled in this run.\n")
    return labelled


def _ask_label(typed: _Answers, out: TextIO) -> str | None:
    """The label the reader typed, or None when there is nothing more to read."""
    out.write("Label (supported, contradicted, not_enough_evidence): ")
    out.flush()
    return typed.take()


def _require_complete(cases: Sequence[Case], labels: Sequence[ReaderLabel], action: str) -> None:
    """Refuses an incomplete reading with a sentence that names how many cases are missing and which ones."""
    done = {label.id for label in labels}
    missing = [case.id for case in cases if case.id not in done]
    if not missing:
        return
    if len(missing) == 1:
        raise HeldoutIncompleteError(
            f"The reading is not complete: 1 case is missing ({missing[0]}), so the tool cannot {action}."
        )
    raise HeldoutIncompleteError(
        f"The reading is not complete: {len(missing)} cases are missing ({', '.join(missing)}), so the tool cannot "
        f"{action}."
    )


def _disagreements(
    cases: Sequence[Case], labels: Sequence[ReaderLabel], recipes: Sequence[Recipe]
) -> list[Disagreement]:
    """The cases where the label of the reader and the label of the recipe do not agree."""
    by_id = {label.id: label for label in labels}
    by_recipe = {recipe.id: recipe for recipe in recipes}
    found: list[Disagreement] = []
    for case in cases:
        recipe = by_recipe.get(case.id)
        label = by_id.get(case.id)
        if recipe is None or label is None or not recipe.expected_label:
            continue
        if label.label == recipe.expected_label:
            continue
        found.append(
            Disagreement(
                id=case.id,
                reader_label=label.label,
                expected_label=recipe.expected_label,
                template=recipe.template,
                pair_id=recipe.pair_id,
                differing_fact=recipe.differing_fact,
                note=label.note,
            )
        )
    return found


def _disagreement_sentence(disagreement: Disagreement) -> str:
    """The sentence that puts a disagreement on the record."""
    fact = (
        f" (the fact that differs: {disagreement.differing_fact})"
        if disagreement.differing_fact
        else ""
    )
    return (
        f"The reading disagrees with the recipe of the case: the reader answered {disagreement.reader_label} and "
        f"the recipe expected {disagreement.expected_label}{fact}."
    )


def _compose_note(reader_note: str, disagreement: Disagreement | None) -> str:
    """The note of a case: what the reader wrote, and the disagreement when there is one."""
    if disagreement is None:
        return reader_note
    sentence = _disagreement_sentence(disagreement)
    if not reader_note:
        return sentence
    return f"{reader_note} {sentence}"


def report_session(
    root: Path, out: TextIO, override: Path | None = None, origin: str = ORIGIN_ONE_READER
) -> int:
    """Compares the labels of the session with the recipes and prints the disagreements.

    Why it exists: the count of the disagreements is a measurement this repository has never had, and every instance
    of it has to be on the record. The report prints the count and writes the note of every disagreement into the
    labelled set, so the file that the manifest will declare carries the record.
    """
    cases = load_cases(root)
    labels = load_labels(root, override)
    _require_complete(cases, labels, "compare the reading with the recipes")
    disagreements = _disagreements(cases, labels, load_recipes(root))

    out.write("Reading compared with the recipes\n")
    out.write("=================================\n")
    if not disagreements:
        out.write("No case of the reading disagrees with a recipe.\n")
    else:
        for disagreement in disagreements:
            out.write(
                f"{disagreement.id}: the reader answered {disagreement.reader_label}, the recipe expected "
                f"{disagreement.expected_label}.\n"
            )
            if disagreement.template:
                out.write(f"  template: {disagreement.template}\n")
            if disagreement.pair_id:
                out.write(f"  pair: {disagreement.pair_id}\n")
            if disagreement.differing_fact:
                out.write(f"  the fact that differs: {disagreement.differing_fact}\n")
            out.write(f"  the note of the reader: {disagreement.note}\n")
            out.write("\n")
    out.write(f"\nDisagreements: {len(disagreements)} of {len(cases)}.\n")
    build_labelled_set(root, override, origin)
    return len(disagreements)


def build_labelled_set(
    root: Path, override: Path | None = None, origin: str = ORIGIN_ONE_READER
) -> Path:
    """Builds the labelled set of the held out set and returns the path of the file.

    Why it exists: the file is what the manifest of the datasets will declare with the role `held_out`. Every line
    carries the label the reader gave, the note of the reader, the origin that says the reading was a blind one, and
    the evidence as it was read. The recipe never overwrites the label of the reader.
    """
    cases = load_cases(root)
    labels = load_labels(root, override)
    _require_complete(cases, labels, "build the labelled set")
    recipes: list[Recipe] = []
    if recipes_path(root).exists():
        recipes = load_recipes(root)
    disagreements = {item.id: item for item in _disagreements(cases, labels, recipes)}
    by_id = {label.id: label for label in labels}

    lines: list[str] = []
    for case in cases:
        label = by_id[case.id]
        record = {
            "id": case.id,
            "claim": case.claim,
            "evidence_ids": list(case.evidence_ids),
            "evidence": [{"id": identifier, "content": content} for identifier, content in case.evidence],
            "label": label.label,
            "origin": origin,
            "note": _compose_note(label.note, disagreements.get(case.id)),
        }
        lines.append(json.dumps(record, ensure_ascii=False))

    path = labelled_set_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    return path


def compare_labels(
    root: Path, first: Path, second: Path, out: TextIO
) -> int:
    """Compares the labels of two readings of the same set and returns how many cases they disagree on.

    Why it exists: the disagreement between two readers who never saw each other is a measurement of the noise of a
    label that does not depend on the recipes of the generator at all. The recipes say what the writer expected; the
    two readers say what two careful readings of the same evidence produced. The first is a property of the
    generator, the second is a property of the rule.

    Why it never opens the recipes: the point of the comparison is to know the noise of the labels without the
    answer key anywhere near it.
    """
    labels_first = {label.id: label for label in load_labels(root, first)}
    labels_second = {label.id: label for label in load_labels(root, second)}
    cases = load_cases(root)
    _require_complete(cases, list(labels_first.values()), f"compare the reading {first}")
    _require_complete(cases, list(labels_second.values()), f"compare the reading {second}")
    out.write("Two readings of the same set, compared\n")
    out.write("=====================================\n")
    found = 0
    for case in cases:
        one = labels_first[case.id]
        two = labels_second[case.id]
        if one.label == two.label:
            continue
        found += 1
        out.write(f"{case.id}: the first reading answered {one.label}, the second answered {two.label}.\n")
        out.write(f"  the claim: {case.claim}\n")
        out.write(f"  the note of the first reading: {one.note}\n")
        out.write(f"  the note of the second reading: {two.note}\n")
        out.write("\n")
    out.write(f"\nDisagreements between the two readings: {found} of {len(cases)}.\n")
    return found


def main(argv: Sequence[str] | None = None) -> int:
    """The command line of the tool: the mode, and the root of the tree of the set.

    Why it returns a code and never a traceback: the reader of the failure is a person, and a data problem is a
    sentence.
    """
    parser = argparse.ArgumentParser(description="The blind reading session of the held out set.")
    parser.add_argument(
        "mode",
        choices=("read", "report", "build", "compare"),
        help="the mode of the tool",
    )
    parser.add_argument(
        "--root",
        default=str(PROJECT_ROOT),
        help="the root of the tree that holds the set (the project root by default)",
    )
    parser.add_argument(
        "--labels",
        default=None,
        help="the file of the labels of this reading, relative to the root (by default labels_v1.jsonl)",
    )
    parser.add_argument(
        "--origin",
        default=ORIGIN_ONE_READER,
        help="the origin that goes into every line of the labelled set (it says who read the cases)",
    )
    parser.add_argument(
        "--first",
        default=None,
        help="the file of the labels of the first reading, for the mode compare",
    )
    parser.add_argument(
        "--second",
        default=None,
        help="the file of the labels of the second reading, for the mode compare",
    )
    arguments = parser.parse_args(argv)
    root = Path(arguments.root).resolve()
    override = Path(arguments.labels) if arguments.labels else None
    try:
        if arguments.mode == "read":
            read_session(root, sys.stdin, sys.stdout, override)
        elif arguments.mode == "report":
            report_session(root, sys.stdout, override, arguments.origin)
        elif arguments.mode == "compare":
            if not arguments.first or not arguments.second:
                print("The mode compare needs the file of the labels of the two readings.", file=sys.stderr)
                return 1
            compare_labels(root, Path(arguments.first), Path(arguments.second), sys.stdout)
        else:
            path = build_labelled_set(root, override, arguments.origin)
            print(f"The labelled set was written: {path}.")
    except HeldoutError as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
