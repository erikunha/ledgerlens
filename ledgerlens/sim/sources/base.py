"""Neutral invoice record shared by every source of the simulator."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class SourceInvoice:
    """One invoice of a public (or sample, or synthetic) source, before any simulation.

    `amount` is the sum of quantity x unit price in `currency` (negative for a cancellation).
    `stock_codes` lists the product codes of the invoice, the line with the largest value first;
    the first code is the one that picks the simulated merchant.
    """

    source_ref: str
    customer_ref: str
    placed_at: datetime
    amount: Decimal
    currency: str
    country: str
    stock_codes: tuple[str, ...]
    is_cancellation: bool


class InvoiceSource(Protocol):
    name: str

    def iter_invoices(self) -> Iterator[SourceInvoice]: ...
