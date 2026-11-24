"""The match of a document against the ledger: the document and the ledger may disagree, and the case says so.

Why the match never writes to the ledger: the ledger states what happened, and a document states what someone
wrote down about it. A disagreement between the two is a finding that a person has to look at, and the match
never corrects the ledger. The pipeline never writes to the ledger, and no task of the milestone adds such a
write.

Why the match reads through the read-only surface: the match reads the record of the ledger through the tool
`get_ledger_record` of the repository, the same read-only surface the agent uses, and it never writes SQL of
its own, because the domain never speaks SQL.

Why the difference is computed with `Decimal`: the difference of two amounts is money, and the money of the
repository is a `Decimal`, never a float.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from ledgerlens.documents.fields import Field

__all__ = ["Discrepancy", "match_against_ledger"]


@dataclass(frozen=True)
class Discrepancy:
    """A disagreement between a document and the ledger: the field, the two amounts and the difference.

    Why the difference is a `Decimal` and the decision names the disagreement: a disagreement is a finding
    that a person has to look at, and the case ends with a named decision, exactly as ADR-074 decides for
    every other disagreement of the repository.
    """

    field: str
    document_value: Decimal
    ledger_value: Decimal
    difference: Decimal
    decision: str


def match_against_ledger(
    fields: list[Field],
    *,
    db_path: Path,
    transaction_id: str,
) -> Discrepancy | None:
    """The disagreement of the total of the document with the amount of the ledger, and None when they agree.

    Why the match reads the record of the ledger and not the document again: the document says what someone
    wrote down, and the ledger says what happened, and the match reads the two and computes the difference.
    """
    from ledgerlens.tools.ledger_api import build_get_ledger_record_tool

    total = next((field for field in fields if field.name == "total" and isinstance(field.value, Decimal)), None)
    if total is None:
        return None
    tool = build_get_ledger_record_tool(db_path=db_path)
    envelope = tool.invoke({"kind": "transaction", "id": transaction_id})
    if not envelope.get("ok"):
        return None
    data = envelope.get("data") or {}
    record = data.get("transaction") or data.get("record") or data
    amount_minor = record.get("amount_minor")
    if amount_minor is None:
        return None
    ledger_value = (Decimal(int(amount_minor)) / 100).quantize(Decimal("0.01"))
    document_value = total.value
    assert isinstance(document_value, Decimal)
    if document_value == ledger_value:
        return None
    difference = abs(document_value - ledger_value)
    return Discrepancy(
        field="total",
        document_value=document_value,
        ledger_value=ledger_value,
        difference=difference,
        decision=(
            f"the document says {document_value} and the ledger says {ledger_value}: the difference of "
            f"{difference} is a disagreement that a person has to look at, and the ledger is not corrected"
        ),
    )
