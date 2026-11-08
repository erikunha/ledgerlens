"""Projector: turns the event log into the seven read tables the agent queries.

Rules:

* events apply in `event_id` order, and the last applied id is kept in `projector_state`;
* an event whose `event_uid` was already applied is skipped;
* an event that refers to a missing parent (a refund for an unknown transaction, say) is an error.
  In strict mode (the default) it raises `ProjectionError` and that event leaves no trace; in lenient
  mode it is recorded in `Projector.errors` and the run goes on;
* replaying the whole log into an empty database gives the same `canonical_hash`.

A rejected refund stores the operator's `rejection_reason` in `refunds.reason`, the single reason
column; the customer's own text stays in the `refund.requested` payload.
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from ledgerlens.sim.events import AppendResult, Event, EventStore, StoredEvent, canonical_json

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
PROJECTOR_NAME = "main"
READ_TABLES = (
    ("merchants", "id"),
    ("customers", "id"),
    ("transactions", "id"),
    ("fx_applied", "id"),
    ("refunds", "id"),
    ("chargebacks", "id"),
    ("settlements", "id"),
)


class ProjectionError(RuntimeError):
    """An event could not be applied in strict mode."""


@dataclass(frozen=True)
class ProjectorError:
    event_id: int | None
    event_uid: str
    event_type: str
    message: str


def create_database(path: str | Path = ":memory:") -> sqlite3.Connection:
    """A new database with the ledger schema. An existing file at `path` is replaced."""
    if str(path) != ":memory:":
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        for suffix in ("", "-journal", "-wal", "-shm"):
            Path(str(target) + suffix).unlink(missing_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
    return conn


def canonical_hash(conn: sqlite3.Connection) -> str:
    """SHA-256 of a sorted dump of the read tables. Events and projector state are not part of it."""
    digest = hashlib.sha256()
    for table, key in READ_TABLES:
        cursor = conn.execute(f"SELECT * FROM {table} ORDER BY {key}")  # noqa: S608 (fixed table list)
        columns = [d[0] for d in cursor.description]
        digest.update(f"#{table}\n".encode())
        for row in cursor:
            digest.update((canonical_json(dict(zip(columns, row, strict=True))) + "\n").encode("utf-8"))
    return digest.hexdigest()


def rebuild_database(source: sqlite3.Connection, *, strict: bool = True) -> sqlite3.Connection:
    """Copy the event log of `source` in order into an empty in-memory database and project it."""
    target = create_database(":memory:")
    projector = Projector(target, strict=strict)
    projector.ingest(stored.event for stored in EventStore(source).read())
    return target


@dataclass
class Projector:
    conn: sqlite3.Connection
    strict: bool = True
    errors: list[ProjectorError] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.store = EventStore(self.conn)
        self._seen: set[str] = set()
        self._handlers: dict[str, Callable[[Event], None]] = {
            "merchant.onboarded": self._merchant,
            "customer.created": self._customer,
            "payment.authorized": self._authorized,
            "payment.captured": self._captured,
            "payment.failed": self._failed,
            "fx.applied": self._fx,
            "refund.requested": self._refund_requested,
            "payment.refunded": self._refund_paid,
            "payment.partially_refunded": self._refund_paid,
            "refund.rejected": self._refund_rejected,
            "chargeback.opened": self._cb_opened,
            "chargeback.evidence_requested": lambda e: self._cb_stage(e, "evidence_requested"),
            "chargeback.evidence_submitted": lambda e: self._cb_stage(e, "evidence_submitted"),
            "chargeback.won": lambda e: self._cb_stage(e, "won"),
            "chargeback.lost": lambda e: self._cb_stage(e, "lost"),
            "settlement.settled": self._settled,
            "payout.paid": self._paid,
        }

    # -- public API ---------------------------------------------------------------------------

    def ingest(self, events: Iterable[Event]) -> AppendResult:
        """Append events to the log (duplicates are ignored) and project whatever is pending."""
        result = self.store.append(events)
        self.project_pending()
        self.conn.commit()
        return result

    def project_pending(self) -> int:
        """Apply every logged event after the checkpoint. Returns how many were applied."""
        row = self.conn.execute(
            "SELECT last_event_id FROM projector_state WHERE name = ?", (PROJECTOR_NAME,)
        ).fetchone()
        last = row[0] if row else 0
        applied = 0
        for stored in list(self.store.read(last)):
            if self._project(stored):
                applied += 1
            self.conn.execute(
                "INSERT INTO projector_state (name, last_event_id) VALUES (?, ?)"
                " ON CONFLICT(name) DO UPDATE SET last_event_id = excluded.last_event_id",
                (PROJECTOR_NAME, stored.event_id),
            )
        return applied

    def apply(self, event: Event) -> bool:
        """Apply one event now. Returns False when its uid was already applied."""
        return self._project(StoredEvent(0, event), event_id=None)

    # -- internals ----------------------------------------------------------------------------

    def _project(self, stored: StoredEvent, event_id: int | None = -1) -> bool:
        event = stored.event
        uid = event.event_uid
        if uid in self._seen:
            return False
        self.conn.execute("SAVEPOINT event")
        try:
            self._handlers[event.type](event)
        except _Missing as problem:
            self.conn.execute("ROLLBACK TO event")
            self.conn.execute("RELEASE event")
            error = ProjectorError(stored.event_id if event_id is not None else None, uid, event.type, str(problem))
            self.errors.append(error)
            if self.strict:
                raise ProjectionError(f"{event.type} {event.aggregate_id}: {problem}") from None
            return False
        except sqlite3.IntegrityError as problem:
            self.conn.execute("ROLLBACK TO event")
            self.conn.execute("RELEASE event")
            error = ProjectorError(stored.event_id if event_id is not None else None, uid, event.type, str(problem))
            self.errors.append(error)
            if self.strict:
                raise ProjectionError(f"{event.type} {event.aggregate_id}: {problem}") from None
            return False
        self.conn.execute("RELEASE event")
        self._seen.add(uid)
        return True

    def _require(self, table: str, key: str, value: str, what: str) -> None:
        found = self.conn.execute(f"SELECT 1 FROM {table} WHERE {key} = ?", (value,)).fetchone()  # noqa: S608
        if not found:
            raise _Missing(f"unknown {what} {value}")

    def _merchant(self, e: Event) -> None:
        p = e.payload
        self.conn.execute(
            "INSERT INTO merchants (id, name, country, category, settlement_currency, fx_plan, refund_window_days, onboarded_at)"  # noqa: E501
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                e.aggregate_id,
                p["name"],
                p["country"],
                p["category"],
                p["settlement_currency"],
                p["fx_plan"],
                p["refund_window_days"],
                e.occurred_at,
            ),
        )

    def _customer(self, e: Event) -> None:
        p = e.payload
        self.conn.execute(
            "INSERT INTO customers (id, display_name, country, billing_currency, created_at) VALUES (?, ?, ?, ?, ?)",
            (e.aggregate_id, p["display_name"], p["country"], p["billing_currency"], e.occurred_at),
        )

    def _authorized(self, e: Event) -> None:
        p = e.payload
        self._require("merchants", "id", p["merchant_id"], "merchant")
        self._require("customers", "id", p["customer_id"], "customer")
        self.conn.execute(
            "INSERT INTO transactions (id, merchant_id, customer_id, amount_minor, currency, method, card_brand,"
            " card_fingerprint, status, created_at, captured_at, origin, source_ref)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'authorized', ?, NULL, ?, ?)",
            (
                e.aggregate_id,
                p["merchant_id"],
                p["customer_id"],
                p["amount_minor"],
                p["currency"],
                p["method"],
                p["card_brand"],
                p["card_fingerprint"],
                e.occurred_at,
                e.origin,
                p["source_ref"],
            ),
        )

    def _move(self, tx_id: str, allowed: tuple[str, ...], status: str, captured_at: str | None = None) -> None:
        row = self.conn.execute("SELECT status FROM transactions WHERE id = ?", (tx_id,)).fetchone()
        if row is None:
            raise _Missing(f"unknown transaction {tx_id}")
        if row[0] not in allowed:
            raise _Missing(f"transaction {tx_id} is {row[0]}, expected one of {', '.join(allowed)}")
        if captured_at is not None:
            self.conn.execute(
                "UPDATE transactions SET status = ?, captured_at = ? WHERE id = ?", (status, captured_at, tx_id)
            )
        else:
            self.conn.execute("UPDATE transactions SET status = ? WHERE id = ?", (status, tx_id))

    def _captured(self, e: Event) -> None:
        self._move(e.aggregate_id, ("authorized",), "captured", e.payload["captured_at"])

    def _failed(self, e: Event) -> None:
        self._move(e.aggregate_id, ("authorized",), "failed")

    def _fx(self, e: Event) -> None:
        p = e.payload
        self._require("transactions", "id", e.aggregate_id, "transaction")
        self.conn.execute(
            "INSERT INTO fx_applied (id, transaction_id, refund_id, kind, from_currency, to_currency, applied_rate, applied_at)"  # noqa: E501
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                p["fx_id"],
                e.aggregate_id,
                p["refund_id"],
                p["kind"],
                p["from_currency"],
                p["to_currency"],
                p["applied_rate"],
                e.occurred_at,
            ),
        )

    def _refund_requested(self, e: Event) -> None:
        p = e.payload
        self._require("transactions", "id", p["transaction_id"], "transaction")
        self.conn.execute(
            "INSERT INTO refunds (id, transaction_id, requested_amount_minor, requested_currency, payout_amount_minor,"
            " payout_currency, fx_applied_id, status, reason, created_at, resolved_at)"
            " VALUES (?, ?, ?, ?, NULL, NULL, NULL, 'requested', ?, ?, NULL)",
            (
                e.aggregate_id,
                p["transaction_id"],
                p["requested_amount_minor"],
                p["requested_currency"],
                p["reason"],
                e.occurred_at,
            ),
        )

    def _refund_paid(self, e: Event) -> None:
        p = e.payload
        self._require("transactions", "id", p["transaction_id"], "transaction")
        if p["fx_id"] is not None:
            self._require("fx_applied", "id", p["fx_id"], "fx rate")
        exists = self.conn.execute("SELECT 1 FROM refunds WHERE id = ?", (p["refund_id"],)).fetchone()
        if exists:
            self.conn.execute(
                "UPDATE refunds SET payout_amount_minor = ?, payout_currency = ?, fx_applied_id = ?, status = 'paid',"
                " resolved_at = ? WHERE id = ?",
                (p["payout_amount_minor"], p["payout_currency"], p["fx_id"], e.occurred_at, p["refund_id"]),
            )
        else:
            self.conn.execute(
                "INSERT INTO refunds (id, transaction_id, requested_amount_minor, requested_currency, payout_amount_minor,"  # noqa: E501
                " payout_currency, fx_applied_id, status, reason, created_at, resolved_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, 'paid', ?, ?, ?)",
                (
                    p["refund_id"],
                    p["transaction_id"],
                    p["requested_amount_minor"],
                    p["requested_currency"],
                    p["payout_amount_minor"],
                    p["payout_currency"],
                    p["fx_id"],
                    p["reason"],
                    e.occurred_at,
                    e.occurred_at,
                ),
            )
        status = "refunded" if e.type == "payment.refunded" else "partially_refunded"
        self.conn.execute("UPDATE transactions SET status = ? WHERE id = ?", (status, p["transaction_id"]))

    def _refund_rejected(self, e: Event) -> None:
        p = e.payload
        self._require("transactions", "id", p["transaction_id"], "transaction")
        exists = self.conn.execute("SELECT 1 FROM refunds WHERE id = ?", (p["refund_id"],)).fetchone()
        if exists:
            self.conn.execute(
                "UPDATE refunds SET status = 'rejected', reason = ?, resolved_at = ? WHERE id = ?",
                (p["rejection_reason"], e.occurred_at, p["refund_id"]),
            )
        else:
            self.conn.execute(
                "INSERT INTO refunds (id, transaction_id, requested_amount_minor, requested_currency, payout_amount_minor,"  # noqa: E501
                " payout_currency, fx_applied_id, status, reason, created_at, resolved_at)"
                " VALUES (?, ?, ?, ?, NULL, NULL, NULL, 'rejected', ?, ?, ?)",
                (
                    p["refund_id"],
                    p["transaction_id"],
                    p["requested_amount_minor"],
                    p["requested_currency"],
                    p["rejection_reason"],
                    e.occurred_at,
                    e.occurred_at,
                ),
            )

    def _cb_opened(self, e: Event) -> None:
        p = e.payload
        self._require("transactions", "id", p["transaction_id"], "transaction")
        self.conn.execute(
            "INSERT INTO chargebacks (id, transaction_id, amount_minor, currency, reason_code, stage, opened_at, deadline, resolved_at)"  # noqa: E501
            " VALUES (?, ?, ?, ?, ?, 'opened', ?, ?, NULL)",
            (
                p["chargeback_id"],
                p["transaction_id"],
                p["amount_minor"],
                p["currency"],
                p["reason_code"],
                e.occurred_at,
                p["deadline"],
            ),
        )
        self.conn.execute("UPDATE transactions SET status = 'disputed' WHERE id = ?", (p["transaction_id"],))

    def _cb_stage(self, e: Event, stage: str) -> None:
        cb_id = e.payload["chargeback_id"]
        row = self.conn.execute("SELECT transaction_id FROM chargebacks WHERE id = ?", (cb_id,)).fetchone()
        if row is None:
            raise _Missing(f"unknown chargeback {cb_id}")
        resolved = e.occurred_at if stage in ("won", "lost") else None
        self.conn.execute("UPDATE chargebacks SET stage = ?, resolved_at = ? WHERE id = ?", (stage, resolved, cb_id))
        if stage == "lost":
            self.conn.execute("UPDATE transactions SET status = 'charged_back' WHERE id = ?", (row[0],))
        elif stage == "won":
            self.conn.execute("UPDATE transactions SET status = 'captured' WHERE id = ?", (row[0],))

    def _settled(self, e: Event) -> None:
        p = e.payload
        self._require("merchants", "id", p["merchant_id"], "merchant")
        self.conn.execute(
            "INSERT INTO settlements (id, merchant_id, period_start, period_end, currency, gross_minor, refunds_minor,"
            " fees_minor, net_minor, status, expected_payout_date, paid_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'scheduled', ?, NULL)",  # noqa: E501
            (
                p["settlement_id"],
                p["merchant_id"],
                p["period_start"],
                p["period_end"],
                p["currency"],
                p["gross_minor"],
                p["refunds_minor"],
                p["fees_minor"],
                p["net_minor"],
                p["expected_payout_date"],
            ),
        )

    def _paid(self, e: Event) -> None:
        p = e.payload
        self._require("settlements", "id", p["settlement_id"], "settlement")
        self.conn.execute(
            "UPDATE settlements SET status = 'paid', paid_at = ? WHERE id = ?", (p["paid_at"], p["settlement_id"])
        )


class _Missing(Exception):
    """A parent or a precondition is missing. Turned into a ProjectorError by the projector."""


def dump_rows(conn: sqlite3.Connection, table: str) -> list[dict]:
    """Rows of one read table as dicts, ordered by primary key. Used by tests and the manifest."""
    cursor = conn.execute(f"SELECT * FROM {table} ORDER BY id")  # noqa: S608
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor]


__all__ = [
    "ProjectionError",
    "Projector",
    "ProjectorError",
    "canonical_hash",
    "create_database",
    "dump_rows",
    "rebuild_database",
]
