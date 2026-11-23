#!/usr/bin/env python3
"""The measurement of the verifier over the held out set of the verification.

Why it exists: the sweep of ADR-007 reads only the datasets with the role `tuning`, and every number the repository
published so far was measured over data a decision was taken against. The held out set is the first set that was
built to be measured and never tuned, so it needs a path of its own: this script measures the verifier over the
labelled file that the reading session of `scripts/label_heldout.py` builds, and it publishes the numbers with the
denominators they were measured over.

The script never decides a verdict of its own. The verifier of `ledgerlens/verify/checks.py` decides every case, and
the reader of `ledgerlens/eval/heldout_reader.py` reads the labelled file and builds the premises. The recipes of
the generator are a private input of the report: they give the template of each case and the label the generator
expected, and the report says how many of them the reading did not agree with, because that count is the noise a
label carries.

A number of this repository is never published without the model that produced it: the report names the model and
the thresholds, and a run with the stand-in of the rules says so in the report itself.

The refusals are sentences with an exit code that is not zero, never a traceback: the labelled file that does not
exist, the reading that left a case out, and the caller that insists on the real model when only the stand-in is
there.

Usage:

```bash
uv run python scripts/measure_heldout.py --labelled data/eval/verification_heldout.jsonl
uv run python scripts/measure_heldout.py --labelled data/eval/verification_heldout.jsonl --out report.md
uv run python scripts/measure_heldout.py --model stub
```

Exit code 0 when the measurement ran, 1 when the run refused, 2 when the model could not be measured with.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ledgerlens.config import offline as offline_mode  # noqa: E402  (the path is set up before the import)
from ledgerlens.eval.heldout import LABELS, RECIPES_PATH, TEMPLATES, load_recipes  # noqa: E402
from ledgerlens.eval.heldout_reader import (  # noqa: E402
    HeldoutCase,
    HeldoutError,
    heldout_counts,
    heldout_nli_cases,
    heldout_result,
    read_heldout_cases,
)
from ledgerlens.eval.manifest import safe_text  # noqa: E402
from ledgerlens.verify.checks import load_thresholds, verify_result  # noqa: E402
from ledgerlens.verify.nli import (  # noqa: E402
    HuggingFaceNli,
    Nli,
    StubNli,
    get_nli,
)

__all__ = [
    "CaseOutcome",
    "HeldoutMeasurement",
    "MeasureRefusal",
    "RecipeFact",
    "TemplateRow",
    "main",
    "measure_heldout",
    "model_name",
    "render_report",
    "select_nli",
]

# The exit code of a run that could not measure anything: the model was not there.
NO_MODEL = 2

# The file the reading session builds, relative to the root of the tree. It is the input of the measurement.
LABELLED_SET_RELATIVE = Path("data") / "eval" / "verification_heldout.jsonl"

# The method of a verdict that the verifier decided by itself, without the model.
CODE_METHOD = "none"


class MeasureRefusal(Exception):
    """The measurement cannot run, and the message says why in one plain English sentence.

    Why it exists: the reader of the failure is a person, and a data problem is a sentence, the way `HeldoutError`
    of the reader of the set is a sentence.
    """


@dataclass(frozen=True)
class RecipeFact:
    """What the recipes of the generator say about a case: its template and the label it expected.

    Why it exists: the template of a case is not in the labelled file, and the report needs it. The recipe is a
    private input of the report and never a label: the label of the reader is the one the verifier is measured
    against.
    """

    case_id: str
    template: str
    expected_label: str


@dataclass(frozen=True)
class CaseOutcome:
    """One case of the set as the verifier judged it, next to the label the reader gave.

    Why it exists: the per case list is the part a reader uses to disagree with the number, so it carries the claim,
    both labels, the method that decided the case and the note of the reader.
    """

    case_id: str
    claim: str
    reader_label: str
    verdict_label: str
    method: str
    template: str
    correct: bool
    note: str
    verifier_note: str


@dataclass(frozen=True)
class TemplateRow:
    """One template of the set: how many cases it has, how the reader labelled them and how many were right.

    Why it exists: the templates are the shapes of the claims, and a number that hides the template hides the shape
    that fails. The reader of the report sees which shape the verifier handles badly.
    """

    template: str
    total: int
    reader_counts: Mapping[str, int]
    correct: int


@dataclass(frozen=True)
class HeldoutMeasurement:
    """The measurement of the verifier over the labelled held out set.

    Why it exists: a number over a set is honest only when its denominator is known and when the cases behind it can
    be read one by one. The record carries the denominators, the counts of both labels, the matrix of the two, the
    table by template, the count of the disagreements of the reading with the recipes and the list of the cases.
    """

    total: int
    model_total: int
    code_total: int
    correct: int
    model_correct: int
    false_supported: int
    false_contradicted: int
    reader_counts: Mapping[str, int]
    verifier_counts: Mapping[str, int]
    matrix: Mapping[tuple[str, str], int]
    by_template: tuple[TemplateRow, ...]
    disagreements: int
    disagreement_ids: tuple[str, ...]
    cases: tuple[CaseOutcome, ...]
    labelled_path: str
    recipes_path: str

    @property
    def accuracy(self) -> Decimal:
        """The accuracy over every case of the set, with its denominator."""
        return _rate(self.correct, self.total)

    @property
    def model_accuracy(self) -> Decimal:
        """The accuracy over the cases the model judged, with its denominator."""
        return _rate(self.model_correct, self.model_total)


def _rate(numerator: int, denominator: int) -> Decimal:
    """The rate of a count over its denominator, with three decimals and no division by zero."""
    if denominator <= 0:
        return Decimal("0.000")
    return (Decimal(numerator) / Decimal(denominator)).quantize(Decimal("0.001"))


def model_name(nli: Nli) -> str:
    """The name of the thing that produced the verdicts, as the report shows it.

    Why it exists: a number without the model that produced it is not a number of this repository. The real model
    says its id, the stand-in of the rules says that it is not the model, and a predictor that a test injected says
    that it is not a model of the repository either.
    """
    if isinstance(nli, HuggingFaceNli):
        return f"{nli.model_id} (the real model)"
    if isinstance(nli, StubNli):
        return "StubNli (the deterministic stand-in of the rules, not the model)"
    return f"{type(nli).__name__} (an injected predictor, not a model of the repository)"


def select_nli(choice: str = "auto") -> Nli:
    """The model that produces the verdicts, and a refusal when the caller asked for one that is not there.

    Why it exists: the caller may insist on the real model, because a number measured with the stand-in measures
    the rules of the stand-in. `auto` takes the real model when the `verify` extra is installed and the stand-in
    otherwise, and every run says which one it took.
    """
    if choice == "stub":
        return get_nli(offline=True)
    if choice == "real":
        if offline_mode():
            raise MeasureRefusal(
                "the real NLI model cannot be measured with in offline mode, because LEDGERLENS_OFFLINE=1 replaces "
                "it with the stand-in. Run the script without it."
            )
        try:
            return get_nli(require_real=True)
        except RuntimeError as error:
            raise MeasureRefusal(f"{error}.") from error
    return get_nli()


def read_recipes(path: Path) -> tuple[RecipeFact, ...]:
    """The recipes of the generator, in the order of the file.

    Why it exists: the template of a case is not in the labelled file, and the report needs it. The reader of the
    set never sees this file: it is a private input of the report.

    Raises `MeasureRefusal` when the file cannot be read or holds a line that is not a recipe.
    """
    if not path.exists():
        raise MeasureRefusal(
            f"The file {safe_text(path)} does not exist, so the template of the cases and the labels of the "
            f"generator are unknown."
        )
    try:
        records = load_recipes(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MeasureRefusal(f"The file {safe_text(path)} could not be read: {error}.") from error

    recipes: list[RecipeFact] = []
    for number, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise MeasureRefusal(
                f"The line {number} of the file {safe_text(path)} is not a JSON object, so it is not a recipe."
            )
        case_id = record.get("id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise MeasureRefusal(
                f"The line {number} of the file {safe_text(path)} has no id, so it is not a recipe."
            )
        template = record.get("template")
        expected = record.get("label")
        recipes.append(
            RecipeFact(
                case_id=case_id,
                template=template if isinstance(template, str) else "",
                expected_label=expected if isinstance(expected, str) else "",
            )
        )
    return tuple(recipes)


def measure_heldout(labelled_path: Path, recipes_path: Path, *, nli: Nli) -> HeldoutMeasurement:
    """The measurement of the verifier over the labelled held out set.

    Why it exists: the number of this repository that is measured over data no decision was taken against. Every
    case is judged by the real verifier of `ledgerlens/verify/checks.py`, the label of the reader is the label the
    verifier is measured against, and the recipes of the generator give the template of each case and the count of
    the disagreements of the reading with them.

    The predictor is a parameter, so a test can measure the same path with a predictor of its own and the model is
    never downloaded.

    Raises `MeasureRefusal` when the labelled file does not exist, when the reading is not complete, when the file
    of the recipes does not exist and when the reader and the verifier do not agree about which cases the model
    reads.
    """
    cases = _read_cases(labelled_path)
    recipes = read_recipes(recipes_path)
    _require_complete(cases, recipes)

    by_id = {recipe.case_id: recipe for recipe in recipes}
    outcomes: list[CaseOutcome] = []
    for case in cases:
        verdict = verify_result(heldout_result(case), nli=nli).verdicts[0]
        recipe = by_id.get(case.case_id)
        outcomes.append(
            CaseOutcome(
                case_id=case.case_id,
                claim=case.claim,
                reader_label=case.label,
                verdict_label=verdict.label,
                method=verdict.method,
                template=recipe.template if recipe is not None else "",
                correct=verdict.label == case.label,
                note=case.note,
                verifier_note=verdict.note or "",
            )
        )

    counts = heldout_counts(labelled_path)
    model_ids = {item.case_id for item in heldout_nli_cases(cases) if item.needs_model}
    model_total = len(model_ids)
    code_total = len(outcomes) - model_total
    if (model_total, code_total) != (counts.nli, counts.decided_by_code):
        raise MeasureRefusal(
            f"The reader counted {counts.nli} case(s) that go to the model and {counts.decided_by_code} that the "
            f"code decides, while the measurement found {model_total} and {code_total}: the numbers do not agree, so "
            f"no measurement is published."
        )

    reader_counts = {label: sum(1 for item in outcomes if item.reader_label == label) for label in LABELS}
    verifier_counts = {label: sum(1 for item in outcomes if item.verdict_label == label) for label in LABELS}
    matrix = {
        (reader, verifier): sum(
            1 for item in outcomes if item.reader_label == reader and item.verdict_label == verifier
        )
        for reader in LABELS
        for verifier in LABELS
    }
    false_supported = sum(
        1 for item in outcomes if item.verdict_label == "supported" and item.reader_label != "supported"
    )
    false_contradicted = sum(
        1 for item in outcomes if item.verdict_label == "contradicted" and item.reader_label != "contradicted"
    )
    disagreements = tuple(
        item.case_id
        for item in outcomes
        if by_id.get(item.case_id) is not None
        and by_id[item.case_id].expected_label
        and by_id[item.case_id].expected_label != item.reader_label
    )

    return HeldoutMeasurement(
        total=counts.total,
        model_total=model_total,
        code_total=code_total,
        correct=sum(1 for item in outcomes if item.correct),
        model_correct=sum(1 for item in outcomes if item.case_id in model_ids and item.correct),
        false_supported=false_supported,
        false_contradicted=false_contradicted,
        reader_counts=reader_counts,
        verifier_counts=verifier_counts,
        matrix=matrix,
        by_template=_by_template(outcomes),
        disagreements=len(disagreements),
        disagreement_ids=disagreements,
        cases=tuple(outcomes),
        labelled_path=str(labelled_path),
        recipes_path=str(recipes_path),
    )


def _relative(path: Path | str) -> str:
    """The path of a file as the repository names it, and never as the machine does.

    Why it exists: the report is written into the tree and committed, and a path that starts with the home of the
    machine that wrote it is a path that says more about the machine than about the repository. The test of the
    public clean tree refuses a file that carries one.
    """
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(Path(__file__).resolve().parent.parent))
    except ValueError:
        return resolved.name


def render_report(
    measurement: HeldoutMeasurement,
    *,
    model: str,
    thresholds: Mapping[str, Any] | None = None,
) -> str:
    """The report of the measurement, in Markdown, as it is printed and as it is written.

    Why it exists: the report is the only place where the numbers of this measurement live, so it carries the model
    that produced them, the thresholds that were applied, the denominators of every rate, the matrix of the two
    labels, the count of the false supported, the table by template, the count of the disagreements of the reading
    with the recipes and the list of every case.
    """
    values = dict(thresholds or load_thresholds())
    lines: list[str] = []
    lines.append("# The verification over the held out set")
    lines.append("")
    lines.append(f"the model that produced the verdicts: {model}")
    lines.append(
        "the thresholds applied: entailment_min "
        f"{values.get('entailment_min')}, contradiction_min {values.get('contradiction_min')}, "
        f"max_premise_chars {values.get('max_premise_chars')} "
        "(the pinned ones of ledgerlens/verify/thresholds.json)"
    )
    lines.append(f"the labelled file: {_relative(measurement.labelled_path)}")
    lines.append(
        "the recipes of the generator (a private input of the report, not published, never a label): "
        f"{_relative(measurement.recipes_path)}"
    )
    lines.append("")

    lines.append("## Accuracy")
    lines.append("")
    lines.append(f"- over the set: {measurement.correct}/{measurement.total} ({measurement.accuracy})")
    lines.append(
        f"- over the cases the model judged: {measurement.model_correct}/{measurement.model_total} "
        f"({measurement.model_accuracy})"
    )
    lines.append(f"- decided by the code, without the model: {measurement.code_total}")
    lines.append("")

    lines.append("## The confusion matrix")
    lines.append("")
    lines.append("| the reader \\ the verifier | " + " | ".join(LABELS) + " | total |")
    lines.append("|---" * (len(LABELS) + 2) + "|")
    for reader in LABELS:
        cells = [str(measurement.matrix[(reader, verifier)]) for verifier in LABELS]
        lines.append(f"| {reader} | " + " | ".join(cells) + f" | {measurement.reader_counts[reader]} |")
    totals = [str(measurement.verifier_counts[verifier]) for verifier in LABELS]
    lines.append("| total | " + " | ".join(totals) + f" | {measurement.total} |")
    lines.append("")
    lines.append(
        "the verifier said: "
        + ", ".join(f"{verifier} {measurement.verifier_counts[verifier]}" for verifier in LABELS)
    )
    lines.append(
        "the reader said: " + ", ".join(f"{reader} {measurement.reader_counts[reader]}" for reader in LABELS)
    )
    lines.append("")
    lines.append(f"the false supported: {measurement.false_supported}")
    lines.append(f"the false contradicted: {measurement.false_contradicted}")
    lines.append("")

    lines.append("## The table by template")
    lines.append("")
    lines.append("| template | cases | " + " | ".join(f"the reader said {label}" for label in LABELS) + " | right |")
    lines.append("|---" * (len(LABELS) + 3) + "|")
    for row in measurement.by_template:
        cells = [str(row.reader_counts[label]) for label in LABELS]
        lines.append(f"| {row.template} | {row.total} | " + " | ".join(cells) + f" | {row.correct} |")
    lines.append("")

    lines.append("## The reader and the recipes")
    lines.append("")
    lines.append(
        f"the reading disagrees with the recipe of {measurement.disagreements} case(s) of {measurement.total}"
        + (f": {', '.join(measurement.disagreement_ids)}" if measurement.disagreement_ids else "")
    )
    lines.append("")

    lines.append("## The cases")
    lines.append("")
    lines.append("| id | the claim | the reader | the verifier | the method | the note |")
    lines.append("|---|---|---|---|---|---|")
    for item in measurement.cases:
        note = item.note or item.verifier_note
        lines.append(
            f"| {item.case_id} | {_cell(item.claim)} | {item.reader_label} | {item.verdict_label} | "
            f"{item.method} | {_cell(note)} |"
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """The command line of the measurement: the labelled file, the model and where the report is written.

    Why it returns a code and never a traceback: the reader of the failure is a person, and a refusal is a sentence.
    """
    parser = argparse.ArgumentParser(
        description="Measures the verifier over the labelled held out set of the verification.",
    )
    parser.add_argument("--root", default=str(ROOT), help="the root the relative paths resolve against")
    parser.add_argument(
        "--labelled",
        default=str(LABELLED_SET_RELATIVE),
        help="the labelled file of the held out set, the input of the measurement",
    )
    parser.add_argument(
        "--recipes",
        default=str(RECIPES_PATH),
        help="the recipes of the generator, the private input of the report",
    )
    parser.add_argument(
        "--model",
        choices=("auto", "real", "stub"),
        default="auto",
        help="the model that produces the verdicts: the real one, the stand-in, or the one that is there",
    )
    parser.add_argument("--out", default=None, help="the Markdown file the report is written to")
    arguments = parser.parse_args(argv)

    root = Path(arguments.root).resolve()
    labelled = _resolve(root, arguments.labelled)
    recipes = _resolve(root, arguments.recipes)

    try:
        nli = select_nli(arguments.model)
    except MeasureRefusal as error:
        return _refuse(str(error))

    try:
        measurement = measure_heldout(labelled, recipes, nli=nli)
    except MeasureRefusal as error:
        return _refuse(str(error))
    except Exception as error:  # the model may be missing, unreachable or broken: it is a sentence and not a pass
        return _refuse(f"the measurement could not run: {safe_text(error)}", code=NO_MODEL)

    report = render_report(measurement, model=model_name(nli))
    print(report)

    if arguments.out:
        out = _resolve(root, arguments.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
    return 0


def _read_cases(path: Path) -> tuple[HeldoutCase, ...]:
    """The cases of the labelled file, or a refusal that says why in one sentence."""
    if not path.exists():
        raise MeasureRefusal(
            f"The file {safe_text(path)} does not exist, so there is nothing to measure. The labelled set is built "
            f"with `uv run python scripts/label_heldout.py build`."
        )
    try:
        return read_heldout_cases(path)
    except HeldoutError as error:
        raise MeasureRefusal(str(error)) from error


def _require_complete(cases: Sequence[HeldoutCase], recipes: Sequence[RecipeFact]) -> None:
    """Refuses a reading that left a case out, and names the cases that are missing."""
    have = {case.case_id for case in cases}
    wanted = {recipe.case_id for recipe in recipes}
    missing = sorted(wanted - have)
    if missing:
        raise MeasureRefusal(
            f"The reading is not complete: {len(missing)} case(s) of the set have no line in the labelled file "
            f"({', '.join(missing)}), so a measurement over it would be a number over fewer cases than the set holds."
        )
    extra = sorted(have - wanted)
    if extra:
        raise MeasureRefusal(
            f"The labelled file holds {len(extra)} case(s) the set does not have ({', '.join(extra)}), so it is not "
            f"the labelled set of the set and no measurement is published."
        )


def _by_template(outcomes: Sequence[CaseOutcome]) -> tuple[TemplateRow, ...]:
    """The table by template: the cases of each template, the labels of the reader and the cases that were right.

    Why it exists: the templates are the shapes of the claims of the set, and the six of them are declared by the
    generator. The order of the declaration is the order of the table, and a template that is not one of them comes
    last, so the table never hides a shape.
    """
    names = [name for name in TEMPLATES]
    names.extend(sorted({item.template for item in outcomes} - set(TEMPLATES)))
    rows: list[TemplateRow] = []
    for name in names:
        of_template = [item for item in outcomes if item.template == name]
        if not of_template:
            continue
        rows.append(
            TemplateRow(
                template=name,
                total=len(of_template),
                reader_counts={
                    label: sum(1 for item in of_template if item.reader_label == label) for label in LABELS
                },
                correct=sum(1 for item in of_template if item.correct),
            )
        )
    return tuple(rows)


def _cell(text: str) -> str:
    """A text that fits in a cell of a Markdown table: no bar and no line break."""
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _resolve(root: Path, value: str) -> Path:
    """A path that is relative to the root when it is not absolute."""
    path = Path(value)
    return path if path.is_absolute() else root / path


def _refuse(message: str, *, code: int = 1) -> int:
    """A refusal: one sentence on the error output and an exit code that is not zero."""
    print(f"measure_heldout: {message}", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
