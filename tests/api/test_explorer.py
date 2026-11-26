"""Exercise the explorer projections against the same account ledger copies the portal uses."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from ledgerlens.api.accounts import scoped_ledger
from ledgerlens.api.explorer import explore_rows
from ledgerlens.sim.config import SimConfig
from ledgerlens.sim.pipeline import build_ledger


@pytest.fixture(scope="module")
def ledger_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("explorer") / "ledger.db"
    build_ledger(SimConfig(source="sample"), path).conn.close()
    return path


def test_customer_explorer_shows_only_its_payments_and_related_rows(ledger_db: Path, tmp_path: Path) -> None:
    ledger = scoped_ledger(ledger_db, "C-0412", tmp_path / "customer.db")
    assert explore_rows(ledger, "transactions") == [
        {
            "id": "TX-2048",
            "merchant_id": "M-17",
            "customer_id": "C-0412",
            "amount_minor": 10000,
            "currency": "EUR",
            "method": "card",
            "card_brand": "visa",
            "status": "refunded",
            "created_at": "2026-10-15T09:12:00Z",
            "captured_at": "2026-10-15T09:12:04Z",
        }
    ]
    (refund,) = explore_rows(ledger, "refunds", "TX-2048")
    assert (refund["id"], refund["transaction_id"], refund["payout_amount_minor"], refund["fx_applied_id"]) == (
        "R-0731",
        "TX-2048",
        54931,
        "FX-9002",
    )
    rates = {row["id"]: (row["kind"], row["applied_rate"]) for row in explore_rows(ledger, "fx_applied", "TX-2048")}
    assert rates == {"FX-9001": ("charge", "5.6679"), "FX-9002": ("refund", "5.4931")}
    for dataset in ("transactions", "refunds", "fx_applied", "events"):
        assert explore_rows(ledger, dataset, "TX-2077") == []
    assert explore_rows(ledger, "settlements") == []


def test_payment_events_include_the_chronological_refund_chain(ledger_db: Path, tmp_path: Path) -> None:
    ledger = scoped_ledger(ledger_db, "C-0412", tmp_path / "customer.db")
    events = explore_rows(ledger, "events", "TX-2048")
    assert [(row["type"], row["aggregate_id"]) for row in events] == [
        ("payment.authorized", "TX-2048"),
        ("payment.captured", "TX-2048"),
        ("fx.applied", "TX-2048"),
        ("refund.requested", "R-0731"),
        ("fx.applied", "TX-2048"),
        ("payment.refunded", "R-0731"),
    ]
    assert [(row["occurred_at"], row["event_id"]) for row in events] == sorted(
        (row["occurred_at"], row["event_id"]) for row in events
    )
    assert json.loads(events[-1]["payload"])["fx_id"] == "FX-9002"
    authorization = json.loads(events[0]["payload"])
    assert authorization["amount_minor"] == 10000
    assert {"card_fingerprint", "source_ref"}.isdisjoint(authorization)
    account_events = explore_rows(ledger, "events")
    assert {row["aggregate_id"] for row in account_events} == {"C-0412", "M-17", "TX-2048", "R-0731"}
    assert [(row["occurred_at"], row["event_id"]) for row in account_events] == sorted(
        (row["occurred_at"], row["event_id"]) for row in account_events
    )


def test_chargeback_projection_and_events_follow_the_transaction(ledger_db: Path, tmp_path: Path) -> None:
    ledger = scoped_ledger(ledger_db, "C-0291", tmp_path / "customer.db")
    (chargeback,) = explore_rows(ledger, "chargebacks", "TX-2077")
    assert (chargeback["id"], chargeback["transaction_id"], chargeback["stage"], chargeback["deadline"]) == (
        "CB-0310",
        "TX-2077",
        "evidence_requested",
        "2026-11-09",
    )
    events = explore_rows(ledger, "events", "TX-2077")
    assert [row["type"] for row in events if row["aggregate_id"] == "CB-0310"] == [
        "chargeback.opened",
        "chargeback.evidence_requested",
    ]
    assert explore_rows(ledger, "chargebacks", "TX-2048") == []


def test_merchant_settlements_are_available_only_without_a_payment_filter(ledger_db: Path, tmp_path: Path) -> None:
    ledger = scoped_ledger(ledger_db, "M-03", tmp_path / "merchant.db")
    settlements = explore_rows(ledger, "settlements")
    assert {row["merchant_id"] for row in settlements} == {"M-03"}
    assert any(row["id"] == "ST-0044" and row["net_minor"] == 2999287 for row in settlements)
    payment = explore_rows(ledger, "transactions")[0]["id"]
    assert [row["id"] for row in explore_rows(ledger, "transactions", payment)] == [payment]
    assert explore_rows(ledger, "settlements", payment) == []


def test_unknown_dataset_is_rejected(ledger_db: Path) -> None:
    with pytest.raises(ValueError, match="Unknown explorer dataset"):
        explore_rows(ledger_db, "customers")


def test_a_missing_ledger_is_not_created(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.db"
    with pytest.raises(sqlite3.OperationalError):
        explore_rows(missing_path, "transactions")
    assert not missing_path.exists()
