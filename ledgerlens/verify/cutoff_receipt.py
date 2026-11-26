"""Verify a narrow set of dated cutoff answers using policy and calculator receipts."""

from __future__ import annotations

import json
import re
from datetime import date
from hashlib import sha256
from typing import Any

from pydantic import ValidationError

from ledgerlens.schemas import InvestigationResult, Verdict
from ledgerlens.tools.calculator import PREVIOUS_BUSINESS_DAY, CalcError, CalculateInput, compute
from ledgerlens.verify.claims import extract_claims

_POLICY_TOOL = "search_policies"
_CALCULATE_TOOL = "calculate"
_POLICY_SOURCE = "policy"
_CALC_SOURCE = "calc"
_CHUNK_ID = "chargeback-handling#response-deadline"
_POLICY_ID = f"{_POLICY_SOURCE}:{_CHUNK_ID}"
# Bind the rule to the whole retrieved passage. A changed policy needs its own proof.
_PASSAGE_DIGEST = "c13c507e87d0ba11ca40cc7e1da63ba47a1a75f0f72f13c2c44e123c345546b5"
_CALC_ID = re.compile(rf"{_CALC_SOURCE}:[1-9][0-9]*")
_DEADLINE_INPUT = "date"
_CURRENCY_INPUT = "currency"
_CHUNK_KEY = "chunk_id"
_PASSAGE_KEY = "text"


def _json(content: str) -> Any:
    try:
        return json.loads(content)
    except ValueError:
        return None


def _has_cutoff_policy(result: InvestigationResult) -> bool:
    cited = [evidence for evidence in result.evidence if evidence.id == _POLICY_ID]
    if len(cited) != 1:
        return False
    policy = cited[0]
    if (policy.source_type, policy.tool, policy.ref) != (_POLICY_SOURCE, _POLICY_TOOL, _CHUNK_ID):
        return False
    data = _json(policy.content)
    if not isinstance(data, dict) or data.get(_CHUNK_KEY) != _CHUNK_ID:
        return False
    passage = data.get(_PASSAGE_KEY)
    if not isinstance(passage, str) or sha256(passage.encode(errors="surrogatepass")).hexdigest() != _PASSAGE_DIGEST:
        return False
    return any(call.ok and call.tool == _POLICY_TOOL and _POLICY_ID in call.evidence_ids for call in result.tool_trace)


def _has_exact_wording(
    result: InvestigationResult, deadline: date, currency: str, cutoff: date, receipt_id: str
) -> bool:
    deadline_text = f"{deadline:%A, %B} {deadline.day}, {deadline.year}"
    cutoff_date = f"{cutoff:%B} {cutoff.day}, {cutoff.year}"
    cutoff_text = f"{cutoff:%A}, {cutoff_date}"
    questions = (
        f"Our settlement currency is {currency}. The dispute response deadline is {deadline_text}. "
        "On what date must we submit evidence?",
        f"{currency} settlement. Our dispute response deadline is {deadline_text}. What date is the evidence due?",
    )
    if result.question.strip() not in questions:
        return False

    # Whole-answer forms prevent bypassing another clause or an assertion that claim extraction omits.
    date_claim = f"For a response deadline of {deadline_text}, and a settlement currency of {currency}, "
    answers = (
        f"Evidence must be submitted at least one business day before the dispute response deadline [{_POLICY_ID}]. "
        f"{date_claim}the evidence submission cutoff is {cutoff_text} [{receipt_id}].",
        "Evidence must be submitted at least one business day before the response deadline of the dispute "
        f"[{_POLICY_ID}]. {date_claim}the previous business day is {cutoff_text} [{receipt_id}]. "
        f"Therefore, you must submit evidence by {cutoff_date}.",
        f"For a dispute with a response deadline of {deadline_text} and settlement in {currency}, "
        f"the evidence is due by the previous business day, which is {cutoff_text} [{_POLICY_ID}, {receipt_id}].",
    )
    return result.answer.strip() in answers


def cutoff_receipt_verdict(result: InvestigationResult) -> Verdict | None:
    """Return a rule verdict for the dated claim when its entire answer can be checked."""
    receipts = [evidence for evidence in result.evidence if _CALC_ID.fullmatch(evidence.id)]
    if len(receipts) != 1 or not _has_cutoff_policy(result):
        return None
    receipt = receipts[0]
    calls = [call for call in result.tool_trace if receipt.id in call.evidence_ids]
    if len(calls) != 1 or (receipt.source_type, receipt.tool) != (_CALC_SOURCE, _CALCULATE_TOOL):
        return None
    call = calls[0]
    if not call.ok or call.tool != _CALCULATE_TOOL or call.evidence_ids != [receipt.id]:
        return None
    try:
        inputs = CalculateInput.model_validate(call.input, strict=True)
        if inputs.operation != PREVIOUS_BUSINESS_DAY or inputs.values.keys() != {_DEADLINE_INPUT, _CURRENCY_INPUT}:
            return None
        cutoff_iso, formula = compute(inputs.operation, inputs.values, inputs.decimals, inputs.plan)
    except (CalcError, ValidationError):
        return None
    data = _json(receipt.content)
    if receipt.ref != formula or data != {"operation": inputs.operation, "result": cutoff_iso, "formula": formula}:
        return None
    deadline = date.fromisoformat(inputs.values[_DEADLINE_INPUT])
    currency = inputs.values[_CURRENCY_INPUT].strip().upper()
    cutoff = date.fromisoformat(data["result"])
    if not _has_exact_wording(result, deadline, currency, cutoff, receipt.id):
        return None
    # Claims may be supplied by callers. Match the parsed answer before selecting the dated claim.
    if result.claims != extract_claims(result.answer, result.evidence):
        return None
    dated_claims = [claim for claim in result.claims if receipt.id in claim.evidence_ids]
    if len(dated_claims) != 1:
        return None
    return Verdict(
        claim_id=dated_claims[0].id,
        label="supported",
        method="rule",
        evidence_ids=[_POLICY_ID, receipt.id],
        note=f"Recomputed the cited cutoff from the stated deadline and settlement currency: {cutoff_iso}.",
    )
