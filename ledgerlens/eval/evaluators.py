"""Evaluators of the agent variants: correctness, groundedness and tool trajectory.

Why it exists: the evaluation's question is what each layer (tools, agent, verification) brings. Each
evaluator answers one part and returns `{"key", "score", "comment"}`, the format LangSmith reads:

- **correctness**: share of the expected facts that appear in the answer. It is code, not a model, because the
  fields are numbers and ids. Values are compared as `Decimal` after reading the thousands separator and the
  decimal point (`49.90`, `1,234.56`), the currency symbol and minor units (the fact `4990` matches `49.90`, and
  `29992.87` matches `2999287`); dates accept `mm/dd/yyyy` and spelled-out months; ids ignore case and `_`, `-`
  and spaces. A number never matches inside an id, a date or a larger number. The LLM judge, which evaluates the
  text explanation, only exists online (`explanation_judge`).
- **groundedness**: share of the answer's claims with a `supported` verdict from the verifier.
- **trajectory**: the `openevals` evaluators (`strict`, `unordered`, `subset`, `superset`) over the
  tools called, compared by name only. Calls in the same message compare as a group and hide the
  order, so the trace becomes one message per call. The modes above are exact. The
  `trajectory_equivalent_*` modes (`EQUIVALENT_MODES`) only swap in an equivalent tool when the case
  declares the group in `equivalent_tools` (see `dataset.py`); both numbers come out side by side.

A variant's output is a dictionary with `answer`, `trajectory` (messages in the OpenAI format) and `verdicts`
(the verdict labels). The reference carries `facts` and `trajectory`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from decimal import Decimal
from typing import Any

from openevals.trajectory.match import create_trajectory_match_evaluator

from ledgerlens.schemas import ToolCallRecord

TRAJECTORY_MODES = ("strict", "unordered", "subset", "superset")
EQUIVALENT_MODES = ("strict", "unordered")  # the modes in which the declared equivalence is reported
Evaluator = Callable[..., dict[str, Any]]


def calls_to_messages(calls: Sequence[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    """One assistant message per call, each followed by the tool message."""
    messages: list[dict[str, Any]] = []
    for index, (name, args) in enumerate(calls, start=1):
        call_id = f"call_{index}"
        messages.append(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}
                ],
            }
        )
        messages.append({"role": "tool", "tool_call_id": call_id, "content": ""})
    return messages


def trace_to_messages(trace: Sequence[ToolCallRecord]) -> list[dict[str, Any]]:
    """The investigation result's `tool_trace`, in step order."""
    return calls_to_messages([(record.tool, record.input) for record in trace])


def reference_messages(expected_tools: Sequence[str]) -> list[dict[str, Any]]:
    """The expected trajectory: names only, because the arguments do not count in the comparison."""
    return calls_to_messages([(name, {}) for name in expected_tools])


def _canonical_tools(messages: list[dict[str, Any]], groups: Sequence[Sequence[str]]) -> list[dict[str, Any]]:
    """The same messages with each tool of a group swapped for the group's first tool."""
    canonical = {name: group[0] for group in groups for name in group}
    out = []
    for message in messages:
        calls = message.get("tool_calls")
        if calls:
            message = {
                **message,
                "tool_calls": [
                    {
                        **c,
                        "function": {
                            **c["function"],
                            "name": canonical.get(c["function"]["name"], c["function"]["name"]),
                        },
                    }
                    for c in calls
                ],
            }
        out.append(message)
    return out


def trajectory_evaluator(mode: str, *, equivalent: bool = False) -> Evaluator:
    """The `openevals` trajectory evaluator in the requested mode, with the score as a number (1.0 or 0.0).

    With `equivalent=True` the tools of one group in `reference_outputs["equivalent_tools"]` count
    as the same; with no declared group the result is that of the exact mode. The score key changes, so both
    numbers can live side by side in the report.
    """
    if mode not in TRAJECTORY_MODES:
        raise ValueError(f"unknown trajectory mode '{mode}'; use one of {', '.join(TRAJECTORY_MODES)}")
    matcher = create_trajectory_match_evaluator(trajectory_match_mode=mode, tool_args_match_mode="ignore")  # type: ignore[arg-type]
    key = f"trajectory_equivalent_{mode}_match" if equivalent else f"trajectory_{mode}_match"

    def evaluate(*, outputs: dict[str, Any], reference_outputs: dict[str, Any], **_: Any) -> dict[str, Any]:
        used, expected = outputs["trajectory"], reference_outputs["trajectory"]
        if equivalent:
            groups = reference_outputs.get("equivalent_tools") or []
            used, expected = _canonical_tools(used, groups), _canonical_tools(expected, groups)
        result = matcher(outputs=used, reference_outputs=expected)
        return {"key": key, "score": 1.0 if result["score"] else 0.0, "comment": result.get("comment")}

    evaluate.__name__ = key
    return evaluate


_NUMBER_TOKEN = re.compile(r"(?<![\w-])\d+(?:[.,]\d+)*(?![\w-])")
_AMOUNT_FACT = re.compile(r"-?\d+(?:\.\d+)?")
_ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_CENT = Decimal("0.01")
_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def _amount_readings(token: str) -> set[Decimal]:
    """The value a number written in the answer has: the comma groups thousands, the period is the decimal point.

    `1,234.56` and `1234.56` read the same. A comma that does not group thousands (`1,2` in a list) is not a number,
    and neither is more than one period.
    """
    integer, _, fraction = token.partition(".")
    groups = integer.split(",")
    if "." in fraction or (len(groups) > 1 and (not 1 <= len(groups[0]) <= 3 or any(len(g) != 3 for g in groups[1:]))):
        return set()
    return {Decimal(token.replace(",", ""))}


def _matches_amount(answer: str, fact: str) -> bool:
    """The fact's value appears in the answer, in major or minor units, in any formatting."""
    expected = Decimal(fact)
    for match in _NUMBER_TOKEN.finditer(answer):
        token = match.group(0)
        for value in _amount_readings(token):
            if value == expected:
                return True
            # minor units on one side and major units on the other: only counts for the major side with exactly two
            # decimal places, because "80" in "80 transactions" is not 80 units of money
            if (
                "." not in fact
                and value == expected / 100
                and value.as_tuple().exponent == -2
                and re.search(r"\.\d{2}$", token)
            ):
                return True
            if (
                "." in fact
                and expected.as_tuple().exponent == -2
                and value == expected * 100
                and re.fullmatch(r"\d+", token)
                and value >= 100
            ):
                return True
    return False


def _matches_date(answer: str, fact: str) -> bool:
    """The date as ISO, as `mm/dd/yyyy` or spelled out (`November 9, 2026`, `9 November 2026`)."""
    year, month, day = _ISO_DATE.fullmatch(fact).groups()  # type: ignore[union-attr]
    name = _MONTHS[int(month) - 1]
    forms = [fact, f"{month}/{day}/{year}", f"{int(month)}/{int(day)}/{year}"]
    forms += [f"{name} {int(day)}, {year}", f"{int(day)} {name} {year}"]
    return any(re.search(rf"(?<![\w/-]){re.escape(form)}(?![\w/-])", answer, re.IGNORECASE) for form in forms)


def _matches_text(answer: str, fact: str) -> bool:
    """Id, status or text: ignores case and accepts `_`, `-` or a space where the fact has `_` or `-`."""
    pattern = "".join(r"[-_ ]" if ch in "-_" else re.escape(ch) for ch in fact)
    return re.search(rf"(?<![\w-]){pattern}(?![\w-])", answer, re.IGNORECASE) is not None


def _contains(answer: str, fact: str) -> bool:
    if _ISO_DATE.fullmatch(fact):
        return _matches_date(answer, fact)
    if _AMOUNT_FACT.fullmatch(fact):
        return _matches_amount(answer, fact)
    return _matches_text(answer, fact)


def correctness(*, outputs: dict[str, Any], reference_outputs: dict[str, Any], **_: Any) -> dict[str, Any]:
    """Share of the expected facts present in the answer."""
    facts = list(reference_outputs["facts"])
    answer = str(outputs.get("answer", ""))
    found = [fact for fact in facts if _contains(answer, fact)]
    missing = [fact for fact in facts if fact not in found]
    score = len(found) / len(facts) if facts else 0.0
    comment = "all facts present" if not missing else "missing: " + ", ".join(missing)
    return {"key": "correctness", "score": score, "comment": comment}


def groundedness(*, outputs: dict[str, Any], **_: Any) -> dict[str, Any]:
    """Share of the claims with a `supported` verdict."""
    labels = list(outputs.get("verdicts", []))
    if not labels:
        return {"key": "groundedness", "score": 0.0, "comment": "the answer has no verified claims"}
    supported = sum(label == "supported" for label in labels)
    return {
        "key": "groundedness",
        "score": supported / len(labels),
        "comment": f"{supported} of {len(labels)} supported",
    }


def verdict_match(*, outputs: dict[str, Any] | None, reference_outputs: dict[str, Any], **_: Any) -> dict[str, Any]:
    """1.0 if the verdict the verifier predicted is the expected one. No output (a failed run) scores 0.0."""
    predicted = (outputs or {}).get("verdict")
    expected = reference_outputs["verdict"]
    return {
        "key": "verdict_match",
        "score": 1.0 if predicted == expected else 0.0,
        "comment": f"{predicted} / {expected}",
    }


def verification_summary(pairs: Sequence[tuple[str | None, str]]) -> dict[str, Any]:
    """Verification set metrics from (predicted, expected) pairs.

    `contradiction_recall`: of the planted contradictions, how many the verifier marked `contradicted`.
    `false_positive_rate`: of the supported claims, how many it flagged as `contradicted`.
    """
    planted = [predicted for predicted, expected in pairs if expected == "contradicted"]
    supported = [predicted for predicted, expected in pairs if expected == "supported"]
    return {
        "cases": len(pairs),
        "accuracy": sum(p == e for p, e in pairs) / len(pairs) if pairs else 0.0,
        "contradiction_recall": sum(p == "contradicted" for p in planted) / len(planted) if planted else 0.0,
        "false_positive_rate": sum(p == "contradicted" for p in supported) / len(supported) if supported else 0.0,
        "planted": len(planted),
        "supported": len(supported),
    }


def offline_evaluators() -> list[Evaluator]:
    """The code evaluators: correctness, groundedness, the four trajectory modes and the two with equivalence."""
    return [
        correctness,
        groundedness,
        *(trajectory_evaluator(mode) for mode in TRAJECTORY_MODES),
        *(trajectory_evaluator(mode, equivalent=True) for mode in EQUIVALENT_MODES),
    ]


_JUDGE_PROMPT = (
    "You evaluate a payments analyst's explanation. Answer whether the explanation is clear, complete and "
    "consistent with the expected facts, without making up anything beyond them.\n\n"
    "<question>\n{inputs}\n</question>\n\n<answer>\n{outputs}\n</answer>\n\n"
    "<expected facts>\n{reference_outputs}\n</expected facts>"
)


def explanation_judge(model: Any) -> Evaluator:
    """LLM judge of the text explanation (online only). Numeric fields never go through it."""
    from openevals.llm import create_llm_as_judge

    judge = create_llm_as_judge(prompt=_JUDGE_PROMPT, judge=model, feedback_key="explanation", continuous=True)

    def evaluate(*, inputs: dict[str, Any], outputs: dict[str, Any], reference_outputs: dict[str, Any], **_: Any):
        return judge(inputs=inputs["question"], outputs=outputs["answer"], reference_outputs=reference_outputs["facts"])

    evaluate.__name__ = "explanation"
    return evaluate
