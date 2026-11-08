"""The event log: what can happen, the shape of each payload, and the append-only store.

Every fact the agent can see was produced by an event. An event says where it came from
(`origin`: `public`, `synthetic` or `scenario:Sxx`). `event_uid` is a hash of
`(type, aggregate_id, occurred_at, payload)`, so appending the same event twice is a no-op.
Timestamps are UTC text, `YYYY-MM-DDTHH:MM:SSZ`.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

# type -> (aggregate type, required payload keys).
EVENT_SHAPES: dict[str, tuple[str, frozenset[str]]] = {
    "merchant.onboarded": (
        "merchant",
        frozenset({"name", "country", "category", "settlement_currency", "fx_plan", "refund_window_days"}),
    ),
    "customer.created": ("customer", frozenset({"display_name", "country", "billing_currency"})),
    "payment.authorized": (
        "transaction",
        frozenset(
            {
                "merchant_id",
                "customer_id",
                "amount_minor",
                "currency",
                "method",
                "card_brand",
                "card_fingerprint",
                "source_ref",
            }
        ),
    ),
    "payment.captured": ("transaction", frozenset({"captured_at"})),
    "payment.failed": ("transaction", frozenset({"reason"})),
    "fx.applied": (
        "transaction",
        frozenset({"fx_id", "refund_id", "kind", "from_currency", "to_currency", "applied_rate"}),
    ),
    "refund.requested": (
        "refund",
        frozenset({"transaction_id", "requested_amount_minor", "requested_currency", "reason"}),
    ),
    "payment.refunded": (
        "refund",
        frozenset(
            {
                "refund_id",
                "transaction_id",
                "requested_amount_minor",
                "requested_currency",
                "payout_amount_minor",
                "payout_currency",
                "fx_id",
                "reason",
            }
        ),
    ),
    "payment.partially_refunded": (
        "refund",
        frozenset(
            {
                "refund_id",
                "transaction_id",
                "requested_amount_minor",
                "requested_currency",
                "payout_amount_minor",
                "payout_currency",
                "fx_id",
                "reason",
            }
        ),
    ),
    "refund.rejected": (
        "refund",
        frozenset(
            {
                "refund_id",
                "transaction_id",
                "requested_amount_minor",
                "requested_currency",
                "reason",
                "rejection_reason",
            }
        ),
    ),
    "chargeback.opened": (
        "chargeback",
        frozenset({"chargeback_id", "transaction_id", "amount_minor", "currency", "reason_code", "deadline"}),
    ),
    "chargeback.evidence_requested": ("chargeback", frozenset({"chargeback_id"})),
    "chargeback.evidence_submitted": ("chargeback", frozenset({"chargeback_id"})),
    "chargeback.won": ("chargeback", frozenset({"chargeback_id"})),
    "chargeback.lost": ("chargeback", frozenset({"chargeback_id"})),
    "settlement.settled": (
        "settlement",
        frozenset(
            {
                "settlement_id",
                "merchant_id",
                "period_start",
                "period_end",
                "currency",
                "gross_minor",
                "refunds_minor",
                "fees_minor",
                "net_minor",
                "expected_payout_date",
            }
        ),
    ),
    "payout.paid": ("settlement", frozenset({"settlement_id", "paid_at"})),
}
EVENT_TYPES = tuple(EVENT_SHAPES)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True)
class Event:
    type: str
    aggregate_type: str
    aggregate_id: str
    occurred_at: str
    payload: dict[str, Any]
    origin: str
    ingested_at: str | None = None

    def __post_init__(self) -> None:
        if self.type not in EVENT_SHAPES:
            raise ValueError(f"unknown event type {self.type!r}")
        aggregate, required = EVENT_SHAPES[self.type]
        if self.aggregate_type != aggregate:
            raise ValueError(f"{self.type} belongs to aggregate {aggregate!r}, not {self.aggregate_type!r}")
        missing = required - set(self.payload)
        if missing:
            raise ValueError(f"{self.type} payload lacks {', '.join(sorted(missing))}")

    @property
    def event_uid(self) -> str:
        body = canonical_json([self.type, self.aggregate_id, self.occurred_at, self.payload])
        return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class StoredEvent:
    event_id: int
    event: Event


@dataclass(frozen=True)
class AppendResult:
    appended: int
    duplicates: int


class EventStore:
    """Append-only access to the `events` table. Updates and deletes are blocked by triggers."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def append(self, events: Iterable[Event]) -> AppendResult:
        appended = duplicates = 0
        for event in events:
            cursor = self.conn.execute(
                "INSERT OR IGNORE INTO events (event_uid, occurred_at, type, aggregate_type, aggregate_id, payload, origin, ingested_at)"  # noqa: E501
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event.event_uid,
                    event.occurred_at,
                    event.type,
                    event.aggregate_type,
                    event.aggregate_id,
                    canonical_json(event.payload),
                    event.origin,
                    event.ingested_at or event.occurred_at,
                ),
            )
            if cursor.rowcount:
                appended += 1
            else:
                duplicates += 1
        return AppendResult(appended, duplicates)

    def read(self, after_id: int = 0) -> Iterator[StoredEvent]:
        rows = self.conn.execute(
            "SELECT event_id, type, aggregate_type, aggregate_id, occurred_at, payload, origin, ingested_at"
            " FROM events WHERE event_id > ? ORDER BY event_id",
            (after_id,),
        ).fetchall()
        for event_id, type_, aggregate_type, aggregate_id, occurred_at, payload, origin, ingested_at in rows:
            yield StoredEvent(
                event_id,
                Event(type_, aggregate_type, aggregate_id, occurred_at, json.loads(payload), origin, ingested_at),
            )

    def count(self) -> int:
        return self.conn.execute("SELECT count(*) FROM events").fetchone()[0]
