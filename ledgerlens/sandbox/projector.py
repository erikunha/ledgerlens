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
The second event of the vocabulary is the duplicate of a payment: the interpreter writes the copy of the row of the
original, with the next free identifier of the branch, the moments moved by the elapsed seconds, the origin of the
sandbox and the identifier of the original as its source. The third event of the vocabulary is the change of the
deadline of a chargeback: the interpreter writes the deadline and nothing else of the row moves. The fourth event of
the vocabulary is the outage of the FX tool of the branch, and the fifth is the injection of an untrusted note on a
record of the branch: neither of them writes a row of the ledger, they change the state of the branch. The last
event of the vocabulary is the marker of an undo (ADR-024): it names the event it undoes and the request that
produced it, and it changes no row. The projection resolves the markers, so the state of a branch is still a pure
function of the base and of the log.

Every event of the vocabulary carries the published payload of the command that produced it and nothing else, and
the interpreter computes the row out of it. So the preview and the commit see exactly the same row, and a branch
rebuilt from the events alone is the branch that was committed (ADR-031).

The state of a branch is more than its rows. Beside the rows of the ledger, a branch holds a derived state: the
state of its tools and the notes of its records. The derived state is derived the same way the rows are, as a pure
function of the base and of the log, so the interpreter derives it while it applies the events, in the order of the
log, and two projections of the same log always have the same derived state (FR-009, ADR-032).

The hash of a branch covers the derived state, and the rule of the hash lives in one place, in `branch_hash`, so the
branch layer and the interpreter cannot disagree about it. A branch that holds no derived state has the hash of its
rows, and the hash of a forked branch is therefore exactly the hash of the published base (FR-010, ADR-021). A branch
that holds a derived state has a hash that combines the hash of its rows with the derived state, so a branch whose
log was tampered with cannot prove its own state and is refused with `HASH_MISMATCH` (ADR-032).

The interpreter reads the payload of every event it applies, and a payload that lost a field it reads is a payload it
refuses to apply. The refusal is a `ProjectionError`, so the branch layer turns it into `HASH_MISMATCH` and the
facade answers 409 and never 500 (ADR-021, ADR-032).

Three answers come out of a projection: the canonical hash, the diff of what the events changed, and the verdict of
the case, which is the comparison of the projected state with the truth of the scenario.
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from ledgerlens.demo import load_manifest
from ledgerlens.sandbox.snapshot import BaseSnapshot
from ledgerlens.sandbox.store import SandboxEventRow
from ledgerlens.sim import gaps
from ledgerlens.sim.events import canonical_json
from ledgerlens.sim.projector import READ_TABLES, canonical_hash, dump_rows

# The label of the origin of every event of a branch, so a sandbox event is never a published one (FR-008).
SANDBOX_ORIGIN = "sandbox"

# The vocabulary of the sandbox. Every event of a branch is one of these, and the interpreter knows each one.
EVENT_REFUND_FX_ADJUSTED = "sandbox.refund.fx_adjusted"
EVENT_PAYMENT_DUPLICATED = "sandbox.payment.duplicated"
EVENT_CHARGEBACK_DEADLINE_CHANGED = "sandbox.chargeback.deadline_changed"
EVENT_TOOL_FX_OUTAGE = "sandbox.tool.fx_outage"
EVENT_RECORD_NOTE_INJECTED = "sandbox.record.note_injected"
EVENT_BRANCH_UNDONE = "sandbox.branch.undone"
EVENT_TYPES = (
    EVENT_REFUND_FX_ADJUSTED,
    EVENT_PAYMENT_DUPLICATED,
    EVENT_CHARGEBACK_DEADLINE_CHANGED,
    EVENT_TOOL_FX_OUTAGE,
    EVENT_RECORD_NOTE_INJECTED,
    EVENT_BRANCH_UNDONE,
)

# The shape of the identifier of a transaction. The published ledger checks it with a glob of exactly four digits, so
# the identifiers a branch can hold are TX-0001 to TX-9999 and the space of them is finite (ADR-031).
TRANSACTION_ID_PREFIX = "TX-"
TRANSACTION_ID_DIGITS = 4
TRANSACTION_ID_SPACE = 10**TRANSACTION_ID_DIGITS - 1

# The keys of the payload of the marker of an undo: the uid of the event it undoes and the command id of the
# request that produced that event (ADR-024).
UNDO_EVENT_UID = "undone_event_uid"
UNDO_COMMAND_ID = "undone_command_id"

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

# The name of the tool of the branch whose state the outage moves.
TOOL_FX = "fx"
# The record of the diff that holds the state of the tools of a branch, and the field that holds the outage of a
# tool. An empty value means the tool is available (ADR-032).
TOOLS_RECORD = "tools"
OUTAGE_FIELD = "outage"
# The field of the diff that holds the untrusted note of a record.
NOTE_FIELD = "untrusted_note"
# The tables of the ledger a record of the case may be. The order is the order the resolver of the table of a record
# looks for it, so the domain and the interpreter always attach the note to the same table (ADR-032).
NOTE_TABLES = ("transactions", "refunds", "chargebacks", "settlements")


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


@dataclass(frozen=True)
class DerivedState:
    """The derived state of a branch: the state of its tools and the notes of its records.

    Why the state is derived and never stored: it is a pure function of the base and of the log, exactly like the
    rows, so the interpreter derives it while it applies the events, in the order of the log, and two projections of
    the same log always have the same derived state (FR-009, ADR-032).

    `tools` holds the state of every tool the branch changed, as pairs of the name of the tool and the error code of
    its outage. A tool that is not named is available. `notes` holds the last untrusted note injected on every record,
    as triples of the table of the record, the identifier of the record and the text of the note.
    """

    tools: tuple[tuple[str, str], ...] = ()
    notes: tuple[tuple[str, str, str], ...] = ()

    def is_empty(self) -> bool:
        """True when the branch holds no derived state at all."""
        return not self.tools and not self.notes

    def outage_of(self, tool: str) -> str:
        """The error code of the outage of a tool, or an empty text when the tool is available."""
        for name, error_code in self.tools:
            if name == tool:
                return error_code
        return ""

    def note_of(self, table: str, record_id: str) -> str:
        """The note a record carries, or an empty text when the record carries none."""
        for note_table, note_id, text in self.notes:
            if note_table == table and note_id == record_id:
                return text
        return ""

    def with_outage(self, tool: str, error_code: str) -> DerivedState:
        """The state with the outage of a tool."""
        kept = [(name, code) for name, code in self.tools if name != tool]
        kept.append((tool, error_code))
        return replace(self, tools=tuple(sorted(kept)))

    def without_outage(self, tool: str) -> DerivedState:
        """The state with a tool that is available again."""
        kept = [(name, code) for name, code in self.tools if name != tool]
        return replace(self, tools=tuple(sorted(kept)))

    def with_note(self, table: str, record_id: str, text: str) -> DerivedState:
        """The state with the last note injected on a record."""
        kept = [note for note in self.notes if not (note[0] == table and note[1] == record_id)]
        kept.append((table, record_id, text))
        return replace(self, notes=tuple(sorted(kept)))

    def to_dict(self) -> dict[str, Any]:
        """The state as the hash reads it: a plain structure with no ambiguity."""
        return {
            "tools": [{"tool": name, "outage": code} for name, code in self.tools],
            "notes": [{"record": table, "record_id": record_id, "text": text} for table, record_id, text in self.notes],
        }


@dataclass
class ProjectedState:
    """The derived state of a branch: the read tables of the base with the events of the branch applied.

    Beside the rows, the projection holds the derived state of the branch, that is, the state of its tools and the
    notes of its records. The canonical hash of the projection covers both, and the rule of the hash lives in
    `branch_hash` so that the branch layer and the interpreter cannot disagree about it (ADR-032).
    """

    conn: sqlite3.Connection
    canonical_hash: str
    rows: dict[str, list[dict[str, Any]]]
    derived: DerivedState = field(default_factory=DerivedState)

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


@dataclass(frozen=True)
class UndoMarks:
    """The marks the undo markers of a log carry.

    `undone_event_uids` are the uids of the events the markers undo, `undone_command_ids` are the command ids of
    the requests whose mutation was undone, and `undone_event_uid_by_command` names the event that each undo undid,
    keyed by the command id of the request that asked for it. The marks are derived from the log and never stored as a
    flag, so they cannot drift away from the truth of the log (ADR-024).

    The two marks never overlap: a request that produced a mutation that was undone is in `undone_command_ids` and
    names no event, and a request that asked for an undo is in `undone_event_uid_by_command` and is never in
    `undone_command_ids`, because an undo can never be undone.
    """

    undone_event_uids: frozenset[str] = frozenset()
    undone_command_ids: frozenset[str] = frozenset()
    undone_event_uid_by_command: dict[str, str] = field(default_factory=dict)


def project(base: BaseSnapshot, events: list[SandboxEventRow] | tuple[SandboxEventRow, ...]) -> ProjectedState:
    """The projection of a branch: the base, read only, with the events of the branch applied.

    Why a copy: the base is the published case, and the sandbox never writes to it (FR-001, FR-007). The copy
    lives in memory, so a preview of a mutation costs nothing on the disk.

    Why the log is read in two passes: the undo markers name the events they undo, and the projection applies only
    the events that are still live. The marker itself changes no row, so the state of the branch stays a pure
    function of the base and of the log, and the hash of a branch after an undo is the hash of the state before the
    undone mutation (FR-009, FR-010, ADR-024).

    Why the derived state is derived here: it is a function of the base and of the log, exactly like the rows, so
    the interpreter derives it while it applies the events, in the order of the log (FR-009, ADR-032).
    """
    conn = _copy_of(base.db_path)
    undone = undo_marks(events).undone_event_uids
    derived = DerivedState()
    for event in events:
        if is_undo_marker(event):
            # The marker of an undo changes no row: it only names the event it undoes (ADR-024).
            continue
        if event.event_uid in undone:
            # The event was undone, so it is not live any more and the projection does not apply it.
            continue
        derived = _apply(conn, event, derived)
    rows = {table: dump_rows(conn, table) for table, _ in READ_TABLES}
    return ProjectedState(
        conn=conn,
        canonical_hash=branch_hash(canonical_hash(conn), derived),
        rows=rows,
        derived=derived,
    )


def branch_hash(rows_hash: str, derived: DerivedState) -> str:
    """The canonical hash of a branch: the hash of its rows and, when it holds one, of its derived state.

    Why the rule lives in one place: the branch layer compares the hash of the projection with the hash the row of
    the branch declares, and the interpreter writes the state of the branch. Two copies of the rule would drift
    apart, and a branch would be refused for a hash it does have (ADR-032).

    Why a branch without derived state has the hash of its rows: the hash of a forked branch has to be the hash of
    the published base, so the two hashes stay comparable (FR-010, ADR-021).

    Why the derived state joins the hash: a branch whose log was tampered with holds a state that its rows do not
    prove, and a hash that only covers the rows would let it pass. A branch that cannot prove its own state is
    refused with `HASH_MISMATCH`, like every other branch that cannot prove itself (ADR-021, ADR-032).
    """
    if derived.is_empty():
        return rows_hash
    digest = hashlib.sha256()
    digest.update(f"rows\n{rows_hash}\n".encode())
    digest.update(canonical_json(derived.to_dict()).encode("utf-8"))
    return digest.hexdigest()


def is_undo_marker(event: SandboxEventRow) -> bool:
    """True when the event is the marker of an undo of the branch (ADR-024)."""
    return event.event_type == EVENT_BRANCH_UNDONE


def undo_marks(events: list[SandboxEventRow] | tuple[SandboxEventRow, ...]) -> UndoMarks:
    """The marks the undo markers of the log carry.

    Why the markers are read apart from the events they undo: the projection has to know which events are still
    live, and the answers of the branch have to know which of them were undone. Both facts come from the log, so
    neither of them can drift away from the truth (ADR-024).

    Why the two marks are kept apart: the answer of a mutation that was undone and the answer of the undo that undid
    it both talk about the same event, and a reader must be able to tell them apart. The request that produced the
    undone mutation is named by the payload of the marker, and the request that asked for the undo is named by the
    command id of the marker itself.
    """
    undone_uids: set[str] = set()
    undone_commands: set[str] = set()
    by_undo_request: dict[str, str] = {}
    for event in events:
        if not is_undo_marker(event):
            continue
        uid = str(event.payload.get(UNDO_EVENT_UID, ""))
        if not uid:
            # A marker that names no event undoes nothing.
            continue
        undone_uids.add(uid)
        if event.command_id:
            # The command id of the request that appended the marker: that request is an undo, and it is the one
            # that names the event it undid.
            by_undo_request[event.command_id] = uid
        command = str(event.payload.get(UNDO_COMMAND_ID, ""))
        if command:
            # The command id of the request that produced the undone event: that request is a mutation, and its
            # mutation was undone.
            undone_commands.add(command)
    return UndoMarks(
        undone_event_uids=frozenset(undone_uids),
        undone_command_ids=frozenset(undone_commands),
        undone_event_uid_by_command=by_undo_request,
    )


def diff_of(before: ProjectedState, after: ProjectedState) -> list[DiffEntry]:
    """The ordered list of the values that changed between two projections.

    Why the order is stable: the tables are read in the order of the projector and the rows in the order of their
    identifier, so two readers of the same revision see the same list, byte for byte (FR-019, SC-009).

    Why the entries of the derived state come after the entries of the rows: the state of the tools of a branch and
    the notes of its records are not rows of the ledger, and the reader of the diff reads the rows first (ADR-032).
    """
    entries: list[DiffEntry] = []
    for table, key in READ_TABLES:
        old = {row[key]: row for row in before.rows.get(table, [])}
        new = {row[key]: row for row in after.rows.get(table, [])}
        for row_id in sorted(set(old) | set(new)):
            entries.extend(_entries_of(table, row_id, old.get(row_id), new.get(row_id)))
    entries.extend(_derived_entries(before.derived, after.derived))
    return entries


def _derived_entries(before: DerivedState, after: DerivedState) -> list[DiffEntry]:
    """The entries of the derived state: the state of the tools and the notes of the records.

    Why an empty value means the tool is available: the diff has no other way to say that a tool carries no
    outage, and the rule is written here once so that every reader of the diff reads it the same way (ADR-032).
    """
    entries: list[DiffEntry] = []
    tools = sorted({name for name, _ in before.tools} | {name for name, _ in after.tools})
    for tool in tools:
        old = before.outage_of(tool)
        new = after.outage_of(tool)
        if old != new:
            entries.append(DiffEntry(TOOLS_RECORD, tool, OUTAGE_FIELD, old, new, VALUE_NON_MONETARY, None))
    records = sorted(
        {(table, record_id) for table, record_id, _ in before.notes}
        | {(table, record_id) for table, record_id, _ in after.notes}
    )
    for table, record_id in records:
        old = before.note_of(table, record_id)
        new = after.note_of(table, record_id)
        if old != new:
            entries.append(DiffEntry(table, record_id, NOTE_FIELD, old, new, VALUE_NON_MONETARY, None))
    return entries


def verdict_of(state: ProjectedState, scenario_id: str) -> Verdict:
    """The verdict of the case: the projected state compared with the truth of the scenario.

    A scenario whose truth declares no range has no verdict to give, and the answer is `not_available`.

    Why the outage of the FX tool comes first: the measure of the case is the markup of the refund, and the markup
    needs the rate of the reference source. With the source down the measure cannot be computed, so the verdict is
    `not_available` and the detail of the answer names the outage and its error code (ADR-032).
    """
    outage = state.derived.outage_of(TOOL_FX)
    if outage:
        return Verdict(
            label=VERDICT_NOT_AVAILABLE,
            detail=(
                f"the FX tool is down with the error {outage}, and the rate of the reference source cannot be read,"
                " so the measure of the case cannot be computed"
            ),
        )
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


def _apply(conn: sqlite3.Connection, event: SandboxEventRow, derived: DerivedState) -> DerivedState:
    """Applies one event of the sandbox to the projected rows and to the derived state of the branch.

    Why the derived state travels with the rows: the two are derived from the same log, in the same order, and the
    hash of the branch covers the two together (ADR-032).
    """
    if event.origin != SANDBOX_ORIGIN:
        raise ProjectionError(f"the event {event.event_uid} does not come from the sandbox")
    if event.event_type == EVENT_REFUND_FX_ADJUSTED:
        _apply_fx_adjustment(conn, event)
        return derived
    if event.event_type == EVENT_PAYMENT_DUPLICATED:
        _apply_duplicate(conn, event)
        return derived
    if event.event_type == EVENT_CHARGEBACK_DEADLINE_CHANGED:
        _apply_deadline_change(conn, event)
        return derived
    if event.event_type == EVENT_TOOL_FX_OUTAGE:
        return _apply_fx_outage(derived, event)
    if event.event_type == EVENT_RECORD_NOTE_INJECTED:
        return _apply_note(conn, derived, event)
    if event.event_type == EVENT_BRANCH_UNDONE:
        # The marker of an undo changes no row: the projection resolves it by skipping the event it undoes.
        return derived
    raise ProjectionError(f"the sandbox does not know the event {event.event_type}")


def _apply_fx_adjustment(conn: sqlite3.Connection, event: SandboxEventRow) -> None:
    """The adjustment of the FX rate of a refund: the payout is recomputed from the new rate.

    Why the payout is recomputed and not read from the event: the event carries the rate the visitor asked for,
    and the amount follows from the rate with the arithmetic of the simulator. So the projection of a branch is
    the same whether it is built by the commit or rebuilt from the events alone.
    """
    payload = event.payload
    refund_id = str(_field_of(payload, "refund_id", event))
    refund = _one(conn, "SELECT * FROM refunds WHERE id = ?", (refund_id,))
    if refund is None:
        raise ProjectionError(f"the refund {refund_id} is not in the projection")
    try:
        rate = Decimal(str(_field_of(payload, "applied_rate", event)))
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


def _apply_duplicate(conn: sqlite3.Connection, event: SandboxEventRow) -> None:
    """The duplicate of a payment: the copy of the row of the original, with the identifier the branch can offer.

    Why the copy is computed here and not carried by the event: the event carries the published payload of the
    command, and the row is a function of the state of the branch. So the preview, the commit and the rebuild of
    the branch from its events alone write the same row (ADR-031).

    Why the copy carries no row of the applied rate: the duplicate is a second charge of the same payment, and the
    conversion of the rate belongs to the payment, which is the same one. The visitor reads the conversion in the
    row of the original.
    """
    payload = event.payload
    transaction_id = str(_field_of(payload, "transaction_id", event))
    original = _one(conn, "SELECT * FROM transactions WHERE id = ?", (transaction_id,))
    if original is None:
        raise ProjectionError(f"the transaction {transaction_id} is not in the projection")
    elapsed = _elapsed_seconds(payload)
    taken = {str(row[0]) for row in conn.execute("SELECT id FROM transactions")}
    identifier = next_transaction_id(taken, transaction_id)
    if identifier is None:
        raise ProjectionError(f"the branch holds no free identifier for the duplicate of {transaction_id}")
    conn.execute(
        "INSERT INTO transactions (id, merchant_id, customer_id, amount_minor, currency, method, card_brand,"
        " card_fingerprint, status, created_at, captured_at, origin, source_ref)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            identifier,
            original["merchant_id"],
            original["customer_id"],
            original["amount_minor"],
            original["currency"],
            original["method"],
            original["card_brand"],
            original["card_fingerprint"],
            # The status of the copy is the status of the original: the duplicate is the same payment, charged twice.
            original["status"],
            _moved_moment(original["created_at"], elapsed),
            # A payment that was never captured has no capture moment, and the copy of it has none either.
            _moved_moment(original["captured_at"], elapsed),
            # The origin of the row tells the visitor which row of the ledger of the branch is the simulated one.
            SANDBOX_ORIGIN,
            # The source says which payment the duplicate comes from.
            transaction_id,
        ),
    )


def _apply_deadline_change(conn: sqlite3.Connection, event: SandboxEventRow) -> None:
    """The change of the deadline of a chargeback: the interpreter writes the deadline and nothing else moves."""
    payload = event.payload
    chargeback_id = str(_field_of(payload, "chargeback_id", event))
    chargeback = _one(conn, "SELECT id FROM chargebacks WHERE id = ?", (chargeback_id,))
    if chargeback is None:
        raise ProjectionError(f"the chargeback {chargeback_id} is not in the projection")
    conn.execute(
        "UPDATE chargebacks SET deadline = ? WHERE id = ?",
        (str(_field_of(payload, "new_deadline", event)), chargeback_id),
    )


def _apply_fx_outage(derived: DerivedState, event: SandboxEventRow) -> DerivedState:
    """The outage of the FX tool of the branch: the state of the tool moves and no row of the ledger does.

    Why the event carries the flag and not the state: the event carries the published payload of the command, and
    the state of the tool is computed out of it. So the preview, the commit and the rebuild of the branch from its
    events alone see the same state (ADR-031, ADR-032).

    Why the last event of the log wins: the events are applied in the order of the log, and each one moves the state
    of the tool, so the state of the branch is the state the last one asks for (ADR-032).

    Why the flag says that the outage is on: the flag of the event is the state of the outage and not the state of
    the tool, so `enabled` true means that the tool of the branch is down with the error code of the event. A
    payload that lost the flag or the error code is a log that was tampered with, and a tool that is down with no
    error code would leave the verdict of the case blind (ADR-021, ADR-032).
    """
    payload = event.payload
    enabled = _field_of(payload, "enabled", event)
    if not isinstance(enabled, bool):
        raise ProjectionError(f"the flag of the event {event.event_uid} is not a boolean")
    error_code = _field_of(payload, "error_code", event)
    if not isinstance(error_code, str) or not error_code:
        raise ProjectionError(f"the error code of the event {event.event_uid} is not a text")
    if enabled:
        return derived.with_outage(TOOL_FX, error_code)
    return derived.without_outage(TOOL_FX)


def _apply_note(conn: sqlite3.Connection, derived: DerivedState, event: SandboxEventRow) -> DerivedState:
    """The untrusted note of a record of the branch: the note moves and no row of the ledger does.

    Why the table of the record is found here: the published payload of the command names the identifier of the
    record and not its table, and the table is a property of the state of the branch. So the interpreter asks the
    resolver of the table, the same one the domain asks, and the two always attach the note to the same table
    (ADR-032).

    Why the note is not a row: a note is text of an untrusted source. It is not evidence, it does not move the
    verdict and it does not move the invariants of the domain (ADR-032).
    """
    payload = event.payload
    record_id = str(_field_of(payload, "record_id", event))
    text = str(_field_of(payload, "text", event))
    table = table_of_the_record(record_id, _holds_the_record_of_the_connection(conn, record_id))
    if table is None:
        raise ProjectionError(f"the record {record_id} is not in the projection")
    return derived.with_note(table, record_id, text)


def _field_of(payload: dict[str, Any], name: str, event: SandboxEventRow) -> Any:
    """The value of a field of the payload of an event, when the payload carries it.

    Why it raises: a payload that lost a field is a log that was tampered with, and a branch that cannot prove its
    own state is refused with `HASH_MISMATCH` (ADR-021, ADR-032). A `KeyError` would leave the refusal unhandled
    and the facade would answer 500 instead of the 409 of the contract.
    """
    if name not in payload:
        raise ProjectionError(f"the payload of the event {event.event_uid} carries no field {name!r}")
    return payload[name]


def _holds_the_record_of_the_connection(conn: sqlite3.Connection, record_id: str) -> Callable[[str], bool]:
    """The lookup that answers whether a table of the case holds the record, read from the connection.

    Why the rows and not a query of the identifier: the SQL of the product lives in the store of the sandbox, and
    the interpreter reads the rows of the case with the helper the projector of the simulator uses.
    """
    rows = {table: dump_rows(conn, table) for table in NOTE_TABLES}
    return holds_the_record(rows, record_id)


def holds_the_record(rows: dict[str, list[dict[str, Any]]], record_id: str) -> Callable[[str], bool]:
    """The lookup that answers whether a table of the case holds the record, read from the rows of a projection.

    Why the rule of the row is here: the domain and the interpreter have to agree on the row that holds the
    record, so the rule of the identifier of a row lives in one place (ADR-032).
    """

    def holds(table: str) -> bool:
        return any(str(row.get("id")) == record_id for row in rows.get(table, []))

    return holds


def table_of_the_record(record_id: str, holds: Callable[[str], bool]) -> str | None:
    """The table of the ledger that holds the record, or None when no table of the case holds it.

    Why the lookup is a callable: the domain reads the rows of the branch from the projection it holds and the
    interpreter reads them from the connection of the branch, and the rule of the table of a record has to be one.
    So the resolver owns the order of `NOTE_TABLES` and the caller owns the way it reads the rows (ADR-032).

    Why the order of `NOTE_TABLES`: the domain and the interpreter have to attach the note to the same table, and
    the identifiers of the tables do not collide, so the first table that holds the record is the table of it
    (ADR-032).
    """
    for table in NOTE_TABLES:
        if holds(table):
            return table
    return None


def next_transaction_id(taken: set[str], original_id: str) -> str | None:
    """The next free identifier of a transaction, starting from the one right after the original.

    Why the rule is here and not in the mutation path: the domain and the interpreter have to agree on the
    identifier of the duplicate, and a rule written twice drifts. The domain asks this function whether the branch
    still has room, and the interpreter asks it for the identifier itself (ADR-031).

    Why the search wraps around: the space of the identifiers is finite, and the branch of a visitor holds rows
    that came from the published case and rows that the visitor added. The search goes from the one after the
    original up to TX-9999 and then from TX-0001 up to the original, so the copy never takes an identifier that is
    free but out of reach. When every identifier of the space is taken, there is no identifier left and the caller
    refuses the command.
    """
    try:
        number = int(original_id.split("-")[-1])
    except ValueError:
        return None
    if not 1 <= number <= TRANSACTION_ID_SPACE:
        return None
    for step in range(1, TRANSACTION_ID_SPACE + 1):
        candidate = ((number + step - 1) % TRANSACTION_ID_SPACE) + 1
        identifier = f"{TRANSACTION_ID_PREFIX}{candidate:0{TRANSACTION_ID_DIGITS}d}"
        if identifier not in taken:
            return identifier
    return None


def _elapsed_seconds(payload: dict[str, Any]) -> int:
    """The elapsed seconds of a duplicate, as a whole number of seconds.

    Why the whole number: the moments of the ledger are written to the second, and a fraction of a second would be
    a number the ledger cannot write.
    """
    value = payload.get("elapsed_seconds")
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProjectionError("the elapsed seconds of the duplicate are not a whole number of seconds")
    return value


def _moved_moment(moment: Any, elapsed: int) -> str | None:
    """A moment of the ledger moved by the elapsed seconds, in the shape the ledger writes it.

    Why the shape is kept: the row of the copy is read by the same rules as every other row of the ledger, and a
    moment written in another shape would not be read the same way.
    """
    if moment is None:
        return None
    text = str(moment)
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    moved = (parsed + timedelta(seconds=elapsed)).astimezone(UTC)
    if text.endswith("Z"):
        return moved.strftime("%Y-%m-%dT%H:%M:%SZ")
    return moved.isoformat()


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
        # A row that appears carries one entry per column and a value before that is empty, and a row that goes
        # away carries the same entries the other way round. The vocabulary of the sandbox adds a row when it
        # simulates a duplicate, and the diff has to say so (ADR-031).
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
    "EVENT_BRANCH_UNDONE",
    "EVENT_CHARGEBACK_DEADLINE_CHANGED",
    "EVENT_PAYMENT_DUPLICATED",
    "EVENT_RECORD_NOTE_INJECTED",
    "EVENT_REFUND_FX_ADJUSTED",
    "EVENT_TOOL_FX_OUTAGE",
    "EVENT_TYPES",
    "NOTE_FIELD",
    "NOTE_TABLES",
    "OUTAGE_FIELD",
    "TOOLS_RECORD",
    "TOOL_FX",
    "TRANSACTION_ID_SPACE",
    "UNDO_COMMAND_ID",
    "UNDO_EVENT_UID",
    "DerivedState",
    "DiffEntry",
    "ProjectedState",
    "ProjectionError",
    "SANDBOX_ORIGIN",
    "UndoMarks",
    "VALUE_MONETARY",
    "VALUE_NON_MONETARY",
    "VERDICT_ABOVE",
    "VERDICT_BELOW",
    "VERDICT_LABELS",
    "VERDICT_NOT_AVAILABLE",
    "VERDICT_WITHIN",
    "Verdict",
    "branch_hash",
    "canonical_rate",
    "diff_of",
    "holds_the_record",
    "is_undo_marker",
    "next_transaction_id",
    "oldest_moment",
    "project",
    "scenario_truth",
    "table_of_the_record",
    "undo_marks",
    "verdict_of",
]
