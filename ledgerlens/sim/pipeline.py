"""Builds the ledger from a source of invoices.

Steps, in order, each reading its own random substream:

1. open the source (public file, committed sample, or seeded generator);
2. select sales inside the window, stratified by day, and link cancellations to selected sales;
3. shift the dates so the last selected day is `--end`;
4. turn invoices into events: merchants, customers, payments, cross-currency charges, refunds,
   late refund requests that get rejected, chargebacks;
5. add the selected scenarios;
6. project into SQLite, then close the weekly settlements from the tables;
7. write the manifest with the ground truth read back from the database.

Nothing here talks to the network. Rates come from the recorded ECB series.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Any

from faker import Faker

from ledgerlens.sim import gaps, scenarios
from ledgerlens.sim.calendars import payout_date
from ledgerlens.sim.config import (
    ABSENT_IDS,
    BR_REASSIGN_SHARE,
    COUNTRY_ISO,
    DEFAULT_FAKER_LOCALE,
    EURO_AREA,
    FAILED_PAYMENT_SHARE,
    FAKER_LOCALES,
    LATE_REFUND_REQUEST_SHARE,
    MARKUP_CHOICES,
    MERCHANTS,
    RESERVED_IDS,
    MerchantSpec,
    SimConfig,
    billing_currency,
    substream,
)
from ledgerlens.sim.events import Event
from ledgerlens.sim.fx import FxTable
from ledgerlens.sim.projector import Projector, canonical_hash, create_database
from ledgerlens.sim.sources.base import InvoiceSource, SourceInvoice
from ledgerlens.sim.sources.sample import SampleSource
from ledgerlens.sim.sources.synthetic import SyntheticSource
from ledgerlens.sim.sources.uci import SERVICE_STOCK_CODES, Link, UciSource, link_cancellations

REFUND_REASONS = (
    "Customer cancelled the order",
    "Product returned",
    "Item damaged in delivery",
    "Changed mind about the purchase",
    "Charge not recognized by the customer",
)
DECLINE_REASONS = ("Card declined by the issuer", "Insufficient funds", "Suspected fraud detected")
LATE_REASONS = ("I want my money back", "I forgot to ask earlier", "I only saw the charge now")
METHODS_BR = (("pix", 45), ("card", 40), ("boleto", 10), ("wallet", 5))
METHODS_EU = (("card", 62), ("wallet", 18), ("bank_transfer", 17), ("voucher", 3))
METHODS_OTHER = (("card", 75), ("wallet", 17), ("bank_transfer", 5), ("voucher", 3))
DEFAULT_BRAND_WEIGHTS = {"visa": 0.5, "mastercard": 0.35, "amex": 0.05, "elo": 0.02, "other": 0.08}


class SourceUnavailable(RuntimeError):
    """The requested source of invoices cannot be used. The message says what is missing."""


def iso(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class BuildResult:
    conn: sqlite3.Connection
    manifest: dict[str, Any]
    source: str
    selected_invoices: list[SourceInvoice]
    events: int = 0


# -- 1. source ------------------------------------------------------------------------------------


def open_source(cfg: SimConfig) -> tuple[InvoiceSource, str]:
    """The first usable source in the order public, sample, synthetic (or the one asked for)."""
    order = ("public", "sample", "synthetic") if cfg.source == "auto" else (cfg.source,)
    for name in order:
        if name == "public" and Path(cfg.raw_path).exists():
            return UciSource(Path(cfg.raw_path)), "public"
        if name == "sample" and Path(cfg.sample_path).exists():
            return SampleSource(Path(cfg.sample_path)), "sample"
        if name == "synthetic":
            return SyntheticSource(cfg.seed, cfg.days, cfg.end, sales=cfg.max_transactions), "synthetic"
    wanted = {
        "public": f"{cfg.raw_path} (run scripts/fetch_public_data.py)",
        "sample": f"{cfg.sample_path}",
    }
    raise SourceUnavailable(f"source {cfg.source!r} is not available: missing {wanted.get(cfg.source, cfg.source)}")


# -- 2 and 3. selection and time shift --------------------------------------------------------------


@dataclass
class Selection:
    sales: list[SourceInvoice]
    links: list[Link]
    shift_days: int
    window: tuple[date, date]
    stats: dict[str, Any] = field(default_factory=dict)

    @property
    def invoices(self) -> list[SourceInvoice]:
        cancellations = [link.cancellation for link in self.links]
        return sorted([*self.sales, *cancellations], key=lambda inv: (inv.placed_at, inv.source_ref))


def _stratified(pool: list[SourceInvoice], limit: int, rng: Any) -> list[SourceInvoice]:
    """At most `limit` invoices, spread over the days in proportion to how many each day has."""
    if len(pool) <= limit:
        return list(pool)
    days: dict[date, list[SourceInvoice]] = defaultdict(list)
    for inv in pool:
        days[inv.placed_at.date()].append(inv)
    ordered = sorted(days)
    exact = {day: limit * len(days[day]) / len(pool) for day in ordered}
    quota = {day: int(exact[day]) for day in ordered}
    leftover = limit - sum(quota.values())
    for day in sorted(ordered, key=lambda d: (-(exact[d] - quota[d]), d))[:leftover]:
        quota[day] += 1
    chosen: list[SourceInvoice] = []
    for day in ordered:
        chosen.extend(rng.sample(days[day], min(quota[day], len(days[day]))))
    return sorted(chosen, key=lambda inv: (inv.placed_at, inv.source_ref))


def select_invoices(invoices: list[SourceInvoice], cfg: SimConfig) -> Selection:
    if not invoices:
        raise SourceUnavailable("the source has no invoices")
    last = max(inv.placed_at.date() for inv in invoices)
    first = last - timedelta(days=cfg.days - 1)
    window = [inv for inv in invoices if first <= inv.placed_at.date() <= last]
    pool = [inv for inv in window if not inv.is_cancellation and inv.amount > 0]
    cancellations = [inv for inv in window if inv.is_cancellation]
    chosen = _stratified(pool, cfg.max_transactions, substream(cfg.seed, "select"))
    linked = link_cancellations([*chosen, *cancellations])
    whole_window = link_cancellations([*pool, *cancellations])

    remaining = {sale.source_ref: sale.amount for sale in chosen}
    kept: list[Link] = []
    over_refund = 0
    for link in sorted(linked.links, key=lambda item: (item.cancellation.placed_at, item.cancellation.source_ref)):
        amount = min(link.amount, remaining[link.sale.source_ref])
        if amount <= 0:
            over_refund += 1
            continue
        remaining[link.sale.source_ref] -= amount
        kept.append(Link(link.cancellation, link.sale, amount, partial=amount < link.sale.amount))

    selected_days = [inv.placed_at.date() for inv in chosen] + [link.cancellation.placed_at.date() for link in kept]
    if not selected_days:
        raise SourceUnavailable("no sale falls inside the window")
    shift = (cfg.end - max(selected_days)).days
    delta = timedelta(days=shift)
    shifted_sales = [replace(inv, placed_at=inv.placed_at + delta) for inv in chosen]
    sale_by_ref = {inv.source_ref: inv for inv in shifted_sales}
    shifted_links = [
        Link(
            replace(link.cancellation, placed_at=link.cancellation.placed_at + delta),
            sale_by_ref[link.sale.source_ref],
            link.amount,
            link.partial,
        )
        for link in kept
    ]
    stats = {
        "window_first": first.isoformat(),
        "window_last": last.isoformat(),
        "sales_in_window": len(pool),
        "sales_selected": len(chosen),
        "cancellations_in_window": linked.cancellations,
        "cancellations_linked": len(linked.links),
        "cancellations_unlinked": len(linked.unlinked),
        "matching_rate": round(linked.matching_rate, 4),
        "matching_rate_whole_window": round(whole_window.matching_rate, 4),
        "refunds_kept": len(kept),
        "dropped_over_refund": over_refund,
    }
    return Selection(shifted_sales, shifted_links, shift, (first, last), stats)


# -- 4. natural events ------------------------------------------------------------------------------


class IdSeq:
    """Ids `PREFIX-nnnn` in order, skipping the ones scenarios reserve."""

    def __init__(self, prefix: str, reserved: tuple[str, ...], width: int = 4) -> None:
        self.prefix, self.width, self.reserved, self.n = prefix, width, set(reserved), 0

    def next(self) -> str:
        while True:
            self.n += 1
            if self.n >= 10**self.width:
                raise OverflowError(f"more than {10**self.width - 1} {self.prefix} ids")
            candidate = f"{self.prefix}-{self.n:0{self.width}d}"
            if candidate not in self.reserved and candidate not in ABSENT_IDS:
                return candidate


@dataclass
class _Tx:
    id: str
    merchant: MerchantSpec
    customer: str
    billing: str
    amount_minor: int
    currency: str
    created: datetime
    captured: datetime | None
    refunded_minor: int = 0
    last_resolved: datetime | None = None
    has_refund: bool = False


def _weighted(options: tuple[tuple[str, int], ...], u: float) -> str:
    total = sum(weight for _, weight in options)
    point = u * total
    running = 0.0
    for name, weight in options:
        running += weight
        if point < running:
            return name
    return options[-1][0]


class _Natural:
    def __init__(self, cfg: SimConfig, fx: FxTable, sel: Selection, source_name: str, bins: dict[str, Any]) -> None:
        self.cfg, self.fx, self.sel = cfg, fx, sel
        self.origin = "synthetic" if source_name == "synthetic" else "public"
        self.bins = bins
        self.end = datetime.combine(cfg.end, time(23, 59, 59))
        self.specs = {m.id: m for m in MERCHANTS}
        draw = substream(cfg.seed, "markup")
        self.markup: dict[str, Decimal] = {}
        for spec in MERCHANTS:
            if spec.fx_plan != "markup":
                continue
            drawn = draw.choice(MARKUP_CHOICES)
            self.markup[spec.id] = Decimal(spec.markup_pct or drawn)
        self.ids = {
            "tx": IdSeq("TX", RESERVED_IDS["transactions"]),
            "customer": IdSeq("C", RESERVED_IDS["customers"]),
            "refund": IdSeq("R", RESERVED_IDS["refunds"]),
            "chargeback": IdSeq("CB", RESERVED_IDS["chargebacks"]),
            "fx": IdSeq("FX", RESERVED_IDS["fx"]),
        }
        self.records: list[tuple[str, int, Event]] = []
        self.txs: dict[str, _Tx] = {}
        self.tx_by_sale: dict[str, _Tx] = {}
        self.stats = {"presentment": 0, "cross_currency_refunds": 0, "late_rejected": 0}
        self._fakers: dict[str, Faker] = {}

    # events are sorted by (time, creation order) at the end, so a parent created first stays first
    def emit(self, event: Event) -> None:
        self.records.append((event.occurred_at, len(self.records), event))

    def faker(self, country: str) -> Faker:
        locale = FAKER_LOCALES.get(country, DEFAULT_FAKER_LOCALE)
        if locale not in self._fakers:
            fake = Faker(locale)
            fake.seed_instance(int(hashlib.sha256(f"{self.cfg.seed}:faker:{locale}".encode()).hexdigest()[:8], 16))
            self._fakers[locale] = fake
        return self._fakers[locale]

    def brand(self, country: str, u: float) -> str:
        weights = self.bins.get("country_brand_weights", {}).get(country) or DEFAULT_BRAND_WEIGHTS
        names = sorted(weights)
        point, running = u * sum(weights[n] for n in names), 0.0
        for name in names:
            running += weights[name]
            if point < running:
                return name
        return names[-1]

    def build(self) -> list[Event]:
        self._merchants()
        self._payments()
        self._refunds()
        self._late_requests()
        self._chargebacks()
        return [event for _, _, event in sorted(self.records, key=lambda item: (item[0], item[1]))]

    def _merchants(self) -> None:
        for index, spec in enumerate(MERCHANTS):
            self.emit(
                Event(
                    "merchant.onboarded",
                    "merchant",
                    spec.id,
                    iso(datetime(2025, 1, 1) + timedelta(days=index)),
                    {
                        "name": spec.name,
                        "country": spec.country,
                        "category": spec.category,
                        "settlement_currency": spec.currency,
                        "fx_plan": spec.fx_plan,
                        "refund_window_days": spec.refund_window_days,
                    },
                    "synthetic",
                )
            )

    def _merchant_for(self, code: str) -> MerchantSpec:
        return MERCHANTS[int(hashlib.sha256(code.encode()).hexdigest()[:8], 16) % len(MERCHANTS)]

    def _payments(self) -> None:
        cfg = self.cfg
        customers: dict[str, tuple[str, str, str]] = {}  # customer_ref -> (id, country, billing)
        pay, cust = substream(cfg.seed, "payments"), substream(cfg.seed, "customers")
        for inv in self.sel.sales:
            if inv.customer_ref not in customers:
                country = COUNTRY_ISO.get(inv.country, "ZZ")
                if cust.random() < BR_REASSIGN_SHARE:
                    country = "BR"
                customer_id = self.ids["customer"].next()
                customers[inv.customer_ref] = (customer_id, country, billing_currency(country))
                self.emit(
                    Event(
                        "customer.created",
                        "customer",
                        customer_id,
                        iso(inv.placed_at - timedelta(minutes=1)),
                        {
                            "display_name": self.faker(country).name(),
                            "country": country,
                            "billing_currency": billing_currency(country),
                        },
                        self.origin,
                    )
                )
            customer_id, country, billing = customers[inv.customer_ref]
            u_fail, u_method, u_brand = pay.random(), pay.random(), pay.random()
            slot, delay = pay.randrange(3), pay.randint(2, 9)
            spec = self._merchant_for(inv.stock_codes[0])
            rate = self.fx.rate(inv.placed_at.date(), "GBP", spec.currency).rate
            amount_minor = max(1, gaps.convert_minor(int(inv.amount * 100), rate, "GBP", spec.currency))
            tx_id = self.ids["tx"].next()
            created = inv.placed_at.replace(second=0)
            options = (
                METHODS_BR
                if country == "BR"
                else METHODS_EU
                if (country in EURO_AREA or country == "GB")
                else METHODS_OTHER
            )
            method = _weighted(options, u_method)
            brand = self.brand(country, u_brand) if method == "card" else None
            fingerprint = (
                "fp_" + hashlib.sha256(f"{cfg.seed}:{customer_id}:{slot % 2}".encode()).hexdigest()[:12]
                if method == "card"
                else None
            )
            source_ref = hashlib.sha256(f"{cfg.seed}:{inv.source_ref}".encode()).hexdigest()[:12]
            self.emit(
                Event(
                    "payment.authorized",
                    "transaction",
                    tx_id,
                    iso(created),
                    {
                        "merchant_id": spec.id,
                        "customer_id": customer_id,
                        "amount_minor": amount_minor,
                        "currency": spec.currency,
                        "method": method,
                        "card_brand": brand,
                        "card_fingerprint": fingerprint,
                        "source_ref": source_ref,
                    },
                    self.origin,
                )
            )
            tx = _Tx(tx_id, spec, customer_id, billing, amount_minor, spec.currency, created, None)
            self.txs[tx_id] = tx
            self.tx_by_sale[inv.source_ref] = tx
            if u_fail < FAILED_PAYMENT_SHARE:
                reason = DECLINE_REASONS[
                    int(u_fail / FAILED_PAYMENT_SHARE * len(DECLINE_REASONS)) % len(DECLINE_REASONS)
                ]
                self.emit(
                    Event(
                        "payment.failed",
                        "transaction",
                        tx_id,
                        iso(created + timedelta(seconds=1)),
                        {"reason": reason},
                        self.origin,
                    )
                )
                continue
            tx.captured = created + timedelta(seconds=delay)
            self.emit(
                Event(
                    "payment.captured",
                    "transaction",
                    tx_id,
                    iso(tx.captured),
                    {"captured_at": iso(tx.captured)},
                    self.origin,
                )
            )
            if tx.currency != billing:
                self.stats["presentment"] += 1
                charge = self.fx.rate(tx.captured.date(), tx.currency, billing).rate
                self.emit(
                    Event(
                        "fx.applied",
                        "transaction",
                        tx_id,
                        iso(tx.captured),
                        {
                            "fx_id": self.ids["fx"].next(),
                            "refund_id": None,
                            "kind": "charge",
                            "from_currency": tx.currency,
                            "to_currency": billing,
                            "applied_rate": str(charge),
                        },
                        "synthetic",
                    )
                )

    def _refunds(self) -> None:
        rng = substream(self.cfg.seed, "refunds")
        for link in sorted(
            self.sel.links, key=lambda item: (item.cancellation.placed_at, item.cancellation.source_ref)
        ):
            reason_index, hours, minutes = rng.randrange(len(REFUND_REASONS)), rng.randint(1, 72), rng.randrange(60)
            tx = self.tx_by_sale[link.sale.source_ref]
            if tx.captured is None:
                continue
            requested = max(
                link.cancellation.placed_at.replace(second=0), tx.captured.replace(second=0) + timedelta(minutes=1)
            )
            if requested > self.end:
                continue
            remaining = tx.amount_minor - tx.refunded_minor
            if remaining <= 0:
                continue
            if link.amount == link.sale.amount:
                minor = tx.amount_minor
            else:
                minor = int(
                    (Decimal(tx.amount_minor) * link.amount / link.sale.amount).quantize(Decimal(1), ROUND_HALF_EVEN)
                )
            minor = min(max(minor, 1), remaining)
            refund_id = self.ids["refund"].next()
            reason = REFUND_REASONS[reason_index]
            tx.has_refund = True
            self.emit(
                Event(
                    "refund.requested",
                    "refund",
                    refund_id,
                    iso(requested),
                    {
                        "transaction_id": tx.id,
                        "requested_amount_minor": minor,
                        "requested_currency": tx.currency,
                        "reason": reason,
                    },
                    self.origin,
                )
            )
            if (requested.date() - tx.captured.date()).days > tx.merchant.refund_window_days:
                self._reject(refund_id, tx, minor, reason, requested + timedelta(hours=2), "synthetic")
                continue
            resolved = requested + timedelta(hours=hours, minutes=minutes)
            if tx.last_resolved is not None and resolved <= tx.last_resolved:
                resolved = tx.last_resolved + timedelta(minutes=1)
            if resolved > self.end:
                continue
            self._pay(refund_id, tx, minor, reason, resolved)

    def _reject(self, refund_id: str, tx: _Tx, minor: int, reason: str, at: datetime, origin: str) -> None:
        self.emit(
            Event(
                "refund.rejected",
                "refund",
                refund_id,
                iso(at),
                {
                    "refund_id": refund_id,
                    "transaction_id": tx.id,
                    "requested_amount_minor": minor,
                    "requested_currency": tx.currency,
                    "reason": reason,
                    "rejection_reason": "outside_refund_window",
                },
                origin,
            )
        )

    def _pay(self, refund_id: str, tx: _Tx, minor: int, reason: str, resolved: datetime) -> None:
        fx_id: str | None = None
        payout_minor, payout_currency = minor, tx.currency
        if tx.billing != tx.currency:
            self.stats["cross_currency_refunds"] += 1
            reference = self.fx.rate(resolved.date(), tx.currency, tx.billing).rate
            refund = gaps.cross_currency_refund(
                minor, tx.currency, tx.billing, reference, self.markup.get(tx.merchant.id, Decimal(0))
            )
            fx_id = self.ids["fx"].next()
            payout_minor, payout_currency = refund.payout_minor, tx.billing
            self.emit(
                Event(
                    "fx.applied",
                    "transaction",
                    tx.id,
                    iso(resolved),
                    {
                        "fx_id": fx_id,
                        "refund_id": refund_id,
                        "kind": "refund",
                        "from_currency": tx.currency,
                        "to_currency": tx.billing,
                        "applied_rate": str(refund.applied_rate),
                    },
                    "synthetic",
                )
            )
        tx.refunded_minor += minor
        tx.last_resolved = resolved
        kind = "payment.refunded" if tx.refunded_minor == tx.amount_minor else "payment.partially_refunded"
        self.emit(
            Event(
                kind,
                "refund",
                refund_id,
                iso(resolved),
                {
                    "refund_id": refund_id,
                    "transaction_id": tx.id,
                    "requested_amount_minor": minor,
                    "requested_currency": tx.currency,
                    "payout_amount_minor": payout_minor,
                    "payout_currency": payout_currency,
                    "fx_id": fx_id,
                    "reason": reason,
                },
                self.origin,
            )
        )

    def _late_requests(self) -> None:
        rng = substream(self.cfg.seed, "late_refunds")
        for tx in self.txs.values():
            u, days, reason_index = rng.random(), rng.randint(1, 30), rng.randrange(len(LATE_REASONS))
            if tx.captured is None or tx.has_refund or u >= LATE_REFUND_REQUEST_SHARE:
                continue
            requested = tx.captured.replace(second=0) + timedelta(days=tx.merchant.refund_window_days + days)
            if requested + timedelta(hours=2) > self.end:
                continue
            refund_id = self.ids["refund"].next()
            tx.has_refund = True
            self.stats["late_rejected"] += 1
            self.emit(
                Event(
                    "refund.requested",
                    "refund",
                    refund_id,
                    iso(requested),
                    {
                        "transaction_id": tx.id,
                        "requested_amount_minor": tx.amount_minor,
                        "requested_currency": tx.currency,
                        "reason": LATE_REASONS[reason_index],
                    },
                    "synthetic",
                )
            )
            self._reject(
                refund_id, tx, tx.amount_minor, LATE_REASONS[reason_index], requested + timedelta(hours=2), "synthetic"
            )

    def _chargebacks(self) -> None:
        rng = substream(self.cfg.seed, "chargebacks")
        rates = {spec.id: gaps.draw_chargeback_rate(rng) for spec in MERCHANTS}
        quiet = scenarios.quiet_chargeback_windows(self.cfg)
        for tx in self.txs.values():
            if tx.captured is None or tx.has_refund:
                continue
            if Decimal(str(rng.random() * 100)) >= rates[tx.merchant.id]:
                continue
            plan = gaps.plan_chargeback(rng, tx.captured, self.end)
            if plan is None:
                continue
            if any(m == tx.merchant.id and a <= plan.opened_at.date() <= b for m, a, b in quiet):
                continue
            cb_id = self.ids["chargeback"].next()
            reason = gaps.draw_reason(rng)
            for stage, when in plan.steps:
                if stage == "opened":
                    event = Event(
                        "chargeback.opened",
                        "chargeback",
                        cb_id,
                        iso(when),
                        {
                            "chargeback_id": cb_id,
                            "transaction_id": tx.id,
                            "amount_minor": tx.amount_minor,
                            "currency": tx.currency,
                            "reason_code": reason,
                            "deadline": plan.deadline.isoformat(),
                        },
                        "synthetic",
                    )
                else:
                    event = Event(
                        f"chargeback.{stage}", "chargeback", cb_id, iso(when), {"chargeback_id": cb_id}, "synthetic"
                    )
                self.emit(event)


# -- 6. settlements ---------------------------------------------------------------------------------


def settlement_events(conn: sqlite3.Connection, cfg: SimConfig) -> list[Event]:
    """Weekly Monday-to-Sunday settlements per merchant, closed before `cfg.end`, read from the tables.

    Only payments in the merchant's settlement currency count; a payment presented in another
    currency is settled outside the weekly flow. Fees are 2.9 percent of gross plus 15.00 per
    chargeback opened in the period. The payout is two business days after the period end.
    """
    overrides = scenarios.settlement_overrides(cfg)
    ids = IdSeq("ST", RESERVED_IDS["settlements"])
    end_dt = datetime.combine(cfg.end, time(23, 59, 59))
    rows: list[tuple[str, str, str, str, gaps.SettlementAmounts]] = []
    for merchant_id, currency in conn.execute("SELECT id, settlement_currency FROM merchants ORDER BY id").fetchall():
        (first,) = conn.execute(
            "SELECT min(captured_at) FROM transactions WHERE merchant_id = ?", (merchant_id,)
        ).fetchone()
        if first is None:
            continue
        start, _ = gaps.period_bounds(date.fromisoformat(first[:10]))
        while start + timedelta(days=6) < cfg.end:
            end = start + timedelta(days=6)
            window = (start.isoformat(), end.isoformat())
            (gross,) = conn.execute(
                "SELECT coalesce(sum(amount_minor), 0) FROM transactions WHERE merchant_id = ? AND currency = ?"
                " AND captured_at IS NOT NULL AND substr(captured_at, 1, 10) BETWEEN ? AND ?",
                (merchant_id, currency, *window),
            ).fetchone()
            (refunds,) = conn.execute(
                "SELECT coalesce(sum(r.requested_amount_minor), 0) FROM refunds r JOIN transactions t ON t.id = r.transaction_id"  # noqa: E501
                " WHERE t.merchant_id = ? AND t.currency = ? AND r.status = 'paid' AND substr(r.resolved_at, 1, 10) BETWEEN ? AND ?",  # noqa: E501
                (merchant_id, currency, *window),
            ).fetchone()
            (opened,) = conn.execute(
                "SELECT count(*) FROM chargebacks c JOIN transactions t ON t.id = c.transaction_id"
                " WHERE t.merchant_id = ? AND t.currency = ? AND substr(c.opened_at, 1, 10) BETWEEN ? AND ?",
                (merchant_id, currency, *window),
            ).fetchone()
            if gross or refunds or opened:
                rows.append(
                    (window[0], merchant_id, window[1], currency, gaps.settlement_amounts(gross, refunds, opened))
                )
            start += timedelta(days=7)
    events: list[Event] = []
    for period_start, merchant_id, period_end, currency, amounts in sorted(rows):
        forced = overrides.get((merchant_id, period_start))
        settlement_id = forced or ids.next()
        origin = "scenario:S08" if forced else "synthetic"
        pay_day = payout_date(date.fromisoformat(period_end), currency)
        events.append(
            Event(
                "settlement.settled",
                "settlement",
                settlement_id,
                iso(datetime.combine(date.fromisoformat(period_end) + timedelta(days=1), time(6))),
                {
                    "settlement_id": settlement_id,
                    "merchant_id": merchant_id,
                    "period_start": period_start,
                    "period_end": period_end,
                    "currency": currency,
                    "gross_minor": amounts.gross_minor,
                    "refunds_minor": amounts.refunds_minor,
                    "fees_minor": amounts.fees_minor,
                    "net_minor": amounts.net_minor,
                    "expected_payout_date": pay_day.isoformat(),
                },
                origin,
            )
        )
        paid_at = datetime.combine(pay_day, time(6))
        if paid_at <= end_dt:
            events.append(
                Event(
                    "payout.paid",
                    "settlement",
                    settlement_id,
                    iso(paid_at),
                    {"settlement_id": settlement_id, "paid_at": iso(paid_at)},
                    origin,
                )
            )
    return events


# -- 7. build ---------------------------------------------------------------------------------------


def _load_bins(cfg: SimConfig) -> dict[str, Any]:
    path = Path(cfg.bins_path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_ledger(cfg: SimConfig, db_path: Path | None = None) -> BuildResult:
    """Run every step and return the open database, the manifest and the selected invoices."""
    cfg.validate()
    fx = FxTable.from_file(Path(cfg.fx_path))
    source, used = open_source(cfg)
    invoices = list(source.iter_invoices())
    sel = select_invoices(invoices, cfg)

    natural = _Natural(cfg, fx, sel, used, _load_bins(cfg))
    natural_events = natural.build()
    ctx = scenarios.ScenarioContext(cfg, fx, natural.specs, natural.markup)
    scenario_events = scenarios.inject(ctx)

    conn = create_database(db_path if db_path is not None else ":memory:")
    projector = Projector(conn, strict=True)
    projector.ingest(natural_events)
    projector.ingest(scenario_events)
    projector.ingest(settlement_events(conn, cfg))

    manifest = _manifest(conn, cfg, used, source, sel, natural, ctx)
    return BuildResult(conn, manifest, used, sel.invoices, events=manifest["counts"]["events"])


def _count(conn: sqlite3.Connection, sql: str) -> int:
    return conn.execute(sql).fetchone()[0]


def _manifest(
    conn: sqlite3.Connection,
    cfg: SimConfig,
    used: str,
    source: InvoiceSource,
    sel: Selection,
    natural: _Natural,
    ctx: scenarios.ScenarioContext,
) -> dict[str, Any]:
    transactions = _count(conn, "SELECT count(*) FROM transactions")
    charges = _count(conn, "SELECT count(*) FROM fx_applied WHERE kind = 'charge'")
    transform: dict[str, Any] = {
        "time_shift_days": sel.shift_days,
        "presentment_share": round(charges / transactions, 4) if transactions else 0.0,
        "max_transactions": cfg.max_transactions,
        "br_reassign_share": BR_REASSIGN_SHARE,
        "failed_payment_share": FAILED_PAYMENT_SHARE,
        "late_refund_request_share": LATE_REFUND_REQUEST_SHARE,
        "merchant_rule": "sha256 of the first stock code of the invoice, modulo 24",
        "linking_rule": "latest earlier sale of the same customer that shares a stock code; refund is min(cancellation, sale)",  # noqa: E501
        "service_stock_codes": sorted(SERVICE_STOCK_CODES),
        "selection": sel.stats,
        "natural": dict(natural.stats),
    }
    meta = getattr(source, "meta", None)
    if used == "sample" and meta:
        # The sample was selected and shifted from the public file: report that selection and shift,
        # so a run from the sample gives the same manifest as the public run, except `source`.
        transform["time_shift_days"] = meta.get("time_shift_days", 0) + sel.shift_days
        if "selection" in meta:
            transform["selection"] = meta["selection"]
        transform["sample_meta"] = meta
    merchant_truth = {merchant_id: {"fx_markup_pct": str(pct)} for merchant_id, pct in sorted(natural.markup.items())}
    return {
        "schema_version": "1",
        "seed": cfg.seed,
        "end": cfg.end.isoformat(),
        "days": cfg.days,
        "source": used,
        "transform": transform,
        "counts": {
            "events": _count(conn, "SELECT count(*) FROM events"),
            "transactions": transactions,
            "public_origin_transactions": _count(conn, "SELECT count(*) FROM transactions WHERE origin = 'public'"),
            "customers": _count(conn, "SELECT count(*) FROM customers"),
            "merchants": _count(conn, "SELECT count(*) FROM merchants"),
            "refunds": _count(conn, "SELECT count(*) FROM refunds"),
            "chargebacks": _count(conn, "SELECT count(*) FROM chargebacks"),
            "settlements": _count(conn, "SELECT count(*) FROM settlements"),
        },
        "db_canonical_sha256": canonical_hash(conn),
        "merchant_truth": merchant_truth,
        "reserved_ids": {key: list(values) for key, values in RESERVED_IDS.items()} | {"absent": list(ABSENT_IDS)},
        "scenarios": scenarios.manifest_entries(conn, ctx),
    }


def write_manifest(manifest: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


__all__ = [
    "BuildResult",
    "IdSeq",
    "Selection",
    "SourceUnavailable",
    "build_ledger",
    "open_source",
    "select_invoices",
    "settlement_events",
    "write_manifest",
]
