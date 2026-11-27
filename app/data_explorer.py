"""Browse the sample ledger or inspect account records before drafting a question."""

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import streamlit as st

from ledgerlens.api.explorer import (
    CHARGEBACKS,
    CUSTOMERS,
    EVENTS,
    FX,
    MERCHANTS,
    PROJECTOR_STATE,
    REFUNDS,
    SETTLEMENTS,
    TRANSACTIONS,
    explore_rows,
    explore_schema,
)

RECORDS_TAB = "Records"
EVENTS_TAB = "Events"
ALL_ACCOUNT_DATA = "All account data"
ALL_SAMPLE_DATA = "All sample data"
ROWS_PER_PAGE = 100

ID = "id"
TRANSACTION_ID = "transaction_id"
EVENT_ID = "event_id"
EVENT_UID = "event_uid"
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
ONBOARDED_AT = "onboarded_at"
BILLING_CURRENCY = "billing_currency"
SETTLEMENT_CURRENCY = "settlement_currency"
DISPLAY_NAME = "display_name"
NAME = "name"
ID_SUFFIX = "_id"

DATASET_LABELS = {
    TRANSACTIONS: "Transactions",
    REFUNDS: "Refunds",
    CHARGEBACKS: "Disputes",
    FX: "FX applications",
    SETTLEMENTS: "Settlements",
}
SAMPLE_RECORDS = (*DATASET_LABELS, CUSTOMERS, MERCHANTS, PROJECTOR_STATE)
NAME_FIELDS = {CUSTOMERS: DISPLAY_NAME, MERCHANTS: NAME, PROJECTOR_STATE: NAME}
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
    CUSTOMERS: CREATED_AT,
    MERCHANTS: ONBOARDED_AT,
}
CURRENCY_FIELDS = {
    TRANSACTIONS: (CURRENCY,),
    REFUNDS: (REQUESTED_CURRENCY, PAYOUT_CURRENCY),
    CHARGEBACKS: (CURRENCY,),
    FX: (FROM_CURRENCY, TO_CURRENCY),
    SETTLEMENTS: (CURRENCY,),
    CUSTOMERS: (BILLING_CURRENCY,),
    MERCHANTS: (SETTLEMENT_CURRENCY,),
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
        if value is not None and (field in (ID, EVENT_UID) or field.endswith(ID_SUFFIX))
    )


def _reset_page(key: str) -> None:
    st.session_state.pop(f"{key}-page", None)


def _filtered(rows: list[Row], dataset: str, key: str) -> list[Row]:
    date_field = DATE_FIELDS.get(dataset)
    name_field = NAME_FIELDS.get(dataset)
    reset = {"on_change": _reset_page, "args": (key,)}
    if date_field:
        identity, after, before = st.columns(3)
        start = after.date_input("From date", value=None, key=f"{key}-start", format="YYYY-MM-DD", **reset)
        end = before.date_input("Through date", value=None, key=f"{key}-end", format="YYYY-MM-DD", **reset)
    else:
        identity = st
        start = end = None
    if dataset == PROJECTOR_STATE:
        search_label = "Search by name"
    else:
        search_label = "Search by ID or name" if name_field else "Search by ID"
    search = identity.text_input(search_label, key=f"{key}-search", **reset).strip().casefold()
    statuses, currencies, types = [], [], []
    status_field = STAGE if dataset == CHARGEBACKS else STATUS
    currency_fields = CURRENCY_FIELDS.get(dataset, ())
    if dataset == EVENTS:
        types = st.multiselect("Event type", _options(rows, (EVENT_TYPE,)), key=f"{key}-type", **reset)
    else:
        if status_field in COLUMNS.get(dataset, ()):
            status_column, currency_column = st.columns(2)
            statuses = status_column.multiselect(
                "Status", _options(rows, (status_field,)), key=f"{key}-status", **reset
            )
        else:
            currency_column = st
        if currency_fields:
            currencies = currency_column.multiselect(
                "Currency", _options(rows, currency_fields), key=f"{key}-currency", **reset
            )

    def matches(row: Row) -> bool:
        day = date.fromisoformat(row[date_field][:10]) if start or end else None
        return (
            (not search or _matches_id(row, search) or (name_field and search in row[name_field].casefold()))
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


def _show_rows(rows: list[Row], dataset: str, key: str, full_sample: bool) -> list[Row]:
    count = len(rows)
    page_count = (count + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE
    if not rows:
        st.caption("0 matching rows")
        return []
    page = st.number_input("Page", min_value=1, max_value=page_count, key=f"{key}-page") if page_count > 1 else 1
    first = (page - 1) * ROWS_PER_PAGE
    visible = rows[first : first + ROWS_PER_PAGE]
    st.caption(
        f"{count:,} matching rows · Showing {first + 1:,} to {first + len(visible):,} · Page {page} of {page_count}"
    )
    if not full_sample:
        frame = [{_column_label(dataset, field): row[field] for field in COLUMNS[dataset]} for row in visible]
    else:
        frame = visible
    st.dataframe(frame, hide_index=True)
    return visible


def _show_schema(path: Path, dataset: str) -> None:
    with st.expander("SQLite schema", expanded=True):
        st.code(explore_schema(path, dataset), language="sql")
        if dataset in (TRANSACTIONS, EVENTS):
            st.caption("The simulator generates card fingerprints and hashes public invoice IDs for source references.")


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
    _reset_page(f"{context}-{dataset}")
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
    on_ask: PrepareDraft | None,
    *,
    full_sample: bool = False,
) -> None:
    """Browse the ledger supplied by the caller and optionally prepare an account draft."""
    transactions = explore_rows(path, TRANSACTIONS, full_sample=full_sample)
    payments = sorted({row[ID] for row in transactions})
    all_data = ALL_SAMPLE_DATA if full_sample else ALL_ACCOUNT_DATA
    selected_payment = st.selectbox(
        "Payment scope",
        [all_data, *payments],
        index=payments.index(payment_id) + 1 if payment_id in payments else 0,
        key=f"explorer-payment-{account_id}-{payment_id}",
    )
    scope = None if selected_payment == all_data else selected_payment
    context = f"explorer-{account_id}-{scope}"
    tabs_key = f"explorer-tabs-{account_id}"
    records, events = st.tabs([RECORDS_TAB, EVENTS_TAB], key=tabs_key, on_change="rerun")
    if records.open:
        with records:
            if full_sample:
                dataset = st.selectbox("Record type", SAMPLE_RECORDS, key=f"{context}-dataset")
                _show_schema(path, dataset)
            else:
                dataset = st.selectbox(
                    "Record type",
                    list(DATASET_LABELS),
                    format_func=DATASET_LABELS.__getitem__,
                    key=f"{context}-dataset",
                )
            rows = (
                transactions
                if dataset == TRANSACTIONS and scope is None
                else explore_rows(path, dataset, scope, full_sample=full_sample)
            )
            key = f"{context}-{dataset}"
            filtered = _filtered(rows, dataset, key)
            visible = _show_rows(filtered, dataset, key, full_sample)
            if not visible:
                st.info("No records match these filters.")
            elif on_ask is not None and not full_sample:
                _inspect_record(visible, dataset, key, on_ask)
    if events.open:
        with events:
            if full_sample:
                _show_schema(path, EVENTS)
            key = f"{context}-{EVENTS}"
            filtered = _filtered(explore_rows(path, EVENTS, scope, full_sample=full_sample), EVENTS, key)
            visible = _show_rows(filtered, EVENTS, key, full_sample)
            if visible:
                _inspect_event(visible, context, tabs_key)
            else:
                st.info("No events match these filters.")
