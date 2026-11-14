"""The projection of a branch: the base, the events of the branch, and everything they add up to.

Why it exists: the state of a branch is a pure function of the base and of the event log (FR-009). The base is
read only, the projection works on a copy of it, and the hash of the projection is the canonical hash of the
projector of the simulator, the same function the base uses, so the two hashes are comparable (FR-010).

The vocabulary of the sandbox is its own (ADR-021). The events of a branch are `sandbox.*` events and the
interpreter that applies them lives here, versioned with the code. The events of the published ledger stay the
events of the published ledger and the two never mix. The first event of the vocabulary is the adjustment of the
FX rate of a refund: the interpreter recomputes the payout of the refund from the new rate, with `Decimal` and
never with a float, and it writes the amount in integer minor units the way the ledger does. The conversion is the
one of the simulator, in `ledgerlens/sim/gaps.py`, so the sandbox and the published ledger agree on the arithmetic.

Three answers come out of a projection: the canonical hash, the diff of what the events changed, and the verdict of
the case, which is the comparison of the projected state with the truth of the scenario.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from ledgerlens.demo import load_manifest
from ledgerlens.sandbox.snapshot import BaseSnapshot
from ledgerlens.sandbox.store import SandboxEventRow
from ledgerlens.sim import gaps
from ledgerlens.sim.projector import READ_TABLES, canonical_hash, dump_rows

# The label of the origin of every event of a branch, so a sandbox event is never a published one (FR-008).
SANDBOX_ORIGIN = "sandbox"

# The vocabulary of the sandbox. Every event of a branch is one of these, and the interpreter knows each one.
EVENT_REFUND_FX_ADJUSTED = "sandbox.refund.fx_adjusted"
EVENT_TYPES = (EVENT_REFUND_FX_ADJUSTED,)

# The four labels of the verdict of a case (ADR-021). The interface renders them and never guesses one.
VERDICT_WITHIN = "within_expected_range"
VERDICT_BELOW = "below_expected_range"
VERDICT_ABOVE = "above_expected_range"
VERDICT_NOT_AVAILABLE = "not_available"
VERDICT_LABELS = (VERDICT_WITHIN, VERDICT_BELOW, VERDICT_ABOVE, VERDICT_NOT_AVAILABLE)

# The kind of a value of the diff: an amount of money, or anything else.
VALUE_MONETARY = "monetary"
VALUE_NON_MONETARY = "non_monetary"

# The column that holds the currency of every monetary column of the read tables.
MONETARY_COLUMNS = {
    ("transactions", "amount_minor"): "currency",
    ("refunds", "requested_amount_minor"): "requested_currency",
    ("refunds", "payout_amount_minor"): "payout_currency",
    ("chargebacks", "amount_minor"): "currency",
    ("settlements", "gross_minor"): "currency",
    ("settlements", "refunds_minor"): "currency",
    ("settlements", "fees_minor"): "currency",
    ("settlements", "net_minor"): "currency",
}

# The columns that hold a rate: a decimal, but not an amount of money.
RATE_COLUMNS = frozenset({("fx_applied", "applied_rate")})

# The truth of a scenario declares the range of a measure, and the measure is named by the key of the range. A
# scenario whose truth declares no range has no verdict to give.
RANGE_MEASURES = {"markup_pct_range": "implied_markup_pct"}


class ProjectionError(RuntimeError):
    """An event of the sandbox could not be applied to the projected rows."""


@dataclass(frozen=True)
class DiffEntry:
    """One value that changed between two projections.

    `record` names the table of the row, `record_id` the row, and `field` the column. `value_kind` says whether
    the value is an amount of money, and `currency` says in which currency it is. The values are text, so the
    interface never reads a number and never calculates one.
    """

    record: str
    record_id: str
    field: str
    before: str
    after: str
    value_kind: str
    currency: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "record": self.record,
            "record_id": self.record_id,
            "field": self.field,
            "before": self.before,
            "after": self.after,
            "value_kind": self.value_kind,
            "currency": self.currency,
        }


@dataclass(frozen=True)
class Verdict:
    """The verdict of a case: one of the four declared labels, and the measure it was computed from."""

    label: str
    measure: str = ""
    value: str | None = None
    low: str | None = None
    high: str | None = None
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "measure": self.measure,
            "value": self.value,
            "low": self.low,
            "high": self.high,
            "detail": self.detail,
        }


@dataclass
class ProjectedState:
    """The derived rows of a branch: the read tables of the base with the events of the branch applied."""

    conn: sqlite3.Connection
    canonical_hash: str
    rows: dict[str, list[dict[str, Any]]]

    def table(self, name: str) -> list[dict[str, Any]]:
        """The rows of one read table, ordered by their identifier."""
        return self.rows[name]

    def row(self, table: str, key: str) -> dict[str, Any] | None:
        """The row of one identifier, or None when the projection does not hold it."""
        for row in self.rows.get(table, []):
            if row.get("id") == key:
                return row
        return None

    def close(self) -> None:
        """Closes the copy of the base. The base itself was never opened for a write."""
        self.conn.close()


def project(base: BaseSnapshot, events: list[SandboxEventRow] | tuple[SandboxEventRow, ...]) -> ProjectedState:
    """The projection of a branch: the base, read only, with the events of the branch applied.

    Why a copy: the base is the published case, and the sandbox never writes to it (FR-001, FR-007). The copy
    lives in memory, so a preview of a mutation costs nothing on the disk.
    """
    conn = _copy_of(base.db_path)
    for event in events:
        _apply(conn, event)
    rows = {table: dump_rows(conn, table) for table, _ in READ_TABLES}
    return ProjectedState(conn=conn, canonical_hash=canonical_hash(conn), rows=rows)


def diff_of(before: ProjectedState, after: ProjectedState) -> list[DiffEntry]:
    """The ordered list of the values that changed between two projections.

    Why the order is stable: the tables are read in the order of the projector and the rows in the order of their
    identifier, so two readers of the same revision see the same list, byte for byte (FR-019, SC-009).
    """
    entries: list[DiffEntry] = []
    for table, key in READ_TABLES:
        old = {row[key]: row for row in before.rows.get(table, [])}
        new = {row[key]: row for row in after.rows.get(table, [])}
        for row_id in sorted(set(old) | set(new)):
            entries.extend(_entries_of(table, row_id, old.get(row_id), new.get(row_id)))
    return entries


def verdict_of(state: ProjectedState, scenario_id: str) -> Verdict:
    """The verdict of the case: the projected state compared with the truth of the scenario.

    A scenario whose truth declares no range has no verdict to give, and the answer is `not_available`.
    """
    truth = scenario_truth(scenario_id)
    if not truth:
        return Verdict(label=VERDICT_NOT_AVAILABLE, detail=f"the scenario {scenario_id} has no truth")
    for range_key, measure in RANGE_MEASURES.items():
        bounds = truth.get(range_key)
        if not bounds:
            continue
        value = _measure(measure, state, truth)
        if value is None:
            return Verdict(
                label=VERDICT_NOT_AVAILABLE,
                measure=measure,
                detail=f"the {measure} is not in the projection",
            )
        low = Decimal(str(bounds[0]))
        high = Decimal(str(bounds[1]))
        if value < low:
            label = VERDICT_BELOW
        elif value > high:
            label = VERDICT_ABOVE
        else:
            label = VERDICT_WITHIN
        return Verdict(
            label=label,
            measure=measure,
            value=str(value),
            low=str(low),
            high=str(high),
            detail=f"the {measure} of the case is {value}, and the expected range is {low} to {high}",
        )
    return Verdict(label=VERDICT_NOT_AVAILABLE, detail=f"the truth of {scenario_id} declares no range")


# --- the interpreter of the vocabulary -----------------------------------------------------------------------


def _apply(conn: sqlite3.Connection, event: SandboxEventRow) -> None:
    """Applies one event of the sandbox to the projected rows."""
    if event.origin != SANDBOX_ORIGIN:
        raise ProjectionError(f"the event {event.event_uid} does not come from the sandbox")
    if event.event_type == EVENT_REFUND_FX_ADJUSTED:
        _apply_fx_adjustment(conn, event)
        return
    raise ProjectionError(f"the sandbox does not know the event {event.event_type}")


def _apply_fx_adjustment(conn: sqlite3.Connection, event: SandboxEventRow) -> None:
    """The adjustment of the FX rate of a refund: the payout is recomputed from the new rate.

    Why the payout is recomputed and not read from the event: the event carries the rate the visitor asked for,
    and the amount follows from the rate with the arithmetic of the simulator. So the projection of a branch is
    the same whether it is built by the commit or rebuilt from the events alone.
    """
    payload = event.payload
    refund_id = str(payload["refund_id"])
    refund = _one(conn, "SELECT * FROM refunds WHERE id = ?", (refund_id,))
    if refund is None:
        raise ProjectionError(f"the refund {refund_id} is not in the projection")
    try:
        rate = Decimal(str(payload["applied_rate"]))
    except InvalidOperation:
        raise ProjectionError(f"the rate of the event {event.event_uid} is not a decimal number") from None
    payout_minor = gaps.convert_minor(
        int(refund["requested_amount_minor"]),
        rate,
        str(refund["requested_currency"]),
        str(refund["payout_currency"]),
    )
    conn.execute("UPDATE refunds SET payout_amount_minor = ? WHERE id = ?", (payout_minor, refund_id))
    fx_id = refund["fx_applied_id"]
    if fx_id:
        conn.execute("UPDATE fx_applied SET applied_rate = ? WHERE id = ?", (canonical_rate(rate), fx_id))


def canonical_rate(rate: Decimal) -> str:
    """The rate as the ledger writes it: a plain decimal text with no trailing zeros.

    Why: the same rate must always produce the same bytes, or the hash of a branch would depend on how the
    visitor wrote the rate. Why the trailing zero: the ledger checks that a rate holds a decimal, so the rate of a
    whole number is written with one.
    """
    text = format(rate.normalize(), "f")
    if "." not in text:
        text = f"{text}.0"
    return text


# --- the internals -------------------------------------------------------------------------------------------


def _copy_of(path: Path) -> sqlite3.Connection:
    """A copy of the base in memory. The file of the base is opened read only and never written."""
    source = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    target = sqlite3.connect(":memory:")
    source.backup(target)
    source.close()
    return target


def _one(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    """The first row of a query, as a map of column to value, or None."""
    cursor = conn.execute(sql, params)
    columns = [column[0] for column in cursor.description]
    row = cursor.fetchone()
    if row is None:
        return None
    return dict(zip(columns, row, strict=True))


def _entries_of(
    table: str, row_id: str, old: dict[str, Any] | None, new: dict[str, Any] | None
) -> list[DiffEntry]:
    """The entries of one record: every value that is not the same on both sides."""
    if old is None or new is None:
        # The vocabulary of the sandbox never adds a row and never drops one, but a diff that hid it would lie.
        present = new if old is None else old
        entries = []
        for column in sorted(present):
            text, kind, currency = _value_of(table, present, column)
            before = "" if old is None else text
            after = "" if new is None else text
            entries.append(DiffEntry(table, row_id, column, before, after, kind, currency))
        return entries
    entries = []
    for column in sorted(set(old) | set(new)):
        if old.get(column) == new.get(column):
            continue
        before, kind, currency = _value_of(table, old, column)
        after, _, _ = _value_of(table, new, column)
        entries.append(DiffEntry(table, row_id, column, before, after, kind, currency))
    return entries


def _value_of(table: str, row: dict[str, Any], column: str) -> tuple[str, str, str | None]:
    """The value of a column as text, the kind of the value and its currency."""
    raw = row.get(column)
    currency_column = MONETARY_COLUMNS.get((table, column))
    if currency_column is not None:
        currency = str(row.get(currency_column) or "")
        return _money_value(int(raw), currency), VALUE_MONETARY, currency
    if (table, column) in RATE_COLUMNS:
        return str(raw), VALUE_NON_MONETARY, None
    return "" if raw is None else str(raw), VALUE_NON_MONETARY, None


def _money_value(amount_minor: int, currency: str) -> str:
    """The amount as the decimal text of the ledger, in major units.

    Why the import is here and not at the top of the module: the money helpers belong to the mutation path, and
    the mutation module needs this module, so the two cannot import each other at the top.
    """
    from ledgerlens.sandbox.mutation import format_minor

    return format_minor(amount_minor, currency)


def _measure(measure: str, state: ProjectedState, truth: dict[str, Any]) -> Decimal | None:
    """The value of a measure of the case, computed over the projected rows."""
    if measure == "implied_markup_pct":
        return _implied_markup_pct(state, truth)
    return None


def _implied_markup_pct(state: ProjectedState, truth: dict[str, Any]) -> Decimal | None:
    """The markup the applied rate of the refund leaves, in percent of the reference rate of the truth.

    Why the truth holds the reference rate: the truth of the case names the rate of the reference source on the
    day of the refund, and the markup is what the applied rate takes away from it. The number is a `Decimal` from
    the first step to the last.
    """
    reference = truth.get("reference_rate_refund_date")
    if reference is None:
        return None
    rate = _applied_rate_of_the_refund(state, truth)
    if rate is None:
        return None
    try:
        reference_rate = Decimal(str(reference))
        applied = Decimal(str(rate))
    except InvalidOperation:
        return None
    if reference_rate == 0:
        return None
    return ((Decimal(1) - applied / reference_rate) * Decimal(100)).quantize(Decimal("0.0001"))


def _applied_rate_of_the_refund(state: ProjectedState, truth: dict[str, Any]) -> str | None:
    """The rate the projection applied to the refund of the case."""
    refund_id = truth.get("refund_id")
    candidates = []
    if refund_id:
        candidates.append(str(refund_id))
    for row in state.rows.get("fx_applied", []):
        if row.get("kind") == "refund" and row.get("refund_id") in candidates:
            return str(row.get("applied_rate"))
    for row in state.rows.get("refunds", []):
        if row.get("id") in candidates:
            fx_id = row.get("fx_applied_id")
            for fx in state.rows.get("fx_applied", []):
                if fx.get("id") == fx_id:
                    return str(fx.get("applied_rate"))
    return None


def scenario_truth(scenario_id: str) -> dict[str, Any]:
    """The truth of a scenario with the identifiers it is about, as the published manifest declares them.

    Why the identifiers are added: the truth holds the numbers of the case, and the verdict has to find the rows
    those numbers are about, so the truth of a scenario is its numbers and the identifier of its refund.
    """
    manifest = load_manifest()
    for scenario in manifest.get("scenarios", []):
        if scenario.get("id") == scenario_id:
            truth = dict(scenario.get("truth") or {})
            ids = scenario.get("ids") or {}
            refunds = ids.get("refund_ids") or []
            if refunds:
                truth.setdefault("refund_id", refunds[0])
            return truth
    return {}


def oldest_moment(state: ProjectedState) -> datetime | None:
    """The oldest moment of the projected rows, the beginning of the window of an effective date."""
    moments: list[datetime] = []
    for rows in state.rows.values():
        for row in rows:
            for value in row.values():
                if not isinstance(value, str) or len(value) < 10 or value[4] != "-" or value[7] != "-":
                    continue
                try:
                    moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if moment.tzinfo is None:
                    # The columns that hold a bare day are read as a day of the clock of the server.
                    moment = moment.replace(tzinfo=UTC)
                moments.append(moment)
    if not moments:
        return None
    return min(moments)


__all__ = [
    "EVENT_REFUND_FX_ADJUSTED",
    "EVENT_TYPES",
    "DiffEntry",
    "ProjectedState",
    "ProjectionError",
    "SANDBOX_ORIGIN",
    "VALUE_MONETARY",
    "VALUE_NON_MONETARY",
    "VERDICT_ABOVE",
    "VERDICT_BELOW",
    "VERDICT_LABELS",
    "VERDICT_NOT_AVAILABLE",
    "VERDICT_WITHIN",
    "Verdict",
    "canonical_rate",
    "diff_of",
    "oldest_moment",
    "project",
    "scenario_truth",
    "verdict_of",
]
