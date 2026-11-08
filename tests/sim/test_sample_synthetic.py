"""The committed sample round-trips, and the synthetic generator is seeded and links its cancellations."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from ledgerlens.sim.sources.base import SourceInvoice
from ledgerlens.sim.sources.sample import SampleSource, write_sample
from ledgerlens.sim.sources.synthetic import SyntheticSource
from ledgerlens.sim.sources.uci import UciSource, link_cancellations

MINI = Path(__file__).resolve().parents[1] / "fixtures" / "uci_mini.csv"


def test_sample_round_trips_every_field_and_the_metadata(tmp_path):
    invoices = list(UciSource(MINI).iter_invoices())
    path = tmp_path / "invoices_sample.jsonl"

    count = write_sample(invoices, path, {"derived_from": "UCI Online Retail II", "license": "CC BY 4.0"})
    source = SampleSource(path)
    back = list(source.iter_invoices())

    assert count == len(invoices) == len(back)
    assert back == invoices
    assert source.meta["license"] == "CC BY 4.0"
    assert path.read_text().splitlines()[0].startswith('{"_meta"')


def test_sample_keeps_signed_decimal_amounts(tmp_path):
    inv = SourceInvoice("C1", "1", datetime(2026, 10, 1, 9, 30), Decimal("-8.40"), "GBP", "Germany", ("A", "B"), True)
    path = tmp_path / "s.jsonl"
    write_sample([inv], path, {})
    (back,) = list(SampleSource(path).iter_invoices())
    assert back.amount == Decimal("-8.40") and back.stock_codes == ("A", "B") and back.is_cancellation


def test_synthetic_is_deterministic_and_seed_sensitive():
    a = list(SyntheticSource(seed=7, sales=200).iter_invoices())
    b = list(SyntheticSource(seed=7, sales=200).iter_invoices())
    c = list(SyntheticSource(seed=8, sales=200).iter_invoices())
    assert a == b
    assert a != c


def test_synthetic_stays_in_the_window_and_in_time_order():
    end = date(2026, 11, 7)
    invoices = list(SyntheticSource(seed=1, days=30, end=end, sales=150).iter_invoices())
    assert invoices == sorted(invoices, key=lambda inv: (inv.placed_at, inv.source_ref))
    assert all(inv.placed_at.date() <= end for inv in invoices)
    assert all(inv.placed_at.date() >= date(2026, 10, 9) for inv in invoices if not inv.is_cancellation)


def test_synthetic_cancellations_link_to_their_sales():
    invoices = list(SyntheticSource(seed=3, sales=400).iter_invoices())
    result = link_cancellations(invoices)
    assert result.cancellations > 0
    assert result.matching_rate == 1.0
    assert all(item.amount <= item.sale.amount for item in result.links)
