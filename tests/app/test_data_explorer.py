"""Exercise filtering and record inspection against the same scoped ledger the portal uses."""

import json
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from ledgerlens.api.accounts import scoped_ledger
from ledgerlens.sim.config import SimConfig
from ledgerlens.sim.pipeline import build_ledger


@pytest.fixture(scope="module")
def sample_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base = tmp_path_factory.mktemp("explorer") / "sample.db"
    build_ledger(SimConfig(source="sample"), base).conn.close()
    return base


@pytest.fixture(scope="module")
def explorer_page(sample_db: Path) -> str:
    folder = sample_db.parent
    base = sample_db
    ledgers = {account: scoped_ledger(base, account, folder / f"{account}.db") for account in ("M-09", "C-0412")}
    paths = {account: str(path) for account, path in ledgers.items()}
    return f"""
from pathlib import Path
import streamlit as st
from app.data_explorer import render_explorer

paths = {paths!r}
account = st.selectbox("Account", list(paths), key="account")
payment_id = st.selectbox("Focused payment", [None, "TX-2048"], key="focus", index=1) if account == "C-0412" else None

def draft(question, ids):
    st.session_state["prepared"] = (question, ids)

render_explorer(Path(paths[account]), account, payment_id, draft)
"""


def _element(elements, label):
    return next(element for element in elements if element.label == label)


def test_record_filters_and_draft_use_visible_account_records(explorer_page: str) -> None:
    page = AppTest.from_string(explorer_page).run()
    assert not page.exception
    assert [tab.label for tab in page.tabs] == ["Records", "Events"]
    _element(page.selectbox, "Record type").select("refunds").run()
    all_refunds = page.dataframe[0].value
    assert {"Refund ID", "Payment ID", "Requested currency", "Payout currency"} <= set(all_refunds.columns)
    assert {"R-0065", "R-0178"} <= set(all_refunds["Refund ID"])

    _element(page.multiselect, "Status").set_value(["paid"]).run()
    assert "R-0178" not in set(page.dataframe[0].value["Refund ID"])
    _element(page.multiselect, "Currency").set_value(["BRL"]).run()
    assert set(page.dataframe[0].value["Payout currency"]) == {"BRL"}
    _element(page.date_input, "From date").set_value(date(2026, 9, 4)).run()
    _element(page.date_input, "Through date").set_value(date(2026, 9, 4)).run()
    assert set(page.dataframe[0].value["Refund ID"]) == {"R-0065"}

    _element(page.text_input, "Search by ID").set_value("R-0005").run()
    assert any("No records match" in note.value for note in page.info)
    _element(page.text_input, "Search by ID").set_value("tx-0164").run()
    assert set(page.dataframe[0].value["Refund ID"]) == {"R-0065"}
    assert not any(button.label == "Ask about this record" for button in page.button)
    _element(page.selectbox, "Record to inspect").set_value("R-0065").run()
    _element(page.button, "Ask about this record").click().run()
    question, ids = page.session_state["prepared"]
    assert "R-0065" in question and "TX-0164" in question
    assert ids == ["R-0065", "TX-0164"]

    page.selectbox(key="account").select("C-0412").run()
    assert not page.exception
    assert _element(page.selectbox, "Payment scope").value == "TX-2048"
    assert _element(page.selectbox, "Record type").value == "transactions"
    assert _element(page.text_input, "Search by ID").value == ""
    assert set(page.dataframe[0].value["Payment ID"]) == {"TX-2048"}


def test_payment_scope_resets_filters_and_event_payload_loads_on_selection(explorer_page: str) -> None:
    page = AppTest.from_string(explorer_page).run()
    page.session_state["explorer-tabs-M-09"] = "Events"
    page.run()
    assert not page.exception
    assert not any(widget.label == "Record type" for widget in page.selectbox)
    assert "settlement.settled" in _element(page.multiselect, "Event type").options
    _element(page.multiselect, "Event type").set_value(["settlement.settled"]).run()
    assert set(page.dataframe[0].value["Event type"]) == {"settlement.settled"}

    _element(page.selectbox, "Payment scope").set_value("TX-0051").run()
    assert _element(page.multiselect, "Event type").value == []
    assert set(page.dataframe[0].value["Aggregate ID"]) == {"TX-0051"}
    assert not page.get("json")
    _element(page.multiselect, "Event type").set_value(["payment.authorized"]).run()
    event = int(page.dataframe[0].value.iloc[0]["Event ID"])
    _element(page.selectbox, "Event to inspect").set_value(event).run()
    payload = json.loads(page.get("json")[0].value)
    assert payload["currency"] == "USD"
    assert "card_fingerprint" not in payload


def test_refund_event_opens_its_record_without_leaving_the_payment(explorer_page: str) -> None:
    page = AppTest.from_string(explorer_page).run()
    page.selectbox(key="account").select("C-0412").run()
    page.session_state["explorer-tabs-C-0412"] = "Events"
    page.run()
    _element(page.multiselect, "Event type").set_value(["refund.requested"]).run()
    event = int(page.dataframe[0].value.iloc[0]["Event ID"])
    _element(page.selectbox, "Event to inspect").set_value(event).run()
    assert json.loads(page.get("json")[0].value)
    assert any("refund.requested" in item.value and "R-0731" in item.value for item in page.caption)

    _element(page.button, "View refund record").click().run()
    assert not page.exception
    assert _element(page.selectbox, "Payment scope").value == "TX-2048"
    assert set(page.dataframe[0].value["Refund ID"]) == {"R-0731"}
    assert _element(page.selectbox, "Record to inspect").value == "R-0731"
    _element(page.button, "Ask about this record").click().run()
    assert page.session_state["prepared"][1] == ["R-0731", "TX-2048"]


def test_full_sample_pages_native_rows_and_filters_tables_without_dates(sample_db: Path) -> None:
    page = AppTest.from_string(f"""
from pathlib import Path
from app.data_explorer import render_explorer

render_explorer(Path({str(sample_db)!r}), "sample", None, None, full_sample=True)
""").run()
    assert not page.exception
    dataset = _element(page.selectbox, "Record type")
    with closing(sqlite3.connect(sample_db)) as conn:
        table_names = {name for (name,) in conn.execute("SELECT name FROM sqlite_schema WHERE type='table'")}
        identifiers = [row[0] for row in conn.execute("SELECT id FROM transactions ORDER BY created_at DESC, id")]
    assert set(dataset.options) == table_names - {"sqlite_sequence", "events"}
    assert any(f"{len(identifiers):,} matching rows" in item.value for item in page.caption)
    assert not any(element.label == "Ask about this record" for element in page.button)
    assert "card_fingerprint" in page.dataframe[0].value.columns
    assert "source_ref" in page.dataframe[0].value.columns

    seen = list(page.dataframe[0].value["id"])
    pagination = _element(page.number_input, "Page")
    page_count = int(pagination.max)
    for number in range(2, page_count + 1):
        _element(page.number_input, "Page").set_value(number).run()
        seen.extend(page.dataframe[0].value["id"])
    assert seen == identifiers

    _element(page.text_input, "Search by ID").set_value(identifiers[0]).run()
    assert list(page.dataframe[0].value["id"]) == [identifiers[0]]
    _element(page.selectbox, "Record type").select("projector_state").run()
    assert not page.date_input and not page.multiselect
    assert "last_event_id" in page.dataframe[0].value.columns
    assert any("CREATE TABLE projector_state" in item.value for item in page.code)
    _element(page.text_input, "Search by name").set_value("missing-projector").run()
    assert not page.dataframe
    assert "0 matching rows" in [item.value for item in page.caption]

    _element(page.selectbox, "Payment scope").set_value("TX-2048").run()
    page.session_state["explorer-tabs-sample"] = "Events"
    page.run()
    frame = page.dataframe[0].value
    assert {"event_uid", "origin", "ingested_at", "payload"} <= set(frame.columns)
    assert set(frame["aggregate_id"]) == {"TX-2048", "R-0731"}
    authorization = frame[frame["type"] == "payment.authorized"].iloc[0]
    _element(page.text_input, "Search by ID").set_value(authorization["event_uid"]).run()
    assert list(page.dataframe[0].value["event_uid"]) == [authorization["event_uid"]]
    _element(page.selectbox, "Event to inspect").set_value(int(authorization["event_id"])).run()
    payload = json.loads(page.get("json")[0].value)
    assert "card_fingerprint" in payload and "source_ref" in payload
