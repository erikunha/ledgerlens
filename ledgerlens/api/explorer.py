"""Read account or sample tables through fixed projections on a read-only ledger."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
from typing import Any

from ledgerlens.api.ledger_service import open_ledger

TRANSACTIONS = "transactions"
REFUNDS = "refunds"
CHARGEBACKS = "chargebacks"
FX = "fx_applied"
SETTLEMENTS = "settlements"
EVENTS = "events"
CUSTOMERS = "customers"
MERCHANTS = "merchants"
PROJECTOR_STATE = "projector_state"

_BY_TRANSACTION = "transaction_id = :payment_id"
_PAYMENT_EVENTS = """
aggregate_id IN (
    SELECT id FROM transactions WHERE id = :payment_id
    UNION ALL SELECT id FROM refunds WHERE transaction_id = :payment_id
    UNION ALL SELECT id FROM chargebacks WHERE transaction_id = :payment_id
)
"""

# Each entry fixes the columns, display order, and payment relationship for that dataset.
_DATASETS: dict[str, tuple[str, str, str | None]] = {
    TRANSACTIONS: (
        "SELECT id, merchant_id, customer_id, amount_minor, currency, method, card_brand, status, "
        "created_at, captured_at FROM transactions",
        "created_at DESC, id",
        "id = :payment_id",
    ),
    REFUNDS: (
        "SELECT id, transaction_id, requested_amount_minor, requested_currency, payout_amount_minor, "
        "payout_currency, fx_applied_id, status, reason, created_at, resolved_at FROM refunds",
        "created_at DESC, id",
        _BY_TRANSACTION,
    ),
    CHARGEBACKS: (
        "SELECT id, transaction_id, amount_minor, currency, reason_code, stage, opened_at, deadline, "
        "resolved_at FROM chargebacks",
        "opened_at DESC, id",
        _BY_TRANSACTION,
    ),
    FX: (
        "SELECT id, transaction_id, refund_id, kind, from_currency, to_currency, applied_rate, applied_at "
        "FROM fx_applied",
        "applied_at DESC, id",
        _BY_TRANSACTION,
    ),
    SETTLEMENTS: (
        "SELECT id, merchant_id, period_start, period_end, currency, gross_minor, refunds_minor, fees_minor, "
        "net_minor, carried_minor, status, expected_payout_date, paid_at FROM settlements",
        "period_start DESC, id",
        None,
    ),
    EVENTS: (
        "SELECT event_id, occurred_at, type, aggregate_type, aggregate_id, "
        "json_remove(payload, '$.card_fingerprint', '$.source_ref') AS payload FROM events",
        "occurred_at, event_id",
        _PAYMENT_EVENTS,
    ),
}

# The simulator generates card fingerprints and hashes the public invoice IDs used as source references.
_SAMPLE_DATASETS = {
    **_DATASETS,
    TRANSACTIONS: (
        "SELECT id, merchant_id, customer_id, amount_minor, currency, method, card_brand, card_fingerprint, "
        "status, created_at, captured_at, origin, source_ref FROM transactions",
        "created_at DESC, id",
        "id = :payment_id",
    ),
    EVENTS: (
        "SELECT event_id, event_uid, occurred_at, type, aggregate_type, aggregate_id, payload, origin, ingested_at "
        "FROM events",
        "occurred_at, event_id",
        _PAYMENT_EVENTS,
    ),
    CUSTOMERS: (
        "SELECT id, display_name, country, billing_currency, created_at FROM customers",
        "id",
        "id IN (SELECT customer_id FROM transactions WHERE id = :payment_id)",
    ),
    MERCHANTS: (
        "SELECT id, name, country, category, settlement_currency, fx_plan, refund_window_days, onboarded_at "
        "FROM merchants",
        "id",
        "id IN (SELECT merchant_id FROM transactions WHERE id = :payment_id)",
    ),
    PROJECTOR_STATE: ("SELECT name, last_event_id FROM projector_state", "name", None),
}


def explore_rows(
    path: Path | str, dataset: str, payment_id: str | None = None, *, full_sample: bool = False
) -> list[dict[str, Any]]:
    """Return rows from a scoped ledger, or from the published sample when explicitly requested."""
    datasets = _SAMPLE_DATASETS if full_sample else _DATASETS
    try:
        select, order, payment_filter = datasets[dataset]
    except KeyError as error:
        raise ValueError(f"Unknown explorer dataset: {dataset}") from error

    params = {}
    if payment_id is not None:
        if payment_filter is None:
            return []  # This table has no direct payment link.
        select += f" WHERE {payment_filter}"
        params["payment_id"] = payment_id

    with closing(open_ledger(path)) as conn:
        return [dict(row) for row in conn.execute(f"{select} ORDER BY {order}", params)]


def explore_schema(path: Path | str, dataset: str) -> str:
    """Read the SQLite table definition for an allowlisted sample table."""
    if dataset not in _SAMPLE_DATASETS:
        raise ValueError(f"Unknown explorer dataset: {dataset}")
    with closing(open_ledger(path)) as conn:
        return conn.execute("SELECT sql FROM sqlite_schema WHERE type = 'table' AND name = ?", (dataset,)).fetchone()[0]
