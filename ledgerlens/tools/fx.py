"""`get_reference_fx`: the European Central Bank (ECB) reference FX rate, through Frankfurter.

Why it exists: to say whether a merchant charged a markup on a refund in another currency, the agent
must compare the rate the acquirer applied with the market rate of the day. That rate comes from an external
API, but the number never comes from the model: it is recorded data or an API response.

Two sources (`source`): `frankfurter` (default, ECB daily rates) and `bcb_ptax` (the closing PTAX rate
of the Banco Central do Brasil, only for pairs with BRL, used as a cross-check).

Only Frankfurter `/v1` is called, and it carries only the ECB. `/v2` without `providers=ECB` mixes providers and
once returned a rate 2.7% above the ECB: the agent would read that as a markup that does not exist. That
is why the base address is validated and anything that is not `/v1` is refused at construction.

Order of a call (the same for both sources)::

    input
      -> currency with three uppercase letters? (else INVALID_CURRENCY)
      -> same currency on both sides? (rate 1, no lookup)
      -> in the cache (source, date, from, to)? (yes: returns with from_cache=True)
      -> asks the origin:
           "live" mode:     HTTP on /v1, 5 s limit, up to 2 retries with a wait
                            (0.5 s and 1.0 s) on timeout, connection error and 5xx
           "fixtures" mode: 1) recorded file <date>_<FROM>_<TO>.json (same content as the API),
                            2) else computes it from the recorded daily series (cross rate through the euro)
      -> stores it in the cache and returns the envelope (the date used may be earlier than the one asked)

The mode comes from `LEDGERLENS_OFFLINE` (offline = "fixtures"). A fault switch (`fault=True`, a constructor
argument, not an environment variable) makes every lookup fail as an origin outage: that is scenario S11.
Errors never go into the cache, so a passing failure does not become a permanent answer.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import httpx
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ledgerlens.config import PROJECT_ROOT, http_mode
from ledgerlens.sim.fx import MAX_CARRY_DAYS, FxTable, FxUnavailable
from ledgerlens.tools.envelope import error, invalid_input, ok

FRANKFURTER_URL = "https://api.frankfurter.dev/v1"
PTAX_URL = "https://olinda.bcb.gov.br"
FIXTURES_DIR = PROJECT_ROOT / "data" / "fixtures" / "fx"
TIMEOUT_SECONDS = 5.0
RETRIES = 2
BACKOFF_SECONDS = (0.5, 1.0)
# The ECB publishes since 1999-01-04; before that the API answers 404 and it is not the currency's fault.
FIRST_RATE_DATE = date(1999, 1, 4)
PTAX_WINDOW_DAYS = 7
INVERSE_PLACES = Decimal("0.000001")

DESCRIPTION = (
    "Get the market reference exchange rate between two currencies on a date, from the European Central Bank "
    "daily rates (Frankfurter, ECB only). Use it to compare against the rate an acquirer applied. It is a "
    "reference, not the rate any acquirer charged. Weekends and holidays return the previous business day; the "
    "result states the date actually used. Supported currencies are the ECB list (for example EUR, USD, BRL, "
    'GBP); others return UNSUPPORTED_CURRENCY. Use source "bcb_ptax" only for a pair that has BRL on one side '
    "when a Brazilian central bank rate is needed."
)

_CURRENCY = re.compile(r"^[A-Z]{3}$")


class _FxError(Exception):
    """An expected failure, already with the contract code. It becomes the error envelope."""

    def __init__(self, code: str, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.code, self.retryable = code, retryable


@dataclass(frozen=True)
class _Quote:
    rate: str
    rate_date: date


def _plain(value: Decimal) -> str:
    """A Decimal with no scientific notation, as the contract requires (`5.6339`, never `5.6339E+0`)."""
    return format(value, "f")


def _check_base_url(url: str) -> str:
    """Only Frankfurter /v1 (ECB only) is accepted; /v2 mixes providers and would make up a markup."""
    path = urlparse(url).path.rstrip("/")
    if path != "/v1":
        raise ValueError(f"base_url must end in /v1 (ECB only); got {url!r}")
    return url.rstrip("/")


class FxClient:
    """FX client with a cache. One instance keeps the cache of one agent session."""

    def __init__(
        self,
        *,
        mode: Literal["fixtures", "live"] | None = None,
        fixtures_dir: Path | str = FIXTURES_DIR,
        base_url: str = FRANKFURTER_URL,
        ptax_base_url: str = PTAX_URL,
        timeout: float = TIMEOUT_SECONDS,
        retries: int = RETRIES,
        backoff: tuple[float, ...] = BACKOFF_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
        transport: httpx.BaseTransport | None = None,
        today: Callable[[], date] = date.today,
        fault: bool = False,
    ) -> None:
        self._mode = mode
        self.fixtures_dir = Path(fixtures_dir)
        self.base_url = _check_base_url(base_url)
        self.ptax_base_url = ptax_base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self._sleep = sleep
        self._transport = transport
        self._today = today
        self.fault = fault
        self.upstream_calls = 0  # attempts at the origin (HTTP or file); the cache does not count
        self._cache: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        self._series: FxTable | None = None

    @property
    def mode(self) -> str:
        # Resolved on each call, to follow `LEDGERLENS_OFFLINE` even if it changes after creation.
        return self._mode or http_mode()

    # --- public entry -------------------------------------------------------------------------

    def get_reference_fx(
        self, from_currency: str, to_currency: str, day: str, source: str = "frankfurter"
    ) -> dict[str, Any]:
        """Returns the tool envelope (success, or an error as data)."""
        for code in (from_currency, to_currency):
            if not _CURRENCY.match(code):
                return error("INVALID_CURRENCY", f"'{code}' is not a currency code of three capital letters", False)
        try:
            requested = date.fromisoformat(day)
        except ValueError:
            return error("INVALID_INPUT", f"'{day}' is not a date in the form YYYY-MM-DD", True)
        if source not in ("frankfurter", "bcb_ptax"):
            return error("INVALID_INPUT", f"source must be 'frankfurter' or 'bcb_ptax', not '{source}'", True)

        suffix = ":ptax" if source == "bcb_ptax" else ""
        if from_currency == to_currency:
            note = "Same currency on both sides."
            data = self._data(requested, requested, from_currency, to_currency, "1", source, note)
            return ok([f"fx:{requested}:{from_currency}-{to_currency}{suffix}"], data)

        key = (source, day, from_currency, to_currency)
        cached = self._cache.get(key)
        if cached is not None:
            return ok([self._evidence(cached, suffix)], {**cached, "from_cache": True})

        try:
            if source == "bcb_ptax":
                quote = self._ptax(from_currency, to_currency, requested)
                note = "BCB PTAX closing (Fechamento) sell rate."
            else:
                quote = self._frankfurter(from_currency, to_currency, requested)
                note = "ECB reference rate (Frankfurter v1)."
        except _FxError as failure:
            return error(failure.code, str(failure), failure.retryable)

        note += " It is a reference, not the rate any acquirer applied."
        if quote.rate_date != requested:
            note += (
                f" No rate was published for {requested} (weekend or holiday);"
                f" the rate of {quote.rate_date}, the previous business day, is used."
            )
        data = self._data(requested, quote.rate_date, from_currency, to_currency, quote.rate, source, note)
        self._cache[key] = data
        return ok([self._evidence(data, suffix)], {**data})

    # --- result assembly ----------------------------------------------------------------------

    @staticmethod
    def _data(requested: date, used: date, from_c: str, to_c: str, rate: str, source: str, note: str) -> dict[str, Any]:
        return {
            "requested_date": requested.isoformat(),
            "rate_date": used.isoformat(),
            "from_currency": from_c,
            "to_currency": to_c,
            "rate": rate,
            "source": source,
            "note": note,
            "from_cache": False,
        }

    @staticmethod
    def _evidence(data: dict[str, Any], suffix: str) -> str:
        # The id uses the rate's date, not the requested one: it is the date that backs the number.
        return f"fx:{data['rate_date']}:{data['from_currency']}-{data['to_currency']}{suffix}"

    # --- origin: retries and waiting ----------------------------------------------------------

    def _attempt(self, call: Callable[[], tuple[int, bytes]]) -> tuple[int, bytes]:
        """Runs `call` with up to `retries` new attempts. Only transport failures and 5xx are retried."""
        reason = "unknown"
        for attempt in range(self.retries + 1):
            self.upstream_calls += 1
            try:
                if self.fault:
                    raise httpx.ConnectError("injected fault (scenario S11)")
                status, body = call()
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                reason = f"{type(exc).__name__}: {exc}"
            else:
                if status < 500:
                    return status, body
                reason = f"HTTP {status}"
            if attempt < self.retries:
                self._sleep(self.backoff[min(attempt, len(self.backoff) - 1)])
        message = f"the rate source did not answer after {self.retries} retries ({reason})"
        raise _FxError("UPSTREAM_UNAVAILABLE", message, True)

    def _http_get(self, url: str) -> Callable[[], tuple[int, bytes]]:
        def call() -> tuple[int, bytes]:
            with httpx.Client(timeout=self.timeout, transport=self._transport) as client:
                response = client.get(url)
            return response.status_code, response.content

        return call

    def _check_live_date(self, requested: date) -> None:
        if requested > self._today():
            raise _FxError("DATE_UNAVAILABLE", f"{requested} is in the future; no rate exists yet")
        if requested < FIRST_RATE_DATE:
            raise _FxError("DATE_UNAVAILABLE", f"{requested} is before the first published rate ({FIRST_RATE_DATE})")

    # --- Frankfurter --------------------------------------------------------------------------

    def _frankfurter(self, from_c: str, to_c: str, requested: date) -> _Quote:
        if self.mode == "live":
            self._check_live_date(requested)
            url = f"{self.base_url}/{requested}?from={from_c}&to={to_c}"
            status, body = self._attempt(self._http_get(url))
            return self._read_frankfurter(status, body, from_c, to_c)

        name = f"{requested}_{from_c}_{to_c}.json"
        recorded = self.fixtures_dir / name
        if recorded.is_file():
            status, body = self._attempt(lambda: self._recorded(recorded, name))
            return self._read_frankfurter(status, body, from_c, to_c)
        self._attempt(lambda: (200, b""))  # counts the lookup and applies the fault switch
        return self._from_series(from_c, to_c, requested)

    def _recorded(self, path: Path, name: str) -> tuple[int, bytes]:
        """A recorded file: the exact API body and the status that `index.json` recorded."""
        body = path.read_bytes()
        index_file = self.fixtures_dir / "index.json"
        if index_file.is_file():
            entry = json.loads(index_file.read_text(encoding="utf-8")).get("files", {}).get(name)
            if entry is not None:
                return int(entry["status"]), body
        return (404 if b'"message"' in body else 200), body

    def _from_series(self, from_c: str, to_c: str, requested: date) -> _Quote:
        """No recorded file for the pair: cross rate through the euro, from the recorded daily series."""
        if self._series is None:
            series_file = self.fixtures_dir / "frankfurter_eur.json"
            if not series_file.is_file():
                raise _FxError("UPSTREAM_UNAVAILABLE", "no recorded rates are available offline")
            self._series = FxTable.from_file(series_file)
        try:
            found = self._series.rate(requested, from_c, to_c)
        except FxUnavailable as exc:
            if "unsupported currency" in str(exc):
                raise _FxError("UNSUPPORTED_CURRENCY", f"no recorded rate for {from_c}/{to_c}: {exc}") from None
            raise _FxError("DATE_UNAVAILABLE", str(exc)) from None
        return _Quote(_plain(found.rate), found.rate_date)

    @staticmethod
    def _read_frankfurter(status: int, body: bytes, from_c: str, to_c: str) -> _Quote:
        if status == 404:
            raise _FxError(
                "UNSUPPORTED_CURRENCY",
                f"the ECB list has no rate for {from_c}/{to_c} (one of these currencies is not published)",
            )
        if status != 200:
            raise _FxError("UPSTREAM_UNAVAILABLE", f"the rate source answered HTTP {status}")
        try:
            payload = json.loads(body, parse_float=Decimal)
            return _Quote(_plain(Decimal(payload["rates"][to_c])), date.fromisoformat(payload["date"]))
        except (ValueError, KeyError, TypeError, ArithmeticError):
            raise _FxError("UPSTREAM_UNAVAILABLE", "the rate source answered in an unknown shape") from None

    # --- PTAX ---------------------------------------------------------------------------------

    def _ptax(self, from_c: str, to_c: str, requested: date) -> _Quote:
        if (from_c == "BRL") == (to_c == "BRL"):
            raise _FxError("UNSUPPORTED_SOURCE_PAIR", "bcb_ptax serves only pairs with BRL on exactly one side")
        currency = to_c if from_c == "BRL" else from_c
        closing = self._ptax_closing(currency, requested)
        found = max((day for day in closing if day <= requested), default=None)
        if found is None or requested > found + timedelta(days=MAX_CARRY_DAYS):
            raise _FxError("DATE_UNAVAILABLE", f"no PTAX closing bulletin for {currency} on or before {requested}")
        sell = Decimal(closing[found])
        rate = sell if to_c == "BRL" else (1 / sell).quantize(INVERSE_PLACES, rounding=ROUND_HALF_EVEN)
        return _Quote(_plain(rate), found)

    def _ptax_closing(self, currency: str, requested: date) -> dict[date, str]:
        """Selling rates of the closing bulletin, per day, from the current mode's source."""
        if self.mode == "live":
            self._check_live_date(requested)
            return self._ptax_live(currency, requested)
        path = self.fixtures_dir / f"bcb_ptax_{currency}_BRL.json"
        if not path.is_file():
            raise _FxError("UNSUPPORTED_SOURCE_PAIR", f"no PTAX data for {currency} (not in the recorded bulletins)")
        self._attempt(lambda: (200, b""))
        values = json.loads(path.read_text(encoding="utf-8"))["values"]
        return {date.fromisoformat(day): value for day, value in values.items()}

    def _ptax_live(self, currency: str, requested: date) -> dict[date, str]:
        def us_date(day: date) -> str:  # the Olinda API wants MM-DD-YYYY
            return f"{day.month:02d}-{day.day:02d}-{day.year}"

        start = requested - timedelta(days=PTAX_WINDOW_DAYS)
        url = (
            f"{self.ptax_base_url}/olinda/servico/PTAX/versao/v1/odata/"
            "CotacaoMoedaPeriodo(moeda=@moeda,dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)"
            f"?@moeda='{currency}'&@dataInicial='{us_date(start)}'&@dataFinalCotacao='{us_date(requested)}'&$format=json"
        )
        status, body = self._attempt(self._http_get(url))
        if status != 200:
            raise _FxError("UPSTREAM_UNAVAILABLE", f"the PTAX service answered HTTP {status}")
        try:
            rows = json.loads(body, parse_float=Decimal)["value"]
            closing = {
                date.fromisoformat(row["dataHoraCotacao"][:10]): _plain(Decimal(row["cotacaoVenda"]))
                for row in sorted(rows, key=lambda r: r["dataHoraCotacao"])
                if str(row["tipoBoletim"]).startswith("Fechamento")
            }
        except (ValueError, KeyError, TypeError, ArithmeticError):
            raise _FxError("UPSTREAM_UNAVAILABLE", "the PTAX service answered in an unknown shape") from None
        if not closing:
            raise _FxError("UNSUPPORTED_SOURCE_PAIR", f"the PTAX service returned no closing bulletin for {currency}")
        return closing


class GetReferenceFxInput(BaseModel):
    """Tool input. The currencies have no `pattern`: the client checks them, so a malformed
    currency comes back as INVALID_CURRENCY (data) and not as a schema error. The format goes in the field's
    description, which is what the model reads (LangChain does not pass `pattern` to the tool schema)."""

    model_config = ConfigDict(extra="forbid")

    from_currency: str = Field(max_length=16, description="Three capital letters, for example EUR")
    to_currency: str = Field(max_length=16, description="Three capital letters, for example BRL")
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$", description="Day in the form YYYY-MM-DD")
    source: Literal["frankfurter", "bcb_ptax"] = "frankfurter"

    @field_validator("date")
    @classmethod
    def _real_date(cls, value: str) -> str:
        date.fromisoformat(value)  # 2026-13-45 has the right shape and does not exist
        return value


def build_get_reference_fx_tool(client: FxClient | None = None) -> StructuredTool:
    """Builds the tool. Without `client`, it creates one that follows the configured offline mode."""
    fx = client or FxClient()

    def get_reference_fx(from_currency: str, to_currency: str, date: str, source: str = "frankfurter") -> dict:
        return fx.get_reference_fx(from_currency, to_currency, date, source)

    return StructuredTool.from_function(
        func=get_reference_fx,
        name="get_reference_fx",
        description=DESCRIPTION,
        args_schema=GetReferenceFxInput,
        handle_validation_error=invalid_input,
    )
