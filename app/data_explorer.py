"""Browse records and events in the signed-in account's ledger before drafting a question."""

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import streamlit as st

from ledgerlens.api.explorer import explore_rows

TRANSACTIONS = "transactions"
REFUNDS = "refunds"
CHARGEBACKS = "chargebacks"
FX = "fx_applied"
SETTLEMENTS = "settlements"
EVENTS = "events"
RECORDS_TAB = "Records"
EVENTS_TAB = "Events"
ALL_ACCOUNT_DATA = "All account data"

ID = "id"
TRANSACTION_ID = "transaction_id"
EVENT_ID = "event_id"
EVENT_TYPE = "type"
AGGREGATE_ID = "aggregate_id"
AGGREGATE_TYPE = "aggregate_type"
PAYLOAD = "payload"
STATUS = "status"
STAGE = "stage"
CURRENCY = "currency"
REQUESTED_CURRENCY = "requested_currency"
PAYOUT_CURRENCY = "payout_currency"
FROM_CURRENCY = "from_currency"
TO_CURRENCY = "to_currency"
CREATED_AT = "created_at"
OPENED_AT = "opened_at"
APPLIED_AT = "applied_at"
PERIOD_START = "period_start"
OCCURRED_AT = "occurred_at"
ID_SUFFIX = "_id"

DATASET_LABELS = {
    TRANSACTIONS: "Transactions",
    REFUNDS: "Refunds",
    CHARGEBACKS: "Disputes",
    FX: "FX applications",
    SETTLEMENTS: "Settlements",
}
RECORD_NAMES = {TRANSACTIONS: "payment", REFUNDS: "refund", CHARGEBACKS: "dispute", SETTLEMENTS: "settlement"}
AGGREGATE_DATASETS = {
    "transaction": TRANSACTIONS,
    "refund": REFUNDS,
    "chargeback": CHARGEBACKS,
    "settlement": SETTLEMENTS,
}
ID_LABELS = {
    TRANSACTIONS: "Payment ID",
    REFUNDS: "Refund ID",
    CHARGEBACKS: "Dispute ID",
    FX: "FX ID",
    SETTLEMENTS: "Settlement ID",
}
DATE_FIELDS = {
    TRANSACTIONS: CREATED_AT,
    REFUNDS: CREATED_AT,
    CHARGEBACKS: OPENED_AT,
    FX: APPLIED_AT,
    SETTLEMENTS: PERIOD_START,
    EVENTS: OCCURRED_AT,
}
CURRENCY_FIELDS = {
    TRANSACTIONS: (CURRENCY,),
    REFUNDS: (REQUESTED_CURRENCY, PAYOUT_CURRENCY),
    CHARGEBACKS: (CURRENCY,),
    FX: (FROM_CURRENCY, TO_CURRENCY),
    SETTLEMENTS: (CURRENCY,),
}
COLUMNS = {
    TRANSACTIONS: (
        ID,
        CREATED_AT,
        STATUS,
        "amount_minor",
        CURRENCY,
        "method",
        "merchant_id",
        "customer_id",
        "card_brand",
        "captured_at",
    ),
    REFUNDS: (
        ID,
        TRANSACTION_ID,
        CREATED_AT,
        STATUS,
        "requested_amount_minor",
        REQUESTED_CURRENCY,
        "payout_amount_minor",
        PAYOUT_CURRENCY,
        "reason",
        "resolved_at",
        "fx_applied_id",
    ),
    CHARGEBACKS: (
        ID,
        TRANSACTION_ID,
        OPENED_AT,
        STAGE,
        "amount_minor",
        CURRENCY,
        "reason_code",
        "deadline",
        "resolved_at",
    ),
    FX: (ID, TRANSACTION_ID, APPLIED_AT, "kind", FROM_CURRENCY, TO_CURRENCY, "applied_rate", "refund_id"),
    SETTLEMENTS: (
        ID,
        PERIOD_START,
        "period_end",
        STATUS,
        "gross_minor",
        "refunds_minor",
        "fees_minor",
        "net_minor",
        "carried_minor",
        CURRENCY,
        "expected_payout_date",
        "paid_at",
        "merchant_id",
    ),
    EVENTS: (EVENT_ID, OCCURRED_AT, EVENT_TYPE, AGGREGATE_ID, AGGREGATE_TYPE),
}
COLUMN_LABELS = {
    TRANSACTION_ID: "Payment ID",
    EVENT_TYPE: "Event type",
    "fx_applied_id": "FX ID",
}

Row = dict[str, Any]
PrepareDraft = Callable[[str, list[str]], None]


def _options(rows: list[Row], fields: tuple[str, ...]) -> list[str]:
    return sorted({row[field] for row in rows for field in fields if row.get(field)})


def _matches_id(row: Row, search: str) -> bool:
    return any(
        search in str(value).casefold()
        for field, value in row.items()
        if value is not None and (field == ID or field.endswith(ID_SUFFIX))
    )


def _filtered(rows: list[Row], dataset: str, key: str) -> list[Row]:
    identity, after, before = st.columns(3)
    search = identity.text_input("Search by ID", key=f"{key}-search").strip().casefold()
    start = after.date_input("From date", value=None, key=f"{key}-start", format="YYYY-MM-DD")
    end = before.date_input("Through date", value=None, key=f"{key}-end", format="YYYY-MM-DD")
    date_field = DATE_FIELDS[dataset]
    statuses, currencies, types = [], [], []
    status_field = STAGE if dataset == CHARGEBACKS else STATUS
    currency_fields = CURRENCY_FIELDS.get(dataset, ())
    if dataset == EVENTS:
        types = st.multiselect("Event type", _options(rows, (EVENT_TYPE,)), key=f"{key}-type")
    else:
        if status_field in COLUMNS[dataset]:
            status_column, currency_column = st.columns(2)
            statuses = status_column.multiselect("Status", _options(rows, (status_field,)), key=f"{key}-status")
        else:
            currency_column = st
        currencies = currency_column.multiselect("Currency", _options(rows, currency_fields), key=f"{key}-currency")

    def matches(row: Row) -> bool:
        day = date.fromisoformat(row[date_field][:10]) if start or end else None
        return (
            (not search or _matches_id(row, search))
            and (not start or day >= start)
            and (not end or day <= end)
            and (not types or row[EVENT_TYPE] in types)
            and (not statuses or row[status_field] in statuses)
            and (not currencies or any(row.get(field) in currencies for field in currency_fields))
        )

    return [row for row in rows if matches(row)]


def _column_label(dataset: str, field: str) -> str:
    if field == ID:
        return ID_LABELS[dataset]
    if field.endswith(ID_SUFFIX):
        return COLUMN_LABELS.get(field, f"{field[: -len(ID_SUFFIX)].replace('_', ' ').capitalize()} ID")
    return COLUMN_LABELS.get(field, field.replace("_", " ").capitalize())


def _show_rows(rows: list[Row], dataset: str) -> None:
    st.dataframe(
        [{_column_label(dataset, field): row.get(field) for field in COLUMNS[dataset]} for row in rows],
        hide_index=True,
    )


def _inspect_record(rows: list[Row], dataset: str, key: str, on_ask: PrepareDraft) -> None:
    by_id = {row[ID]: row for row in rows}
    selected = st.selectbox("Record to inspect", list(by_id), index=None, key=f"{key}-inspect")
    if selected is None:
        return
    transaction_id = by_id[selected].get(TRANSACTION_ID)
    ids = [selected, transaction_id] if transaction_id else [selected]
    if dataset == FX:
        question = f"What exchange rate was applied in {selected} for payment {transaction_id}?"
    else:
        reference = f"{selected} for payment {transaction_id}" if transaction_id else selected
        question = f"What can you tell me about {RECORD_NAMES[dataset]} {reference}?"
    st.button("Ask about this record", key=f"{key}-ask", on_click=on_ask, args=(question, ids))


def _open_record(tabs_key: str, context: str, dataset: str, record_id: str) -> None:
    st.session_state.update(
        {
            tabs_key: RECORDS_TAB,
            f"{context}-dataset": dataset,
            f"{context}-{dataset}-search": record_id,
            f"{context}-{dataset}-inspect": record_id,
        }
    )


def _inspect_event(rows: list[Row], context: str, tabs_key: str) -> None:
    by_id = {row[EVENT_ID]: row for row in rows}
    key = f"{context}-{EVENTS}"

    def label(event_id: int) -> str:
        row = by_id[event_id]
        return f"{event_id} · {row[EVENT_TYPE]} · {row[AGGREGATE_ID]}"

    selected = st.selectbox("Event to inspect", list(by_id), index=None, format_func=label, key=f"{key}-inspect")
    if selected is None:
        return
    row = by_id[selected]
    st.caption(f"{label(selected)} · {row[OCCURRED_AT]} · {row[AGGREGATE_TYPE]}")
    st.markdown("**Event payload**")
    st.json(row[PAYLOAD])
    dataset = AGGREGATE_DATASETS.get(row[AGGREGATE_TYPE])
    if dataset:
        st.button(
            f"View {RECORD_NAMES[dataset]} record",
            key=f"{key}-record",
            on_click=_open_record,
            args=(tabs_key, context, dataset, row[AGGREGATE_ID]),
        )


def render_explorer(
    path: Path,
    account_id: str,
    payment_id: str | None,
    on_ask: PrepareDraft,
) -> None:
    """Render account data from an already scoped ledger and send draft text to the composer."""
    transactions = explore_rows(path, TRANSACTIONS)
    payments = sorted({row[ID] for row in transactions})
    selected_payment = st.selectbox(
        "Payment scope",
        [ALL_ACCOUNT_DATA, *payments],
        index=payments.index(payment_id) + 1 if payment_id in payments else 0,
        key=f"explorer-payment-{account_id}-{payment_id}",
    )
    scope = None if selected_payment == ALL_ACCOUNT_DATA else selected_payment
    context = f"explorer-{account_id}-{scope}"
    tabs_key = f"explorer-tabs-{account_id}"
    records, events = st.tabs([RECORDS_TAB, EVENTS_TAB], key=tabs_key, on_change="rerun")
    if records.open:
        with records:
            dataset = st.selectbox(
                "Record type", list(DATASET_LABELS), format_func=DATASET_LABELS.__getitem__, key=f"{context}-dataset"
            )
            rows = transactions if dataset == TRANSACTIONS and scope is None else explore_rows(path, dataset, scope)
            key = f"{context}-{dataset}"
            filtered = _filtered(rows, dataset, key)
            if filtered:
                _show_rows(filtered, dataset)
                _inspect_record(filtered, dataset, key, on_ask)
            else:
                st.info("No records match these filters.")
    if events.open:
        with events:
            key = f"{context}-{EVENTS}"
            filtered = _filtered(explore_rows(path, EVENTS, scope), EVENTS, key)
            if filtered:
                _show_rows(filtered, EVENTS)
                _inspect_event(filtered, context, tabs_key)
            else:
                st.info("No events match these filters.")
