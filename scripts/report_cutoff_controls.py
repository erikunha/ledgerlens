"""Replay fixed date and currency families to measure verifier transfer and unsafe releases."""

import json
from collections import Counter
from datetime import date
from pathlib import Path

from ledgerlens.tools.calculator import PREVIOUS_BUSINESS_DAY, compute
from ledgerlens.verify.checks import verify_result
from ledgerlens.verify.nli import StubNli
from scripts.report_cutoff_receipts import reconstruct_archived_case

ROOT = Path(__file__).resolve().parents[1]
CONTROL_FILE = ROOT / "data/eval/cutoff_receipt_controls.json"
ARCHIVE = ROOT / "data/eval/reports/policy-journeys-openai.json"
CURRENCIES = ("USD", "EUR")


def _long_date(iso):
    day = date.fromisoformat(iso)
    return f"{day:%A}, {day:%B} {day.day}, {day.year}"


def run():
    controls = json.loads(CONTROL_FILE.read_text())
    prototype = next(case for case in json.loads(ARCHIVE.read_text())["cases"] if case["case_id"] == "july-cutoff-usd")
    base = reconstruct_archived_case(prototype)
    rows = []
    paraphrases = []
    for family in controls["families"]:
        deadline = family["deadline"]
        for currency in CURRENCIES:
            cutoff = family[currency]
            for condition, expected in controls["conditions"].items():
                receipt_currency = (
                    next(c for c in CURRENCIES if c != currency) if condition == "wrong-currency" else currency
                )
                inputs = {"date": deadline, "currency": receipt_currency}
                value, formula = compute(PREVIOUS_BUSINESS_DAY, inputs)
                if value != family[receipt_currency]:
                    raise ValueError(f"Calendar differs from fixed label for {family['id']} / {receipt_currency}.")
                question = (
                    prototype["question"].replace("USD", currency).replace("Monday, July 7, 2025", _long_date(deadline))
                )
                answer = (
                    prototype["answer"].replace("USD", currency).replace("Monday, July 7, 2025", _long_date(deadline))
                )
                stated = deadline if condition == "altered-date" else cutoff
                answer = answer.replace("Thursday, July 3, 2025", _long_date(stated))
                if condition == "false-promise":
                    answer += " Acme guarantees the dispute will be won."
                evidence = [entry for entry in base.evidence if entry.source_type != "calc"]
                trace = [entry for entry in base.tool_trace if entry.tool != "calculate"]
                if condition != "missing-receipt":
                    calc = next(entry for entry in base.evidence if entry.source_type == "calc")
                    data = {"operation": PREVIOUS_BUSINESS_DAY, "result": value, "formula": formula}
                    evidence.append(calc.model_copy(update={"content": json.dumps(data), "ref": formula}))
                    call = next(entry for entry in base.tool_trace if entry.tool == "calculate")
                    trace.append(
                        call.model_copy(update={"input": {"operation": PREVIOUS_BUSINESS_DAY, "values": inputs}})
                    )
                case = base.model_copy(
                    update=dict(
                        question=question,
                        answer=answer,
                        claims=[],
                        evidence=evidence,
                        tool_trace=trace,
                        requires_human_review=condition == "prior-review",
                    )
                )
                row = dict(family=family["id"], currency=currency, condition=condition, expected_review=expected)
                for name, enabled in (("baseline", False), ("candidate", True)):
                    row[name] = verify_result(case, nli=StubNli(), use_cutoff_receipts=enabled).requires_human_review
                rows.append(row)
                if condition == "valid":
                    alternative = case.model_copy(
                        update={
                            "question": (
                                f"The dispute deadline is {_long_date(deadline)}. We settle in {currency}. "
                                "When is our evidence submission due?"
                            )
                        }
                    )
                    paraphrases.append(
                        {
                            "family": family["id"],
                            "currency": currency,
                            "candidate_review": verify_result(
                                alternative, nli=StubNli(), use_cutoff_receipts=True
                            ).requires_human_review,
                        }
                    )
    totals = {}
    for name in ("baseline", "candidate"):
        failures = Counter(
            "unsafe_release" if row["expected_review"] else "unnecessary_review"
            for row in rows
            if row[name] != row["expected_review"]
        )
        totals[name] = {key: failures[key] for key in ("unsafe_release", "unnecessary_review")}
    return {
        "families": len(controls["families"]),
        "cases": len(rows),
        "errors": totals,
        "rows": rows,
        "paraphrase_probes": paraphrases,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
