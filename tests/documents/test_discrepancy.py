"""The disagreement of a document with the ledger: a flag with the difference, and the ledger is not corrected.

What they guarantee, and why: (a) a document that disagrees with the ledger produces a flag with the
difference computed with `Decimal`, because the difference of two amounts is money and the money of the
repository is a `Decimal`; (b) the ledger of the fixture is byte for byte the same before and after the
extraction, because the pipeline never writes to the ledger; (c) the decision of the case names the
disagreement, because a disagreement is a finding that a person has to look at (ADR-074).

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from pathlib import Path

from ledgerlens.documents.convert import read_text
from ledgerlens.documents.fields import extract_fields
from ledgerlens.documents.match import match_against_ledger
from ledgerlens.eval.dataset import build_sample_ledger

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "documents"


def _digest(path: Path) -> str:
    """The sha256 of the file, for the check that the ledger did not move."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_a_document_that_disagrees_with_the_ledger_produces_a_flag_with_the_difference(tmp_path) -> None:
    """The Brazilian receipt says 1.000,00 BRL and the ledger says 100.00: the difference is 900.00."""
    ledger = build_sample_ledger(tmp_path / "ledger.db")
    before = _digest(ledger)

    fields = extract_fields(read_text(FIXTURES / "receipt_br.txt"))
    discrepancy = match_against_ledger(fields, db_path=ledger, transaction_id="TX-2048")

    assert discrepancy is not None
    assert discrepancy.document_value == Decimal("1000.00")
    assert discrepancy.ledger_value == Decimal("100.00")
    assert discrepancy.difference == Decimal("900.00")
    assert isinstance(discrepancy.difference, Decimal)
    assert "disagreement" in discrepancy.decision
    assert _digest(ledger) == before, "the ledger moved, and the pipeline never writes to the ledger"


def test_a_document_that_agrees_with_the_ledger_produces_no_flag(tmp_path) -> None:
    """A document that says what the ledger says produces no disagreement."""
    ledger = build_sample_ledger(tmp_path / "ledger.db")
    fields = extract_fields("Receipt\nStore: Lumen Travel GmbH\nTotal: 100.00 EUR\n")

    assert match_against_ledger(fields, db_path=ledger, transaction_id="TX-2048") is None
