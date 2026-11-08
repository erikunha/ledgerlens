"""Adapter for UCI Online Retail II (CC BY 4.0): lines become invoices, cancellations become refunds.

The public file has one row per invoice line. This adapter

1. aggregates the lines of an invoice into one `SourceInvoice` (sum of quantity x price, GBP),
2. drops service lines (postage, manual adjustments, bank charges and similar) by stock code,
3. drops invoices without a customer and sales whose total is not positive,
4. flags cancellations (invoice number starting with "C", negative total).

`link_cancellations` then ties each cancellation to the latest earlier sale of the same customer
that shares a stock code. The refund is the smaller of the two amounts, so it is partial when the
cancellation is smaller. Cancellations that find no sale are returned, never hidden.

The distributed file is an `.xlsx` inside a zip, with two sheets that overlap for the first days of
December 2010. `ensure_csv` converts it once to a CSV next to the zip, keeping the first copy of any
invoice that appears in both sheets.
"""

from __future__ import annotations

import csv
import zipfile
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from ledgerlens.sim.sources.base import SourceInvoice

CURRENCY = "GBP"

# Stock codes that are not products. Compared in upper case.
SERVICE_STOCK_CODES = frozenset(
    {
        "POST",
        "DOT",
        "M",
        "BANK CHARGES",
        "AMAZONFEE",
        "ADJUST",
        "ADJUST2",
        "CRUK",
        "S",
        "B",
        "D",
        "C2",
        "PADS",
        "TEST001",
        "TEST002",
    }
)

CANONICAL_COLUMNS = (
    "Invoice",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "Price",
    "Customer ID",
    "Country",
)
_ALIASES = {
    "invoiceno": "Invoice",
    "invoice": "Invoice",
    "stockcode": "StockCode",
    "description": "Description",
    "quantity": "Quantity",
    "invoicedate": "InvoiceDate",
    "unitprice": "Price",
    "price": "Price",
    "customerid": "Customer ID",
    "customer id": "Customer ID",
    "country": "Country",
}


@dataclass
class UciStats:
    """What the adapter read and dropped. Counts are invoices, except `rows`."""

    rows: int = 0
    invoices: int = 0
    dropped_no_customer: int = 0
    dropped_service_only: int = 0
    dropped_non_positive: int = 0


def _canonical(header: Iterable[Any]) -> list[str]:
    names = []
    for raw in header:
        key = str(raw).strip().lower()
        if key not in _ALIASES:
            raise ValueError(f"unexpected column {raw!r} in the Online Retail II file")
        names.append(_ALIASES[key])
    missing = set(CANONICAL_COLUMNS) - set(names)
    if missing:
        raise ValueError(f"the Online Retail II file lacks columns: {', '.join(sorted(missing))}")
    return names


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return str(int(value)) if value == int(value) else str(value)
    return str(value).strip()


def _cache_path(path: Path) -> Path:
    return path.with_name(path.stem + ".rows.csv")


def ensure_csv(path: Path) -> Path:
    """Return a CSV with the canonical columns for `path` (a CSV, an xlsx, or a zip holding one).

    A CSV is returned as it is. Otherwise the file is converted once to `<name>.rows.csv` next to
    it, and the converted file is reused while it is newer than the source.
    """
    if path.suffix.lower() == ".csv":
        return path
    target = _cache_path(path)
    if target.exists() and target.stat().st_mtime >= path.stat().st_mtime:
        return target
    partial = target.with_suffix(".part")
    with partial.open("w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(CANONICAL_COLUMNS)
        if path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path) as archive:
                name = next(
                    (n for n in archive.namelist() if n.lower().endswith((".xlsx", ".csv"))),
                    None,
                )
                if name is None:
                    raise ValueError(f"{path} holds no .xlsx or .csv file")
                with archive.open(name) as member:
                    if name.lower().endswith(".csv"):
                        _copy_csv(member, writer)
                    else:
                        _copy_xlsx(member, writer)
        else:
            with path.open("rb") as member:
                _copy_xlsx(member, writer)
    partial.replace(target)
    return target


def _copy_csv(member: Any, writer: Any) -> None:
    import io

    reader = csv.reader(io.TextIOWrapper(member, encoding="utf-8", newline=""))
    order = _canonical(next(reader))
    for row in reader:
        values = dict(zip(order, row, strict=False))
        writer.writerow([values.get(col, "") for col in CANONICAL_COLUMNS])


def _copy_xlsx(member: Any, writer: Any) -> None:
    from openpyxl import load_workbook

    book = load_workbook(member, read_only=True)
    seen: set[str] = set()
    for sheet in book.worksheets:
        rows = sheet.iter_rows(values_only=True)
        order = _canonical(next(rows))
        in_this_sheet: set[str] = set()
        for row in rows:
            values = dict(zip(order, row, strict=False))
            invoice = _text(values.get("Invoice"))
            if not invoice or invoice in seen:
                continue  # blank row, or an invoice already read from an earlier sheet
            in_this_sheet.add(invoice)
            when = values.get("InvoiceDate")
            when_text = when.strftime("%Y-%m-%d %H:%M:%S") if isinstance(when, datetime) else _text(when)
            writer.writerow(
                [
                    invoice,
                    _text(values.get("StockCode")),
                    _text(values.get("Description")),
                    _text(values.get("Quantity")),
                    when_text,
                    repr(values["Price"]) if isinstance(values.get("Price"), float) else _text(values.get("Price")),
                    _text(values.get("Customer ID")),
                    _text(values.get("Country")),
                ]
            )
        seen |= in_this_sheet
    book.close()


def _parse_time(text: str) -> datetime:
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return datetime.fromisoformat(text)


@dataclass
class UciSource:
    """Reads the public file and yields one `SourceInvoice` per kept invoice, oldest first."""

    path: Path
    name: str = "public"
    stats: UciStats = field(default_factory=UciStats)

    def iter_invoices(self) -> Iterator[SourceInvoice]:
        self.stats = UciStats()
        stats = self.stats
        with ensure_csv(Path(self.path)).open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            order = _canonical(next(reader))
            head: dict[str, tuple[datetime, str, str]] = {}
            lines: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
            service_lines: set[str] = set()
            for row in reader:
                stats.rows += 1
                values = dict(zip(order, row, strict=False))
                invoice = values["Invoice"].strip()
                if invoice not in head:
                    head[invoice] = (
                        _parse_time(values["InvoiceDate"]),
                        values["Customer ID"].strip(),
                        values["Country"].strip(),
                    )
                code = values["StockCode"].strip()
                if code.upper() in SERVICE_STOCK_CODES:
                    service_lines.add(invoice)
                    continue
                lines[invoice][code] += Decimal(values["Quantity"]) * Decimal(values["Price"])
        kept: list[SourceInvoice] = []
        for invoice, (placed_at, customer, country) in head.items():
            if not customer:
                stats.dropped_no_customer += 1
                continue
            if invoice not in lines:
                stats.dropped_service_only += 1
                continue
            is_cancellation = invoice.upper().startswith("C")
            totals = lines[invoice]
            amount = sum(totals.values(), Decimal(0))
            if (amount >= 0) if is_cancellation else (amount <= 0):
                stats.dropped_non_positive += 1
                continue
            codes = tuple(code for code, _ in sorted(totals.items(), key=lambda item: (-abs(item[1]), item[0])))
            kept.append(
                SourceInvoice(
                    source_ref=invoice,
                    customer_ref=customer,
                    placed_at=placed_at,
                    amount=amount.quantize(Decimal("0.01")),
                    currency=CURRENCY,
                    country=country,
                    stock_codes=codes,
                    is_cancellation=is_cancellation,
                )
            )
        kept.sort(key=lambda inv: (inv.placed_at, inv.source_ref))
        stats.invoices = len(kept)
        yield from kept


@dataclass(frozen=True)
class Link:
    """A cancellation tied to the sale it refunds. `amount` is in the invoice currency, positive."""

    cancellation: SourceInvoice
    sale: SourceInvoice
    amount: Decimal
    partial: bool


@dataclass(frozen=True)
class LinkResult:
    links: tuple[Link, ...]
    unlinked: tuple[SourceInvoice, ...]

    @property
    def cancellations(self) -> int:
        return len(self.links) + len(self.unlinked)

    @property
    def matching_rate(self) -> float:
        return len(self.links) / self.cancellations if self.cancellations else 0.0


def link_cancellations(invoices: Iterable[SourceInvoice]) -> LinkResult:
    """Tie every cancellation to the latest earlier sale of its customer that shares a stock code.

    Only the sales present in `invoices` are candidates. Sale and cancellation compare by
    `placed_at`; a sale at the same instant is not earlier.
    """
    sales: dict[str, list[SourceInvoice]] = defaultdict(list)
    cancellations: list[SourceInvoice] = []
    for inv in invoices:
        if inv.is_cancellation:
            cancellations.append(inv)
        else:
            sales[inv.customer_ref].append(inv)
    for customer_sales in sales.values():
        customer_sales.sort(key=lambda inv: (inv.placed_at, inv.source_ref))
    links: list[Link] = []
    unlinked: list[SourceInvoice] = []
    for cancel in sorted(cancellations, key=lambda inv: (inv.placed_at, inv.source_ref)):
        wanted = set(cancel.stock_codes)
        match = next(
            (
                sale
                for sale in reversed(sales.get(cancel.customer_ref, ()))
                if sale.placed_at < cancel.placed_at and wanted & set(sale.stock_codes)
            ),
            None,
        )
        if match is None:
            unlinked.append(cancel)
            continue
        amount = min(abs(cancel.amount), match.amount)
        links.append(Link(cancel, match, amount, partial=amount < match.amount))
    return LinkResult(tuple(links), tuple(unlinked))
