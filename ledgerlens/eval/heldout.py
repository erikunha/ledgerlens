"""The generator of the held out set: the cases a person reads and the recipes that person never sees.

Why it exists: the verifier of the repository was calibrated against two sets, and every number it published since
was a number over a set nobody held back. The milestone that closes that gap needs a set that a person labelled
without seeing how it was built, and the machine half of that work is this module. It writes the cases, it keeps the
recipe of each case in a second file, and it proves, before anybody reads a sentence, that the set is different from
the tuning material, that no case names a record of the tuning material, that the pairs of the set differ by one
fact, and that the recipes are not in the file the person reads.

The split is the point of the module. The generator writes the cases. One person reads the labels, blind to the
recipe of each case. The recipe and the label are allowed to disagree, and the disagreement counts: it is the
measure of the set.

What the module holds:

- **Six named templates, eight instances each.** A hedge, a compound whose evidence carries only one of its two
  facts, a negation inside the sentence, a relative clause about a period, a number written as a range, and a
  premise that concatenates two tools at once.
- **Three negative controls**, among the 48: a claim that cites no evidence at all, a claim whose evidence
  contradicts itself, and a benign claim the evidence does not support.
- **Pairs certified by code.** Two cases share the template and the record and change one fact, and the recipe names
  the fact that changes.
- **An exclusion that is read, not written.** The ids of the tuning material are read from the tuning datasets and
  from the manifest of the scenarios when the set is built, so a case of the set can never name a record the tuning
  material names. The synthetic ledger reuses the id space of the sample ledger, so the exclusion is not automatic.
- **A novelty test.** The shape of the held out set differs from the shape of both tuning sets, and no claim of the
  set is closer to a claim of the tuning material than the ceiling of the token overlap.

The file the person reads holds no label, no template name and no recipe. `data/eval/heldout/cases.jsonl` holds the
claim and the evidence of each case; `data/eval/heldout/recipes.jsonl` holds the label, the template, the pair and
the fact that differs. The folder sits outside the scan of `data/eval/*.jsonl`, so the set is not a dataset of the
manifest until the coordinator declares it.

The ledger the cases come from is the synthetic one of the seed 7301, built with the simulator of the repository and
read with `sqlite3` in the style of `ledgerlens/eval/dataset.py`. The module never writes to the database and never
imports the API.

Usage:

```python
from ledgerlens.eval.heldout import build_cases, build_recipes, write_held_out

cases = build_cases()        # the 48 cases, in the order of the file
recipes = build_recipes()    # the recipe of each case, in the same order
write_held_out()             # the two files of the folder
```
"""

from __future__ import annotations

import atexit
import json
import random
import re
import shutil
import sqlite3
import tempfile
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from ledgerlens.config import PROJECT_ROOT

__all__ = [
    "CASES_PATH",
    "CASE_COUNT",
    "CONTROL_BENIGN_UNSUPPORTED",
    "CONTROL_NO_EVIDENCE",
    "CONTROL_SELF_CONTRADICTION",
    "HELD_OUT_SEED",
    "INSTANCES_PER_TEMPLATE",
    "LABELS",
    "RECIPES_PATH",
    "TEMPLATES",
    "TOKEN_OVERLAP_CEILING",
    "build_cases",
    "build_recipes",
    "claim_shapes",
    "is_tuning_id",
    "label_distribution",
    "load_cases",
    "load_recipes",
    "main",
    "premise_contradiction",
    "premise_shapes",
    "shape_inventory",
    "synthetic_ledger",
    "token_overlap",
    "tuning_dataset_ids",
    "tuning_ids",
    "tuning_material_paths",
    "write_held_out",
]

# The seed of the set. It is not the default of the simulator (42), so the world of the cases is not the world of any
# other artifact of the repository, and the ledger it builds is the same on every run.
HELD_OUT_SEED = 7301

# The six templates of the set, in the order they are declared. The name says the shape of the claim, and it never
# appears in the file the person reads.
TEMPLATES: tuple[str, ...] = (
    "hedge_shape",
    "compound_shape",
    "negation_shape",
    "relative_period_shape",
    "range_shape",
    "two_source_shape",
)

# How many cases the set holds and how many instances each template has in it.
CASE_COUNT = 48
INSTANCES_PER_TEMPLATE = 8

# The ceiling of the token overlap between a claim of the set and a claim of the tuning material. Two texts that
# share more than this share their wording, and a set of cases that repeats the wording of the tuning material is
# not a set of new cases.
TOKEN_OVERLAP_CEILING = 0.3

# The labels the verifier uses. The recipe of a case carries one of them, and the person who reads the case may
# disagree with it.
LABELS: tuple[str, ...] = ("supported", "contradicted", "not_enough_evidence")

# The three negative controls of the set.
CONTROL_NO_EVIDENCE = "no_evidence"
CONTROL_SELF_CONTRADICTION = "self_contradicting_premise"
CONTROL_BENIGN_UNSUPPORTED = "benign_unsupported"

# The two files of the set. The folder sits outside the scan of `data/eval/*.jsonl`, so neither file is a dataset of
# the manifest until the coordinator declares the labelled set.
HELDOUT_DIR = PROJECT_ROOT / "data" / "eval" / "heldout"
CASES_PATH = HELDOUT_DIR / "cases.jsonl"
RECIPES_PATH = HELDOUT_DIR / "recipes.jsonl"

# The manifest of the datasets and the manifest of the scenarios. The first says which datasets may be tuned
# against; the second names the records the scenarios planted.
MANIFEST_PATH = PROJECT_ROOT / "data" / "eval" / "datasets.json"
SCENARIOS_PATH = PROJECT_ROOT / "data" / "scenarios.json"
_TUNING_ROLE = "tuning"

# The shape of an id of the ledger. The same shape the module writes in the exclusion and the one a reader of the
# set sees in a claim.
_ID = re.compile(r"\b(?:TX|R|CB|ST|C|M|FX)-\d{2,4}\b")

# The markers of the shapes of a claim. They are read from the text of the claim, so the shape of a case of the
# tuning material and the shape of a case of this set are measured with the same rule.
_HEDGE_MARKERS = ("it appears that", "probably", "likely", "seems to", "appears to")
_NEGATION_MARKERS = (" not ", " never ", " no ", "n't", "cannot ")
_RELATIVE_MARKERS = (" whose ", " which ", " who ", " whom ")
_RANGE_PHRASE = re.compile(r"\bbetween\b[^.]*?\band\b")
_RANGE = re.compile(r"\bbetween\s+\d[^.]*?\band\s+\d")
_WORD = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")

# The statuses a claim may carry. A status that is not the truth of the record makes a claim the evidence
# contradicts.
_STATUSES = (
    "captured",
    "refunded",
    "partially_refunded",
    "failed",
    "disputed",
    "charged_back",
    "authorized",
)

# The readable form of a status. A claim is read by a person and the ledger writes a status with an underscore.
_STATUS_TEXT = {
    "captured": "captured",
    "refunded": "refunded",
    "partially_refunded": "partially refunded",
    "failed": "failed",
    "disputed": "disputed",
    "charged_back": "charged back",
    "authorized": "authorized",
}

# The reasons a refund of the ledger carries. A reason that is not the reason of the record makes a claim the
# evidence contradicts.
_REASONS = (
    "Customer cancelled the order",
    "Charge not recognized by the customer",
    "Item damaged in delivery",
    "Product returned",
    "outside_refund_window",
    "Changed mind about the purchase",
)

# The policy excerpts the two tool premises quote. The chunk id is the id the tool `search_policies` returns.
_PROCESSING_TIME_CHUNK = "refund-policy#processing-time"
_NEGATIVE_NET_CHUNK = "settlement-schedule#negative-net"

# The ledger of a seed, built once per process and kept alive for as long as the process lives.
_LEDGERS: dict[int, Path] = {}
_LEDGER_WORK: list[str] = []


def _cleanup_ledgers() -> None:
    """The temporary folders of the ledgers of this process, removed when the process ends."""
    for work in _LEDGER_WORK:
        shutil.rmtree(work, ignore_errors=True)


atexit.register(_cleanup_ledgers)


def tuning_material_paths() -> tuple[Path, ...]:
    """The files of the tuning material: the datasets whose role is tuning and the manifest of the scenarios.

    Why it is read and not written: the role of a dataset is what says what may be done with it, and a list of files
    written by hand drifts the day a dataset changes its role. The manifest of the scenarios is part of the material
    because the scenarios planted the records the tuning cases talk about.
    """
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    paths = [
        PROJECT_ROOT / entry["path"] for entry in manifest["datasets"] if entry["split_role"] == _TUNING_ROLE
    ]
    paths.append(SCENARIOS_PATH)
    return tuple(paths)


def tuning_dataset_ids() -> frozenset[str]:
    """The ids of the datasets whose role is tuning."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return frozenset(entry["dataset_id"] for entry in manifest["datasets"] if entry["split_role"] == _TUNING_ROLE)


def tuning_ids() -> frozenset[str]:
    """The ids of the records that the tuning material names.

    Why it is read from the material and not written here: the exclusion of the tuning material is the promise that
    a case of the set is a case nobody has worked on, and a list of ids written by hand is a promise that goes stale
    the day the material moves.
    """
    found: set[str] = set()
    for path in tuning_material_paths():
        found |= set(_ID.findall(path.read_text(encoding="utf-8")))
    return frozenset(found)


def is_tuning_id(identifier: str) -> bool:
    """Whether the id belongs to the tuning material, be it the id of a dataset or the id of a record."""
    return identifier in tuning_dataset_ids() or identifier in tuning_ids()


def synthetic_ledger(seed: int = HELD_OUT_SEED) -> Path:
    """The database of the synthetic ledger of the seed, built once per process.

    Why the simulator builds it and this module does not write it: the ledger of the set is the ledger of the
    repository, with its own rules, its own ids and its own determinism. The module reads it and never writes to it.
    """
    if seed not in _LEDGERS:
        from ledgerlens.sim.config import SimConfig
        from ledgerlens.sim.pipeline import build_ledger

        work = tempfile.mkdtemp(prefix=f"ledgerlens_heldout_{seed}_")
        _LEDGER_WORK.append(work)
        path = Path(work) / "ledger.db"
        build_ledger(SimConfig(source="synthetic", seed=seed, days=90, scenarios=()), path).conn.close()
        _LEDGERS[seed] = path
    return _LEDGERS[seed]


def claim_shapes(claim: str) -> frozenset[str]:
    """The shapes of a claim, read from the text of the claim.

    The shapes are the features the novelty test compares: a hedge, a conjunction of two facts, a negation, a
    relative clause and a number written as a range. The "and" of a "between" phrase is not the conjunction of two
    facts, so the phrase is taken out of the text before the conjunction is looked for, and a range only counts when
    both of its ends are numbers.
    """
    text = f" {claim.lower().strip()} "
    shapes: set[str] = set()
    if any(marker in text for marker in _HEDGE_MARKERS):
        shapes.add("hedge")
    if any(marker in text for marker in _NEGATION_MARKERS):
        shapes.add("negation")
    if any(marker in text for marker in _RELATIVE_MARKERS):
        shapes.add("relative_period")
    if _RANGE.search(text):
        shapes.add("range")
    outside = _RANGE_PHRASE.sub(" ", text)
    if " and " in outside:
        shapes.add("compound")
    return frozenset(shapes)


def premise_shapes(record: Mapping[str, Any]) -> frozenset[str]:
    """The shapes of the premise of a case, read from the evidence the case cites.

    The premise of a case is empty, it comes from one tool, or it comes from two tools at once. The last one is the
    shape the tuning sets do not have, so it is part of the inventory that the novelty test compares.
    """
    items, tools = _premise_items(record)
    if not items:
        return frozenset({"no_evidence_premise"})
    if len(tools) >= 2:
        return frozenset({"multi_source_premise"})
    return frozenset({"single_source_premise"})


def shape_inventory(records: Iterable[Mapping[str, Any]]) -> frozenset[str]:
    """The shapes of a set of cases: the shapes of the claims and the shapes of the premises.

    Why it skips the records without a claim: a coherence case holds several claims and a numeric case holds an
    amount, and neither is a case of the shape this set is made of.
    """
    shapes: set[str] = set()
    for record in records:
        claim = record.get("claim")
        if not isinstance(claim, str) or not claim.strip():
            continue
        shapes |= claim_shapes(claim)
        shapes |= premise_shapes(record)
    return frozenset(shapes)


def token_overlap(left: str, right: str) -> float:
    """The share of the words the two texts have in common, from 0 to 1.

    Why it is the Jaccard of the words: two texts that share a wording share their words, and the ids and the dates
    of the ledger are words like any other, so a case that repeats a tuning case shows up here. An id and a date
    count as one word each, because the day of a claim is one thing and not three.
    """
    first, second = _words(left), _words(right)
    if not first or not second:
        return 0.0
    return len(first & second) / len(first | second)


def premise_contradiction(case: Mapping[str, Any]) -> str | None:
    """The description of the contradiction of the premise of a case, or None when the premise holds none.

    Why it exists: the set carries a control whose evidence contradicts itself, and the machine has to see it
    without a person reading the file. The rule is the rule of the data: a settlement row that says a payout was
    made for a period whose net amount is negative, together with the rule that says a negative period gets no
    payout. The two items of the premise say opposite things about the same payout.
    """
    ledger = [text for text in _contents(case) if text.startswith("ledger/")]
    policies = [text for text in _contents(case) if text.startswith("policy/")]
    for row in ledger:
        if not _NEGATIVE_NET.search(row):
            continue
        if "status paid" not in row:
            continue
        if any("no payout is made" in text for text in policies):
            return (
                "the record shows a payout for a period with a negative net amount and the rule says that a period "
                "with a negative net amount gets no payout"
            )
    return None


def label_distribution(recipes: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    """How many cases of the set carry each label."""
    return dict(sorted(Counter(str(recipe["label"]) for recipe in recipes).items()))


def build_cases(seed: int = HELD_OUT_SEED) -> list[dict[str, Any]]:
    """The 48 cases of the set, in the order of the file.

    Why it is deterministic: the seed fixes the ledger, the ledger fixes the records, and the order of the file is
    a scatter of the records that the seed fixes too. The same seed always gives the same cases and the same bytes.
    """
    cases, _recipes = _generate(seed)
    return cases


def build_recipes(seed: int = HELD_OUT_SEED) -> list[dict[str, Any]]:
    """The recipe of each case of the set, in the order of the file.

    The recipe holds the label the generator expects, the template of the case, the pair it belongs to and the fact
    that the pair changes. It is never shown to the person who reads the cases.
    """
    _cases, recipes = _generate(seed)
    return recipes


def write_held_out(
    seed: int = HELD_OUT_SEED,
    cases_path: Path = CASES_PATH,
    recipes_path: Path = RECIPES_PATH,
) -> tuple[Path, Path]:
    """Writes the two files of the set and returns their paths.

    Why the two files are written together: the recipes file is the recipe of the cases file, and a set whose
    recipes are of another set is a set nobody can read blind.
    """
    cases, recipes = _generate(seed)
    _write_jsonl(cases_path, cases)
    _write_jsonl(recipes_path, recipes)
    return cases_path, recipes_path


def load_cases(path: Path = CASES_PATH) -> list[dict[str, Any]]:
    """The cases of the file, in the order of the file."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_recipes(path: Path = RECIPES_PATH) -> list[dict[str, Any]]:
    """The recipes of the file, in the order of the file."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    """Regenerates the two files of the set over the synthetic ledger of the seed."""
    cases_path, recipes_path = write_held_out()
    print(f"{len(load_cases(cases_path))} cases in {cases_path}")
    print(f"{len(load_recipes(recipes_path))} recipes in {recipes_path}")


# ---- the build of the set ---------------------------------------------------------------------------
# The rest of the module is the build itself: the queries that read the ledger, the renderings of the records, the
# templates and the pairs. It is kept apart from the public part so the reader of the module finds the contract of
# the set first.

_NEGATIVE_NET = re.compile(r"\| net (-\d+(?:\.\d+)?) [A-Z]{3} \|")


def _contents(case: Mapping[str, Any]) -> list[str]:
    """The content of every evidence a case cites."""
    return [str(item.get("content", "")) for item in case.get("evidence", []) if isinstance(item, Mapping)]


def _premise_items(record: Mapping[str, Any]) -> tuple[list[str], set[str]]:
    """The items of the premise of a case and the tools they come from.

    Why it reads every shape of evidence: the inventory of the shape has to compare the cases of this set with the
    cases of the tuning sets, and the first tuning set carries a prose evidence, the second carries rendered
    envelopes. A record without a list of evidence but with a calculation carries one premise as well.
    """
    raw = record.get("evidence")
    items: list[str] = []
    tools: set[str] = set()
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, Mapping):
                identifier = str(item.get("id", ""))
                items.append(identifier)
                tools.add(identifier.split(":")[0])
            elif isinstance(item, str):
                items.append(item)
                tools.add("prose")
    elif isinstance(raw, str):
        items.append(raw)
        tools.add("prose")
    elif "calc" in record:
        items.append("calc:1")
        tools.add("calc")
    return items, tools


def _words(text: str) -> set[str]:
    """The words of a text, in lower case."""
    return set(_WORD.findall(text.lower()))


def _money(minor: int, currency: str) -> str:
    """The amount of the ledger in the currency of the record.

    Why it comes from `Decimal`: an amount of money is never a float, and the rounding of the platform is round half
    to even.
    """
    return f"{(Decimal(minor) / 100).quantize(Decimal('0.01'))} {currency}"


def _day(value: str) -> str:
    """The day of an instant of the ledger."""
    return value[:10]


def _shifted_day(value: str, days: int) -> str:
    """The day that is `days` after the day of an instant of the ledger."""
    return (date.fromisoformat(_day(value)) + timedelta(days=days)).isoformat()


def _policy_text(chunk_id: str) -> str:
    """The text of a policy excerpt, without its heading.

    Why it comes from the retrieval of the repository: the premise of a two tool case quotes what the tool
    `search_policies` returns, and a second rendering of the policy would be a text the tool never said.
    """
    if not _POLICIES:
        from ledgerlens.retrieval import load_policy_documents

        for document in load_policy_documents():
            _POLICIES[document.metadata["chunk_id"]] = document.page_content.split("\n", 1)[-1].strip()
    return _POLICIES[chunk_id]


_POLICIES: dict[str, str] = {}


def _transaction_evidence(row: sqlite3.Row) -> str:
    """The transaction row as the reader of the set sees it."""
    parts = [
        "ledger/transactions",
        row["id"],
        f"merchant {row['merchant_id']}",
        f"customer {row['customer_id']}",
        f"amount {_money(row['amount_minor'], row['currency'])}",
        f"status {row['status']}",
    ]
    if row["captured_at"]:
        parts.append(f"captured_at {row['captured_at']}")
    if row["card_brand"]:
        parts.append(f"card {row['card_brand']}")
    return " | ".join(parts)


def _refund_evidence(row: sqlite3.Row) -> str:
    """The refund row as the reader of the set sees it: the request and the day it was issued.

    Why the status is left out: the compound template needs a premise that carries one of the two facts of the claim
    and not the other, and a claim about the amount that was paid is not decided by a status the premise does not
    carry. The column of the request is the day the request was issued.
    """
    return " | ".join(
        [
            "ledger/refunds",
            row["id"],
            f"transaction {row['transaction_id']}",
            f"requested {_money(row['requested_amount_minor'], row['requested_currency'])}",
            f"issued_at {row['created_at']}",
            f"reason {row['reason']}",
        ]
    )


def _chargeback_evidence(row: sqlite3.Row) -> str:
    """The chargeback row as the reader of the set sees it."""
    return " | ".join(
        [
            "ledger/chargebacks",
            row["id"],
            f"transaction {row['transaction_id']}",
            f"reason_code {row['reason_code']}",
            f"stage {row['stage']}",
            f"opened_at {row['opened_at']}",
            f"deadline {row['deadline']}",
        ]
    )


def _settlement_evidence(row: sqlite3.Row) -> str:
    """The settlement row as the reader of the set sees it."""
    return " | ".join(
        [
            "ledger/settlements",
            row["id"],
            f"merchant {row['merchant_id']}",
            f"period {row['period_start']} to {row['period_end']}",
            f"gross {_money(row['gross_minor'], row['currency'])}",
            f"refunds {_money(row['refunds_minor'], row['currency'])}",
            f"fees {_money(row['fees_minor'], row['currency'])}",
            f"net {_money(row['net_minor'], row['currency'])}",
            f"status {row['status']}",
            f"expected_payout_date {row['expected_payout_date']}",
            f"paid_at {row['paid_at'] or '-'}",
        ]
    )


def _policy_evidence(chunk_id: str) -> str:
    """The excerpt of the policy as the reader of the set sees it."""
    return f"policy/{chunk_id} | {_policy_text(chunk_id)}"


def _names_tuning(text: str, forbidden: frozenset[str]) -> bool:
    """Whether the text names an id of the tuning material."""
    return bool(set(_ID.findall(text)) & forbidden)


def _pick(
    rows: list[sqlite3.Row],
    forbidden: frozenset[str],
    rng: random.Random,
    render: Any,
) -> sqlite3.Row:
    """The first row of the list whose rendering names no id of the tuning material.

    Why the rendering and not the id of the row: a record names the merchant and the customer that belong to it, and
    the exclusion holds for every id the case carries, not only for the one it is about.
    """
    order = list(rows)
    rng.shuffle(order)
    for row in order:
        if not _names_tuning(render(row), forbidden):
            return row
    raise ValueError("the ledger holds no record of this shape that names no id of the tuning material.")


def _status_text(status: str) -> str:
    """The readable form of a status of the ledger, as a claim writes it."""
    return _STATUS_TEXT.get(status, status)


def _other_status(truth: str, index: int) -> str:
    """A status that is not the truth of the record, chosen by the index so the pairs do not repeat one."""
    others = [status for status in _STATUSES if status != truth]
    return others[index % len(others)]


def _other_reason(truth: str, index: int) -> str:
    """A reason that is not the reason of the record, chosen by the index so the pairs do not repeat one.

    Why the reasons are the ones of the ledger: a claim that carries a reason the ledger never holds is contradicted
    by the premise, and a reason nobody wrote would be contradicted by nothing.
    """
    others = [reason for reason in _REASONS if reason != truth]
    return others[index % len(others)]


def _member(
    *,
    template: str,
    record_id: str,
    claim: str,
    evidence: list[tuple[str, str]],
    label: str,
    fact_key: str,
    fact_value: str,
    control: str | None = None,
    unsupported_marker: str | None = None,
    evidence_note: str = "",
) -> dict[str, Any]:
    """One case of the set with its recipe, before the ids of the file are given."""
    return {
        "claim": claim,
        "evidence": evidence,
        "template": template,
        "record_id": record_id,
        "label": label,
        "fact_key": fact_key,
        "fact_value": fact_value,
        "control": control,
        "unsupported_marker": unsupported_marker,
        "evidence_note": evidence_note,
    }


def _transactions(conn: sqlite3.Connection, status: str | None = None) -> list[sqlite3.Row]:
    """The transactions of the ledger, in the order of their ids."""
    query = (
        "SELECT id, merchant_id, customer_id, amount_minor, currency, status, captured_at, card_brand "
        "FROM transactions"
    )
    parameters: tuple[Any, ...] = ()
    if status is not None:
        query += " WHERE status = ?"
        parameters = (status,)
    return list(conn.execute(query + " ORDER BY id", parameters))


def _refunds(conn: sqlite3.Connection, status: str | None = None) -> list[sqlite3.Row]:
    """The refunds of the ledger, in the order of their ids."""
    query = (
        "SELECT id, transaction_id, requested_amount_minor, requested_currency, payout_amount_minor, "
        "payout_currency, status, reason, created_at FROM refunds"
    )
    parameters: tuple[Any, ...] = ()
    if status is not None:
        query += " WHERE status = ?"
        parameters = (status,)
    return list(conn.execute(query + " ORDER BY id", parameters))


def _chargebacks(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """The chargebacks of the ledger, in the order of their ids."""
    return list(
        conn.execute(
            "SELECT id, transaction_id, reason_code, stage, opened_at, deadline FROM chargebacks ORDER BY id"
        )
    )


def _settlements(conn: sqlite3.Connection, negative_net: bool | None = None) -> list[sqlite3.Row]:
    """The settlements of the ledger, in the order of their ids.

    Why the net amount is a filter: a settlement whose net amount is negative is the record of the premise that
    contradicts itself, and that record belongs to the control alone.
    """
    query = (
        "SELECT id, merchant_id, period_start, period_end, currency, gross_minor, refunds_minor, fees_minor, "
        "net_minor, status, expected_payout_date, paid_at FROM settlements"
    )
    if negative_net is True:
        query += " WHERE net_minor < 0"
    elif negative_net is False:
        query += " WHERE net_minor >= 0"
    return list(conn.execute(query + " ORDER BY id"))


def _hedge_cases(conn: sqlite3.Connection, forbidden: frozenset[str], seed: int) -> list[dict[str, Any]]:
    """The eight cases of the hedge template: four pairs over four transactions.

    The pair changes the status the claim hedges about, so one case of the pair is what the record says and the
    other is what the record contradicts. The first pair carries the control of the case with no evidence at all: its
    claim is true and the premise is empty, so only the label of the recipe can be reached by the person who reads it.
    """
    rng = random.Random(f"{seed}:hedge")
    rows = _transactions(conn)
    by_status: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        by_status[row["status"]].append(row)
    wanted = ("refunded", "partially_refunded", "charged_back", "disputed")
    cases: list[dict[str, Any]] = []
    for index, status in enumerate(wanted):
        pool = by_status.get(status) or rows
        row = _pick(pool, forbidden, rng, _transaction_evidence)
        truth = row["status"]
        wrong = _other_status(truth, index)
        evidence = [("sql:1", _transaction_evidence(row))]
        control = CONTROL_NO_EVIDENCE if index == 0 else None
        cases.append(
            _member(
                template="hedge_shape",
                record_id=row["id"],
                claim=(
                    f"It appears that the payment {row['id']} of merchant {row['merchant_id']} "
                    f"was {_status_text(truth)}."
                ),
                evidence=[] if control else evidence,
                label="not_enough_evidence" if control else "supported",
                fact_key="status",
                fact_value=_status_text(truth),
                control=control,
                evidence_note=(
                    "the premise of this case is empty by design: it is the control of the set" if control else ""
                ),
            )
        )
        cases.append(
            _member(
                template="hedge_shape",
                record_id=row["id"],
                claim=(
                    f"It appears that the payment {row['id']} of merchant {row['merchant_id']} "
                    f"was {_status_text(wrong)}."
                ),
                evidence=evidence,
                label="contradicted",
                fact_key="status",
                fact_value=_status_text(wrong),
            )
        )
    return cases


def _compound_cases(conn: sqlite3.Connection, forbidden: frozenset[str], seed: int) -> list[dict[str, Any]]:
    """The eight cases of the compound template: four pairs over four refunds.

    The premise of a case carries the fact of the first half of the claim and not the fact of the second half, so the
    claim is never decided by the premise alone. The pair changes the reason the refund carries, so one case of the
    pair is what the record says and the other is what the record contradicts. The last pair carries the benign
    control: the fact the premise does not carry is a claim a reader would believe, the refund was paid.

    Why the first half of the claim is the reason and not the day of the request: a claim about a refund and a day
    reads like the claims of the tuning material, and the novelty test of the set measures the wording as well as
    the shape.
    """
    rng = random.Random(f"{seed}:compound")
    tails = (
        ("the merchant was told of it", "told"),
        ("the case was closed by the risk team", "risk team"),
        ("the acquiring bank confirmed the credit", "acquiring bank"),
        ("the customer received the money", "money"),
    )
    rows = _refunds(conn, status="requested")
    cases: list[dict[str, Any]] = []
    for index, (tail, marker) in enumerate(tails):
        row = _pick(rows, forbidden, rng, _refund_evidence)
        reason = row["reason"]
        other = _other_reason(reason, index)
        evidence = [("sql:1", _refund_evidence(row))]
        benign = index == len(tails) - 1
        cases.append(
            _member(
                template="compound_shape",
                record_id=row["id"],
                claim=f'The refund {row["id"]} has the reason "{reason}" and {tail}.',
                evidence=evidence,
                label="not_enough_evidence",
                fact_key="reason",
                fact_value=reason,
                control=CONTROL_BENIGN_UNSUPPORTED if benign else None,
                unsupported_marker=marker,
                evidence_note=(
                    "the premise carries the first fact of the claim and not the second one, and the second one is "
                    "the benign claim of the set"
                    if benign
                    else "the premise carries the first fact of the claim and not the second one"
                ),
            )
        )
        cases.append(
            _member(
                template="compound_shape",
                record_id=row["id"],
                claim=f'The refund {row["id"]} has the reason "{other}" and {tail}.',
                evidence=evidence,
                label="contradicted",
                fact_key="reason",
                fact_value=other,
                unsupported_marker=marker,
            )
        )
    return cases


def _negation_cases(conn: sqlite3.Connection, forbidden: frozenset[str], seed: int) -> list[dict[str, Any]]:
    """The eight cases of the negation template: four pairs over four captured transactions.

    The claim negates the status of the payment, so one case of the pair is what the record says and the other is
    what the record contradicts.
    """
    rng = random.Random(f"{seed}:negation")
    rows = _transactions(conn, status="captured")
    cases: list[dict[str, Any]] = []
    for index in range(4):
        row = _pick(rows, forbidden, rng, _transaction_evidence)
        truth = row["status"]
        other = _other_status(truth, index)
        evidence = [("sql:1", _transaction_evidence(row))]
        cases.append(
            _member(
                template="negation_shape",
                record_id=row["id"],
                claim=(
                    f"The payment {row['id']} of merchant {row['merchant_id']} "
                    f"was not {_status_text(other)}."
                ),
                evidence=evidence,
                label="supported",
                fact_key="status",
                fact_value=_status_text(other),
            )
        )
        cases.append(
            _member(
                template="negation_shape",
                record_id=row["id"],
                claim=(
                    f"The payment {row['id']} of merchant {row['merchant_id']} "
                    f"was not {_status_text(truth)}."
                ),
                evidence=evidence,
                label="contradicted",
                fact_key="status",
                fact_value=_status_text(truth),
            )
        )
    return cases


def _relative_period_cases(conn: sqlite3.Connection, forbidden: frozenset[str], seed: int) -> list[dict[str, Any]]:
    """The eight cases of the relative period template: four pairs over four chargebacks.

    The claim holds a relative clause about the window of the dispute, and the pair changes the day the window
    closed, so one case of the pair is what the record says and the other is what the record contradicts.
    """
    rng = random.Random(f"{seed}:relative_period")
    rows = _chargebacks(conn)
    cases: list[dict[str, Any]] = []
    for _ in range(4):
        row = _pick(rows, forbidden, rng, _chargeback_evidence)
        deadline = row["deadline"]
        shifted = (date.fromisoformat(deadline) + timedelta(days=7)).isoformat()
        evidence = [("sql:1", _chargeback_evidence(row))]
        cases.append(
            _member(
                template="relative_period_shape",
                record_id=row["id"],
                claim=(
                    f"The dispute {row['id']} whose response window closed on {deadline} "
                    f"was in stage {row['stage']}."
                ),
                evidence=evidence,
                label="supported",
                fact_key="deadline",
                fact_value=deadline,
            )
        )
        cases.append(
            _member(
                template="relative_period_shape",
                record_id=row["id"],
                claim=(
                    f"The dispute {row['id']} whose response window closed on {shifted} "
                    f"was in stage {row['stage']}."
                ),
                evidence=evidence,
                label="contradicted",
                fact_key="deadline",
                fact_value=shifted,
            )
        )
    return cases


def _range_cases(conn: sqlite3.Connection, forbidden: frozenset[str], seed: int) -> list[dict[str, Any]]:
    """The eight cases of the range template: four pairs over four settlements.

    The claim writes the period of the payout as a range of days, and the pair changes the day the range ends, so
    one case of the pair is what the record says and the other is what the record contradicts.
    """
    rng = random.Random(f"{seed}:range")
    rows = _settlements(conn, negative_net=False)
    cases: list[dict[str, Any]] = []
    for _ in range(4):
        row = _pick(rows, forbidden, rng, _settlement_evidence)
        start = row["period_start"]
        end = row["period_end"]
        shifted = (date.fromisoformat(end) + timedelta(days=7)).isoformat()
        evidence = [("sql:1", _settlement_evidence(row))]
        cases.append(
            _member(
                template="range_shape",
                record_id=row["id"],
                claim=f"The period that the payout {row['id']} settled ran between {start} and {end}.",
                evidence=evidence,
                label="supported",
                fact_key="period_end",
                fact_value=end,
            )
        )
        cases.append(
            _member(
                template="range_shape",
                record_id=row["id"],
                claim=f"The period that the payout {row['id']} settled ran between {start} and {shifted}.",
                evidence=evidence,
                label="contradicted",
                fact_key="period_end",
                fact_value=shifted,
            )
        )
    return cases


def _two_source_cases(conn: sqlite3.Connection, forbidden: frozenset[str], seed: int) -> list[dict[str, Any]]:
    """The eight cases of the two source template: three pairs over payments and one pair over a settlement.

    The premise of a case is the concatenation of two tools at once, the ledger and a policy excerpt, so the premise
    is longer and structured in a way the tuning sets do not have. The pair changes one fact of the ledger half.

    The last pair carries the control of the premise that contradicts itself: the settlement row says a payout was
    made for a period whose net amount is negative, and the excerpt of the policy says a period with a negative net
    amount gets no payout.
    """
    rng = random.Random(f"{seed}:two_source")
    cases: list[dict[str, Any]] = []
    rows = _transactions(conn, status="captured")
    for _ in range(3):
        row = _pick(rows, forbidden, rng, _transaction_evidence)
        day = _day(row["captured_at"])
        shifted = _shifted_day(row["captured_at"], 1)
        evidence = [
            ("sql:1", _transaction_evidence(row)),
            (f"policy:{_PROCESSING_TIME_CHUNK}", _policy_evidence(_PROCESSING_TIME_CHUNK)),
        ]
        tail = (
            ", and the refund policy says that a refund request is paid on the same business day or on the next one"
        )
        cases.append(
            _member(
                template="two_source_shape",
                record_id=row["id"],
                claim=f"The payment {row['id']} was captured on {day}{tail}.",
                evidence=evidence,
                label="supported",
                fact_key="captured_day",
                fact_value=day,
            )
        )
        cases.append(
            _member(
                template="two_source_shape",
                record_id=row["id"],
                claim=f"The payment {row['id']} was captured on {shifted}{tail}.",
                evidence=evidence,
                label="contradicted",
                fact_key="captured_day",
                fact_value=shifted,
            )
        )
    negative = _settlements(conn, negative_net=True)
    row = _pick(negative, forbidden, rng, _settlement_evidence)
    evidence = [
        ("sql:1", _settlement_evidence(row)),
        (f"policy:{_NEGATIVE_NET_CHUNK}", _policy_evidence(_NEGATIVE_NET_CHUNK)),
    ]
    tail = ", and the settlement schedule says that a period with a negative net amount gets no payout"
    cases.append(
        _member(
            template="two_source_shape",
            record_id=row["id"],
            claim=f"The payout {row['id']} for merchant {row['merchant_id']} was made{tail}.",
            evidence=evidence,
            label="not_enough_evidence",
            fact_key="payout",
            fact_value="made",
            control=CONTROL_SELF_CONTRADICTION,
            evidence_note=(
                "the two items of the premise say opposite things about the payout: the record shows one and the "
                "rule says there is none"
            ),
        )
    )
    cases.append(
        _member(
            template="two_source_shape",
            record_id=row["id"],
            claim=f"The payout {row['id']} for merchant {row['merchant_id']} was withheld{tail}.",
            evidence=evidence,
            label="contradicted",
            fact_key="payout",
            fact_value="withheld",
        )
    )
    return cases


def _scatter(templates: list[str], rng: random.Random) -> list[int]:
    """The order of the cases, with no two neighbours of the same template.

    Why the order is scattered: the id of a case must not say which template the case belongs to, and an order that
    groups the templates would let the person who reads the set guess the template from the position of the case.
    """
    order = list(range(len(templates)))
    rng.shuffle(order)
    for index in range(1, len(order)):
        current = order[index]
        if templates[current] != templates[order[index - 1]]:
            continue
        for other in range(index + 1, len(order)):
            candidate = order[other]
            if templates[candidate] == templates[current]:
                continue
            if other + 1 < len(order) and templates[current] == templates[order[other + 1]]:
                continue
            order[index], order[other] = candidate, current
            break
    return order


def _generate(seed: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The cases and the recipes of the set, in the order of the file."""
    forbidden = tuning_ids()
    conn = sqlite3.connect(f"file:{synthetic_ledger(seed)}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        raw = (
            _hedge_cases(conn, forbidden, seed)
            + _compound_cases(conn, forbidden, seed)
            + _negation_cases(conn, forbidden, seed)
            + _relative_period_cases(conn, forbidden, seed)
            + _range_cases(conn, forbidden, seed)
            + _two_source_cases(conn, forbidden, seed)
        )
    finally:
        conn.close()

    if len(raw) != CASE_COUNT:
        raise ValueError(f"the build produced {len(raw)} cases and the set must hold {CASE_COUNT}.")
    templates = [str(item["template"]) for item in raw]
    order = _scatter(templates, random.Random(f"{seed}:order"))

    cases: list[dict[str, Any]] = []
    recipes: list[dict[str, Any]] = []
    pair_ids: dict[int, str] = {}
    pair_numbers: dict[int, int] = {}
    for position in range(len(raw)):
        pair_numbers[position] = position // 2
    for index, position in enumerate(order, start=1):
        item = raw[position]
        number = pair_numbers[position]
        if number not in pair_ids:
            pair_ids[number] = f"hp-{len(pair_ids) + 1:02d}"
        case_id = f"ho-{index:03d}"
        evidence = list(item["evidence"])
        cases.append(
            {
                "id": case_id,
                "claim": item["claim"],
                "evidence_ids": [identifier for identifier, _content in evidence],
                "evidence": [{"id": identifier, "content": content} for identifier, content in evidence],
            }
        )
        recipes.append(
            {
                "id": case_id,
                "pair_id": pair_ids[number],
                "template": item["template"],
                "record_id": item["record_id"],
                "label": item["label"],
                "fact_key": item["fact_key"],
                "fact_value": item["fact_value"],
                "differing_fact": f"{item['fact_key']}: {item['fact_value']}",
                "control": item["control"],
                "unsupported_marker": item["unsupported_marker"],
                "evidence_note": item["evidence_note"],
            }
        )
    return cases, recipes


def _write_jsonl(path: Path, records: Iterable[Mapping[str, Any]]) -> None:
    """Writes the records of a file, one JSON object per line, with the keys in the order of the alphabet."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
