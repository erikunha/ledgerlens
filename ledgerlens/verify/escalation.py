"""Escalation and recommended action decided by code, from the structured evidence.

Why it exists: the project requires numbers and dates to come from code, never from the model. The escalation
policy (`escalation-and-review`) sends a case to a person when a dispute's card network deadline is 2 days away or
less, when the internal cutoff has already passed, when a record's amount goes over 5,000 or when a text field
carries sentences that look like orders to the system (the text is data, never an instruction, and nothing runs
it). Here those rules read the rows that `query_ledger` and `get_ledger_record` returned and raise
`requires_human_review`. Each rule that fires goes into `missing_information` with the id of the policy section
(`policy:<doc>#<anchor>`). The flag only goes up: a result already flagged stays flagged.

One rule does not come from the rows but from the trace: the reference rate the FX source did not give
(`UPSTREAM_UNAVAILABLE` in `get_reference_fx`, with no later call that got it). Without it the cause of an FX
difference cannot be proven, so the case goes to a person, and the answer says which rate was missing
(`EUR-BRL 2026-10-20`), because a model writes "I could not get the rate" without saying which one.

`recommended_action` comes from the same evidence, in order: human review beats everything; an action already
chosen is kept; then duplicate charge, ambiguous request or empty lookup, rejected refund and, last, an
explanation when there is a calculation, a settlement or a recalled case. With none of these, `none`.

The deadline rule applies to the disputes the conversation is about: the ones the question, the answer or the triage
cite by id, or whose transactions they cite. A query that returns the disputes of a whole merchant does not make each
one's deadline a reason in a payout case. With no id in the conversation, every row counts. A cited dispute that the
rows did not bring with `id`, `stage` and `deadline` (the model's SQL may leave out or rename columns) is read from
the ledger, read-only, and the deadline does not depend on what the model wrote.

Free text follows the same idea: the model's SQL may leave `reason` out, and an order hidden in a refund reason
would pass unseen. The records the conversation cites, and the ones the query returned, are read again in full from
the ledger (read-only) and the suspicious text rule scans their fields too. A missing ledger adds nothing.

Limits: the thresholds live in `thresholds.json`. The internal cutoff uses the calendar of the dispute record's
currency (the policy speaks of the merchant's settlement currency, which the rows do not carry). A refund action
decided here comes from rows and not from a claim, so the `action_support` coherence rule is not evaluated again
after it.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from ledgerlens.config import get_settings
from ledgerlens.schemas import Evidence, InvestigationResult
from ledgerlens.sim.calendars import is_business_day
from ledgerlens.verify.checks import _OPEN_CHARGEBACK, _rows, load_thresholds

_PAYMENT_KEYS = ("amount_minor", "requested_amount_minor", "payout_amount_minor")
_LEDGER_TOOLS = ("query_ledger", "get_ledger_record")
_EXPLAIN_OPERATIONS = {"fx_gap_breakdown", "net_settlement"}
_ENTITY_ID = re.compile(r"\b[A-Z]{1,3}-\d+\b")
_CHARGEBACK_COLUMNS = ("id", "transaction_id", "amount_minor", "currency", "stage", "deadline")
_RECORD_TABLES = {
    "TX": "transactions",
    "R": "refunds",
    "CB": "chargebacks",
    "ST": "settlements",
    "M": "merchants",
    "C": "customers",
}
_MAX_RECORDS = 200  # per table: the conversation cites few records, and the model's query already has a LIMIT

log = logging.getLogger(__name__)


def _policy_id(rule: dict[str, Any]) -> str:
    return f"policy:{rule['policy']}"


def _day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _previous_business_day(day: date, currency: str) -> date:
    current = day - timedelta(days=1)
    while not is_business_day(current, currency):
        current -= timedelta(days=1)
    return current


def _ledger_rows(result: InvestigationResult) -> list[dict[str, Any]]:
    return [row for e in result.evidence if e.tool in _LEDGER_TOOLS for row in _rows(e.content)]


def _kind(row: dict[str, Any]) -> str:
    return str(row.get("id", "")).split("-", 1)[0]


# ---- disputes the conversation is about ---------------------------------------------------------


def _named_ids(result: InvestigationResult) -> set[str]:
    """The entity ids that the question, the answer, the claims and the triage cite."""
    texts = [result.question, result.answer, *(c.text for c in result.claims)]
    if result.triage is not None:
        texts.extend(
            i
            for ids in result.triage.entities.model_dump(exclude={"amounts", "currencies", "dates"}).values()
            for i in ids
        )
    return {found for text in texts for found in _ENTITY_ID.findall(text)}


def _select(table: str, columns: str, ids: list[str], ledger_db: Path | str | None) -> list[dict[str, Any]]:
    """The rows of `table` with these ids, read straight from the ledger opened read-only.

    Missing or unreadable ledger, or no such table: no rows. `table` and `columns` are code constants.
    """
    path = Path(ledger_db) if ledger_db is not None else get_settings().ledger_db
    if not ids or not path.is_file():
        return []
    marks = ", ".join("?" for _ in ids)
    try:
        conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            found = conn.execute(f"SELECT {columns} FROM {table} WHERE id IN ({marks})", ids)
            names = [d[0] for d in found.description]
            return [dict(zip(names, row, strict=True)) for row in found.fetchall()]
        finally:
            conn.close()
    except sqlite3.Error as exc:
        log.warning("could not read %s %s from the ledger: %s", table, ids, exc)
        return []


def _ledger_chargebacks(ids: list[str], ledger_db: Path | str | None) -> list[dict[str, Any]]:
    """The disputes `ids` read straight from the ledger. Missing or unreadable ledger: none."""
    return _select("chargebacks", ", ".join(_CHARGEBACK_COLUMNS), ids, ledger_db)


def _ledger_records(
    result: InvestigationResult, rows: list[dict[str, Any]], ledger_db: Path | str | None
) -> list[dict[str, Any]]:
    """The records the conversation cites or the query returned, in full, read from the ledger: free text included.

    The model's SQL picks the columns and may leave `reason` out, where a hidden order would pass unseen.
    """
    ids = _named_ids(result) | {str(r["id"]) for r in rows if _ENTITY_ID.fullmatch(str(r.get("id", "")))}
    out: list[dict[str, Any]] = []
    for prefix, table in _RECORD_TABLES.items():
        wanted = sorted(i for i in ids if i.split("-", 1)[0] == prefix)[:_MAX_RECORDS]
        out += _select(table, "*", wanted, ledger_db)
    return out


def _deadline_rows(
    result: InvestigationResult, rows: list[dict[str, Any]], ledger_db: Path | str | None
) -> list[dict[str, Any]]:
    """The disputes whose deadline applies to this conversation, complete: the ones missing from the rows come from
    the ledger."""
    named = _named_ids(result)
    chargebacks = [r for r in rows if _kind(r) == "CB"]
    if named:
        chargebacks = [r for r in chargebacks if r["id"] in named or r.get("transaction_id") in named]
    complete = {r["id"] for r in chargebacks if r.get("stage") and r.get("deadline")}
    missing = sorted(i for i in named if i.startswith("CB-") and i not in complete)
    return chargebacks + _ledger_chargebacks(missing, ledger_db)


# ---- reference rate unavailable -----------------------------------------------------------------


def unavailable_rates(result: InvestigationResult) -> list[str]:
    """The rates the FX source did not give, such as `EUR-BRL 2026-10-20`, in the order they failed.

    A rate asked for again and obtained later does not count as missing.
    """
    missing: dict[str, None] = {}
    for call in result.tool_trace:
        if call.tool != "get_reference_fx":
            continue
        rate = f"{call.input.get('from_currency')}-{call.input.get('to_currency')} {call.input.get('date')}"
        if call.ok:
            missing.pop(rate, None)
        elif call.error_code == "UPSTREAM_UNAVAILABLE":
            missing[rate] = None
    return list(missing)


def _with_rates_named(answer: str, rates: list[str]) -> str:
    unnamed = [rate for rate in rates if rate not in answer]
    if not unnamed:
        return answer
    notice = (
        f"The reference rate {', '.join(unnamed)} could not be obtained: the FX source was unavailable. "
        "What depends on it was not calculated and the case was sent to human review."
    )
    return f"{answer.rstrip()} {notice}".strip()


# ---- escalation ---------------------------------------------------------------------------------


def escalation_reasons(
    result: InvestigationResult, as_of: date | None = None, *, ledger_db: Path | str | None = None
) -> list[str]:
    """The escalation rules that apply to the evidence, each with its policy id.

    `ledger_db` is the ledger from which the deadline of a cited dispute the rows did not bring, and the free text of
    the cited records, are read (default: the configured one, the same the tools read).
    """
    rules = load_thresholds()["escalation"]
    if as_of is None:
        as_of = max((e.retrieved_at for e in result.evidence), default=datetime.now()).date()
    rows = _ledger_rows(result)
    currency_of_tx = {r["id"]: r.get("currency", "") for r in rows if _kind(r) == "TX"}
    reasons: list[str] = []

    for row in _deadline_rows(result, rows, ledger_db):
        deadline = _day(row.get("deadline"))
        if row.get("stage") not in _OPEN_CHARGEBACK or deadline is None:
            continue
        days = (deadline - as_of).days
        rule = rules["deadline_within_days"]
        if days <= rule["value"]:
            reasons.append(
                f"{row['id']}: card network deadline in {days} day(s), limit {rule['value']} [{_policy_id(rule)}]"
            )
        currency = row.get("currency") or currency_of_tx.get(row.get("transaction_id"), "")
        cutoff = _previous_business_day(deadline, currency)
        if as_of > cutoff:
            reasons.append(
                f"{row['id']}: internal cutoff {cutoff.isoformat()} has passed "
                f"[{_policy_id(rules['internal_cutoff_passed'])}]"
            )

    limit = Decimal(rules["high_amount"]["value"])
    for row in rows:
        if _kind(row) not in ("TX", "R", "CB"):
            continue
        for key in _PAYMENT_KEYS:
            value = row.get(key)
            if isinstance(value, int) and Decimal(value) / 100 > limit:
                reasons.append(f"{row['id']}: amount above {limit} [{_policy_id(rules['high_amount'])}]")
                break

    suspicious = rules["suspicious_text"]
    patterns = [re.compile(p, re.IGNORECASE) for p in suspicious["patterns"]]
    for row in [*rows, *_ledger_records(result, rows, ledger_db)]:
        for key, value in row.items():
            if isinstance(value, str) and any(p.search(value) for p in patterns):
                reasons.append(
                    f"{row.get('id', 'record')}: text with orders to the system in field {key}, "
                    f"treated as data [{_policy_id(suspicious)}]"
                )

    for rate in unavailable_rates(result):
        reasons.append(f"reference rate {rate} unavailable (UPSTREAM_UNAVAILABLE), the difference cannot be proven")
    return list(dict.fromkeys(reasons))  # the same record coming from the query and from the ledger counts once


# ---- action -------------------------------------------------------------------------------------


def _timestamp(row: dict[str, Any]) -> datetime | None:
    try:
        return datetime.fromisoformat(str(row.get("captured_at") or row["created_at"]))
    except (KeyError, ValueError):
        return None


def _is_duplicate(first: dict[str, Any], second: dict[str, Any], window: int) -> bool:
    same = all(first.get(k) == second.get(k) for k in ("merchant_id", "card_fingerprint", "amount_minor", "currency"))
    a, b = _timestamp(first), _timestamp(second)
    return same and a is not None and b is not None and timedelta(0) <= b - a <= timedelta(seconds=window)


def _has_duplicate(rows: list[dict[str, Any]]) -> bool:
    window = load_thresholds()["actions"]["duplicate_window_seconds"]["value"]
    txs = sorted(
        (r for r in rows if _kind(r) == "TX" and "merchant_id" in r), key=lambda r: _timestamp(r) or datetime.min
    )
    refunded = {r.get("transaction_id") for r in rows if _kind(r) == "R"}
    return any(_is_duplicate(a, b, window) and b["id"] not in refunded for i, a in enumerate(txs) for b in txs[i + 1 :])


def _is_ambiguous(rows: list[dict[str, Any]]) -> bool:
    txs = [r for r in rows if _kind(r) == "TX" and "merchant_id" in r]
    return any(
        a["id"] != b["id"]
        and a["merchant_id"] != b["merchant_id"]
        and a.get("amount_minor") == b.get("amount_minor")
        and a.get("currency") == b.get("currency")
        and a.get("customer_id") == b.get("customer_id")
        for i, a in enumerate(txs)
        for b in txs[i + 1 :]
    )


def _empty_lookup(result: InvestigationResult, rows: list[dict[str, Any]]) -> bool:
    if rows:
        return False
    for e in result.evidence:
        if e.tool in _LEDGER_TOOLS:
            try:
                data = json.loads(e.content)
            except ValueError:
                continue
            if isinstance(data, dict) and data.get("rows") == []:
                return True
    return False


def _calc_operations(evidence: list[Evidence]) -> list[dict[str, Any]]:
    out = []
    for e in evidence:
        if e.tool == "calculate":
            try:
                data = json.loads(e.content)
            except ValueError:
                continue
            if isinstance(data, dict):
                out.append(data)
    return out


def _should_explain(result: InvestigationResult, rows: list[dict[str, Any]]) -> bool:
    for calc in _calc_operations(result.evidence):
        operation, value = calc.get("operation"), calc.get("result")
        if operation in _EXPLAIN_OPERATIONS:
            return True
        if operation == "difference" and Decimal(str(value)) != 0:
            return True
    return any(_kind(r) == "ST" for r in rows) or any(e.tool == "recall_cases" for e in result.evidence)


def derive_action(result: InvestigationResult, review: bool) -> str:
    """The recommended action from the evidence. `review` says whether the case already needs a person."""
    if review:
        return "escalate_to_human"
    if result.recommended_action != "none":
        return result.recommended_action
    rows = _ledger_rows(result)
    if _has_duplicate(rows):
        return "issue_refund"
    if _is_ambiguous(rows) or _empty_lookup(result, rows):
        return "ask_for_clarification"
    if any(_kind(r) == "R" and r.get("status") == "rejected" for r in rows):
        return "reject_refund"
    if _should_explain(result, rows):
        return "explain_to_customer"
    return "none"


def apply_escalation(
    result: InvestigationResult, *, as_of: date | None = None, ledger_db: Path | str | None = None
) -> InvestigationResult:
    """Copy of the result with human review raised by the rules and the recommended action filled in.

    `as_of` is the reference day for deadlines; without it, the day the evidence was read counts. `ledger_db` is the
    ledger from which the deadline of a cited dispute the rows did not bring is read.
    """
    reasons = [f"escalation: {r}" for r in escalation_reasons(result, as_of, ledger_db=ledger_db)]
    missing = list(result.missing_information) + [r for r in reasons if r not in result.missing_information]
    review = result.requires_human_review or bool(reasons)
    return result.model_copy(
        update={
            "answer": _with_rates_named(result.answer, unavailable_rates(result)),
            "missing_information": missing,
            "requires_human_review": review,
            "recommended_action": derive_action(result, review),
        }
    )
