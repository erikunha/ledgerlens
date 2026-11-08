"""Rate lookup over the recorded ECB series (weekend carry-forward) and the holiday calendars."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import holidays
import pytest
from holidays.financial import BrasilBolsaBalcao

from ledgerlens.sim.fx import FxTable, FxUnavailable

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "data" / "fixtures"


@pytest.fixture(scope="module")
def table() -> FxTable:
    return FxTable.from_file(FIXTURES / "fx" / "frankfurter_eur.json")


def test_direct_euro_rates_are_the_recorded_ones(table):
    rate = table.rate(date(2026, 10, 20), "EUR", "BRL")
    assert rate.rate == Decimal("5.6339") and rate.rate_date == date(2026, 10, 20)
    assert table.rate(date(2026, 10, 15), "EUR", "BRL").rate == Decimal("5.6679")


def test_a_weekend_reuses_the_previous_business_day(table):
    saturday = table.rate(date(2026, 10, 17), "EUR", "BRL")
    assert saturday.rate_date == date(2026, 10, 16) and saturday.requested_date == date(2026, 10, 17)
    assert saturday.rate == Decimal("5.7197")
    assert table.rate(date(2026, 11, 7), "EUR", "BRL").rate_date == date(2026, 11, 6)
    assert table.rate(date(2026, 10, 18), "EUR", "BRL").rate == saturday.rate


def test_the_carry_forward_matches_what_the_api_answered_for_a_saturday(table):
    recorded = json.loads((FIXTURES / "fx" / "2026-10-17_EUR_BRL.json").read_text(), parse_float=Decimal)
    answer = table.rate(date(2026, 10, 17), "EUR", "BRL")
    assert answer.rate_date.isoformat() == recorded["date"]
    assert answer.rate == recorded["rates"]["BRL"]


def test_cross_rates_go_through_the_euro_and_round_to_four_decimals(table):
    rate = table.rate(date(2026, 10, 20), "USD", "BRL")
    recorded = json.loads((FIXTURES / "fx" / "2026-10-20_USD_BRL.json").read_text(), parse_float=Decimal)
    assert rate.rate == recorded["rates"]["BRL"] == Decimal("5.0235")
    inverse = table.rate(date(2026, 10, 20), "BRL", "EUR")
    assert inverse.rate == Decimal("0.1775")
    assert table.rate(date(2026, 10, 20), "EUR", "EUR").rate == Decimal("1")


def test_an_unsupported_currency_is_reported_not_guessed(table):
    with pytest.raises(FxUnavailable, match="ARS"):
        table.rate(date(2026, 10, 15), "EUR", "ARS")


def test_dates_outside_the_series_are_refused(table):
    with pytest.raises(FxUnavailable, match="before"):
        table.rate(date(2026, 6, 1), "EUR", "BRL")
    with pytest.raises(FxUnavailable, match="after"):
        table.rate(date(2026, 12, 31), "EUR", "BRL")


def test_the_series_agrees_with_the_ecb_data_portal(table):
    ecb = json.loads((FIXTURES / "fx" / "ecb_reference.json").read_text())
    for currency, values in ecb["series"].items():
        for day, value in values.items():
            assert table.rate(date.fromisoformat(day), "EUR", currency).rate == Decimal(value), (day, currency)


def test_scenario_rates_equal_the_ecb_values_the_scenarios_quote(table):
    ecb = json.loads((FIXTURES / "fx" / "ecb_reference.json").read_text())["series"]["BRL"]
    assert table.rate(date(2026, 10, 15), "EUR", "BRL").rate == Decimal(ecb["2026-10-15"]) == Decimal("5.6679")
    assert table.rate(date(2026, 10, 20), "EUR", "BRL").rate == Decimal(ecb["2026-10-20"]) == Decimal("5.6339")


def _nager(country: str) -> list[dict]:
    return json.loads((FIXTURES / "holidays" / f"nager_{country}_2026.json").read_text())


def test_the_b3_calendar_covers_every_national_holiday_nager_lists_for_brazil():
    # explicit language: without it the library picks the name from the machine's LANG, and CI (C.UTF-8) differs
    b3 = BrasilBolsaBalcao(years=2026, language="en_US")
    national = [
        h
        for h in _nager("BR")
        if h["global"] and "Public" in h["types"] and date.fromisoformat(h["date"]).weekday() < 5
    ]
    assert national, "the fixture should list weekday holidays"
    assert [h["date"] for h in national if h["date"] not in b3] == []
    assert "2026-10-12" in b3 and b3["2026-10-12"] == "Our Lady of Aparecida"


def test_the_us_calendar_has_columbus_day_like_nager():
    us = holidays.US(years=2026)
    columbus = [h for h in _nager("US") if h["date"] == "2026-10-12"]
    assert columbus and "2026-10-12" in us
