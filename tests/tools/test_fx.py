"""`get_reference_fx`: the ECB reference rate (Frankfurter v1), with recorded responses offline.

Offline the tool reads `data/fixtures/fx/`. Online it calls the API; here "online" is a local HTTP server
(`local_http`) or an `httpx.MockTransport`, so no test uses the network. The wait between attempts is swapped
for a recorder, so no test really sleeps.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import httpx
import pytest

from ledgerlens.tools.fx import FxClient, build_get_reference_fx_tool

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "fx"
EVIDENCE = re.compile(r"^(sql|api|policy|fx|calc|case):.+$")


class Clock:
    """Swaps the client's `sleep`: records the waits asked for and does not wait."""

    def __init__(self) -> None:
        self.waits: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.waits.append(seconds)


def offline_client(**kwargs) -> tuple[FxClient, Clock]:
    clock = Clock()
    return FxClient(mode="fixtures", sleep=clock, **kwargs), clock


def live_client(transport: httpx.MockTransport, **kwargs) -> tuple[FxClient, Clock]:
    clock = Clock()
    client = FxClient(mode="live", sleep=clock, transport=transport, today=lambda: date(2026, 11, 7), **kwargs)
    return client, clock


def frankfurter_body(day: str, to: str, rate: str, base: str = "EUR") -> bytes:
    return f'{{"amount":1.0,"base":"{base}","date":"{day}","rates":{{"{to}":{rate}}}}}'.encode()


def assert_envelope(result: dict) -> None:
    assert isinstance(result, dict)
    if result["ok"]:
        assert set(result) == {"ok", "evidence_ids", "data"}
        assert len(result["evidence_ids"]) == 1 and EVIDENCE.match(result["evidence_ids"][0])
        assert set(result["data"]) == {
            "requested_date", "rate_date", "from_currency", "to_currency", "rate", "source", "note", "from_cache",
        }  # fmt: skip
        assert re.fullmatch(r"[0-9]+(\.[0-9]+)?", result["data"]["rate"])
    else:
        assert set(result) == {"ok", "error"}
        assert set(result["error"]) == {"code", "message", "retryable"}


# --- recorded responses (offline) -------------------------------------------------------------


def test_eur_brl_on_the_refund_date_of_s01() -> None:
    client, _ = offline_client()
    result = client.get_reference_fx("EUR", "BRL", "2026-10-20")
    assert_envelope(result)
    assert result["evidence_ids"] == ["fx:2026-10-20:EUR-BRL"]
    data = result["data"]
    assert (data["rate"], data["rate_date"], data["requested_date"]) == ("5.6339", "2026-10-20", "2026-10-20")
    assert (data["source"], data["from_cache"]) == ("frankfurter", False)
    assert "ECB" in data["note"] and "not the rate" in data["note"]


def test_eur_brl_on_the_charge_date_of_s01() -> None:
    client, _ = offline_client()
    assert client.get_reference_fx("EUR", "BRL", "2026-10-15")["data"]["rate"] == "5.6679"


def test_a_saturday_returns_the_previous_business_day_and_says_so() -> None:
    client, _ = offline_client()
    result = client.get_reference_fx("EUR", "BRL", "2026-10-17")
    assert_envelope(result)
    data = result["data"]
    assert (data["requested_date"], data["rate_date"], data["rate"]) == ("2026-10-17", "2026-10-16", "5.7197")
    assert result["evidence_ids"] == ["fx:2026-10-16:EUR-BRL"]
    assert "2026-10-17" in data["note"] and "2026-10-16" in data["note"]


def test_a_recorded_pair_that_does_not_involve_the_euro() -> None:
    client, _ = offline_client()
    assert client.get_reference_fx("USD", "BRL", "2026-10-20")["data"]["rate"] == "5.0235"


def test_a_pair_without_a_recorded_response_is_computed_from_the_series() -> None:
    client, _ = offline_client()
    series = json.loads((FIXTURES / "frankfurter_eur.json").read_text())["rates"]
    day = "2026-10-14"
    result = client.get_reference_fx("EUR", "GBP", day)
    assert result["ok"] and result["data"]["rate"] == str(series[day]["GBP"])
    cross = client.get_reference_fx("GBP", "BRL", day)
    assert cross["ok"] and cross["data"]["rate_date"] == day
    expected = round(series[day]["BRL"] / series[day]["GBP"], 4)
    assert abs(float(cross["data"]["rate"]) - expected) < 1e-9


def test_ars_is_unsupported_even_on_the_recorded_404() -> None:
    client, _ = offline_client()
    for day in ("2026-10-15", "2026-10-21"):
        result = client.get_reference_fx("EUR", "ARS", day)
        assert_envelope(result)
        assert result["error"] == {
            "code": "UNSUPPORTED_CURRENCY",
            "message": result["error"]["message"],
            "retryable": False,
        }
        assert "ARS" in result["error"]["message"]


@pytest.mark.parametrize("day", ["1999-01-01", "2030-01-01"])
def test_a_date_outside_the_recorded_series_is_unavailable(day: str) -> None:
    client, _ = offline_client()
    error = client.get_reference_fx("EUR", "BRL", day)["error"]
    assert error["code"] == "DATE_UNAVAILABLE" and error["retryable"] is False


@pytest.mark.parametrize("code", ["eur", "EURO", "E1R", "", "€"])
def test_a_malformed_currency_is_invalid(code: str) -> None:
    client, _ = offline_client()
    for args in ((code, "BRL"), ("EUR", code)):
        error = client.get_reference_fx(*args, "2026-10-20")["error"]
        assert error["code"] == "INVALID_CURRENCY" and error["retryable"] is False


def test_the_same_currency_on_both_sides_is_rate_one() -> None:
    client, _ = offline_client()
    data = client.get_reference_fx("USD", "USD", "2026-10-20")["data"]
    assert data["rate"] == "1"


def test_every_recorded_single_date_rate_matches_the_ecb_data_portal() -> None:
    """Each scenario's rate matches the value recorded from the ECB Data Portal."""
    ecb = json.loads((FIXTURES / "ecb_reference.json").read_text())["series"]
    index = json.loads((FIXTURES / "index.json").read_text())["files"]
    client, _ = offline_client()
    checked = 0
    for name, meta in index.items():
        if meta["status"] != 200:
            continue
        day, base, quote = name.removesuffix(".json").split("_")
        if base != "EUR":
            continue
        data = client.get_reference_fx(base, quote, day)["data"]
        assert data["rate"] == ecb[quote][data["rate_date"]], name
        checked += 1
    assert checked >= 4


def test_the_whole_recorded_series_matches_the_ecb_data_portal() -> None:
    ecb = json.loads((FIXTURES / "ecb_reference.json").read_text())["series"]
    series = json.loads((FIXTURES / "frankfurter_eur.json").read_text())["rates"]
    for day, rates in series.items():
        for currency, value in rates.items():
            assert str(value) == ecb[currency][day], (day, currency)


def test_the_s01_rates_are_the_ones_of_the_manifest() -> None:
    manifest = json.loads((FIXTURES.parents[1] / "scenarios.json").read_text())
    truth = next(s for s in manifest["scenarios"] if s["id"] == "S01")["truth"]
    client, _ = offline_client()
    assert client.get_reference_fx("EUR", "BRL", "2026-10-15")["data"]["rate"] == truth["reference_rate_charge_date"]
    assert client.get_reference_fx("EUR", "BRL", "2026-10-20")["data"]["rate"] == truth["reference_rate_refund_date"]


# --- cache and injected failure ---------------------------------------------------------------


def test_the_second_identical_call_comes_from_the_cache() -> None:
    client, _ = offline_client()
    first = client.get_reference_fx("EUR", "BRL", "2026-10-20")
    second = client.get_reference_fx("EUR", "BRL", "2026-10-20")
    assert (first["data"]["from_cache"], second["data"]["from_cache"]) == (False, True)
    assert client.upstream_calls == 1
    assert {**first["data"], "from_cache": True} == second["data"]


def test_the_cache_is_keyed_by_source_date_and_pair() -> None:
    client, _ = offline_client()
    client.get_reference_fx("EUR", "BRL", "2026-10-20")
    client.get_reference_fx("EUR", "USD", "2026-10-20")
    client.get_reference_fx("EUR", "BRL", "2026-10-15")
    client.get_reference_fx("EUR", "BRL", "2026-10-20", source="bcb_ptax")
    assert client.upstream_calls == 4


def test_an_error_is_not_cached() -> None:
    client, _ = offline_client()
    client.get_reference_fx("EUR", "ARS", "2026-10-15")
    client.get_reference_fx("EUR", "ARS", "2026-10-15")
    assert client.upstream_calls == 2


def test_the_fault_switch_fails_after_two_retries_with_backoff() -> None:
    client, clock = offline_client(fault=True)
    result = client.get_reference_fx("EUR", "BRL", "2026-10-20")
    assert_envelope(result)
    assert result["error"]["code"] == "UPSTREAM_UNAVAILABLE" and result["error"]["retryable"] is True
    assert client.upstream_calls == 3
    assert clock.waits == [0.5, 1.0]


def test_the_fault_switch_does_not_poison_the_cache() -> None:
    healthy, _ = offline_client()
    assert healthy.get_reference_fx("EUR", "BRL", "2026-10-20")["ok"] is True
    broken, _ = offline_client(fault=True)
    assert broken.get_reference_fx("EUR", "BRL", "2026-10-20")["ok"] is False


# --- real calls (local server and fake transport) ---------------------------------------------


def test_live_mode_calls_v1_only_with_a_five_second_timeout(local_http) -> None:
    local_http.add("/v1/2026-10-20", frankfurter_body("2026-10-20", "BRL", "5.6339"))
    client = FxClient(mode="live", base_url=f"{local_http.base_url}/v1", sleep=Clock(), today=lambda: date(2026, 11, 7))
    result = client.get_reference_fx("EUR", "BRL", "2026-10-20")
    assert result["ok"] and result["data"]["rate"] == "5.6339"
    assert local_http.requests == ["/v1/2026-10-20?from=EUR&to=BRL"]
    assert client.timeout == 5.0


def test_v2_is_never_called_and_cannot_be_configured() -> None:
    for base in ("https://api.frankfurter.dev/v2", "https://api.frankfurter.dev/v2/rates", "https://x.test"):
        with pytest.raises(ValueError, match="v1"):
            FxClient(mode="live", base_url=base)


def test_every_live_request_stays_under_v1() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(200, content=frankfurter_body("2026-10-20", "BRL", "5.6339"))

    client, _ = live_client(httpx.MockTransport(handler))
    for pair in (("EUR", "BRL"), ("EUR", "BRL"), ("USD", "BRL")):
        client.get_reference_fx(*pair, "2026-10-20")
    assert paths and all(p.startswith("/v1/") for p in paths)


def test_live_saturday_reports_the_date_the_api_used() -> None:
    client, _ = live_client(
        httpx.MockTransport(lambda r: httpx.Response(200, content=frankfurter_body("2026-10-16", "BRL", "5.7197")))
    )
    data = client.get_reference_fx("EUR", "BRL", "2026-10-17")["data"]
    assert (data["requested_date"], data["rate_date"]) == ("2026-10-17", "2026-10-16")


def test_live_404_is_an_unsupported_currency() -> None:
    client, clock = live_client(httpx.MockTransport(lambda r: httpx.Response(404, json={"message": "not found"})))
    error = client.get_reference_fx("EUR", "ARS", "2026-10-15")["error"]
    assert error["code"] == "UNSUPPORTED_CURRENCY" and error["retryable"] is False
    assert clock.waits == []  # a 404 is not retried


def test_a_future_date_never_reaches_the_api() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(404, json={"message": "not found"})

    client, _ = live_client(httpx.MockTransport(handler))
    error = client.get_reference_fx("EUR", "BRL", "2026-12-31")["error"]
    assert error["code"] == "DATE_UNAVAILABLE" and calls == []


def test_a_server_error_is_retried_twice_then_reported() -> None:
    hits: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hits.append(1)
        return httpx.Response(503)

    client, clock = live_client(httpx.MockTransport(handler))
    error = client.get_reference_fx("EUR", "BRL", "2026-10-20")["error"]
    assert error["code"] == "UPSTREAM_UNAVAILABLE" and error["retryable"] is True
    assert len(hits) == 3 and clock.waits == [0.5, 1.0]


def test_a_timeout_then_success_is_a_success() -> None:
    good = httpx.Response(200, content=frankfurter_body("2026-10-20", "BRL", "5.6339"))
    answers = iter([httpx.ReadTimeout("slow"), good])

    def handler(request: httpx.Request) -> httpx.Response:
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer

    client, clock = live_client(httpx.MockTransport(handler))
    result = client.get_reference_fx("EUR", "BRL", "2026-10-20")
    assert result["ok"] and clock.waits == [0.5]


def test_a_connection_error_is_upstream_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    client, _ = live_client(httpx.MockTransport(handler))
    assert client.get_reference_fx("EUR", "BRL", "2026-10-20")["error"]["code"] == "UPSTREAM_UNAVAILABLE"


def test_another_client_error_is_not_retried() -> None:
    hits: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hits.append(1)
        return httpx.Response(422, json={"message": "bad"})

    client, _ = live_client(httpx.MockTransport(handler))
    error = client.get_reference_fx("EUR", "BRL", "2026-10-20")["error"]
    assert error["code"] == "UPSTREAM_UNAVAILABLE" and error["retryable"] is False and len(hits) == 1


def test_an_unreadable_answer_is_upstream_unavailable() -> None:
    client, _ = live_client(httpx.MockTransport(lambda r: httpx.Response(200, content=b"<html>oops</html>")))
    assert client.get_reference_fx("EUR", "BRL", "2026-10-20")["error"]["code"] == "UPSTREAM_UNAVAILABLE"


# --- the bcb_ptax source ----------------------------------------------------------------------


def test_ptax_returns_the_closing_sell_rate_and_marks_the_evidence() -> None:
    values = json.loads((FIXTURES / "bcb_ptax_USD_BRL.json").read_text())["values"]
    client, _ = offline_client()
    result = client.get_reference_fx("USD", "BRL", "2026-10-20", source="bcb_ptax")
    assert_envelope(result)
    assert result["evidence_ids"] == ["fx:2026-10-20:USD-BRL:ptax"]
    assert result["data"]["rate"] == values["2026-10-20"] and result["data"]["source"] == "bcb_ptax"
    assert "PTAX" in result["data"]["note"]


def test_ptax_on_a_weekend_uses_the_previous_bulletin() -> None:
    values = json.loads((FIXTURES / "bcb_ptax_EUR_BRL.json").read_text())["values"]
    client, _ = offline_client()
    data = client.get_reference_fx("EUR", "BRL", "2026-10-17", source="bcb_ptax")["data"]
    assert (data["requested_date"], data["rate_date"]) == ("2026-10-17", "2026-10-16")
    assert data["rate"] == values["2026-10-16"]


def test_ptax_inverts_when_brl_is_the_base() -> None:
    values = json.loads((FIXTURES / "bcb_ptax_USD_BRL.json").read_text())["values"]
    client, _ = offline_client()
    data = client.get_reference_fx("BRL", "USD", "2026-10-20", source="bcb_ptax")["data"]
    assert abs(float(data["rate"]) - 1 / float(values["2026-10-20"])) < 1e-6


@pytest.mark.parametrize("pair", [("EUR", "USD"), ("GBP", "BRL"), ("USD", "ARS")])
def test_ptax_needs_a_brl_side_and_a_listed_currency(pair: tuple[str, str]) -> None:
    client, _ = offline_client()
    error = client.get_reference_fx(*pair, "2026-10-20", source="bcb_ptax")["error"]
    assert error["code"] == "UNSUPPORTED_SOURCE_PAIR" and error["retryable"] is False


def test_ptax_date_outside_the_recorded_bulletins_is_unavailable() -> None:
    client, _ = offline_client()
    assert client.get_reference_fx("USD", "BRL", "2030-01-01", source="bcb_ptax")["error"]["code"] == "DATE_UNAVAILABLE"
    assert client.get_reference_fx("USD", "BRL", "2020-01-01", source="bcb_ptax")["error"]["code"] == "DATE_UNAVAILABLE"


def test_ptax_live_reads_the_closing_bulletin_from_olinda(local_http) -> None:
    rows = {
        "value": [
            {"cotacaoVenda": 5.01, "dataHoraCotacao": "2026-10-19 10:00:00.0", "tipoBoletim": "Abertura"},
            {"cotacaoVenda": 5.02, "dataHoraCotacao": "2026-10-19 13:00:00.0", "tipoBoletim": "Fechamento"},
            {"cotacaoVenda": 5.0235, "dataHoraCotacao": "2026-10-20 13:00:00.0", "tipoBoletim": "Fechamento PTAX"},
        ]
    }
    route = (
        "/olinda/servico/PTAX/versao/v1/odata/"
        "CotacaoMoedaPeriodo(moeda=@moeda,dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)"
    )
    local_http.add(route, json.dumps(rows))
    client = FxClient(mode="live", ptax_base_url=local_http.base_url, sleep=Clock(), today=lambda: date(2026, 11, 7))
    data = client.get_reference_fx("USD", "BRL", "2026-10-20", source="bcb_ptax")["data"]
    assert data["rate"] == "5.0235" and data["rate_date"] == "2026-10-20"
    assert "@moeda='USD'" in local_http.requests[0] and "10-20-2026" in local_http.requests[0]


# --- the tool ---------------------------------------------------------------------------------


def test_the_tool_is_described_for_the_model() -> None:
    client, _ = offline_client()
    tool = build_get_reference_fx_tool(client)
    assert tool.name == "get_reference_fx"
    assert "European Central Bank" in tool.description and "UNSUPPORTED_CURRENCY" in tool.description
    assert set(tool.args) == {"from_currency", "to_currency", "date", "source"}
    assert tool.args["source"]["default"] == "frankfurter"
    assert "three capital letters" in tool.args["from_currency"]["description"].lower()


def test_the_tool_answers_with_the_envelope() -> None:
    client, _ = offline_client()
    tool = build_get_reference_fx_tool(client)
    result = tool.invoke({"from_currency": "EUR", "to_currency": "BRL", "date": "2026-10-20"})
    assert_envelope(result)
    assert result["data"]["rate"] == "5.6339"
    assert tool.invoke({"from_currency": "EUR", "to_currency": "ARS", "date": "2026-10-15"})["error"]["code"] == (
        "UNSUPPORTED_CURRENCY"
    )


def test_the_tool_reports_a_malformed_currency_as_data() -> None:
    tool = build_get_reference_fx_tool(offline_client()[0])
    result = tool.invoke({"from_currency": "euro", "to_currency": "BRL", "date": "2026-10-20"})
    assert result["error"]["code"] == "INVALID_CURRENCY"


@pytest.mark.parametrize("day", ["20/10/2026", "2026-13-45", "yesterday"])
def test_the_tool_refuses_a_bad_date_before_any_lookup(day: str) -> None:
    client, _ = offline_client()
    tool = build_get_reference_fx_tool(client)
    result = tool.invoke({"from_currency": "EUR", "to_currency": "BRL", "date": day})
    assert "INVALID_INPUT" in str(result) and client.upstream_calls == 0


def test_the_default_client_follows_the_offline_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    tool = build_get_reference_fx_tool()
    assert tool.invoke({"from_currency": "EUR", "to_currency": "BRL", "date": "2026-10-20"})["data"]["rate"] == "5.6339"
