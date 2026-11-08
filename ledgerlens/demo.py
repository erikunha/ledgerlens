"""What the demo page needs beyond the agent: questions per statement line, offline scripts and readable summaries.

Why it exists: the Streamlit page (`app/streamlit_app.py`) reads like a payments portal. The person signs in as
one account, clicks "Ask" on a line of their statement and the question box fills with a question about that
line. Offline, a scripted model answers; this module holds those scripts, so the page and its tests share them.

- `PLANTED`: the planted complaints of `data/scenarios.json` the page offers, each tied to its accounts and to the
  statement lines whose "Ask" button uses its question.
- `ask_question`: the question a statement line puts in the box.
- `offline_script`: the scripted tool calls, the scripted SQL and the answer for a planted question, or `None`.
- `account_context`: the context message that tells the agent who is signed in and which line was picked.
- `ids_read`, `verification_summary`, `short_result`: what the page shows about how the agent reached the answer.

Numbers in the scripted answers come from the scenario's ground truth and are checked by the verifier like any
other answer.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage

from ledgerlens.offline import text_message, tool_call_message
from ledgerlens.schemas import Evidence, InvestigationResult, ToolCallRecord
from ledgerlens.tools.sql import major_amount

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIOS_PATH = PROJECT_ROOT / "data" / "scenarios.json"
LEDGER_ID = re.compile(r"\b(?:(?:TX|R|CB|ST|FX)-\d{4}|M-\d{2}|C-\d{4})\b")
LEDGER_SOURCES = ("sql", "ledger_api")  # the evidence that comes from ledger rows
FX_SQL = "SELECT kind, applied_rate, applied_at FROM fx_applied WHERE transaction_id = 'TX-2048' ORDER BY applied_at"
UNKNOWN_ID_QUESTION = "What is the status of TX-9999?"


@dataclass(frozen=True)
class Planted:
    """A planted complaint the page offers: its question for each kind of account and the lines it is about."""

    scenario: str
    question: str  # as the merchant or an analyst asks it (the scenario's own wording)
    customer_question: str | None  # first person, when the customer asks
    lines: tuple[str, ...]  # statement line ids whose "Ask" uses this question; empty for a question of the account

    def for_account(self, account_id: str) -> str:
        return self.customer_question if account_id.startswith("C-") and self.customer_question else self.question


def load_manifest(path: Path = SCENARIOS_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _scenario(manifest: dict[str, Any], scenario_id: str) -> dict[str, Any]:
    return next(s for s in manifest["scenarios"] if s["id"] == scenario_id)


def planted(manifest: dict[str, Any]) -> list[Planted]:
    q = {s["id"]: s["questions"][0] for s in manifest["scenarios"]}
    return [
        Planted("S01", q["S01"], None, ("TX-2048", "R-0731")),
        Planted(
            "S02",
            q["S02"],
            "I was charged twice for the same amount, TX-2051 and TX-2052. Was it a duplicate charge?",
            ("TX-2051", "TX-2052"),
        ),
        Planted("S03", q["S03"], "What is the deadline for my dispute CB-0310 and what happens next?", ("CB-0310",)),
        Planted("S08", q["S08"], None, ("ST-0044",)),
        Planted("S04", q["S04"], None, ()),
    ]


def accounts_of(manifest: dict[str, Any], scenario_id: str) -> list[str]:
    ids = _scenario(manifest, scenario_id)["ids"]
    return [*ids.get("customer_ids", []), *ids.get("merchant_ids", [])]


def ask_question(line: dict[str, Any], account_id: str, manifest: dict[str, Any]) -> str:
    """The question the line's "Ask" button puts in the box: the planted one when the line has one, else by type."""
    for item in planted(manifest):
        if line["id"] in item.lines and account_id in accounts_of(manifest, item.scenario):
            return item.for_account(account_id)
    ident, kind = line["id"], line["type"]
    if kind == "Refund":
        related = next((i for i in line["ids"] if i.startswith("TX-")), "")
        return f"What is the status of refund {ident}" + (f" for {related}?" if related else "?")
    if kind == "Chargeback":
        if account_id.startswith("C-"):
            return f"What is happening with my dispute {ident}?"
        return f"What is the deadline for dispute {ident} and what do we need to do?"
    if kind == "Payout":
        return f"How was payout {ident} calculated and when is it paid?"
    return f"What is the status of {ident}?"


def account_questions(account_id: str, manifest: dict[str, Any]) -> list[str]:
    """Questions to try for the account: its planted questions, then one about an id that is not on any statement."""
    out = [
        item.for_account(account_id)
        for item in planted(manifest)
        if item.lines and account_id in accounts_of(manifest, item.scenario)
    ]
    return [*dict.fromkeys(out), UNKNOWN_ID_QUESTION]


def account_context(account_id: str, kind: str, name: str, selected: list[str]) -> str:
    """The context message for the agent: who is signed in and which statement line they picked."""
    text = (
        f"The person asking is signed in to the payments portal as {kind} {account_id} ({name}). "
        f"The ledger your tools read holds only this account's records: answer about this account only."
    )
    if selected:
        text += f" They picked {', '.join(selected)} on their statement before asking."
    return text


# ---- offline scripts ----------------------------------------------------------------------------------


def _s01(truth: dict[str, Any]) -> tuple[list[AIMessage], list[str]]:
    calls = [
        tool_call_message("query_ledger", {"question": "FX rates applied to TX-2048"}),
        tool_call_message("search_policies", {"query": "refund in another currency", "transform": "none"}),
        tool_call_message("get_reference_fx", {"from_currency": "EUR", "to_currency": "BRL", "date": "2026-10-20"}),
        tool_call_message(
            "calculate",
            {
                "operation": "fx_gap_breakdown",
                "values": {
                    "units": "100.00",
                    "charge_rate": truth["charge_rate"],
                    "refund_reference_rate": truth["reference_rate_refund_date"],
                    "refund_applied_rate": truth["applied_rate"],
                },
            },
        ),
    ]
    answer = (
        f"The payment came to BRL {truth['charge_brl']} and the refund to BRL {truth['refund_brl']}, "
        f"a difference of BRL {truth['gap_brl']}. [sql:1, calc:1] "
        f"Of that, BRL {truth['rate_move_brl']} comes from the FX movement and BRL {truth['markup_brl']} is the "
        "markup over the day's reference rate. [calc:1] "
        f"The reference rate on 2026-10-20 was {truth['reference_rate_refund_date']}. [fx:2026-10-20:EUR-BRL]"
    )
    return [*calls, text_message(answer)], [FX_SQL]


def _s02(truth: dict[str, Any]) -> tuple[list[AIMessage], list[str]]:
    sql = (
        "SELECT id, merchant_id, amount_minor, currency, card_fingerprint, captured_at FROM transactions "
        "WHERE id IN ('TX-2051', 'TX-2052') ORDER BY id"
    )
    calls = [
        tool_call_message("query_ledger", {"question": "transactions TX-2051 and TX-2052"}),
        tool_call_message("search_policies", {"query": "duplicate charge detection rule", "k": 8, "transform": "none"}),
    ]
    answer = (
        f"TX-2051 and TX-2052 were both captured for {truth['currency']} {truth['refund_amount']} at the same "
        "merchant with the same card. [sql:1] "
        "Two captures count as duplicates when they have the same merchant, the same card, the same amount and the "
        "same currency, and the second one happens within 5 minutes after the first. "
        "[policy:duplicate-charges#detection-rule] "
        "TX-2052 was captured right after TX-2051, so TX-2052 is the duplicate and the recommendation is to "
        "refund it in full. [sql:1, policy:duplicate-charges#detection-rule]"
    )
    return [*calls, text_message(answer)], [sql]


def _s03(truth: dict[str, Any]) -> tuple[list[AIMessage], list[str]]:
    sql = (
        "SELECT id, transaction_id, amount_minor, currency, reason_code, stage, deadline FROM chargebacks "
        "WHERE id = 'CB-0310'"
    )
    calls = [
        tool_call_message("query_ledger", {"question": "dispute CB-0310"}),
        tool_call_message("search_policies", {"query": "response deadline for a dispute", "k": 8, "transform": "none"}),
    ]
    answer = (
        f"Dispute CB-0310 is at stage {truth['stage']}, with reason code {truth['reason_code']}, and the card "
        f"network deadline is {truth['deadline']}. [sql:1] "
        "Evidence must be sent at least one business day before the card network deadline. "
        "[policy:chargeback-handling#response-deadline] "
        "The evidence for this dispute has to be prepared and submitted now, by a person on the team. [sql:1]"
    )
    return [*calls, text_message(answer)], [sql]


def _s04(truth: dict[str, Any]) -> tuple[list[AIMessage], list[str]]:
    sql = "SELECT id, status FROM transactions WHERE id = 'TX-9999'"
    calls = [tool_call_message("query_ledger", {"question": "the status of TX-9999"})]
    answer = (
        "There is no transaction TX-9999 in the ledger. [sql:1] "
        "Could you check the id on the receipt, or tell me the date and amount of the payment?"
    )
    return [*calls, text_message(answer)], [sql]


def _s08(truth: dict[str, Any]) -> tuple[list[AIMessage], list[str]]:
    sql = "SELECT * FROM settlements WHERE id = 'ST-0044'"
    calls = [
        tool_call_message("query_ledger", {"question": "payout ST-0044"}),
        tool_call_message("search_policies", {"query": "when the payout is paid", "k": 8, "transform": "none"}),
        tool_call_message(
            "calculate",
            {"operation": "net_settlement", "values": {"gross": "30919.54", "refunds": "0.00", "fees": "926.67"}},
        ),
    ]
    answer = (
        f"Payout ST-0044 covers {truth['period'][0]} to {truth['period'][1]}, with gross sales of BRL 30919.54, "
        "no refunds and fees of BRL 926.67. [sql:1] "
        "The net payout is gross minus refunds minus fees, BRL 29992.87. [calc:1] "
        "The payout is paid 2 business days after the end of the period. [policy:settlement-schedule#payout-timing] "
        f"It was due on {truth['expected_payout_date']} and is marked as paid. [sql:1]"
    )
    return [*calls, text_message(answer)], [sql]


_SCRIPTS = {"S01": _s01, "S02": _s02, "S03": _s03, "S04": _s04, "S08": _s08}


def offline_script(question: str, manifest: dict[str, Any]) -> tuple[list[AIMessage], list[str]] | None:
    """The agent model's messages and the `query_ledger` SQL for a planted question, or None when there is none.

    Only the exact wording has a script, as the page offers it.
    """
    for item in planted(manifest):
        scenario = _scenario(manifest, item.scenario)
        if question in {item.question, item.customer_question, *scenario["questions"]}:
            return _SCRIPTS[item.scenario](scenario["truth"])
    return None


def scripted_questions(manifest: dict[str, Any]) -> list[str]:
    return [q for item in planted(manifest) for q in (item.question, item.customer_question) if q]


# ---- statement filters ---------------------------------------------------------------------------------

PERIODS = {"All dates": None, "Last 30 days": 30, "Last 7 days": 7}


def filter_lines(
    lines: list[dict[str, Any]],
    *,
    period: str = "All dates",
    types: list[str] | None = None,
    statuses: list[str] | None = None,
    search: str = "",
) -> list[dict[str, Any]]:
    """The statement lines that pass the filters. The period counts back from the newest line of the statement."""
    out = list(lines)
    days = PERIODS[period]
    if days is not None and out:
        newest = max(date.fromisoformat(line["date"]) for line in out)
        start = (newest - timedelta(days=days - 1)).isoformat()
        out = [line for line in out if line["date"] >= start]
    if types:
        out = [line for line in out if line["type"] in types]
    if statuses:
        out = [line for line in out if status_pill(line)[0] in statuses]
    needle = search.strip().upper()
    if needle:
        out = [line for line in out if any(needle in i for i in [line["id"], *line["ids"]])]
    return out


# ---- what the page shows about a turn -----------------------------------------------------------------


def ledger_ids(text: str) -> list[str]:
    """Ledger ids in a text, in order of appearance, each once."""
    return list(dict.fromkeys(LEDGER_ID.findall(text)))


def ids_read(result: InvestigationResult) -> set[str]:
    """Ids of the ledger records the agent read in the turn: those in ledger evidence (rows and the query that
    selected them). Policy passages and FX rates do not count: they are not ledger rows."""
    found: set[str] = set()
    for evidence in result.evidence:
        if evidence.source_type in LEDGER_SOURCES:
            found.update(ledger_ids(evidence.content))
            found.update(ledger_ids(evidence.ref))
    return found


def verification_summary(result: InvestigationResult) -> dict[str, Any]:
    """Verdict counts, whether a person must review and why."""
    counts = {"supported": 0, "contradicted": 0, "not_enough_evidence": 0}
    for verdict in result.verdicts:
        counts[verdict.label] += 1
    reasons = [m.removeprefix("escalation: ") for m in result.missing_information if m.startswith("escalation: ")]
    if result.requires_human_review and not reasons:
        reasons = list(result.missing_information)
    return {**counts, "review": result.requires_human_review, "reasons": reasons}


def short_result(record: ToolCallRecord, evidence: dict[str, Evidence], limit: int = 160) -> str:
    """One line on what a tool call returned: the error code, or the start of its first evidence."""
    if not record.ok:
        return f"failed: {record.error_code}"
    texts = [evidence[i].content for i in record.evidence_ids if i in evidence]
    if not texts:
        return "no evidence"
    text = " ".join(texts[0].split())
    try:
        data = json.loads(texts[0])
    except ValueError:
        data = None
    if isinstance(data, dict) and isinstance(data.get("rows"), list):
        text = f"{len(data['rows'])} row(s): {json.dumps(data['rows'], ensure_ascii=False)}"
    more = f" (+{len(texts) - 1} more)" if len(texts) > 1 else ""
    return (text if len(text) <= limit else text[: limit - 3] + "...") + more


# ---- how a portal shows a statement line -----------------------------------------------------------------

# (label, colour) of the status pill, per line type and stored status
_PILLS = {
    "Payment": {
        "captured": ("Settled", "green"),
        "authorized": ("Pending", "blue"),
        "failed": ("Failed", "red"),
        "refunded": ("Refunded", "violet"),
        "partially_refunded": ("Partially refunded", "violet"),
        "disputed": ("Disputed", "orange"),
        "charged_back": ("Charged back", "red"),
    },
    "Refund": {"requested": ("Pending", "blue"), "paid": ("Refunded", "violet"), "rejected": ("Declined", "red")},
    "Chargeback": {
        "opened": ("Disputed", "orange"),
        "evidence_requested": ("Action needed", "orange"),
        "evidence_submitted": ("Under review", "blue"),
        "won": ("Won", "green"),
        "lost": ("Lost", "red"),
    },
    "Payout": {"scheduled": ("Pending", "blue"), "paid": ("Settled", "green")},
}
REASON_CODES = {
    "FRD": "Fraud",
    "DUP": "Duplicate processing",
    "NRC": "Item not received",
    "NAD": "Not as described",
    "OTH": "Other",
}
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def status_pill(line: dict[str, Any]) -> tuple[str, str]:
    """The status as a portal shows it: a short label and its colour."""
    return _PILLS.get(line["type"], {}).get(line["status"], (line["status"].replace("_", " ").capitalize(), "gray"))


def money(amount: str | None, currency: str | None) -> str:
    """`"29992.87", "BRL"` as `BRL 29,992.87`."""
    if amount is None or not currency:
        return "-"
    whole, _, cents = amount.partition(".")
    sign = "-" if whole.startswith("-") else ""
    return f"{currency} {sign}{int(whole.lstrip('-')):,}.{cents or '00'}"


def nice_date(value: str | None, *, time: bool = False) -> str:
    """`2026-10-15T09:12:00Z` as `Oct 15, 2026` (with `, 09:12 UTC` when `time`)."""
    if not value:
        return "-"
    day = date.fromisoformat(value[:10])
    text = f"{_MONTHS[day.month - 1]} {day.day}, {day.year}"
    if time and len(value) >= 16 and value[10] == "T":
        text += f", {value[11:16]} UTC"
    return text


def line_title(line: dict[str, Any], kind: str) -> str:
    """What the line is, in the words of a statement."""
    who = line.get("counterparty") or ""
    if line["type"] == "Payment":
        return who if kind == "customer" else f"Payment from {who}"
    if line["type"] == "Refund":
        return f"Refund from {who}" if kind == "customer" else f"Refund to {who}"
    if line["type"] == "Chargeback":
        return f"Dispute on a payment to {who}" if kind == "customer" else f"Dispute opened by {who}"
    record = line["record"]
    return f"Payout for {nice_date(record['period_start'])} to {nice_date(record['period_end'])}"


def _fx_text(fx: list[dict[str, Any]]) -> str | None:
    if not fx:
        return None
    rate = fx[0]
    return (
        f"1 {rate['from_currency']} = {rate['applied_rate']} {rate['to_currency']} on {nice_date(rate['applied_at'])}"
    )


def _card_text(record: dict[str, Any]) -> str:
    method = record.get("method", "")
    if method != "card":
        return method.replace("_", " ").capitalize()
    brand = (record.get("card_brand") or "card").capitalize()
    fingerprint = record.get("card_fingerprint") or ""
    return f"{brand} card, on file as ****{fingerprint[-4:]}" if fingerprint else f"{brand} card"


ID_LABELS = {"Payment": "Transaction ID", "Refund": "Refund ID", "Chargeback": "Dispute ID", "Payout": "Payout ID"}


def line_details(line: dict[str, Any], kind: str) -> list[tuple[str, str]]:
    """The fields a portal shows when a line is opened, as (label, value) pairs.

    What the closed line already says (amount, date, status) is not repeated; the id is shown apart
    (`ID_LABELS`)."""
    record = line["record"]
    if line["type"] == "Payment":
        pairs = [
            ("Merchant" if kind == "customer" else "Customer", line["counterparty"]),
            ("Payment method", _card_text(record)),
            ("Time", nice_date(record["created_at"], time=True)),
        ]
        if (fx := _fx_text(record.get("fx", []))) is not None:
            pairs.append(("Exchange rate applied", fx))
        return pairs
    if line["type"] == "Refund":
        pairs = [
            ("Original payment", record["transaction_id"]),
            ("Paid back", money(major_amount(record.get("payout_amount_minor")), record.get("payout_currency"))),
            ("Reason", record["reason"]),
        ]
        if record.get("resolved_at"):
            pairs.append(("Resolved", nice_date(record["resolved_at"], time=True)))
        if (fx := _fx_text(record.get("fx", []))) is not None:
            pairs.append(("Exchange rate applied", fx))
        return pairs
    if line["type"] == "Chargeback":
        return [
            ("Payment", record["transaction_id"]),
            ("Reason", REASON_CODES.get(record["reason_code"], record["reason_code"])),
            ("Respond by", nice_date(record["deadline"])),
        ]
    currency = record["currency"]
    return [
        ("Period", f"{nice_date(record['period_start'])} to {nice_date(record['period_end'])}"),
        ("Gross sales", money(major_amount(record["gross_minor"]), currency)),
        ("Refunds", money(major_amount(record["refunds_minor"]), currency)),
        ("Fees", money(major_amount(record["fees_minor"]), currency)),
        ("Expected on", nice_date(record["expected_payout_date"])),
        ("Paid on", nice_date(record["paid_at"]) if record.get("paid_at") else "Not yet"),
    ]


def account_summary(lines: list[dict[str, Any]], kind: str) -> list[tuple[str, str]]:
    """The figures on the account card, as (label, value) pairs."""
    open_disputes = sum(1 for x in lines if x["type"] == "Chargeback" and x["status"] not in ("won", "lost"))
    pending_refunds = sum(1 for x in lines if x["type"] == "Refund" and x["status"] == "requested")
    if kind == "customer":
        payments = [x for x in lines if x["type"] == "Payment"]
        return [
            ("Payments", str(len(payments))),
            ("Refunds in progress", str(pending_refunds)),
            ("Open disputes", str(open_disputes)),
        ]
    payouts = [x for x in lines if x["type"] == "Payout"]
    pending = [x for x in payouts if x["status"] == "scheduled"]
    paid = [x for x in payouts if x["status"] == "paid"]
    currency = payouts[0]["currency"] if payouts else ""
    pending_total = sum(int(x["record"]["net_minor"]) for x in pending)
    last = max(paid, key=lambda x: x["date"]) if paid else None
    return [
        ("Pending settlement", money(major_amount(pending_total), currency) if payouts else "-"),
        ("Last payout", f"{money(last['amount'], last['currency'])}" if last else "-"),
        ("Open disputes", str(open_disputes)),
    ]
