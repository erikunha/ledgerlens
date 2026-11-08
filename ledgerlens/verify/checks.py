"""Verification of an answer: numbers by code, coherence by rules, text by the NLI model.

Why it exists: the principle is that the model never decides whether a number is right.
`check_numeric` compares the claim's values with what `calculate` returned and with the cited ledger values,
using `Decimal`.
`check_ledger_amounts` does the same for a sentence with a currency value that cites the ledger (or FX) but no
calculation: the stated value must be exactly a number of the cited ledger evidence. `check_rates` does it for a
sentence that states a rate (`5.4931`) with no currency value.
`check_coherence` applies rules to the rows the queries returned. Only text claims with no currency value, or with
no cited ledger, go to the NLI model, and the label comes from the thresholds in `thresholds.json`. `verify_result`
puts it all together and returns a copy of the result with verdicts, coherence, missing information and
`requires_human_review`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

from ledgerlens.schemas import (
    Claim,
    Coherence,
    CoherenceIssue,
    Evidence,
    InvestigationResult,
    NliScores,
    Verdict,
    VerdictLabel,
)
from ledgerlens.verify.claims import (
    Amount,
    amounts_match,
    calc_operands,
    calc_values,
    check_amounts_against_ledger,
    check_rates_against_ledger,
    direction_in_words,
    evidence_values,
    extract_claims,
    find_amounts,
    focus_premise,
    fx_dates_without_origin,
    has_currency_amount,
    has_rate,
    ledger_values,
    render_premise,
)
from ledgerlens.verify.nli import Nli

THRESHOLDS_PATH = Path(__file__).with_name("thresholds.json")
_NEGATIONS = {"not", "no", "never", "cannot", "without"}
_DUPLICATE_OR_DISCREPANCY = re.compile(r"duplicat|discrepan|overcharg|differs?\b", re.IGNORECASE)
_OPEN_CHARGEBACK = {"opened", "evidence_requested", "evidence_submitted"}


@lru_cache(maxsize=1)
def _thresholds() -> Mapping[str, Any]:
    return json.loads(THRESHOLDS_PATH.read_text())


def load_thresholds() -> dict[str, Any]:
    return dict(_thresholds())


def label_from_scores(scores: Mapping[str, float], thresholds: Mapping[str, Any]) -> VerdictLabel:
    """The label from the NLI scores; between the two thresholds, evidence is missing."""
    entailment, contradiction = scores["entailment"], scores["contradiction"]
    if contradiction >= thresholds["contradiction_min"] and contradiction > entailment:
        return "contradicted"
    if entailment >= thresholds["entailment_min"] and entailment > contradiction:
        return "supported"
    return "not_enough_evidence"


# ---- numbers ------------------------------------------------------------------------------------


def check_numeric(claim: Claim, evidence_by_id: Mapping[str, Evidence]) -> Verdict:
    """Compares the values stated in the claim with what the cited evidence produced. Never calls the NLI model.

    Each stated value must match, with its sign, a cited `calculate` result or a cited ledger value; a value nobody
    computed or read is "no evidence", and the sentence is supported only if none is left over and at least one
    comes from a result or the ledger. A value that only shows up as an input of the calculation is not enough.
    `contradicted` is kept for the clear pair: a single stated value, a single result, and they differ.
    """

    def verdict(label: VerdictLabel, note: str, ids: list[str] | None = None) -> Verdict:
        return Verdict(claim_id=claim.id, label=label, method="numeric", evidence_ids=ids or [], note=note)

    numeric = claim.numeric
    if numeric is None:
        return verdict("not_enough_evidence", "The numeric claim does not point to a calculation.")
    calc = evidence_by_id.get(numeric.calc_evidence_id)
    if calc is None:
        return verdict("not_enough_evidence", f"Evidence {numeric.calc_evidence_id} is not in the result.")
    ids = [calc.id]
    if not any(abs(v - numeric.expected) <= numeric.tolerance for v in calc_values(calc.content)):
        return verdict("contradicted", "The expected value did not come out of the calculate tool.", ids)
    stated = [a for a in find_amounts(claim.text) if a.unit in ("", numeric.unit)]
    if not stated:
        return verdict("not_enough_evidence", "The claim carries no value in the expected unit.", ids)

    cited = [evidence_by_id[i] for i in dict.fromkeys([calc.id, *claim.evidence_ids]) if i in evidence_by_id]
    calcs = [e for e in cited if e.source_type == "calc"]
    results = [v for e in calcs for v in calc_values(e.content)]
    operands = [v for e in calcs for v in calc_operands(e.content)]
    ledger = [v for e in cited if e.source_type != "calc" for v in evidence_values(e.content)]
    ids = [e.id for e in cited]
    direction = direction_in_words(claim.text)
    tolerance = numeric.tolerance

    def source(amount: Amount) -> str:
        if any(amounts_match(amount.value, v, tolerance, direction) for v in results):
            return "result"
        if any(amounts_match(amount.value, v, tolerance) for v in ledger):
            return "ledger"
        if any(amounts_match(amount.value, v, tolerance) for v in operands):
            return "input"
        return "none"

    sources = [source(a) for a in stated]
    if "none" not in sources and ("result" in sources or "ledger" in sources):
        return verdict("supported", f"Matches {', '.join(str(v) for v in results)} ({', '.join(ids)}).", ids)
    if len(stated) == 1 and len(results) == 1:
        return verdict("contradicted", f"The stated value differs from the computed {results[0]} ({calc.id}).", ids)
    unmatched = ", ".join(str(a.value) for a, kind in zip(stated, sources, strict=True) if kind in ("none", "input"))
    return verdict("not_enough_evidence", f"No cited calculation or ledger value produced: {unmatched}.", ids)


_LEDGER_SOURCES = ("sql", "ledger_api", "fx")


def check_ledger_amounts(claim: Claim, evidence_by_id: Mapping[str, Evidence]) -> Verdict | None:
    """Checks by code a sentence with a currency value and no cited calculation, against the ledger it cites.

    With no `calculate` in the citation the sentence went to the NLI model, which scored low a value that is in the
    ledger. Here a stated value that is exactly a number of the cited ledger (`_minor` columns divided by 100,
    `_major` as they are, currency respected) supports the sentence; with no equal value, the sentence stays without
    evidence. `contradicted` only when the sentence names a single column and it holds another value. `None` when
    the sentence is not of this type (no currency value, or no ledger or FX evidence among the cited ones): it goes on
    to the NLI model. Only the numbers are checked; the rest of the sentence (status, dates) is not.
    """
    cited = [evidence_by_id[i] for i in claim.evidence_ids if i in evidence_by_id]
    structured = [e for e in cited if e.source_type in _LEDGER_SOURCES]
    if not structured or not has_currency_amount(claim.text):
        return None
    label, note = check_amounts_against_ledger(claim.text, [v for e in structured for v in ledger_values(e.content)])
    return Verdict(claim_id=claim.id, label=label, method="numeric", evidence_ids=[e.id for e in structured], note=note)


def check_rates(claim: Claim, evidence_by_id: Mapping[str, Evidence]) -> Verdict | None:
    """Checks by code a sentence that states a rate (`5.4931`), with no currency value, against the cited ledger or FX.

    An applied rate (`applied_rate`) or a reference rate (`rate`) is in the record, and the NLI model does not tell
    `5.4931` from `5.4932`. Every stated number must be exactly a number of the cited ledger, as in
    `check_ledger_amounts`. `None` when the sentence has no rate, when no ledger or FX evidence was cited, and when
    some other number in it is left unchecked: it goes on to the NLI model. Only the numbers are checked.
    """
    cited = [evidence_by_id[i] for i in claim.evidence_ids if i in evidence_by_id]
    structured = [e for e in cited if e.source_type in _LEDGER_SOURCES]
    if not structured or not has_rate(claim.text):
        return None
    checked = check_rates_against_ledger(claim.text, [v for e in structured for v in evidence_values(e.content)])
    if checked is None:
        return None
    label, note = checked
    return Verdict(claim_id=claim.id, label=label, method="numeric", evidence_ids=[e.id for e in structured], note=note)


# ---- coherence ----------------------------------------------------------------------------------


def _rows(content: str) -> list[dict[str, Any]]:
    """The rows of a JSON evidence, in any format the tools return.

    Accepts a list of objects, `rows`/`data` (`query_ledger` sends `columns` and `rows` as lists, which
    become objects), and nested objects (`get_ledger_record` carries `transaction`, `refunds`,
    `chargebacks`, `settlements`). Free text has no rows.
    """
    try:
        data = json.loads(content)
    except ValueError:
        return []
    return _flatten(data)


def _flatten(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [row for item in data for row in _flatten(item)]
    if not isinstance(data, dict):
        return []
    columns, raw_rows = data.get("columns"), data.get("rows")
    if isinstance(columns, list) and isinstance(raw_rows, list) and all(isinstance(r, list) for r in raw_rows):
        return [dict(zip(columns, r, strict=False)) for r in raw_rows]  # query_ledger columns and rows
    for key in ("rows", "data"):
        if key in data:
            return _flatten(data[key])
    nested = [row for value in data.values() if isinstance(value, (dict, list)) for row in _flatten(value)]
    return [data, *nested]


def _words(text: str) -> tuple[tuple[str, ...], bool]:
    tokens = re.findall(r"[a-z0-9_-]+", text.lower().replace("n't", " not"))
    return tuple(t for t in tokens if t not in _NEGATIONS), any(t in _NEGATIONS for t in tokens)


def check_coherence(result: InvestigationResult) -> Coherence:
    """Applies the coherence rules to the verdicts and to the rows the queries returned."""
    issues: list[CoherenceIssue] = []
    rows = [row for e in result.evidence for row in _rows(e.content)]

    for row in rows:
        keys = ("gross_minor", "refunds_minor", "fees_minor", "net_minor")
        if all(isinstance(row.get(k), int) for k in keys) and row["net_minor"] != (
            row["gross_minor"] - row["refunds_minor"] - row["fees_minor"]
        ):
            issues.append(
                CoherenceIssue(
                    rule="settlement_net",
                    message=f"{row.get('id', 'settlement')}: net differs from gross - refunds - fees.",
                )
            )
        if row.get("status") == "paid" and "payout_amount_minor" in row and row["payout_amount_minor"] is None:
            issues.append(
                CoherenceIssue(
                    rule="refund_payout",
                    message=f"{row.get('id', 'refund')}: refund paid with no payout amount.",
                )
            )

    transactions = {r["id"]: r for r in rows if str(r.get("id", "")).startswith("TX-") and "status" in r}
    for row in rows:
        tx = transactions.get(row.get("transaction_id"))
        if tx is None:
            continue
        if (
            "payout_amount_minor" in row
            and row.get("status") == "paid"
            and tx["status"] not in ("refunded", "partially_refunded")
        ):
            issues.append(
                CoherenceIssue(
                    rule="status_event", message=f"{tx['id']}: refund paid, but the transaction is {tx['status']}."
                )
            )
        if row.get("stage") in _OPEN_CHARGEBACK and tx["status"] not in ("disputed", "charged_back"):
            issues.append(
                CoherenceIssue(
                    rule="status_event", message=f"{tx['id']}: dispute open, but the transaction is {tx['status']}."
                )
            )

    supported_ids = {v.claim_id for v in result.verdicts if v.label == "supported"}
    supported = [c for c in result.claims if c.id in supported_ids]
    seen = {}
    for claim in supported:
        base, negated = _words(claim.text)
        other = seen.get(base)
        if other is not None and other[1] != negated:
            issues.append(
                CoherenceIssue(
                    rule="negation_pair",
                    message="A claim and its negation are both supported.",
                    claim_ids=[other[0], claim.id],
                )
            )
        seen[base] = (claim.id, negated)

    if result.recommended_action == "issue_refund" and not any(
        _DUPLICATE_OR_DISCREPANCY.search(c.text) for c in supported
    ):
        issues.append(
            CoherenceIssue(
                rule="action_support", message="A refund needs a supported claim of a duplicate or a discrepancy."
            )
        )
    for day, claim_ids in fx_dates_without_origin(result):
        issues.append(
            CoherenceIssue(
                rule="fx_date_origin",
                message=f"FX rate for a date with no origin in the ledger: {day}.",
                claim_ids=claim_ids,
            )
        )
    return Coherence(passed=not issues, issues=issues)


# ---- result -------------------------------------------------------------------------------------


def text_premise(claim: Claim, by_id: Mapping[str, Evidence], max_chars: int) -> str | None:
    """The premise the NLI model gets for the claim: the cited evidence as text, focused and truncated.

    `None` when no cited evidence is in the result.
    """
    cited = [by_id[i] for i in claim.evidence_ids if i in by_id]
    if not cited:
        return None
    text = "\n".join(render_premise(e.content) for e in cited)
    return focus_premise(text, claim.text)[:max_chars]


def _text_verdict(claim: Claim, by_id: Mapping[str, Evidence], nli: Nli, thresholds: Mapping[str, Any]) -> Verdict:
    premise = text_premise(claim, by_id, int(thresholds["max_premise_chars"]))
    if premise is None:
        return Verdict(
            claim_id=claim.id,
            label="not_enough_evidence",
            method="none",
            note="No cited evidence is in the result.",
        )
    scores = nli.predict(premise, claim.text)
    return Verdict(
        claim_id=claim.id,
        label=label_from_scores(scores, thresholds),
        method="nli",
        scores=NliScores(**scores),
        evidence_ids=[i for i in claim.evidence_ids if i in by_id],
    )


def verify_result(result: InvestigationResult, *, nli: Nli | None = None) -> InvestigationResult:
    """Gives each claim a verdict and returns a copy with coherence, missing information and human review.

    With no claims in the result, they are extracted from the answer and the evidence.

    Sets `requires_human_review` when there is a contradiction, when coherence fails or when the share of
    claims with no evidence goes over `unsupported_share_review`. A flag already set stays.
    """
    thresholds = load_thresholds()
    if not result.claims:  # the integrator delivers only the answer and the evidence: claims come from the text
        result = result.model_copy(update={"claims": extract_claims(result.answer, result.evidence)})
    by_id = {e.id: e for e in result.evidence}
    if nli is None:
        from ledgerlens.verify.nli import get_nli

        nli = get_nli()

    verdicts = [
        check_numeric(c, by_id)
        if c.kind == "numeric" or c.numeric is not None
        else check_ledger_amounts(c, by_id) or check_rates(c, by_id) or _text_verdict(c, by_id, nli, thresholds)
        for c in result.claims
    ]
    coherence = check_coherence(result.model_copy(update={"verdicts": verdicts}))

    unsupported = [c for c, v in zip(result.claims, verdicts, strict=True) if v.label == "not_enough_evidence"]
    missing = list(result.missing_information)
    for claim in unsupported:
        item = f"Missing evidence for: {claim.text}"
        if item not in missing:
            missing.append(item)
    for issue in coherence.issues:
        if issue.rule == "fx_date_origin" and issue.message not in missing:
            missing.append(issue.message)  # the date stays named: it is what the agent must look up in the ledger
    share = len(unsupported) / len(result.claims) if result.claims else 0.0
    review = (
        result.requires_human_review
        or any(v.label == "contradicted" for v in verdicts)
        or not coherence.passed
        or share > thresholds["unsupported_share_review"]
    )
    return result.model_copy(
        update={
            "verdicts": verdicts,
            "coherence": coherence,
            "missing_information": missing,
            "requires_human_review": review,
        }
    )
