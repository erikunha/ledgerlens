"""Claim extraction from the answer, number parsing, and the text the NLI model gets as its premise.

Why it exists: the verifier works one claim at a time. Here the answer becomes a list of `Claim`, each with
its kind (fact, numeric, policy or inference) and the evidence ids the answer itself cites in brackets,
such as `[sql:1]` or `[sql:1, policy:2]`. A claim that states a value and is backed by a `calculate` call
becomes `numeric`: code checks it.

Not every sentence of the answer claims something. A closing offer ("If you want, I can detail..."), an
uncited hedge ("Perhaps ..."), an uncited conclusion with no numbers ("Therefore, ...") and a back reference
with no number or entity ("This explains the difference...") have nothing to check: a sentence with no id never
gets past "no evidence" and used to inflate the share that sends the case to review. They do not become claims.
A conclusion that cites evidence is still a claim, and so is one that states numbers when its paragraph cites
evidence. A sentence with no citation of its own inherits the ones that close its paragraph (only inside it,
never past a blank line or a list item) and is judged against that evidence: inheritance gives the evidence, not
the verdict. Citations that follow the period ("... [api:1]. [sql:1]. [calc:1].") belong to the sentence they
close; they are not sentences. A sentence that starts with "This payout" or "This dispute" gets the id of the
entity in the previous sentence, when that sentence cites exactly one of the same kind, so the NLI model and the
premise filter know which record it talks about.

Accepted value formats: `1,250.00`, `1250.00`, `$1,250.00`, `R$ 1,250.00`, `BRL 17.48`, `2.5%`, `5.6339`. The
comma only groups thousands; the period is the decimal point, so `1.250` is one and a quarter. The sign counts
when it touches the number (`-14.08`); in `563.39 - 549.31` the dash is arithmetic. A sentence that gives the
direction in words ("14.08 lower", "more", "less") speaks in absolute value, and `direction_in_words` lets the
check compare only the magnitude with the `calculate` result, which carries the sign.

A rate is a decimal with three places or more that is not a percentage (`5.4931`, `5.6339 BRL per EUR`):
`check_rates_against_ledger` checks it, and the other numbers of the sentence, against the exact numbers of the
cited ledger or FX evidence.

`ledger_values` reads the numbers of a ledger evidence (with the column, whether it is money and the row's
currency) and `check_amounts_against_ledger` checks the values a sentence states against them: exact equality,
`_minor` divided by 100, currency respected. Spelled-out dates ("October 14, 2026") and slash dates are never
values.

`fx_dates_without_origin` finds the FX rate of a date that is neither in the turn's ledger evidence nor in the
question: the model made it up, and its rate is faithful to the tool but does not answer the case.

`render_premise` writes the content of a JSON evidence as running text, so the NLI model can compare it with a
sentence. Each query row becomes `column: value`, the SQL is left out, and the SQL equality filters
(`id = 'TX-0001'`) come in as columns, because a one-column query (`status`) does not say whose value it is. The
evidence stored in the result is still the original JSON.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from typing import Any, NamedTuple

from ledgerlens.schemas import Claim, Evidence, InvestigationResult, NumericClaim

EVIDENCE_ID = re.compile(r"^(?:sql|api|policy|fx|calc|case):\S+$")
_BRACKET = re.compile(r"\[([^\[\]]*)\]")
# Entity ids (TX-2048, CB-0310) and dates (ISO, "11/08/2026", "October 14, 2026") are never money values.
_MONTH = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?"
    r"|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
_ENTITY_OR_DATE = re.compile(
    r"\b[A-Z]{1,3}-\d+\b|\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b"
    rf"|\b{_MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,\s*|\s+)\d{{4}}\b"
    rf"|\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?{_MONTH}\.?(?:,\s*|\s+)\d{{4}}\b",
    re.IGNORECASE,
)
# The sign counts only when it touches the number (or the currency symbol): "563.39 - 549.31" is arithmetic.
_AMOUNT = re.compile(
    r"(?<![\w.,])(?P<sign>[-\u2212])?(?:(?P<pre>R\$|US\$|\$|€|£)\s?|(?P<code>[A-Z]{3})\s)?(?P<sign2>[-\u2212])?"
    r"(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?:\s?(?P<post>%|[A-Z]{3}\b))?"
)
_SYMBOLS = {"R$": "BRL", "US$": "USD", "$": "USD", "€": "EUR", "£": "GBP"}
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


class Amount(NamedTuple):
    value: Decimal  # with the sign, when the text puts it next to the number
    unit: str  # currency code, "%" or "" when the text does not say


def _to_decimal(raw: str) -> Decimal:
    # the comma only groups thousands; the period is the decimal point
    return Decimal(raw.replace(",", ""))


def find_amounts(text: str) -> list[Amount]:
    """The values in the text, in order of appearance, not counting ids or dates."""
    cleaned = _ENTITY_OR_DATE.sub(" ", text)
    found: list[Amount] = []
    for match in _AMOUNT.finditer(cleaned):
        try:
            value = _to_decimal(match["num"])
        except InvalidOperation:
            continue
        unit = _SYMBOLS.get(match["pre"] or "") or match["code"] or match["post"] or ""
        found.append(Amount(-value if match["sign"] or match["sign2"] else value, unit))
    return found


# Direction given in words: the text speaks in absolute value ("14.08 lower") and `calculate` carries the sign (-14.08).
_LOWER = re.compile(r"\b(?:lower|less|below|smaller|fewer|under)\b", re.IGNORECASE)
_HIGHER = re.compile(r"\b(?:higher|more|above|larger|greater|over)\b", re.IGNORECASE)


def direction_in_words(text: str) -> int:
    """-1 if the sentence says the value is lower, +1 if it says higher, 0 if it says neither or both."""
    return bool(_HIGHER.search(text)) - bool(_LOWER.search(text))


def amounts_match(amount: Decimal, value: Decimal, tolerance: Decimal, direction: int = 0) -> bool:
    """The stated value matches `value`: equal with the sign, or equal in absolute value when the sentence gives the
    direction in words.

    With "lower" or "more" in the sentence the sign says nothing: which operand `calculate` subtracted first does not
    show in the text. With no direction word, a flipped sign does not match: that is the error the verifier must find.
    """
    if direction:
        return abs(abs(amount) - abs(value)) <= tolerance
    return abs(amount - value) <= tolerance


def calc_values(content: str) -> list[Decimal]:
    """The numbers a `calculate` call produced (one, or several for `fx_gap_breakdown`)."""
    try:
        data = json.loads(content)
    except ValueError:
        return [a.value for a in find_amounts(content)]
    if isinstance(data, dict) and "result" not in data and isinstance(data.get("data"), dict):
        data = data["data"]
    result = data.get("result") if isinstance(data, dict) else None
    raw = list(result.values()) if isinstance(result, dict) else [result] if result is not None else []
    values: list[Decimal] = []
    for item in raw:
        try:
            values.append(Decimal(str(item)))
        except InvalidOperation:
            continue
    return values


def calc_operands(content: str) -> list[Decimal]:
    """The numbers that went into the calculation (the `calculate` `formula`), with their sign."""
    try:
        data = json.loads(content)
    except ValueError:
        return []
    if isinstance(data, dict) and "formula" not in data and isinstance(data.get("data"), dict):
        data = data["data"]
    formula = data.get("formula") if isinstance(data, dict) else None
    return [a.value for a in find_amounts(formula)] if isinstance(formula, str) else []


_PLAIN_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


class LedgerValue(NamedTuple):
    """A number from a ledger evidence, in major units."""

    value: Decimal
    column: str  # the column name without `_minor` or `_major`: `fees`, `gross`, `payout_amount`
    money: bool  # only `_minor` and `_major` columns are money; `refund_window_days` and `rate` are not
    currency: str  # the row's currency, or "" when the row does not carry one


def _currency_of(stem: str, row: dict[str, Any]) -> str:
    """The currency of a value column: the one of its own prefix (`payout_currency`), else the row's."""
    for key in (f"{stem.removesuffix('_amount')}_currency", "currency", "settlement_currency"):
        code = row.get(key)
        if isinstance(code, str) and len(code) == 3:
            return code
    return ""


def ledger_values(content: str) -> list[LedgerValue]:
    """The numbers of a JSON ledger evidence, each with its column, whether it is money and the row's currency.

    A `_minor` column comes in divided by 100, never raw. Text that is not JSON has no columns: empty list.
    """
    try:
        data = json.loads(content)
    except ValueError:
        return []
    found: list[LedgerValue] = []

    def leaf(value: Any, key: str, row: dict[str, Any]) -> None:
        if isinstance(value, bool) or value is None:
            return
        if isinstance(value, (int, float)):
            number = Decimal(str(value))
        elif isinstance(value, str) and _PLAIN_NUMBER.fullmatch(value.strip()):
            number = Decimal(value.strip())
        else:
            return
        money = key.endswith(("_minor", "_major"))
        stem = key.removesuffix("_minor").removesuffix("_major")
        found.append(
            LedgerValue(
                number / 100 if key.endswith("_minor") else number,
                stem,
                money,
                _currency_of(stem, row) if money else "",
            )
        )

    def walk(node: Any, key: str = "", row: dict[str, Any] | None = None) -> None:
        if isinstance(node, dict):
            columns, rows = node.get("columns"), node.get("rows")
            if isinstance(columns, list) and isinstance(rows, list) and all(isinstance(r, list) for r in rows):
                for values in rows:
                    record = dict(zip(columns, values, strict=False))
                    for column, value in record.items():
                        leaf(value, str(column), record)
                return
            for name, value in node.items():
                walk(value, name, node)
        elif isinstance(node, list):
            for item in node:
                walk(item, key, row)
        else:
            leaf(node, key, row or {})

    walk(data)
    return found


def evidence_values(content: str) -> list[Decimal]:
    """The numeric values of a ledger evidence, in major units.

    A `_minor` column comes in divided by 100, never raw: "54,931.00" is not the ledger's `54931`. Text that is not
    JSON comes in through the values `find_amounts` reads.
    """
    try:
        json.loads(content)
    except ValueError:
        return [a.value for a in find_amounts(content)]
    return [v.value for v in ledger_values(content)]


# Words that say which column the sentence talks about; a column with no entry counts by its own name
# ("requested amount").
_COLUMN_WORDS = {
    "gross": r"\bgross\b",
    "refunds": r"\brefund(?:s|ed)?\b",
    "fees": r"\bfees?\b",
    "net": r"\bnet\b",
}


def _names_column(text: str, column: str) -> bool:
    pattern = _COLUMN_WORDS.get(column) or rf"\b{re.escape(column.replace('_', ' '))}\b"
    return re.search(pattern, text, re.IGNORECASE) is not None


# Decimal places from which a number is a rate (`5.4931`), not a money value (`2.90`).
RATE_PLACES = 3


def _is_rate(amount: Amount) -> bool:
    """A rate may come with the currency ("5.6339 BRL per EUR"), and is never a percentage."""
    return amount.unit != "%" and amount.value.as_tuple().exponent <= -RATE_PLACES  # type: ignore[operator]


def has_rate(text: str) -> bool:
    """Does the sentence state a rate, a decimal with three places or more that is not a percentage?"""
    return any(_is_rate(a) for a in find_amounts(text))


def _is_ledger_value(amount: Amount, value: LedgerValue) -> bool:
    """Equal, with no tolerance. A value with a currency only matches money of the same currency (or of no currency).

    A rate matches any equal ledger number: `applied_rate` and `rate` are not money.
    """
    if amount.value != value.value:
        return False
    return (
        amount.unit == ""
        or _is_rate(amount)
        or (amount.unit != "%" and value.money and value.currency in ("", amount.unit))
    )


def has_currency_amount(text: str) -> bool:
    """Does the sentence state a value with a currency (`BRL 926.67`, `100 EUR`)? Percentages, rates and bare numbers
    do not count."""
    return any(a.unit not in ("", "%") and not _is_rate(a) for a in find_amounts(text))


def check_rates_against_ledger(text: str, values: list[Decimal]) -> tuple[str, str] | None:
    """Checks the rates the sentence states, and its other numbers, against the cited ledger or FX numbers.

    `values` comes from `evidence_values`: exact equality, `_minor` divided by 100. `supported` when every stated
    number is exactly one of them. `not_enough_evidence` when some rate is none of them: a number never goes to the
    NLI model to be approved by resemblance. `None` when the rates match but another number of the sentence (a count,
    a percentage) cannot be confirmed by code: the NLI model judges the sentence as before.
    """
    unmatched = [a for a in find_amounts(text) if a.unit == "%" or a.value not in values]
    if not unmatched:
        return "supported", "Every stated number is a value of the cited ledger or FX evidence."
    if any(_is_rate(a) for a in unmatched):
        return "not_enough_evidence", f"No cited ledger value is: {', '.join(str(a.value) for a in unmatched)}."
    return None


def check_amounts_against_ledger(text: str, values: list[LedgerValue]) -> tuple[str, str]:
    """Checks the values stated in the sentence against the numbers of the cited ledger evidence: `(label, note)`.

    `supported` when every stated value is exactly a ledger number (in the stated currency). `contradicted` only in
    the clear pair: a single stated value, the sentence names a single money column and that column holds a single,
    different value. The other cases are `not_enough_evidence`.
    """
    stated = find_amounts(text)
    unmatched = [a for a in stated if not any(_is_ledger_value(a, v) for v in values)]
    if not unmatched:
        return "supported", "Every stated value is a value of the cited ledger evidence."
    if len(stated) == 1:  # the caller guarantees a currency value, so this one is not a percentage
        [amount] = stated
        named = {v.column for v in values if v.money and _names_column(text, v.column)}
        if len(named) == 1:
            [column] = named
            same = {
                v.value
                for v in values
                if v.column == column and v.money and (amount.unit == "" or v.currency in ("", amount.unit))
            }
            if len(same) == 1:
                return "contradicted", f"Stated value {amount.value} differs from the ledger {column}: {same.pop()}."
    return "not_enough_evidence", f"No cited ledger value is: {', '.join(str(a.value) for a in unmatched)}."


def _citations(sentence: str) -> tuple[str, list[str]]:
    """Splits the text from the `[id, id]` citations. Brackets that are not ids stay in the text."""
    ids: list[str] = []

    def take(match: re.Match[str]) -> str:
        parts = [p.strip() for p in match[1].split(",") if p.strip()]
        if parts and all(EVIDENCE_ID.match(p) for p in parts):
            ids.extend(p for p in parts if p not in ids)
            return ""
        return match[0]

    text = _BRACKET.sub(take, sentence)
    text = re.sub(r"\s+([.,;!?])", r"\1", re.sub(r"\s+", " ", text)).strip()
    return text, ids


# One or more citations after the period ("... paid. [sql:1]" or "... paid [api:1]. [sql:1]. [calc:1].")
# belong to the sentence before them; they are not sentences: each one alone has fewer than three words and the
# paragraph used to close only with the last one.
_CITATION = r"\[(?:sql|api|policy|fx|calc|case):[^\[\]]*\]"
_TRAILING_CITATION = re.compile(rf"([.!?])((?:\s+{_CITATION}[.!?]?(?=\s|$))+)")


def _attach_trailing_citations(answer: str) -> str:
    """Puts the citations that follow a period back inside the sentence, before its period."""
    return _TRAILING_CITATION.sub(lambda m: " " + " ".join(re.findall(_CITATION, m[2])) + m[1], answer)


def _paragraphs(answer: str) -> Iterable[list[str]]:
    """The answer's sentences, grouped by paragraph: a blank line or a list marker closes the group."""
    answer = _attach_trailing_citations(answer)
    group: list[str] = []
    for line in answer.splitlines():
        starts_item = bool(_BULLET.match(line))
        line = _BULLET.sub("", line).strip()
        if (not line or starts_item) and group:
            yield group
            group = []
        if line:
            group.extend(_SENTENCE_END.split(line))
    if group:
        yield group


# Closing offer: says nothing about the case, whatever it cites.
_OFFER = re.compile(
    r"^(?:if\s+(?:you\s+)?(?:want|need|like|wish|prefer)\b|if\s+you\s+(?:would|'d)\s+like\b|should\s+you\s+need\b"
    r"|let\s+me\s+know|i\s+can\s+\w|i\s+could\s+\w|feel\s+free\b|(?:do\s+not|don't)\s+hesitate"
    r"|i\s+am\s+available|i'm\s+available|please\s+(?:contact|reach\s+out)|would\s+you\s+like\b"
    r"|(?:do|would)\s+you\s+want\s+me\b)",
    re.IGNORECASE,
)
# Conclusion with no citation of its own: repeats what the other sentences claim, unless it states values
# (`_is_not_a_claim`).
_CONCLUSION = re.compile(
    r"^(?:therefore|thus|hence|so,|in\s+summary|to\s+summarize|in\s+short|in\s+sum|to\s+conclude|in\s+conclusion"
    r"|in\s+other\s+words|this\s+way|that\s+way|that\s+is\s+why|this\s+is\s+why|for\s+this\s+reason)\b",
    re.IGNORECASE,
)
# Uncited hedge: claims nothing, not even when it states a value ("Perhaps the amount was 549.31").
_HEDGE = re.compile(
    r"^(?:perhaps|maybe|possibly|probably|apparently"
    r"|it\s+may\s+be\s+that\b|it\s+is\s+possible\s+that|it\s+is\s+not\s+possible\s+to\s+(?:say|conclude|determine)"
    r"|there\s+is\s+no\s+way\s+to\s+(?:say|know|tell))",
    re.IGNORECASE,
)
# Back reference to what was already said ("This explains the difference..."): a claim only with a value or entity.
_REFERS_BACK = re.compile(
    r"^(?:(?:this|that|(?:this|that)\s+fact)\s+(?:also\s+|further\s+)?"
    r"(?:explains|shows|indicates|demonstrates|confirms|means|suggests|justifies|illustrates|reveals|clarifies))\b",
    re.IGNORECASE,
)
# Demonstrative at the start of the sentence and the id kind its noun asks for.
_DEMONSTRATIVE = re.compile(
    r"^(?P<head>(?:this|that|the\s+same)\s+(?P<noun>payout|settlement|refund|transaction|payment|charge"
    r"|dispute|chargeback|merchant|customer))\b",
    re.IGNORECASE,
)
_ID_KIND = {
    "payout": "ST",
    "settlement": "ST",
    "refund": "R",
    "transaction": "TX",
    "payment": "TX",
    "charge": "TX",
    "dispute": "CB",
    "chargeback": "CB",
    "merchant": "M",
    "customer": "C",
}


def _is_not_a_claim(text: str, own_ids: list[str], closing_ids: list[str]) -> bool:
    """The sentence claims nothing that can be checked.

    Offers, uncited hedges and back references with no value or entity ("This explains the difference...") are left
    out. So is a conclusion with no citation of its own, unless it states values and the paragraph cites evidence to
    check them: it inherits that evidence and its numbers are checked by code.
    """
    if _OFFER.match(text):
        return True
    if _REFERS_BACK.match(text) and not find_amounts(text) and not _ENTITY_ID.search(text):
        return True
    if own_ids:
        return False
    if _HEDGE.match(text):
        return True
    return bool(_CONCLUSION.match(text)) and not (closing_ids and find_amounts(text))


def _resolve_demonstrative(text: str, previous: str) -> str:
    """Adds the id of the previous sentence to "This payout ...", when that sentence cites a single id of that kind."""
    match = _DEMONSTRATIVE.match(text)
    if match is None:
        return text
    kind = _ID_KIND[match["noun"].lower()]
    found = set(re.findall(rf"\b{kind}-\d+\b", previous))
    if len(found) != 1 or next(iter(found)) in text:
        return text
    return f"{match['head']} ({next(iter(found))}){text[match.end() :]}"


def _numeric_block(
    text: str, ids: list[str], by_id: dict[str, Evidence], *, exact_only: bool = False
) -> NumericClaim | None:
    amounts = find_amounts(text)
    direction = direction_in_words(text)
    best: tuple[Decimal, Amount, Decimal, str] | None = None
    for evidence_id in ids:
        evidence = by_id.get(evidence_id)
        if evidence is None or evidence.source_type != "calc":
            continue
        for value in calc_values(evidence.content):
            for amount in amounts:
                gap = (
                    Decimal(0)
                    if amounts_match(amount.value, value, Decimal(0), direction)
                    else abs(value - amount.value)
                )
                if best is None or gap < best[0]:
                    best = (gap, amount, value, evidence_id)
    if best is None or (exact_only and best[0] != 0):
        return None  # inherited ids: a value the calculation did not produce goes to the NLI model, not to code
    _, amount, value, evidence_id = best
    return NumericClaim(expected=value, unit=amount.unit, calc_evidence_id=evidence_id)


def _with_paragraph_citations(answer: str) -> Iterable[tuple[str, list[str]]]:
    """Each sentence with the ids that close its paragraph, so a sentence with no citation of its own inherits them.

    Only the citation of the paragraph's last sentence counts; a sentence that has its own inherits nothing.
    """
    for group in _paragraphs(answer):
        closing = _citations(group[-1])[1]
        for sentence in group:
            yield sentence, closing


def extract_claims(answer: str, evidence: list[Evidence]) -> list[Claim]:
    """One `Claim` per assertive sentence of the answer, with the ids `CL1`, `CL2`, ..."""
    by_id = {e.id: e for e in evidence}
    claims: list[Claim] = []
    previous = ""
    for sentence, ids in _with_paragraph_citations(answer):
        text, own_ids = _citations(sentence)
        if text.endswith("?") or len(text.split()) < 3:
            continue  # a question or a fragment ("Ok.", "Thanks!") claims nothing
        if text[-1] not in ".!":
            text += "."
        if _is_not_a_claim(text, own_ids, ids):
            continue  # decided by the sentence's own citation; inheritance only matters for sentences with values
        inherited = not own_ids and bool(ids)
        ids = own_ids or ids
        text = _resolve_demonstrative(text, previous)
        previous = text
        numeric = _numeric_block(text, ids, by_id, exact_only=inherited)
        if numeric is not None:
            kind = "numeric"
        elif any(i.startswith("policy:") for i in ids):
            kind = "policy"
        elif ids:
            kind = "fact"
        else:
            kind = "inference"
        claims.append(Claim(id=f"CL{len(claims) + 1}", text=text, kind=kind, evidence_ids=ids, numeric=numeric))
    return claims


# ---- NLI premise ------------------------------------------------------------------------------------

_WHERE = re.compile(r"\bWHERE\b(.*)", re.IGNORECASE | re.DOTALL)
_NOT_A_PLAIN_FILTER = re.compile(r"\b(?:OR|NOT)\b|\(\s*SELECT\b", re.IGNORECASE)
_EQUALS_LITERAL = re.compile(r"(\w+)\s*=\s*'([^']*)'")
# Size from which the premise does not fit the model's 512 tokens (about 3 characters per token in tables).
FOCUS_PREMISE_CHARS = 1500
_ENTITY_ID = re.compile(r"\b[A-Z]{1,3}-\d+\b")
_NOT_FOUND = "The record was not found and does not exist in the ledger."


def _filters(sql: object) -> dict[str, str]:
    """The `column = 'value'` equalities that hold for every row of the query, in order of appearance.

    With `OR`, `NOT` or a subquery in the filter, or with the same column compared to two values, nothing holds
    for every row and the column is left out.
    """
    where = _WHERE.search(sql) if isinstance(sql, str) else None
    if where is None or _NOT_A_PLAIN_FILTER.search(where[1]):
        return {}
    found: dict[str, str | None] = {}
    for column, value in _EQUALS_LITERAL.findall(where[1]):
        found[column] = value if found.get(column, value) == value else None
    return {column: value for column, value in found.items() if value is not None}


def _show(value: Any) -> str:
    if isinstance(value, (dict, list, bool)) or value is None:
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _line(row: dict[str, Any]) -> str:
    return "; ".join(f"{key}: {_show(value)}" for key, value in row.items()) + "."


def _table(data: dict[str, Any]) -> str | None:
    columns, rows = data["columns"], data["rows"]
    if not isinstance(columns, list) or not isinstance(rows, list) or not all(isinstance(r, list) for r in rows):
        return None
    filters = _filters(data.get("sql"))
    if not rows:
        where = " and ".join(f"{column} = {value}" for column, value in filters.items())
        return f"Zero rows found{' where ' + where if where else ''} (row_count: 0). {_NOT_FOUND}"
    known = {column: value for column, value in filters.items() if column not in columns}
    return "\n".join(_line({**known, **dict(zip(columns, row, strict=False))}) for row in rows)


def _sections(data: dict[str, Any]) -> str | None:
    """A record with parts (`transaction`, `refunds`, ...): the loose fields on one line and one line per part."""
    scalars = {k: v for k, v in data.items() if not isinstance(v, (dict, list))}
    parts = {k: v for k, v in data.items() if isinstance(v, (dict, list))}
    if not parts or not all(isinstance(v, dict) or all(isinstance(i, dict) for i in v) for v in parts.values()):
        return None
    lines = [_line(scalars)] if scalars else []
    for name, part in parts.items():
        items = [part] if isinstance(part, dict) else part
        lines += [f"{name}: {_line(item)}" for item in items if item] or [f"{name}: none."]
    return "\n".join(lines)


def _rate(data: dict[str, Any]) -> str:
    sentence = (
        f"Reference rate from {data['from_currency']} to {data['to_currency']} on {data.get('requested_date', '')} "
        f"(rate date {data.get('rate_date', '')}, source {data.get('source', '')}): {data['rate']}."
    )
    return f"{sentence} {data['note']}" if data.get("note") else sentence


def _calculation(data: dict[str, Any]) -> str:
    result = data["result"]
    shown = ", ".join(f"{k} {v}" for k, v in result.items()) if isinstance(result, dict) else str(result)
    formula = f" Formula: {data['formula']}." if data.get("formula") else ""
    return f"Calculation {data['operation']}: result {shown}.{formula}"


def _case(data: dict[str, Any]) -> str:
    details = f"{data.get('kind', '')}, {str(data.get('created_at', ''))[:10]}, confidence {data.get('confidence', '')}"
    return f"Case {data['case_id']} ({details}): {data['finding']}"


def render_premise(content: str) -> str:
    """The content of an evidence as text for the NLI model. Anything with no known format passes as it came."""
    try:
        data = json.loads(content)
    except ValueError:
        return content
    if not isinstance(data, dict):
        return content
    text: str | None
    if "columns" in data and "rows" in data:
        text = _table(data)
    elif "chunk_id" in data and isinstance(data.get("text"), str):
        text = data["text"]
    elif {"from_currency", "to_currency", "rate"} <= data.keys():
        text = _rate(data)
    elif {"operation", "result"} <= data.keys():
        text = _calculation(data)
    elif {"case_id", "finding"} <= data.keys():
        text = _case(data)
    else:
        text = _sections(data)
    return content if text is None else text


def focus_premise(premise: str, claim_text: str, limit: int = FOCUS_PREMISE_CHARS) -> str:
    """In a premise longer than `limit`, only the lines that cite the most ids of the claim (`ST-0044`, `M-03`).

    The NLI model reads only the start of the premise and, with many similar lines (a merchant's payouts), calls a
    true claim "contradicted" because the other lines say something else. With no id in the claim, or no line
    citing one, the premise stays whole.
    """
    ids = set(_ENTITY_ID.findall(claim_text))
    if len(premise) <= limit or not ids:
        return premise
    lines = premise.splitlines()
    hits = [len(ids & set(_ENTITY_ID.findall(line))) for line in lines]
    best = max(hits)
    if best == 0:
        return premise
    return "\n".join(line for line, count in zip(lines, hits, strict=True) if count == best)


# ---- FX date ---------------------------------------------------------------------------------------

_ISO_DAY = re.compile(r"(\d{4}-\d{2}-\d{2})(?:[T ]\S*)?")
_QUESTION_DAY = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b|\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_LEDGER_SOURCES = ("sql", "ledger_api")


def _days_in_question(question: str) -> set[str]:
    """The days the user wrote, in ISO or `mm/dd/yyyy`. Spelled-out dates do not count."""
    days = set()
    for iso_y, iso_m, iso_d, m, d, y in _QUESTION_DAY.findall(question):
        days.add(f"{iso_y}-{iso_m}-{iso_d}" if iso_y else f"{y}-{int(m):02d}-{int(d):02d}")
    return days


def _days_in(node: Any) -> set[str]:
    """The days (`YYYY-MM-DD`) of values that are only a date or an instant, anywhere in the JSON.

    Free text (`reason`) and SQL do not count: only the whole value of a date column counts.
    """
    if isinstance(node, str):
        found = _ISO_DAY.fullmatch(node.strip())
        return {found.group(1)} if found else set()
    if isinstance(node, dict):
        return {day for value in node.values() for day in _days_in(value)}
    if isinstance(node, list):
        return {day for item in node for day in _days_in(item)}
    return set()


def _requested_day(fx: Evidence) -> str | None:
    """The day the model asked the FX tool for (the `requested_date`; else the one in the id `fx:<day>:<pair>`)."""
    try:
        data = json.loads(fx.content)
    except ValueError:
        data = None
    if isinstance(data, dict) and isinstance(data.get("requested_date"), str):
        return data["requested_date"]
    parts = fx.id.split(":")
    return parts[1] if len(parts) > 2 and _ISO_DAY.fullmatch(parts[1]) else None


def ledger_days(evidence: Iterable[Evidence], question: str) -> set[str] | None:
    """The days that have an origin: date columns of the ledger evidence (`sql`, `ledger_api`) and question dates.

    `None` when there is no ledger evidence: without it there is nothing to compare with. A date written in the
    question was given by the user, so the model did not make it up.
    """
    ledger = [e for e in evidence if e.source_type in _LEDGER_SOURCES]
    if not ledger:
        return None
    known = _days_in_question(question)
    for e in ledger:
        try:
            known |= _days_in(json.loads(e.content))
        except ValueError:
            continue
    return known


def fx_dates_without_origin(result: InvestigationResult) -> list[tuple[str, list[str]]]:
    """The days of the FX rates the answer uses that have no origin (`ledger_days`), with the claims that cite them.

    A rate is used when a claim cites it or the answer carries its id: the wrong query the agent redid with the right
    date does not count.
    """
    known = ledger_days(result.evidence, result.question)
    if known is None:
        return []
    found: dict[str, list[str]] = {}
    for fx in result.evidence:
        day = _requested_day(fx) if fx.source_type == "fx" else None
        if day is None or day in known:
            continue
        citing = [c.id for c in result.claims if fx.id in c.evidence_ids]
        if citing or fx.id in result.answer:
            found.setdefault(day, []).extend(i for i in citing if i not in found.get(day, []))
    return list(found.items())
