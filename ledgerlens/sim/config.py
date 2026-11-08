"""Defaults of the simulator: the merchant catalog, reserved ids, country maps and run settings.

Everything a run depends on is here or in `SimConfig`, and the manifest echoes it, so a run can be
reproduced from `data/scenarios.json` alone.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
DEFAULT_END = date(2026, 11, 7)
DEFAULT_MAX_TRANSACTIONS = 2100
MAX_TRANSACTIONS_LIMIT = 8000  # ids are TX-nnnn and TX-9999 must stay unused (scenario S04)
BR_REASSIGN_SHARE = 0.12
FAILED_PAYMENT_SHARE = 0.03
LATE_REFUND_REQUEST_SHARE = 0.03
SOURCES = ("auto", "public", "sample", "synthetic")
SCENARIO_IDS = tuple(f"S{n:02d}" for n in range(1, 13))


def substream(seed: int, component: str) -> random.Random:
    """The random stream of one component. Adding a component does not move another one's numbers."""
    return random.Random(f"{seed}:{component}")


@dataclass(frozen=True)
class MerchantSpec:
    id: str
    name: str
    country: str
    category: str
    currency: str
    fx_plan: str  # "standard" or "markup"
    refund_window_days: int = 30
    markup_pct: str | None = None  # fixed markup for planted merchants; others are drawn from MARKUP_CHOICES


MARKUP_CHOICES = ("1.5", "2.0", "2.5", "3.0")

# 24 merchants. M-03, M-05, M-09, M-17 and M-22 are planted by scenarios and keep these attributes.
MERCHANTS: tuple[MerchantSpec, ...] = (
    MerchantSpec("M-01", "Atlas Viagens Ltda", "BR", "travel", "BRL", "standard"),
    MerchantSpec("M-02", "Nordlicht Reisen AG", "DE", "travel", "EUR", "markup"),
    MerchantSpec("M-03", "Casa Verde Foods", "BR", "food", "BRL", "standard"),
    MerchantSpec("M-04", "Pixel Forge Studios", "SE", "gaming", "EUR", "standard", refund_window_days=14),
    MerchantSpec("M-05", "Brisa Apps Inc", "US", "saas", "USD", "standard"),
    MerchantSpec("M-06", "Mercado do Sol", "BR", "retail", "BRL", "markup"),
    MerchantSpec("M-07", "Bluebird Books Ltd", "GB", "retail", "GBP", "standard"),
    MerchantSpec("M-08", "Rhein Gadgets GmbH", "DE", "retail", "EUR", "standard"),
    MerchantSpec("M-09", "Harbor Goods LLC", "US", "retail", "USD", "standard"),
    MerchantSpec("M-10", "Taverna Lisboa Lda", "PT", "food", "EUR", "standard"),
    MerchantSpec("M-11", "Cloudnine SaaS Inc", "US", "saas", "USD", "markup"),
    MerchantSpec("M-12", "Sertao Digital Ltda", "BR", "saas", "BRL", "standard"),
    MerchantSpec("M-13", "Alpenmarkt GmbH", "DE", "marketplace", "EUR", "standard", refund_window_days=60),
    MerchantSpec("M-14", "Thames Gifts Ltd", "GB", "retail", "GBP", "markup"),
    MerchantSpec("M-15", "Fiesta Games SL", "ES", "gaming", "EUR", "standard"),
    MerchantSpec("M-16", "Oceano Marketplace SA", "BR", "marketplace", "BRL", "markup"),
    MerchantSpec("M-17", "Lumen Travel GmbH", "DE", "travel", "EUR", "markup", markup_pct="2.5"),
    MerchantSpec("M-18", "Prairie Outfitters Inc", "US", "retail", "USD", "standard", refund_window_days=45),
    MerchantSpec("M-19", "Seine Gourmet SAS", "FR", "food", "EUR", "markup"),
    MerchantSpec("M-20", "Bits and Bytes Ltd", "GB", "saas", "GBP", "standard"),
    MerchantSpec("M-21", "Tupa Eletro Ltda", "BR", "retail", "BRL", "standard"),
    MerchantSpec("M-22", "Pampa Games SA", "AR", "gaming", "USD", "standard"),
    MerchantSpec("M-23", "Dolce Vita Srl", "IT", "food", "EUR", "standard"),
    MerchantSpec("M-24", "Maple Market Ltd", "CA", "marketplace", "CAD", "standard"),
)

# Ids that scenarios use. Natural rows skip them, so the scenario facts never depend on the source.
RESERVED_IDS: dict[str, tuple[str, ...]] = {
    "merchants": ("M-03", "M-05", "M-09", "M-17", "M-22"),
    "customers": ("C-0205", "C-0291", "C-0412", "C-0501", "C-0600", "C-0733", "C-0777", "C-0888", "C-0900"),
    "transactions": (
        "TX-2030",
        "TX-2048",
        "TX-2051",
        "TX-2052",
        "TX-2060",
        "TX-2061",
        "TX-2077",
        "TX-2081",
        "TX-2082",
        "TX-2083",
        "TX-2084",
        "TX-2090",
        "TX-2095",
        "TX-2099",
    ),
    "refunds": ("R-0720", "R-0731", "R-0740", "R-0750"),
    "chargebacks": ("CB-0310", "CB-0311", "CB-0312"),
    "settlements": ("ST-0044",),
    "fx": ("FX-9001", "FX-9002"),
}
ABSENT_IDS = ("TX-9999",)  # scenario S04: this id must not exist

EURO_AREA = frozenset("AT BE CY DE EE ES FI FR GR HR IE IT LT LU LV MT NL PT SI SK".split())

# Country names of the Online Retail II file to ISO 3166-1 alpha-2. Unknown names become "ZZ".
COUNTRY_ISO = {
    "United Kingdom": "GB",
    "France": "FR",
    "Germany": "DE",
    "EIRE": "IE",
    "Spain": "ES",
    "Netherlands": "NL",
    "Belgium": "BE",
    "Switzerland": "CH",
    "Portugal": "PT",
    "Australia": "AU",
    "Norway": "NO",
    "Italy": "IT",
    "Channel Islands": "GB",
    "Finland": "FI",
    "Cyprus": "CY",
    "Sweden": "SE",
    "Austria": "AT",
    "Denmark": "DK",
    "Japan": "JP",
    "Poland": "PL",
    "Israel": "IL",
    "USA": "US",
    "Hong Kong": "HK",
    "Singapore": "SG",
    "Iceland": "IS",
    "Canada": "CA",
    "Greece": "GR",
    "Malta": "MT",
    "United Arab Emirates": "AE",
    "European Community": "EU",
    "RSA": "ZA",
    "Lebanon": "LB",
    "Lithuania": "LT",
    "Brazil": "BR",
    "Czech Republic": "CZ",
    "Bahrain": "BH",
    "Saudi Arabia": "SA",
    "Korea": "KR",
    "Nigeria": "NG",
    "Thailand": "TH",
    "Bermuda": "BM",
    "Malaysia": "MY",
    "Unspecified": "ZZ",
}

FAKER_LOCALES = {"BR": "pt_BR", "DE": "de_DE", "FR": "fr_FR", "ES": "es_ES", "PT": "pt_PT", "IT": "it_IT"}
DEFAULT_FAKER_LOCALE = "en_GB"


def billing_currency(country: str) -> str:
    """Euro area countries pay in EUR, the United Kingdom in GBP, Brazil in BRL, everyone else in USD."""
    if country in EURO_AREA or country == "EU":
        return "EUR"
    if country == "GB":
        return "GBP"
    if country == "BR":
        return "BRL"
    return "USD"


@dataclass(frozen=True)
class SimConfig:
    seed: int = 42
    days: int = 90
    end: date = DEFAULT_END
    source: str = "auto"
    max_transactions: int = DEFAULT_MAX_TRANSACTIONS
    scenarios: tuple[str, ...] = SCENARIO_IDS
    raw_path: Path = DATA / "raw" / "online_retail_ii.zip"
    sample_path: Path = DATA / "sample" / "invoices_sample.jsonl"
    fx_path: Path = DATA / "fixtures" / "fx" / "frankfurter_eur.json"
    bins_path: Path = DATA / "fixtures" / "bins.json"
    extra: dict = field(default_factory=dict, compare=False)

    def validate(self) -> None:
        if self.source not in SOURCES:
            raise ValueError(f"source must be one of {', '.join(SOURCES)}")
        if self.days < 1:
            raise ValueError("days must be at least 1")
        if not 1 <= self.max_transactions <= MAX_TRANSACTIONS_LIMIT:
            raise ValueError(f"max-transactions must be between 1 and {MAX_TRANSACTIONS_LIMIT}")
        unknown = set(self.scenarios) - set(SCENARIO_IDS)
        if unknown:
            raise ValueError(f"unknown scenario(s): {', '.join(sorted(unknown))}")
