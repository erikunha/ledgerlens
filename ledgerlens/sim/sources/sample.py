"""The committed sample: invoices already selected and time-shifted, one JSON object per line.

The first line is a metadata record `{"_meta": {...}}` that says what the file derives from and
what was changed (dates, currencies and merchants are changed by the simulator). Every other line
is one `SourceInvoice`. The file is derived from UCI Online Retail II (CC BY 4.0); `NOTICE`
carries the attribution.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from ledgerlens.sim.sources.base import SourceInvoice


def invoice_to_json(inv: SourceInvoice) -> dict[str, Any]:
    return {
        "source_ref": inv.source_ref,
        "customer_ref": inv.customer_ref,
        "placed_at": inv.placed_at.isoformat(sep=" "),
        "amount": str(inv.amount),
        "currency": inv.currency,
        "country": inv.country,
        "stock_codes": list(inv.stock_codes),
        "is_cancellation": inv.is_cancellation,
    }


def invoice_from_json(data: dict[str, Any]) -> SourceInvoice:
    return SourceInvoice(
        source_ref=data["source_ref"],
        customer_ref=data["customer_ref"],
        placed_at=datetime.fromisoformat(data["placed_at"]),
        amount=Decimal(data["amount"]),
        currency=data["currency"],
        country=data["country"],
        stock_codes=tuple(data["stock_codes"]),
        is_cancellation=bool(data["is_cancellation"]),
    )


def write_sample(invoices: Iterable[SourceInvoice], path: Path, meta: dict[str, Any]) -> int:
    """Write the metadata line and the invoices, oldest first. Returns the number of invoices."""
    ordered = sorted(invoices, key=lambda inv: (inv.placed_at, inv.source_ref))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({"_meta": meta}, sort_keys=True, ensure_ascii=False) + "\n")
        for inv in ordered:
            handle.write(json.dumps(invoice_to_json(inv), sort_keys=True, ensure_ascii=False) + "\n")
    return len(ordered)


@dataclass
class SampleSource:
    path: Path
    name: str = "sample"
    meta: dict[str, Any] = field(default_factory=dict)

    def iter_invoices(self) -> Iterator[SourceInvoice]:
        with Path(self.path).open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                data = json.loads(line)
                if "_meta" in data:
                    self.meta = data["_meta"]
                    continue
                yield invoice_from_json(data)
