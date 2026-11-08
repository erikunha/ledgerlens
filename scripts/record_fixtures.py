#!/usr/bin/env python3
"""Record the reference data the simulator and the tools read offline into data/fixtures/.

Run as: uv run python scripts/record_fixtures.py [fx|ecb|ptax|holidays|bins|all] [--start D] [--end D]

Steps (all keyless):
  fx        Frankfurter v1 (ECB only): the daily series for the simulator window
            (fx/frankfurter_eur.json), plus single-date responses kept byte for byte
            (fx/<date>_<FROM>_<TO>.json) and fx/index.json with the HTTP status of each.
            Plain /v2 blends providers and is never called.
  ecb       ECB Data Portal values for the same window (fx/ecb_reference.json), the primary
            source the Frankfurter values are checked against.
  ptax      BCB PTAX closing sell rates (fx/bcb_ptax_<CUR>_BRL.json).
  holidays  Nager.Date public holidays (holidays/nager_<CC>_<year>.json), used to cross-check the
            `holidays` library calendars.
  bins      bins.json derived from the CC BY 4.0 BIN list in data/raw/ (run fetch_public_data.py first).

A request that answers with an unexpected status is an error and writes nothing for that file,
so a failing upstream never becomes a fixture.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "fixtures"
DEFAULT_BIN_CSV = ROOT / "data" / "raw" / "bin-list-data.csv"

FRANKFURTER_URL = "https://api.frankfurter.dev"
ECB_URL = "https://data-api.ecb.europa.eu"
BCB_URL = "https://olinda.bcb.gov.br"
NAGER_URL = "https://date.nager.at"

DEFAULT_START = "2026-07-01"
DEFAULT_END = "2026-11-06"
FX_SYMBOLS = ("BRL", "CAD", "CHF", "GBP", "USD")
PTAX_CURRENCIES = ("EUR", "USD")
HOLIDAY_COUNTRIES = ("BR", "DE", "US")
HOLIDAY_YEAR = 2026

# (date, from, to, expected HTTP status). 2026-10-15 and 2026-10-20 feed scenario S01, 2026-10-17 is a
# Saturday (the API answers with Friday's date), 2026-10-05 is the date of the source comparison in
# the research, and ARS is not an ECB currency (HTTP 404).
FRANKFURTER_SINGLES: tuple[tuple[str, str, str, int], ...] = (
    ("2026-10-05", "EUR", "BRL", 200),
    ("2026-10-15", "EUR", "BRL", 200),
    ("2026-10-15", "EUR", "USD", 200),
    ("2026-10-17", "EUR", "BRL", 200),
    ("2026-10-20", "EUR", "BRL", 200),
    ("2026-10-20", "EUR", "USD", 200),
    ("2026-10-20", "USD", "BRL", 200),
    ("2026-10-15", "EUR", "ARS", 404),
)

BRAND_MAP = {
    "VISA": "visa",
    "MASTERCARD": "mastercard",
    "AMERICAN EXPRESS": "amex",
    "AMEX": "amex",
    "ELO": "elo",
}
BIN_PREFIXES_PER_BRAND = 25
BIN_LICENSE = "CC BY 4.0, https://github.com/venelinkochev/bin-list-data"


class RecordError(RuntimeError):
    """A recording step failed. The message names the URL and the reason."""


def _get(
    client: httpx.Client, url: str, *, expected: int = 200, headers: dict[str, str] | None = None
) -> httpx.Response:
    try:
        response = client.get(url, headers=headers)
    except httpx.HTTPError as error:
        raise RecordError(f"{url}: {type(error).__name__}: {error}") from error
    if response.status_code != expected:
        raise RecordError(f"{url}: expected HTTP {expected}, got {response.status_code}")
    return response


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _client() -> httpx.Client:
    return httpx.Client(timeout=30.0, follow_redirects=True)


def record_frankfurter(
    out_dir: Path,
    base_url: str,
    *,
    start: str,
    end: str,
    symbols: Sequence[str] = FX_SYMBOLS,
    singles: Iterable[tuple[str, str, str, int]] = FRANKFURTER_SINGLES,
    client: httpx.Client | None = None,
) -> None:
    owns = client is None
    client = client or _client()
    try:
        fx = out_dir / "fx"
        series_url = f"{base_url}/v1/{start}..{end}?base=EUR&symbols={','.join(sorted(symbols))}"
        raw = _get(client, series_url).json(parse_float=Decimal)
        series = {
            "base": "EUR",
            "provider": "ECB",
            "source": "Frankfurter v1 (ECB only), https://frankfurter.dev",
            "start_date": raw["start_date"],
            "end_date": raw["end_date"],
            "symbols": sorted(symbols),
            "rates": {
                day: {cur: rate for cur, rate in sorted(rates.items())} for day, rates in sorted(raw["rates"].items())
            },
        }
        recorded: dict[str, tuple[int, bytes, str]] = {}
        for day, source, target, status in singles:
            url = f"{base_url}/v1/{day}?from={source}&to={target}"
            response = _get(client, url, expected=status)
            recorded[f"{day}_{source}_{target}.json"] = (status, response.content, url)
        _write_series_and_singles(fx, series, recorded)
    finally:
        if owns:
            client.close()


def _write_series_and_singles(fx: Path, series: dict, recorded: dict[str, tuple[int, bytes, str]]) -> None:
    fx.mkdir(parents=True, exist_ok=True)
    _write_json(fx / "frankfurter_eur.json", _as_floats(series))
    index_path = fx / "index.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else {"schema_version": "1", "files": {}}
    for name, (status, body, url) in recorded.items():
        (fx / name).write_bytes(body)
        digest = hashlib.sha256(body).hexdigest()
        previous = index["files"].get(name)
        if previous and previous["sha256"] == digest and previous["status"] == status:
            continue
        index["files"][name] = {"url": url, "status": status, "sha256": digest, "recorded_at": _now()}
    index["files"] = dict(sorted(index["files"].items()))
    _write_json(index_path, index)


def _as_floats(value: object) -> object:
    """Rates are written as JSON numbers (shortest repr, the digits the API sent); readers parse with Decimal."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: _as_floats(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_as_floats(item) for item in value]
    return value


def record_ecb(
    out_dir: Path,
    base_url: str,
    *,
    start: str,
    end: str,
    currencies: Sequence[str] = FX_SYMBOLS,
    client: httpx.Client | None = None,
) -> None:
    owns = client is None
    client = client or _client()
    try:
        series: dict[str, dict[str, str]] = {}
        for currency in currencies:
            url = (
                f"{base_url}/service/data/EXR/D.{currency}.EUR.SP00.A"
                f"?startPeriod={start}&endPeriod={end}&detail=dataonly"
            )
            text = _get(client, url, headers={"Accept": "text/csv"}).text
            rows = csv.DictReader(text.splitlines())
            series[currency] = {row["TIME_PERIOD"]: row["OBS_VALUE"] for row in rows}
        _write_json(
            out_dir / "fx" / "ecb_reference.json",
            {
                "source": "ECB Data Portal (SDMX), dataset EXR, https://data.ecb.europa.eu",
                "unit": "units of currency per 1 EUR",
                "start_date": start,
                "end_date": end,
                "series": {cur: dict(sorted(values.items())) for cur, values in sorted(series.items())},
            },
        )
    finally:
        if owns:
            client.close()


def _ptax_date(day: str) -> str:
    parsed = date.fromisoformat(day)
    return f"{parsed.month:02d}-{parsed.day:02d}-{parsed.year}"


def _plain(value: object) -> str:
    return format(Decimal(str(value)).normalize(), "f")


def record_ptax(
    out_dir: Path,
    base_url: str,
    *,
    start: str,
    end: str,
    currencies: Sequence[str] = PTAX_CURRENCIES,
    client: httpx.Client | None = None,
) -> None:
    owns = client is None
    client = client or _client()
    try:
        for currency in currencies:
            url = (
                f"{base_url}/olinda/servico/PTAX/versao/v1/odata/"
                "CotacaoMoedaPeriodo(moeda=@moeda,dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)"
                f"?@moeda='{currency}'&@dataInicial='{_ptax_date(start)}'&@dataFinalCotacao='{_ptax_date(end)}'"
                "&$format=json"
            )
            rows = _get(client, url).json(parse_float=Decimal)["value"]
            closing: dict[str, str] = {}
            for row in sorted(rows, key=lambda r: r["dataHoraCotacao"]):
                if str(row["tipoBoletim"]).startswith("Fechamento"):
                    closing[row["dataHoraCotacao"][:10]] = _plain(row["cotacaoVenda"])
            _write_json(
                out_dir / "fx" / f"bcb_ptax_{currency}_BRL.json",
                {
                    "source": "BCB Olinda PTAX, https://olinda.bcb.gov.br",
                    "currency": currency,
                    "quote": "BRL",
                    "bulletin": "Fechamento",
                    "field": "cotacaoVenda",
                    "values": dict(sorted(closing.items())),
                },
            )
    finally:
        if owns:
            client.close()


def record_holidays(
    out_dir: Path,
    base_url: str,
    *,
    year: int = HOLIDAY_YEAR,
    countries: Sequence[str] = HOLIDAY_COUNTRIES,
    client: httpx.Client | None = None,
) -> None:
    owns = client is None
    client = client or _client()
    try:
        target = out_dir / "holidays"
        target.mkdir(parents=True, exist_ok=True)
        for country in countries:
            body = _get(client, f"{base_url}/api/v3/PublicHolidays/{year}/{country}").content
            (target / f"nager_{country}_{year}.json").write_bytes(body)
    finally:
        if owns:
            client.close()


def derive_bins(csv_path: Path, out_path: Path) -> None:
    """Brand to BIN prefixes and per-country brand weights from the CC BY 4.0 BIN list."""
    prefixes: dict[str, list[str]] = defaultdict(list)
    by_country: dict[str, Counter] = defaultdict(Counter)
    with csv_path.open(newline="", encoding="utf-8", errors="replace") as handle:
        for row in csv.DictReader(handle):
            brand = BRAND_MAP.get(row["Brand"].strip().upper(), "other")
            code = row["BIN"].strip()
            country = row["isoCode2"].strip().upper()
            if not code or len(country) != 2:
                continue
            if len(prefixes[brand]) < BIN_PREFIXES_PER_BRAND:
                prefixes[brand].append(code)
            by_country[country][brand] += 1
    weights = {
        country: {brand: round(count / sum(counts.values()), 6) for brand, count in sorted(counts.items())}
        for country, counts in sorted(by_country.items())
    }
    for brand in ("visa", "mastercard", "amex", "elo", "other"):
        prefixes.setdefault(brand, [])
    _write_json(
        out_path,
        {
            "source": "venelinkochev/bin-list-data",
            "license": BIN_LICENSE,
            "brands": {brand: sorted(codes) for brand, codes in sorted(prefixes.items())},
            "country_brand_weights": weights,
        },
    )


STEPS = ("fx", "ecb", "ptax", "holidays", "bins")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("steps", nargs="*", default=["all"], choices=[*STEPS, "all"], metavar="STEP")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    parser.add_argument("--bin-csv", type=Path, default=DEFAULT_BIN_CSV)
    parser.add_argument("--frankfurter-url", default=FRANKFURTER_URL)
    parser.add_argument("--ecb-url", default=ECB_URL)
    parser.add_argument("--bcb-url", default=BCB_URL)
    parser.add_argument("--nager-url", default=NAGER_URL)
    args = parser.parse_args(argv)
    steps = STEPS if "all" in args.steps else tuple(args.steps)
    try:
        if "fx" in steps:
            record_frankfurter(args.out, args.frankfurter_url, start=args.start, end=args.end)
            print("recorded fx/frankfurter_eur.json and single-date responses")
        if "ecb" in steps:
            record_ecb(args.out, args.ecb_url, start=args.start, end=args.end)
            print("recorded fx/ecb_reference.json")
        if "ptax" in steps:
            record_ptax(args.out, args.bcb_url, start=args.start, end=args.end)
            print("recorded fx/bcb_ptax_*_BRL.json")
        if "holidays" in steps:
            record_holidays(args.out, args.nager_url)
            print("recorded holidays/nager_*.json")
        if "bins" in steps:
            if not args.bin_csv.exists():
                print(f"error: {args.bin_csv} not found; run scripts/fetch_public_data.py first", file=sys.stderr)
                return 1
            derive_bins(args.bin_csv, args.out / "bins.json")
            print("derived bins.json")
    except RecordError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
