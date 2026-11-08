"""`get_ledger_record`: a ledger record by id, asked of the internal service.

Why it exists: when the agent already knows the exact id (a transaction, a merchant, a record whose
history it wants to see), asking the service is more direct and safer than generating SQL. The service is in
`ledgerlens/api/ledger_service.py`; this tool only builds the request and translates the response into the common
envelope (`ledgerlens/tools/envelope.py`).

Four kinds of request (`kind`)::

    transaction            GET /transactions/{id}
    settlement             GET /settlements/{id}
    merchant_settlements   GET /merchants/{id}/settlements?from&to
    event_replay           GET /webhooks/replay?aggregate_id={id}

There is no lookup of a refund or a dispute by its own id: the transaction carries both, and `event_replay` shows
the history of either.

Where the service runs: with `LEDGERLENS_LEDGER_API_URL` set, the tool calls that URL over the network. Without
it (offline mode and tests), it calls the app inside the same process, over the database in
`LEDGERLENS_LEDGER_DB`: no port is opened.

Order of a call::

    input -> id in the right format for the kind? (else INVALID_ID, without calling the service)
          -> GET (5 s limit; one retry on connection failure, timeout or 5xx)
          -> 200 becomes ok with `api:<n>`; 404 becomes NOT_FOUND; 422 becomes INVALID_ID; the rest, API_UNAVAILABLE

Money: each `x_minor` field of the record comes back with `x_major` beside it, the same value in major units as
text (`add_major_units`, in `sql.py`), so the model does not convert cents into units.

Errors become data, never exceptions. The text of the records (refund reasons, for example) comes back inside
`data` and is only data.
"""

from __future__ import annotations

import itertools
import re
import time
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any, Literal

import httpx
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ledgerlens.config import get_settings
from ledgerlens.tools.envelope import error, invalid_input, ok
from ledgerlens.tools.sql import add_major_units

TIMEOUT_SECONDS = 5.0
RETRIES = 1
BACKOFF_SECONDS = 0.5

DESCRIPTION = (
    "Fetch one record from the internal ledger service by id. "
    'kind "transaction" (id TX-nnnn) returns the transaction with its refunds, chargebacks and applied exchange '
    'rates. kind "settlement" (id ST-nnnn) returns one settlement. kind "merchant_settlements" (id M-nn) returns '
    "a merchant's settlements, optionally between two dates. "
    'kind "event_replay" (id TX-, R-, CB-, ST- or M-) returns the ordered event history of one record, as the '
    "service would replay it to a webhook. There is no lookup by refund or chargeback id: read them from the "
    "transaction, or use query_ledger. Use it when you know the exact id. Use query_ledger for searches, filters "
    "and totals."
)

_ID_PATTERNS = {
    "transaction": re.compile(r"^TX-[0-9]{4}$"),
    "settlement": re.compile(r"^ST-[0-9]{4}$"),
    "merchant_settlements": re.compile(r"^M-[0-9]{2}$"),
    "event_replay": re.compile(r"^(TX|R|CB|ST)-[0-9]{4}$|^M-[0-9]{2}$"),
}
_ID_HELP = {
    "transaction": "TX- and four digits, for example TX-2048",
    "settlement": "ST- and four digits, for example ST-0033",
    "merchant_settlements": "M- and two digits, for example M-09",
    "event_replay": "TX-, R-, CB- or ST- and four digits, or M- and two digits",
}
# For an id the kind does not accept, what to do with it, by prefix: the agent does not repeat the same mistake.
_ID_ROUTE = {
    "TX": "a transaction id: use kind 'transaction' (it also returns the refunds and chargebacks)",
    "ST": "a settlement id: use kind 'settlement'",
    "M": "a merchant id: use kind 'merchant_settlements' for its settlements",
    "R": (
        "a refund id: there is no lookup by refund id, use kind 'event_replay' for its history, kind 'transaction' "
        "with the id of its payment, or query_ledger"
    ),
    "CB": (
        "a chargeback id: there is no lookup by chargeback id, use kind 'event_replay' for its history, kind "
        "'transaction' with the id of its payment, or query_ledger"
    ),
}


def _wrong_id_message(kind: str, record_id: str) -> str:
    message = f"'{record_id}' is not an id for kind '{kind}': use {_ID_HELP[kind]}"
    if re.match(r"^(TX|ST|R|CB)-[0-9]{4}$|^M-[0-9]{2}$", record_id):
        message += f". '{record_id}' is {_ID_ROUTE[record_id.split('-', 1)[0]]}"
    return message


class GetLedgerRecordInput(BaseModel):
    """Tool input. The `id` format is not in the schema: the tool checks it, so a
    malformed id comes back as INVALID_ID (data) and not as a schema error."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["transaction", "settlement", "merchant_settlements", "event_replay"]
    id: str = Field(max_length=64, description="Record id, for example TX-2048, ST-0033, M-09, R-0731 or CB-0042")
    date_from: str | None = Field(
        default=None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="Only for merchant_settlements: first day, YYYY-MM-DD"
    )
    date_to: str | None = Field(
        default=None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="Only for merchant_settlements: last day, YYYY-MM-DD"
    )

    @field_validator("date_from", "date_to")
    @classmethod
    def _real_date(cls, value: str | None) -> str | None:
        if value is not None:
            date.fromisoformat(value)  # 2026-13-45 has the right shape and does not exist
        return value

    @model_validator(mode="after")
    def _ordered(self) -> GetLedgerRecordInput:
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must not be after date_to")
        return self


def build_get_ledger_record_tool(
    *,
    db_path: Path | str | None = None,
    base_url: str | None = None,
    transport: httpx.BaseTransport | None = None,
    timeout: float = TIMEOUT_SECONDS,
    retries: int = RETRIES,
    sleep: Callable[[float], None] = time.sleep,
) -> StructuredTool:
    """Builds the tool.

    `base_url` (or `LEDGERLENS_LEDGER_API_URL`) picks the service over the network; with neither, the
    app runs in process over `db_path` (or `LEDGERLENS_LEDGER_DB`). `transport` swaps the HTTP
    transport, for the tests.
    """
    counter = itertools.count(1)

    def open_client() -> tuple[httpx.Client, str]:
        url = (base_url or get_settings().ledger_api_url or "").rstrip("/")
        if url:
            return httpx.Client(timeout=timeout, transport=transport), url
        from fastapi.testclient import TestClient  # "api" extra; only the in-process mode needs it

        from ledgerlens.api.ledger_service import create_app

        app = create_app(db_path or get_settings().ledger_db)
        return TestClient(app, raise_server_exceptions=False), "http://ledger.local"

    def fetch(client: httpx.Client, url: str, params: dict[str, str]) -> httpx.Response:
        """GET with up to `retries` new attempts. Only transport failures and 5xx are retried."""
        reason = "unknown"
        for attempt in range(retries + 1):
            try:
                response = client.get(url, params=params)
            except httpx.TransportError as exc:
                reason = f"{type(exc).__name__}: {exc}"
            else:
                if response.status_code < 500:
                    return response
                reason = f"HTTP {response.status_code}"
            if attempt < retries:
                sleep(BACKOFF_SECONDS)
        raise ConnectionError(f"the ledger service did not answer after {retries} retry ({reason})")

    def get_ledger_record(
        kind: str, id: str, date_from: str | None = None, date_to: str | None = None
    ) -> dict[str, Any]:
        if not _ID_PATTERNS[kind].match(id):
            return error("INVALID_ID", _wrong_id_message(kind, id), False)

        params: dict[str, str] = {}
        if kind == "transaction":
            path = f"/transactions/{id}"
        elif kind == "settlement":
            path = f"/settlements/{id}"
        elif kind == "merchant_settlements":
            path = f"/merchants/{id}/settlements"
            params = {**({"from": date_from} if date_from else {}), **({"to": date_to} if date_to else {})}
        else:
            path, params = "/webhooks/replay", {"aggregate_id": id}

        try:
            client, root = open_client()
        except ImportError:
            message = "the ledger service needs the 'api' extra (fastapi) to run in process"
            return error("API_UNAVAILABLE", message, False)
        try:
            with client:
                response = fetch(client, root + path, params)
        except ConnectionError as exc:
            return error("API_UNAVAILABLE", str(exc), True)

        if response.status_code == 404:
            return error("NOT_FOUND", f"the ledger service has no {kind} '{id}'", False)
        if response.status_code == 422:
            return error("INVALID_ID", f"the ledger service rejected '{id}' as an id for kind '{kind}'", False)
        if response.status_code != 200:
            return error("API_UNAVAILABLE", f"the ledger service answered HTTP {response.status_code}", False)
        try:
            data = response.json()
        except ValueError:
            return error("API_UNAVAILABLE", "the ledger service answered with something that is not JSON", True)
        if not isinstance(data, dict):
            return error("API_UNAVAILABLE", "the ledger service answered in an unknown shape", True)
        return ok([f"api:{next(counter)}"], add_major_units(data))

    return StructuredTool.from_function(
        func=get_ledger_record,
        name="get_ledger_record",
        description=DESCRIPTION,
        args_schema=GetLedgerRecordInput,
        handle_validation_error=invalid_input,
    )
