"""`calculate`: the agent's exact calculator for money, FX rates and fees.

Why it exists: a language model gets arithmetic wrong, above all with many decimal places, and a wrong
value in a payments report is worse than none. The project's rule is that no number
comes from the model: it picks the operation and passes the values as text, and this function does the math.

How the math is done
--------------------
- Everything uses `Decimal` (never `float`), with precision high enough that multiplying and dividing
  round nothing along the way.
- Rounding happens once, at the end, to `decimals` places, with round half to even
  (`ROUND_HALF_EVEN`, the same as the policy fees): 0.125 becomes 0.12 and 0.135 becomes 0.14.
- The result comes back as text with exactly `decimals` places (`"3.40"`, not `"3.4"`).

Inputs the tool refuses before calculating (`guard_inputs`): a money value that looks like it is in
minor units (`10000` with no decimal point, copied from an `amount_minor`) and, in `fx_gap_breakdown`, an applied
rate above the reference rate (the two roles swapped). Both errors come back as data, with what to
fix, because a real model made each one and the wrong math looks right. `compute` is still
only exact arithmetic; the refusal lives in the tool, which is what the model calls.

Operations (required keys in parentheses): `convert` (amount, rate), `difference` (a, b),
`percent_diff` (base, other), `implied_markup_pct` (reference_rate, applied_rate), `fee` (gross, percent,
fixed_per_item, items), `net_settlement` (gross, refunds, fees) and `fx_gap_breakdown` (units, charge_rate,
refund_reference_rate, refund_applied_rate).

`fx_gap_breakdown` explains why the refund in another currency came in lower than the payment. The gap
(`gap`) is the actual money difference (`charge - refund`, already rounded). It splits into
`markup` (what the merchant took from the reference rate on the refund day) and `rate_move` (how much the
rate moved between the payment and the refund). `markup` is computed directly and `rate_move` is the remainder,
so that `gap = rate_move + markup` always holds with the places shown.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Callable
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field

from ledgerlens.tools.envelope import error, invalid_input, ok

DESCRIPTION = (
    "Do exact arithmetic for money, rates and fees. Never do arithmetic yourself: call this tool. "
    "Choose an operation and pass the named values as decimal strings. Operations: convert (amount, rate), "
    "difference (a, b), percent_diff (base, other), implied_markup_pct (reference_rate, applied_rate), "
    "fee (gross, percent, fixed_per_item, items), net_settlement (gross, refunds, fees), "
    "fx_gap_breakdown (units, charge_rate, refund_reference_rate, refund_applied_rate). "
    "All results use exact decimal math and round half to even."
)

# Digits only, with optional sign and point: no exponent ("1e5"), no NaN, no space, no comma.
_NUMBER = re.compile(r"^-?[0-9]+(\.[0-9]+)?$")
MAX_NUMBER_CHARS = 64
# 64 digits times 64 digits fit with room to spare: multiplication never rounds on its own.
PRECISION = 200


class CalcError(Exception):
    """An expected calculator error, with the contract code."""

    def __init__(self, code: str, message: str, retryable: bool) -> None:
        super().__init__(message)
        self.code, self.retryable = code, retryable


def _divide(numerator: Decimal, denominator: Decimal, name: str) -> Decimal:
    if denominator == 0:
        raise CalcError("DIVISION_BY_ZERO", f"'{name}' is zero, so the division is undefined", False)
    return numerator / denominator


def _round(value: Decimal, decimals: int) -> str:
    rounded = value.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_EVEN)
    if rounded == 0:
        rounded = abs(rounded)  # never "-0.00"
    return format(rounded, "f")


# Each operation gets the values already converted and returns (result, formula). The result is an
# unrounded Decimal (or a dictionary of strings already rounded, for the FX gap).


def _convert(v: dict[str, Decimal], d: int, raw: dict[str, str]):
    value = v["amount"] * v["rate"]
    return value, f"{raw['amount']} * {raw['rate']}"


def _difference(v: dict[str, Decimal], d: int, raw: dict[str, str]):
    return v["a"] - v["b"], f"{raw['a']} - {raw['b']}"


def _percent_diff(v: dict[str, Decimal], d: int, raw: dict[str, str]):
    value = _divide(v["base"] - v["other"], v["base"], "base") * 100
    return value, f"({raw['base']} - {raw['other']}) / {raw['base']} * 100"


def _implied_markup_pct(v: dict[str, Decimal], d: int, raw: dict[str, str]):
    ratio = _divide(v["applied_rate"], v["reference_rate"], "reference_rate")
    return (1 - ratio) * 100, f"(1 - {raw['applied_rate']} / {raw['reference_rate']}) * 100"


def _fee(v: dict[str, Decimal], d: int, raw: dict[str, str]):
    value = v["gross"] * v["percent"] / 100 + v["fixed_per_item"] * v["items"]
    return value, f"{raw['gross']} * {raw['percent']} / 100 + {raw['fixed_per_item']} * {raw['items']}"


def _net_settlement(v: dict[str, Decimal], d: int, raw: dict[str, str]):
    return v["gross"] - v["refunds"] - v["fees"], f"{raw['gross']} - {raw['refunds']} - {raw['fees']}"


def _fx_gap_breakdown(v: dict[str, Decimal], d: int, raw: dict[str, str]):
    charge = Decimal(_round(v["units"] * v["charge_rate"], d))
    refund = Decimal(_round(v["units"] * v["refund_applied_rate"], d))
    markup = Decimal(_round(v["units"] * (v["refund_reference_rate"] - v["refund_applied_rate"]), d))
    gap = charge - refund
    pct = (1 - _divide(v["refund_applied_rate"], v["refund_reference_rate"], "refund_reference_rate")) * 100
    parts = {
        "charge": _round(charge, d),
        "refund": _round(refund, d),
        "gap": _round(gap, d),
        "rate_move": _round(gap - markup, d),  # the remainder: so gap = rate_move + markup always
        "markup": _round(markup, d),
        "markup_pct": _round(pct, d),
    }
    formula = (
        f"charge = {raw['units']} * {raw['charge_rate']}; refund = {raw['units']} * {raw['refund_applied_rate']}; "
        f"gap = charge - refund; markup = {raw['units']} * ({raw['refund_reference_rate']} - "
        f"{raw['refund_applied_rate']}); rate_move = gap - markup; "
        f"markup_pct = (1 - {raw['refund_applied_rate']} / {raw['refund_reference_rate']}) * 100"
    )
    return parts, formula


Operation = Callable[[dict[str, Decimal], int, dict[str, str]], tuple[Any, str]]

OPERATIONS: dict[str, tuple[tuple[str, ...], Operation]] = {
    "convert": (("amount", "rate"), _convert),
    "difference": (("a", "b"), _difference),
    "percent_diff": (("base", "other"), _percent_diff),
    "implied_markup_pct": (("reference_rate", "applied_rate"), _implied_markup_pct),
    "fee": (("gross", "percent", "fixed_per_item", "items"), _fee),
    "net_settlement": (("gross", "refunds", "fees"), _net_settlement),
    "fx_gap_breakdown": (
        ("units", "charge_rate", "refund_reference_rate", "refund_applied_rate"),
        _fx_gap_breakdown,
    ),
}


def compute(operation: str, values: dict[str, str], decimals: int = 2) -> tuple[str | dict[str, str], str]:
    """Does the math. Returns (result, formula) or raises `CalcError`."""
    if operation not in OPERATIONS:
        known = ", ".join(OPERATIONS)
        raise CalcError("UNKNOWN_OPERATION", f"unknown operation '{operation}'; use one of {known}", False)
    required, function = OPERATIONS[operation]
    missing = [key for key in required if key not in values]
    if missing:
        raise CalcError("MISSING_VALUE", f"missing value(s) for {operation}: {', '.join(missing)}", True)
    for key in required:
        text = values[key]
        if len(text) > MAX_NUMBER_CHARS or not _NUMBER.match(text):
            shown = text[:20]
            message = f"'{key}' must be a plain decimal string such as '12.50', got {shown!r}"
            raise CalcError("INVALID_NUMBER", message, True)

    numbers = {key: Decimal(values[key]) for key in required}
    raw = {key: values[key] for key in required}
    with localcontext() as context:
        context.prec = PRECISION
        result, formula = function(numbers, decimals, raw)
        if isinstance(result, dict):
            return result, formula
        rounded = _round(result, decimals)
    return rounded, f"{formula} = {rounded}"


# Money fields (major units, such as "100.00") of each operation. Rates and percentages are left out.
MONEY_FIELDS: dict[str, tuple[str, ...]] = {
    "convert": ("amount",),
    "fee": ("gross",),
    "net_settlement": ("gross", "refunds", "fees"),
    "fx_gap_breakdown": ("units",),
}
# A money value with no decimal point and this many digits or more looks like `amount_minor` (10000 = 100.00).
MINOR_UNITS_DIGITS = 4


def guard_inputs(operation: str, values: dict[str, str]) -> None:
    """Refuses the incoherent input a real model sent. Raises `CalcError`; does no math.

    Runs only over values that exist and are well written; an unknown operation, a missing value, a badly written
    number and division by zero are `compute` errors.
    """
    for field in MONEY_FIELDS.get(operation, ()):
        text = values.get(field, "")
        digits = text.lstrip("-")
        well_formed = len(text) <= MAX_NUMBER_CHARS and _NUMBER.match(text)  # a badly written number is compute's
        if well_formed and digits.isdigit() and len(digits) >= MINOR_UNITS_DIGITS:
            major = format(Decimal(text) / 100, ".2f")
            message = (
                f"'{field}' is {text}, with no decimal point: that looks like minor units (the ledger's amount_minor). "
                f"Money here is in major units: divide by 100 and pass '{major}'. If {text} really is a major-unit "
                f"amount, write it with decimals, '{text}.00'."
            )
            raise CalcError("SUSPECTED_MINOR_UNITS", message, True)
    if operation == "fx_gap_breakdown" and {"refund_reference_rate", "refund_applied_rate"} <= values.keys():
        reference, applied = values["refund_reference_rate"], values["refund_applied_rate"]
        numbers = [value for value in (reference, applied) if len(value) <= MAX_NUMBER_CHARS and _NUMBER.match(value)]
        # a zero reference is division by zero, a compute error; here the comparison runs only with a real reference
        if len(numbers) == 2 and Decimal(reference) > 0 and Decimal(applied) > Decimal(reference):
            message = (
                f"refund_applied_rate ({applied}) is above refund_reference_rate ({reference}), so the two look "
                "swapped. refund_reference_rate is the market reference rate on the refund date (get_reference_fx); "
                "refund_applied_rate is the rate the acquirer actually used on the refund (from the ledger), which "
                "is never above it."
            )
            raise CalcError("SWAPPED_RATES", message, True)


# What the model reads about `values`: units and the role of each rate. The tool description stays as it is
# (it matches docs/contracts/tools.md); this text goes into the argument schema.
VALUES_DESCRIPTION = (
    "Named values as decimal strings. Money is always in MAJOR units written with a decimal point, such as "
    '"100.00": the ledger stores amount_minor, so amount_minor 10000 is "100.00", never "10000". Rates are '
    'decimal strings such as "5.6339". For fx_gap_breakdown: units = the amount paid, in major units of the '
    "charge currency; charge_rate = the rate that converted the charge; refund_reference_rate = the market "
    "reference rate on the REFUND date (from get_reference_fx, not the charge date); refund_applied_rate = the rate "
    "the acquirer actually applied to the refund (from the ledger), never above refund_reference_rate. For "
    "implied_markup_pct: reference_rate = market reference rate, applied_rate = rate the acquirer applied. For "
    "convert, fee and net_settlement every money value is in major units."
)


class CalculateInput(BaseModel):
    """Tool input. `operation` is free text (not a `Literal`) so a wrong name comes back
    as UNKNOWN_OPERATION, data the agent reads, and not as a schema error."""

    model_config = ConfigDict(extra="forbid")

    operation: str = Field(max_length=40, description="One of the operations listed in the tool description")
    values: dict[str, str] = Field(description=VALUES_DESCRIPTION)
    decimals: int = Field(default=2, ge=0, le=6)


def build_calculate_tool() -> StructuredTool:
    """Builds the tool. Each tool has its own `calc:<n>` counter, which only counts successes."""
    counter = itertools.count(1)

    def calculate(operation: str, values: dict[str, str], decimals: int = 2) -> dict[str, Any]:
        try:
            guard_inputs(operation, values)
            result, formula = compute(operation, values, decimals)
        except CalcError as failure:
            return error(failure.code, str(failure), failure.retryable)
        return ok([f"calc:{next(counter)}"], {"operation": operation, "result": result, "formula": formula})

    return StructuredTool.from_function(
        func=calculate,
        name="calculate",
        description=DESCRIPTION,
        args_schema=CalculateInput,
        handle_validation_error=invalid_input,
    )
