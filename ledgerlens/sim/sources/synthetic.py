"""Seeded invoice generator, the last fallback when neither the public file nor the sample exists.

Same record shape as the public source: invoices in pounds, cancellations that share a stock code
with an earlier sale of the same customer. Everything comes from `random.Random(f"{seed}:synthetic")`,
so the same arguments give the same invoices.
"""

from __future__ import annotations

import random
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_EVEN, Decimal

from ledgerlens.sim.sources.base import SourceInvoice

COUNTRIES = (
    ("United Kingdom", 62),
    ("Germany", 7),
    ("France", 7),
    ("EIRE", 4),
    ("Spain", 3),
    ("Netherlands", 3),
    ("Belgium", 2),
    ("Switzerland", 2),
    ("Portugal", 2),
    ("Australia", 2),
    ("Norway", 2),
    ("Italy", 2),
    ("USA", 2),
)
CATALOG_SIZE = 90


@dataclass
class SyntheticSource:
    seed: int = 42
    days: int = 90
    end: date = date(2026, 11, 7)
    sales: int = 2100
    cancellation_share: float = 0.07
    name: str = "synthetic"

    def iter_invoices(self) -> Iterator[SourceInvoice]:
        rng = random.Random(f"{self.seed}:synthetic")
        codes = [f"SYN{n:04d}" for n in range(1, CATALOG_SIZE + 1)]
        prices = {code: Decimal(str(round(rng.uniform(0.5, 40.0), 2))) for code in codes}
        weights = [w for _, w in COUNTRIES]
        customers = max(10, self.sales // 3)
        country_of = {f"{20000 + n}": rng.choices([c for c, _ in COUNTRIES], weights)[0] for n in range(customers)}
        customer_ids = sorted(country_of)
        start = self.end - timedelta(days=self.days - 1)
        sales: list[SourceInvoice] = []
        for n in range(self.sales):
            customer = rng.choice(customer_ids)
            day = start + timedelta(days=rng.randrange(self.days))
            placed_at = datetime.combine(day, time(rng.randrange(7, 20), rng.randrange(60)))
            picked = rng.sample(codes, rng.randint(1, 5))
            totals = {code: prices[code] * rng.randint(1, 12) for code in picked}
            ordered = tuple(code for code, _ in sorted(totals.items(), key=lambda item: (-item[1], item[0])))
            sales.append(
                SourceInvoice(
                    source_ref=f"S{n + 1:06d}",
                    customer_ref=customer,
                    placed_at=placed_at,
                    amount=sum(totals.values(), Decimal(0)).quantize(Decimal("0.01"), ROUND_HALF_EVEN),
                    currency="GBP",
                    country=country_of[customer],
                    stock_codes=ordered,
                    is_cancellation=False,
                )
            )
        out = list(sales)
        for n, sale in enumerate(rng.sample(sales, int(len(sales) * self.cancellation_share))):
            share = Decimal(str(round(rng.uniform(0.3, 1.2), 2)))
            delay = timedelta(hours=rng.randint(1, 24 * 20), minutes=rng.randrange(60))
            placed_at = min(sale.placed_at + delay, datetime.combine(self.end, time(23, 59)))
            if placed_at <= sale.placed_at:
                continue
            out.append(
                SourceInvoice(
                    source_ref=f"CS{n + 1:06d}",
                    customer_ref=sale.customer_ref,
                    placed_at=placed_at,
                    amount=-(sale.amount * share).quantize(Decimal("0.01"), ROUND_HALF_EVEN),
                    currency="GBP",
                    country=sale.country,
                    stock_codes=sale.stock_codes[:1],
                    is_cancellation=True,
                )
            )
        out.sort(key=lambda inv: (inv.placed_at, inv.source_ref))
        yield from out
