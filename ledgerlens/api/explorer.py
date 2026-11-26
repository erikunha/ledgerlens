"""Read portal datasets from an account's scoped ledger using fixed projections."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
from typing import Any

from ledgerlens.api.ledger_service import open_ledger

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
    "transactions": (
        "SELECT id, merchant_id, customer_id, amount_minor, currency, method, card_brand, status, "
        "created_at, captured_at FROM transactions",
        "created_at DESC, id",
        "id = :payment_id",
    ),
    "refunds": (
        "SELECT id, transaction_id, requested_amount_minor, requested_currency, payout_amount_minor, "
        "payout_currency, fx_applied_id, status, reason, created_at, resolved_at FROM refunds",
        "created_at DESC, id",
        _BY_TRANSACTION,
    ),
    "chargebacks": (
        "SELECT id, transaction_id, amount_minor, currency, reason_code, stage, opened_at, deadline, "
        "resolved_at FROM chargebacks",
        "opened_at DESC, id",
        _BY_TRANSACTION,
    ),
    "fx_applied": (
        "SELECT id, transaction_id, refund_id, kind, from_currency, to_currency, applied_rate, applied_at "
        "FROM fx_applied",
        "applied_at DESC, id",
        _BY_TRANSACTION,
    ),
    "settlements": (
        "SELECT id, merchant_id, period_start, period_end, currency, gross_minor, refunds_minor, fees_minor, "
        "net_minor, carried_minor, status, expected_payout_date, paid_at FROM settlements",
        "period_start DESC, id",
        None,
    ),
    "events": (
        "SELECT event_id, occurred_at, type, aggregate_type, aggregate_id, "
        "json_remove(payload, '$.card_fingerprint', '$.source_ref') AS payload FROM events",
        "occurred_at, event_id",
        _PAYMENT_EVENTS,
    ),
}


def explore_rows(path: Path | str, dataset: str, payment_id: str | None = None) -> list[dict[str, Any]]:
    """Return the display columns for a dataset in an already-scoped ledger."""
    try:
        select, order, payment_filter = _DATASETS[dataset]
    except KeyError as error:
        raise ValueError(f"Unknown explorer dataset: {dataset}") from error

    params = {}
    if payment_id is not None:
        if payment_filter is None:
            return []  # A settlement covers a merchant period without a direct payment link.
        select += f" WHERE {payment_filter}"
        params["payment_id"] = payment_id

    with closing(open_ledger(path)) as conn:
        return [dict(row) for row in conn.execute(f"{select} ORDER BY {order}", params)]
