"""record_fixtures.py records Frankfurter v1, ECB Data Portal, BCB PTAX, Nager.Date holidays and the BIN table.

Every request goes to a local HTTP server fixture; nothing here touches the network.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "record_fixtures.py"
REPO = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("record_fixtures", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


rec = _load()

SERIES = {
    "amount": 1.0,
    "base": "EUR",
    "start_date": "2026-10-15",
    "end_date": "2026-10-20",
    "rates": {
        "2026-10-15": {"BRL": 5.6679, "GBP": 0.8461, "USD": 1.1208},
        "2026-10-16": {"BRL": 5.7197, "GBP": 0.84, "USD": 1.12},
        "2026-10-19": {"BRL": 5.65, "GBP": 0.841, "USD": 1.121},
        "2026-10-20": {"BRL": 5.6339, "GBP": 0.84028, "USD": 1.1215},
    },
}
SINGLE_1015 = b'{"amount":1.0,"base":"EUR","date":"2026-10-15","rates":{"BRL":5.6679}}'
SINGLE_1020 = b'{"amount":1.0,"base":"EUR","date":"2026-10-20","rates":{"BRL":5.6339}}'
SINGLE_1017 = b'{"amount":1.0,"base":"EUR","date":"2026-10-16","rates":{"BRL":5.7197}}'
NOT_FOUND = b'{"message":"not found"}'

PTAX_PATH = "/olinda/servico/PTAX/versao/v1/odata/CotacaoMoedaPeriodo(moeda=@moeda,dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)"  # noqa: E501


def _frankfurter(server):
    server.add("/v1/2026-10-15..2026-10-20", json.dumps(SERIES))
    server.add("/v1/2026-10-15", SINGLE_1015)
    server.add("/v1/2026-10-20", SINGLE_1020)
    server.add("/v1/2026-10-17", SINGLE_1017)
    server.add("/v1/2026-10-15?from=EUR&to=ARS", NOT_FOUND, status=404)


SINGLES = (
    ("2026-10-15", "EUR", "BRL", 200),
    ("2026-10-20", "EUR", "BRL", 200),
    ("2026-10-17", "EUR", "BRL", 200),
    ("2026-10-15", "EUR", "ARS", 404),
)


def test_series_is_normalized_with_provider_and_exact_rates(local_http, tmp_path):
    _frankfurter(local_http)

    rec.record_frankfurter(
        tmp_path,
        local_http.base_url,
        start="2026-10-15",
        end="2026-10-20",
        symbols=("BRL", "GBP", "USD"),
        singles=SINGLES,
    )

    data = json.loads((tmp_path / "fx" / "frankfurter_eur.json").read_text(), parse_float=Decimal)
    assert data["base"] == "EUR" and data["provider"] == "ECB"
    assert data["rates"]["2026-10-20"]["BRL"] == Decimal("5.6339")
    assert sorted(data["rates"]) == ["2026-10-15", "2026-10-16", "2026-10-19", "2026-10-20"], "no weekend entries"
    assert any(r.startswith("/v1/2026-10-15..2026-10-20") for r in local_http.requests)
    assert not any("/v2" in r for r in local_http.requests), "plain /v2 blends providers and is never called"


def test_single_date_responses_are_kept_byte_for_byte_with_status(local_http, tmp_path):
    _frankfurter(local_http)

    rec.record_frankfurter(
        tmp_path, local_http.base_url, start="2026-10-15", end="2026-10-20", symbols=("BRL",), singles=SINGLES
    )

    fx = tmp_path / "fx"
    assert (fx / "2026-10-15_EUR_BRL.json").read_bytes() == SINGLE_1015
    assert (fx / "2026-10-20_EUR_BRL.json").read_bytes() == SINGLE_1020
    assert (fx / "2026-10-17_EUR_BRL.json").read_bytes() == SINGLE_1017, "Saturday request keeps the Friday date"
    assert (fx / "2026-10-15_EUR_ARS.json").read_bytes() == NOT_FOUND
    index = json.loads((fx / "index.json").read_text())["files"]
    assert index["2026-10-15_EUR_BRL.json"]["status"] == 200
    assert index["2026-10-15_EUR_ARS.json"]["status"] == 404
    assert index["2026-10-20_EUR_BRL.json"]["sha256"] == hashlib.sha256(SINGLE_1020).hexdigest()


def test_unexpected_status_is_an_error_and_writes_nothing(local_http, tmp_path):
    _frankfurter(local_http)
    local_http.add("/v1/2026-10-20", b"boom", status=500)

    with pytest.raises(rec.RecordError) as excinfo:
        rec.record_frankfurter(
            tmp_path, local_http.base_url, start="2026-10-15", end="2026-10-20", symbols=("BRL",), singles=SINGLES
        )

    assert "2026-10-20" in str(excinfo.value) and "500" in str(excinfo.value)
    assert not (tmp_path / "fx" / "2026-10-20_EUR_BRL.json").exists()


def test_default_singles_cover_the_scenarios():
    wanted = {(d, f, t, s) for d, f, t, s in rec.FRANKFURTER_SINGLES}
    assert ("2026-10-15", "EUR", "BRL", 200) in wanted
    assert ("2026-10-20", "EUR", "BRL", 200) in wanted
    assert any(f == "EUR" and t == "ARS" and s == 404 for _, f, t, s in wanted)


def test_ecb_reference_values_come_from_the_csv(local_http, tmp_path):
    csv = (
        "KEY,FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE\n"
        "EXR.D.BRL.EUR.SP00.A,D,BRL,EUR,SP00,A,2026-10-15,5.6679\n"
        "EXR.D.BRL.EUR.SP00.A,D,BRL,EUR,SP00,A,2026-10-20,5.6339\n"
    )
    local_http.add("/service/data/EXR/D.BRL.EUR.SP00.A", csv)

    rec.record_ecb(tmp_path, local_http.base_url, start="2026-10-15", end="2026-10-20", currencies=("BRL",))

    data = json.loads((tmp_path / "fx" / "ecb_reference.json").read_text())
    assert data["series"]["BRL"] == {"2026-10-15": "5.6679", "2026-10-20": "5.6339"}
    assert data["source"].startswith("ECB Data Portal")


def test_ptax_keeps_the_closing_bulletin_sell_rate(local_http, tmp_path):
    body = {
        "value": [
            {
                "cotacaoCompra": 5.6,
                "cotacaoVenda": 5.61,
                "dataHoraCotacao": "2026-10-15 10:03:45.5",
                "tipoBoletim": "Abertura",
            },
            {
                "cotacaoCompra": 5.64,
                "cotacaoVenda": 5.6489,
                "dataHoraCotacao": "2026-10-15 12:11:13.9",
                "tipoBoletim": "Intermediário",
            },
            {
                "cotacaoCompra": 5.65,
                "cotacaoVenda": 5.65090,
                "dataHoraCotacao": "2026-10-15 13:05:17.8",
                "tipoBoletim": "Fechamento",
            },
            {
                "cotacaoCompra": 5.6,
                "cotacaoVenda": 5.6,
                "dataHoraCotacao": "2026-10-16 13:05:17.8",
                "tipoBoletim": "Fechamento PTAX",
            },
        ]
    }
    local_http.add(PTAX_PATH, json.dumps(body))

    rec.record_ptax(tmp_path, local_http.base_url, start="2026-10-15", end="2026-10-16", currencies=("EUR",))

    data = json.loads((tmp_path / "fx" / "bcb_ptax_EUR_BRL.json").read_text())
    assert data["values"] == {"2026-10-15": "5.6509", "2026-10-16": "5.6"}
    assert data["currency"] == "EUR" and data["quote"] == "BRL"
    request = next(r for r in local_http.requests if "CotacaoMoedaPeriodo" in r)
    assert "10-15-2026" in request and "10-16-2026" in request, "Olinda wants MM-DD-YYYY"


def test_holidays_are_recorded_as_served(local_http, tmp_path):
    body = b'[{"date":"2026-10-12","localName":"Nossa Senhora Aparecida","countryCode":"BR","types":["Public"]}]'
    local_http.add("/api/v3/PublicHolidays/2026/BR", body)

    rec.record_holidays(tmp_path, local_http.base_url, year=2026, countries=("BR",))

    assert (tmp_path / "holidays" / "nager_BR_2026.json").read_bytes() == body


def test_bins_are_derived_with_brand_mapping_and_weights(tmp_path):
    csv = tmp_path / "bins.csv"
    csv.write_text(
        "BIN,Brand,Type,Category,Issuer,IssuerPhone,IssuerUrl,isoCode2,isoCode3,CountryName\n"
        "411111,VISA,CREDIT,,Bank A,,,BR,BRA,BRAZIL\n"
        "411112,VISA,DEBIT,,Bank A,,,BR,BRA,BRAZIL\n"
        "511111,MASTERCARD,CREDIT,,Bank B,,,BR,BRA,BRAZIL\n"
        "636368,ELO,CREDIT,,Bank C,,,BR,BRA,BRAZIL\n"
        "341111,AMERICAN EXPRESS,CREDIT,,Bank D,,,US,USA,UNITED STATES\n"
        "601111,DISCOVER,CREDIT,,Bank E,,,US,USA,UNITED STATES\n"
        "002102,PRIVATE LABEL,CREDIT,,Bank F,,,CN,CHN,CHINA\n",
        encoding="utf-8",
    )

    rec.derive_bins(csv, tmp_path / "bins.json")

    data = json.loads((tmp_path / "bins.json").read_text())
    assert set(data["brands"]) >= {"visa", "mastercard", "amex", "elo", "other"}
    assert "411111" in data["brands"]["visa"]
    weights = data["country_brand_weights"]["BR"]
    assert weights["visa"] == pytest.approx(0.5) and weights["elo"] == pytest.approx(0.25)
    assert sum(weights.values()) == pytest.approx(1.0)
    assert data["country_brand_weights"]["US"]["other"] == pytest.approx(0.5)
    assert "CC BY 4.0" in data["license"]


def test_main_runs_a_chosen_step_into_the_out_dir(local_http, tmp_path):
    body = b'[{"date":"2026-01-01"}]'
    for country in ("BR", "US", "DE"):
        local_http.add(f"/api/v3/PublicHolidays/2026/{country}", body)

    code = rec.main(["holidays", "--out", str(tmp_path), "--nager-url", local_http.base_url])

    assert code == 0
    assert (tmp_path / "holidays" / "nager_DE_2026.json").exists()


def test_recorded_fixtures_in_the_repository_are_consistent():
    """When fixtures are committed, the series, the single responses and the ECB values agree."""
    fx = REPO / "data" / "fixtures" / "fx"
    if not (fx / "frankfurter_eur.json").exists():
        pytest.skip("fixtures not recorded yet")
    series = json.loads((fx / "frankfurter_eur.json").read_text(), parse_float=Decimal)
    ecb = json.loads((fx / "ecb_reference.json").read_text())
    for day, rates in series["rates"].items():
        for currency, value in rates.items():
            reference = ecb["series"].get(currency, {}).get(day)
            assert reference is None or Decimal(reference) == value, (day, currency)
    single = json.loads((fx / "2026-10-20_EUR_BRL.json").read_text(), parse_float=Decimal)
    assert single["rates"]["BRL"] == series["rates"]["2026-10-20"]["BRL"]
