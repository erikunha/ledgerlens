"""Event log and projector: replay is deterministic, duplicates are skipped, `events` is append-only,
and a refund for an unknown transaction fails in strict mode."""

from __future__ import annotations

import sqlite3

import pytest

from ledgerlens.sim.events import Event
from ledgerlens.sim.projector import (
    ProjectionError,
    Projector,
    canonical_hash,
    create_database,
    rebuild_database,
)


def ev(type_: str, aggregate_type: str, aggregate_id: str, at: str, payload: dict, origin: str = "synthetic") -> Event:
    return Event(type_, aggregate_type, aggregate_id, at, payload, origin)


def story() -> list[Event]:
    """One merchant and customer, a captured payment, a partial cross-currency refund, a chargeback
    that is lost on another payment, and a settlement that gets paid."""
    return [
        ev(
            "merchant.onboarded",
            "merchant",
            "M-01",
            "2026-01-01T00:00:00Z",
            {
                "name": "Loja Azul",
                "country": "DE",
                "category": "retail",
                "settlement_currency": "EUR",
                "fx_plan": "markup",
                "refund_window_days": 30,
            },
        ),
        ev(
            "customer.created",
            "customer",
            "C-0001",
            "2026-10-01T08:59:00Z",
            {"display_name": "Ana Souza", "country": "BR", "billing_currency": "BRL"},
        ),
        ev(
            "payment.authorized",
            "transaction",
            "TX-0001",
            "2026-10-01T09:00:00Z",
            {
                "merchant_id": "M-01",
                "customer_id": "C-0001",
                "amount_minor": 10000,
                "currency": "EUR",
                "method": "card",
                "card_brand": "visa",
                "card_fingerprint": "fp_1",
                "source_ref": "abc",
            },
            "public",
        ),
        ev(
            "payment.captured",
            "transaction",
            "TX-0001",
            "2026-10-01T09:00:03Z",
            {"captured_at": "2026-10-01T09:00:03Z"},
            "public",
        ),
        ev(
            "fx.applied",
            "transaction",
            "TX-0001",
            "2026-10-01T09:00:03Z",
            {
                "fx_id": "FX-0001",
                "refund_id": None,
                "kind": "charge",
                "from_currency": "EUR",
                "to_currency": "BRL",
                "applied_rate": "5.6000",
            },
        ),
        ev(
            "refund.requested",
            "refund",
            "R-0001",
            "2026-10-05T10:00:00Z",
            {
                "transaction_id": "TX-0001",
                "requested_amount_minor": 4000,
                "requested_currency": "EUR",
                "reason": "Produto devolvido",
            },
        ),
        ev(
            "fx.applied",
            "transaction",
            "TX-0001",
            "2026-10-05T10:30:00Z",
            {
                "fx_id": "FX-0002",
                "refund_id": "R-0001",
                "kind": "refund",
                "from_currency": "EUR",
                "to_currency": "BRL",
                "applied_rate": "5.4600",
            },
        ),
        ev(
            "payment.partially_refunded",
            "refund",
            "R-0001",
            "2026-10-05T10:30:00Z",
            {
                "refund_id": "R-0001",
                "transaction_id": "TX-0001",
                "requested_amount_minor": 4000,
                "requested_currency": "EUR",
                "payout_amount_minor": 21840,
                "payout_currency": "BRL",
                "fx_id": "FX-0002",
                "reason": "Produto devolvido",
            },
        ),
        ev(
            "payment.authorized",
            "transaction",
            "TX-0002",
            "2026-10-02T09:00:00Z",
            {
                "merchant_id": "M-01",
                "customer_id": "C-0001",
                "amount_minor": 5000,
                "currency": "EUR",
                "method": "card",
                "card_brand": "mastercard",
                "card_fingerprint": "fp_2",
                "source_ref": None,
            },
        ),
        ev(
            "payment.captured",
            "transaction",
            "TX-0002",
            "2026-10-02T09:00:02Z",
            {"captured_at": "2026-10-02T09:00:02Z"},
        ),
        ev(
            "chargeback.opened",
            "chargeback",
            "CB-0001",
            "2026-10-12T08:00:00Z",
            {
                "chargeback_id": "CB-0001",
                "transaction_id": "TX-0002",
                "amount_minor": 5000,
                "currency": "EUR",
                "reason_code": "FRD",
                "deadline": "2026-10-24",
            },
        ),
        ev(
            "chargeback.evidence_requested",
            "chargeback",
            "CB-0001",
            "2026-10-13T08:00:00Z",
            {"chargeback_id": "CB-0001"},
        ),
        ev("chargeback.lost", "chargeback", "CB-0001", "2026-10-26T08:00:00Z", {"chargeback_id": "CB-0001"}),
        ev(
            "settlement.settled",
            "settlement",
            "ST-0001",
            "2026-10-12T00:00:00Z",
            {
                "settlement_id": "ST-0001",
                "merchant_id": "M-01",
                "period_start": "2026-10-05",
                "period_end": "2026-10-11",
                "currency": "EUR",
                "gross_minor": 0,
                "refunds_minor": 4000,
                "fees_minor": 1500,
                "net_minor": -5500,
                "expected_payout_date": "2026-10-14",
            },
        ),
        ev(
            "payout.paid",
            "settlement",
            "ST-0001",
            "2026-10-14T06:00:00Z",
            {"settlement_id": "ST-0001", "paid_at": "2026-10-14T06:00:00Z"},
        ),
    ]


def fresh() -> tuple[sqlite3.Connection, Projector]:
    conn = create_database(":memory:")
    return conn, Projector(conn)


def test_events_project_into_the_read_tables():
    conn, projector = fresh()
    projector.ingest(story())

    assert conn.execute("SELECT name, fx_plan, refund_window_days FROM merchants").fetchall() == [
        ("Loja Azul", "markup", 30)
    ]
    assert conn.execute("SELECT display_name, billing_currency FROM customers").fetchall() == [("Ana Souza", "BRL")]
    rows = dict(conn.execute("SELECT id, status FROM transactions").fetchall())
    assert rows == {"TX-0001": "partially_refunded", "TX-0002": "charged_back"}
    tx = conn.execute("SELECT origin, captured_at, source_ref FROM transactions WHERE id='TX-0001'").fetchone()
    assert tx == ("public", "2026-10-01T09:00:03Z", "abc")
    refund = conn.execute(
        "SELECT status, payout_amount_minor, payout_currency, fx_applied_id, created_at, resolved_at FROM refunds"
    ).fetchone()
    assert refund == ("paid", 21840, "BRL", "FX-0002", "2026-10-05T10:00:00Z", "2026-10-05T10:30:00Z")
    assert conn.execute("SELECT stage, resolved_at FROM chargebacks").fetchone() == ("lost", "2026-10-26T08:00:00Z")
    assert conn.execute("SELECT status, paid_at, net_minor FROM settlements").fetchone() == (
        "paid",
        "2026-10-14T06:00:00Z",
        -5500,
    )
    assert conn.execute("SELECT kind, applied_rate, refund_id FROM fx_applied ORDER BY id").fetchall() == [
        ("charge", "5.6000", None),
        ("refund", "5.4600", "R-0001"),
    ]


def test_replaying_the_log_into_an_empty_database_gives_the_same_hash():
    conn, projector = fresh()
    projector.ingest(story())
    first = canonical_hash(conn)

    replayed = rebuild_database(conn)
    again = rebuild_database(replayed)

    assert canonical_hash(replayed) == first
    assert canonical_hash(again) == first
    assert len(first) == 64


def test_projecting_again_changes_nothing():
    conn, projector = fresh()
    projector.ingest(story())
    before = canonical_hash(conn)

    assert projector.project_pending() == 0
    assert Projector(conn).project_pending() == 0, "a new projector resumes from the stored checkpoint"
    assert canonical_hash(conn) == before


def test_checkpoint_follows_the_log_and_new_events_apply_incrementally():
    conn, projector = fresh()
    events = story()
    projector.ingest(events[:4])
    last = conn.execute("SELECT last_event_id FROM projector_state").fetchone()[0]
    assert last == 4

    projector.ingest(events[4:])
    assert conn.execute("SELECT last_event_id FROM projector_state").fetchone()[0] == len(events)


def test_a_duplicate_event_uid_is_skipped():
    conn, projector = fresh()
    events = story()

    first = projector.ingest(events)
    second = projector.ingest(events[:6])

    assert first.appended == len(events) and first.duplicates == 0
    assert second.appended == 0 and second.duplicates == 6
    assert conn.execute("SELECT count(*) FROM events").fetchone()[0] == len(events)
    assert conn.execute("SELECT count(*) FROM merchants").fetchone()[0] == 1
    assert conn.execute("SELECT count(*) FROM transactions").fetchone()[0] == 2


def test_the_projector_skips_an_event_it_has_already_applied():
    conn, projector = fresh()
    merchant = story()[0]
    assert projector.apply(merchant) is True
    assert projector.apply(merchant) is False
    assert conn.execute("SELECT count(*) FROM merchants").fetchone()[0] == 1


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE events SET origin = 'tampered'",
        "UPDATE events SET payload = '{}' WHERE event_id = 1",
        "DELETE FROM events",
        "DELETE FROM events WHERE event_id = 1",
    ],
)
def test_update_and_delete_on_events_abort(statement):
    conn, projector = fresh()
    projector.ingest(story())

    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute(statement)
    assert conn.execute("SELECT count(*) FROM events").fetchone()[0] == len(story())


def test_a_refund_for_an_unknown_transaction_fails_in_strict_mode():
    conn, projector = fresh()
    bad = ev(
        "refund.requested",
        "refund",
        "R-0009",
        "2026-10-05T10:00:00Z",
        {"transaction_id": "TX-7777", "requested_amount_minor": 100, "requested_currency": "EUR", "reason": "x"},
    )

    with pytest.raises(ProjectionError, match="TX-7777"):
        projector.ingest([bad])
    assert conn.execute("SELECT count(*) FROM refunds").fetchone()[0] == 0


def test_in_lenient_mode_the_error_is_listed_and_the_run_goes_on():
    conn = create_database(":memory:")
    projector = Projector(conn, strict=False)
    bad = ev(
        "refund.requested",
        "refund",
        "R-0009",
        "2026-10-05T10:00:00Z",
        {"transaction_id": "TX-7777", "requested_amount_minor": 100, "requested_currency": "EUR", "reason": "x"},
    )

    projector.ingest([bad, *story()[:2]])

    assert [e.event_type for e in projector.errors] == ["refund.requested"]
    assert "TX-7777" in projector.errors[0].message
    assert conn.execute("SELECT count(*) FROM merchants").fetchone()[0] == 1


@pytest.mark.parametrize(
    ("type_", "aggregate", "aggregate_id", "payload", "message"),
    [
        ("payment.captured", "transaction", "TX-0099", {"captured_at": "2026-10-01T09:00:03Z"}, "TX-0099"),
        (
            "chargeback.opened",
            "chargeback",
            "CB-0009",
            {
                "chargeback_id": "CB-0009",
                "transaction_id": "TX-0099",
                "amount_minor": 1,
                "currency": "EUR",
                "reason_code": "FRD",
                "deadline": "2026-10-24",
            },
            "TX-0099",
        ),
        ("chargeback.won", "chargeback", "CB-0099", {"chargeback_id": "CB-0099"}, "CB-0099"),
        (
            "payout.paid",
            "settlement",
            "ST-0099",
            {"settlement_id": "ST-0099", "paid_at": "2026-10-14T06:00:00Z"},
            "ST-0099",
        ),
        (
            "payment.authorized",
            "transaction",
            "TX-0050",
            {
                "merchant_id": "M-99",
                "customer_id": "C-0001",
                "amount_minor": 1,
                "currency": "EUR",
                "method": "card",
                "card_brand": None,
                "card_fingerprint": None,
                "source_ref": None,
            },
            "M-99",
        ),
    ],
)
def test_strict_mode_rejects_every_child_without_a_parent(type_, aggregate, aggregate_id, payload, message):
    conn, projector = fresh()
    projector.ingest(story()[:2])
    with pytest.raises(ProjectionError, match=message):
        projector.ingest([ev(type_, aggregate, aggregate_id, "2026-10-05T10:00:00Z", payload)])


def test_a_strict_failure_leaves_no_partial_row_and_no_checkpoint_move():
    conn, projector = fresh()
    projector.ingest(story()[:3])
    checkpoint = conn.execute("SELECT last_event_id FROM projector_state").fetchone()[0]
    bad = ev("chargeback.won", "chargeback", "CB-0404", "2026-10-30T00:00:00Z", {"chargeback_id": "CB-0404"})

    with pytest.raises(ProjectionError):
        projector.ingest([bad])

    assert conn.execute("SELECT last_event_id FROM projector_state").fetchone()[0] == checkpoint


def test_event_uid_is_a_content_hash_that_ignores_key_order_and_origin():
    a = ev(
        "customer.created",
        "customer",
        "C-0001",
        "2026-10-01T08:59:00Z",
        {"display_name": "A", "country": "BR", "billing_currency": "BRL"},
    )
    b = ev(
        "customer.created",
        "customer",
        "C-0001",
        "2026-10-01T08:59:00Z",
        {"billing_currency": "BRL", "country": "BR", "display_name": "A"},
        "scenario:S01",
    )
    c = ev(
        "customer.created",
        "customer",
        "C-0001",
        "2026-10-01T08:59:00Z",
        {"display_name": "B", "country": "BR", "billing_currency": "BRL"},
    )
    assert a.event_uid == b.event_uid
    assert a.event_uid != c.event_uid
    assert len(a.event_uid) == 64


def test_events_are_validated_when_they_are_built():
    with pytest.raises(ValueError, match="unknown event type"):
        Event("payment.exploded", "transaction", "TX-0001", "2026-10-01T09:00:00Z", {}, "synthetic")
    with pytest.raises(ValueError, match="aggregate"):
        Event("payment.captured", "refund", "TX-0001", "2026-10-01T09:00:00Z", {"captured_at": "x"}, "synthetic")
    with pytest.raises(ValueError, match="captured_at"):
        Event("payment.captured", "transaction", "TX-0001", "2026-10-01T09:00:00Z", {}, "synthetic")


def test_a_rejected_refund_keeps_the_transaction_status_and_records_the_reason():
    conn, projector = fresh()
    projector.ingest(story()[:4])
    projector.ingest(
        [
            ev(
                "refund.rejected",
                "refund",
                "R-0005",
                "2026-12-01T00:00:00Z",
                {
                    "refund_id": "R-0005",
                    "transaction_id": "TX-0001",
                    "requested_amount_minor": 10000,
                    "requested_currency": "EUR",
                    "reason": "I want my money back",
                    "rejection_reason": "outside_refund_window",
                },
            )
        ]
    )

    assert conn.execute("SELECT status FROM transactions WHERE id='TX-0001'").fetchone() == ("captured",)
    assert conn.execute("SELECT status, reason FROM refunds").fetchone() == ("rejected", "outside_refund_window")


def test_a_won_chargeback_returns_the_transaction_to_captured():
    conn, projector = fresh()
    events = story()
    projector.ingest(events[:12])
    assert conn.execute("SELECT status FROM transactions WHERE id='TX-0002'").fetchone() == ("disputed",)
    projector.ingest(
        [ev("chargeback.won", "chargeback", "CB-0001", "2026-10-26T08:00:00Z", {"chargeback_id": "CB-0001"})]
    )
    assert conn.execute("SELECT status FROM transactions WHERE id='TX-0002'").fetchone() == ("captured",)
