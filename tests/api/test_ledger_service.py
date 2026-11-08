"""The internal ledger API: read-only, over the same SQLite file `query_ledger` uses.

The database comes from `build_ledger` with the committed sample, in a temporary folder. The `TestClient`
calls the app in process, so no test opens a port or uses the network.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from ledgerlens.api import ledger_service  # noqa: E402
from ledgerlens.api.ledger_service import create_app, open_ledger  # noqa: E402
from ledgerlens.sim.config import SimConfig  # noqa: E402
from ledgerlens.sim.pipeline import build_ledger  # noqa: E402


@pytest.fixture(scope="module")
def ledger_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("ledger") / "ledger.db"
    build_ledger(SimConfig(source="sample"), path).conn.close()
    return path


@pytest.fixture
def client(ledger_db: Path) -> TestClient:
    return TestClient(create_app(ledger_db))


# --- reads ------------------------------------------------------------------------------------


def test_transaction_comes_with_refunds_chargebacks_and_fx(client: TestClient) -> None:
    response = client.get("/transactions/TX-2048")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"transaction", "refunds", "chargebacks", "fx_applied"}
    assert body["transaction"]["id"] == "TX-2048"
    assert body["transaction"]["amount_minor"] == 10000
    assert [r["id"] for r in body["refunds"]] == ["R-0731"]
    assert body["refunds"][0]["payout_amount_minor"] == 54931
    assert body["chargebacks"] == []
    assert [(f["kind"], f["applied_rate"]) for f in body["fx_applied"]] == [
        ("charge", "5.6679"),
        ("refund", "5.4931"),
    ]


def test_unknown_transaction_is_404(client: TestClient) -> None:
    response = client.get("/transactions/TX-9999")
    assert response.status_code == 404
    assert "TX-9999" in response.json()["detail"]


def test_malformed_transaction_id_is_422(client: TestClient) -> None:
    assert client.get("/transactions/not-an-id").status_code == 422


def test_settlement_by_id(client: TestClient) -> None:
    response = client.get("/settlements/ST-0033")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"settlement"}
    assert body["settlement"]["id"] == "ST-0033"
    assert body["settlement"]["net_minor"] == (
        body["settlement"]["gross_minor"] - body["settlement"]["refunds_minor"] - body["settlement"]["fees_minor"]
    )


def test_unknown_settlement_is_404(client: TestClient) -> None:
    assert client.get("/settlements/ST-9999").status_code == 404


def test_malformed_settlement_id_is_422(client: TestClient) -> None:
    assert client.get("/settlements/M-09").status_code == 422


def test_merchant_settlements_are_listed_in_period_order(client: TestClient) -> None:
    response = client.get("/merchants/M-09/settlements")
    assert response.status_code == 200
    body = response.json()
    assert body["merchant_id"] == "M-09"
    starts = [s["period_start"] for s in body["settlements"]]
    assert starts and starts == sorted(starts)
    assert {s["merchant_id"] for s in body["settlements"]} == {"M-09"}


def test_merchant_settlements_can_be_cut_by_date(client: TestClient) -> None:
    everything = client.get("/merchants/M-09/settlements").json()["settlements"]
    cut = client.get("/merchants/M-09/settlements", params={"from": "2026-08-17", "to": "2026-08-23"}).json()
    assert [s["id"] for s in cut["settlements"]] == ["ST-0033"]
    assert len(everything) > 1


def test_bad_date_is_422(client: TestClient) -> None:
    assert client.get("/merchants/M-09/settlements", params={"from": "ontem"}).status_code == 422


def test_unknown_merchant_is_404(client: TestClient) -> None:
    assert client.get("/merchants/M-99/settlements").status_code == 404


def test_replay_returns_the_events_in_order_and_delivers_nothing(client: TestClient, ledger_db: Path) -> None:
    before = _digest(ledger_db)
    response = client.get("/webhooks/replay", params={"aggregate_id": "TX-2048"})
    assert response.status_code == 200
    body = response.json()
    assert body["aggregate_id"] == "TX-2048"
    ids = [e["event_id"] for e in body["events"]]
    assert ids == sorted(ids) and len(ids) >= 4
    assert body["events"][0]["type"] == "payment.authorized"
    assert body["events"][0]["payload"]["amount_minor"] == 10000  # the body is JSON, not text
    assert set(body["events"][0]) == {"event_id", "type", "occurred_at", "payload"}
    assert _digest(ledger_db) == before


def test_replay_without_events_is_404(client: TestClient) -> None:
    assert client.get("/webhooks/replay", params={"aggregate_id": "TX-9999"}).status_code == 404


def test_replay_needs_an_aggregate_id(client: TestClient) -> None:
    assert client.get("/webhooks/replay").status_code == 422


def test_health_counts_events(client: TestClient, ledger_db: Path) -> None:
    with sqlite3.connect(ledger_db) as conn:
        total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert client.get("/health").json() == {"status": "ok", "events": total}


# --- read-only --------------------------------------------------------------------------------


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
@pytest.mark.parametrize(
    "path",
    ["/transactions/TX-2048", "/merchants/M-09/settlements", "/webhooks/replay", "/health"],
)
def test_every_write_method_answers_405(client: TestClient, method: str, path: str) -> None:
    assert getattr(client, method)(path).status_code == 405


def test_no_route_accepts_a_write_method() -> None:
    app = create_app(Path("unused.db"))
    methods = {m for route in app.routes for m in getattr(route, "methods", set())}
    assert methods <= {"GET", "HEAD", "OPTIONS"}


def test_the_database_is_opened_read_only(ledger_db: Path) -> None:
    conn = open_ledger(ledger_db)
    try:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("DELETE FROM refunds")
    finally:
        conn.close()


def test_serving_requests_never_changes_the_file(client: TestClient, ledger_db: Path) -> None:
    before = _digest(ledger_db)
    for path in ("/transactions/TX-2048", "/merchants/M-09/settlements", "/health"):
        client.get(path)
    assert _digest(ledger_db) == before


def test_missing_database_is_503_and_is_not_created(tmp_path: Path) -> None:
    missing = tmp_path / "none.db"
    response = TestClient(create_app(missing)).get("/health")
    assert response.status_code == 503
    assert not missing.exists()


def test_default_database_comes_from_the_settings(ledger_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEDGERLENS_LEDGER_DB", str(ledger_db))
    assert TestClient(create_app()).get("/health").status_code == 200


def test_the_command_runs_uvicorn_on_loopback_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(ledger_service, "_serve", lambda *a, **k: calls.append((a, k)))
    ledger_service.main([])
    ledger_service.main(["--port", "9001"])
    assert calls[0][1] == {"host": "127.0.0.1", "port": 8000}
    assert calls[1][1] == {"host": "127.0.0.1", "port": 9001}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
