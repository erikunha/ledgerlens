"""`calculate`: exact arithmetic of money, rates and fees with `Decimal`, rounding half to even.

The property tests compare the tool with a second calculation done with `Fraction` (exact rationals),
with no `float` at all: if both agree on hundreds of inputs drawn with a fixed seed, the tool loses no
precision.
"""

from __future__ import annotations

import json
import random
import re
from decimal import ROUND_HALF_EVEN, Decimal
from fractions import Fraction

import pytest

from ledgerlens.tools.calculator import OPERATIONS, build_calculate_tool, compute

EVIDENCE = re.compile(r"^(sql|api|policy|fx|calc|case):.+$")
NUMBER = re.compile(r"^-?[0-9]+(\.[0-9]+)?$")


def run(operation: str, decimals: int = 2, **values: str) -> dict:
    return build_calculate_tool().invoke({"operation": operation, "values": values, "decimals": decimals})


def result_of(operation: str, decimals: int = 2, **values: str):
    answer = run(operation, decimals, **values)
    assert answer["ok"], answer
    return answer["data"]["result"]


def code_of(operation: str, **values: object) -> str:
    answer = build_calculate_tool().invoke({"operation": operation, "values": values})
    assert answer["ok"] is False, answer
    return answer["error"]["code"]


# --- each operation ---------------------------------------------------------------------------


def test_convert() -> None:
    assert result_of("convert", amount="100.00", rate="5.6339") == "563.39"


def test_difference() -> None:
    assert result_of("difference", a="566.79", b="549.31") == "17.48"
    assert result_of("difference", a="1.00", b="2.50") == "-1.50"


def test_percent_diff() -> None:
    assert result_of("percent_diff", base="100", other="97.5") == "2.50"
    assert result_of("percent_diff", base="200", other="250") == "-25.00"


def test_implied_markup_pct() -> None:
    assert result_of("implied_markup_pct", reference_rate="5.6339", applied_rate="5.4931") == "2.50"
    assert result_of("implied_markup_pct", 4, reference_rate="5.6339", applied_rate="5.4931") == "2.4992"


def test_fee() -> None:
    assert result_of("fee", gross="10000.00", percent="2.9", fixed_per_item="15.00", items="2") == "320.00"
    assert result_of("fee", gross="0", percent="2.9", fixed_per_item="15.00", items="0") == "0.00"


def test_net_settlement() -> None:
    assert result_of("net_settlement", gross="1000.00", refunds="150.25", fees="29.00") == "820.75"


def test_the_s01_breakdown_matches_the_worked_example() -> None:
    answer = run(
        "fx_gap_breakdown",
        units="100.00",
        charge_rate="5.6679",
        refund_reference_rate="5.6339",
        refund_applied_rate="5.4931",
    )
    assert answer["ok"] and answer["evidence_ids"] == ["calc:1"]
    assert answer["data"]["operation"] == "fx_gap_breakdown"
    assert answer["data"]["result"] == {
        "charge": "566.79",
        "refund": "549.31",
        "gap": "17.48",
        "rate_move": "3.40",
        "markup": "14.08",
        "markup_pct": "2.50",
    }


def test_every_declared_operation_is_tested_here() -> None:
    assert set(OPERATIONS) == {
        "convert", "difference", "percent_diff", "implied_markup_pct", "fee", "net_settlement", "fx_gap_breakdown",
    }  # fmt: skip


# --- rounding --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("amount", "decimals", "expected"),
    [
        ("0.125", 2, "0.12"),  # a tie goes to the even digit (2)
        ("0.135", 2, "0.14"),  # a tie goes to the even digit (4)
        ("0.145", 2, "0.14"),
        ("2.5", 0, "2"),
        ("3.5", 0, "4"),
        ("-0.125", 2, "-0.12"),
        ("14.5", 0, "14"),  # the fees policy example: 14.5 cents become 14
        ("43.5", 0, "44"),
        ("1.0000005", 6, "1.000000"),
        ("1.0000015", 6, "1.000002"),
    ],
)
def test_rounding_is_half_to_even(amount: str, decimals: int, expected: str) -> None:
    assert result_of("convert", decimals, amount=amount, rate="1") == expected


def test_a_tiny_negative_result_is_not_minus_zero() -> None:
    assert result_of("convert", 2, amount="-0.001", rate="1") == "0.00"


def test_the_result_has_exactly_the_requested_decimals() -> None:
    assert result_of("convert", 0, amount="10", rate="3") == "30"
    assert result_of("convert", 6, amount="10", rate="3") == "30.000000"


def test_precision_is_not_lost_before_the_final_rounding() -> None:
    # repeated 1/3: rounding halfway through would give another last digit.
    assert result_of("percent_diff", 6, base="3", other="2") == "33.333333"


# --- errors as data ---------------------------------------------------------------------------


def test_errors_are_data_with_code_message_and_retryable() -> None:
    answer = run("nope", a="1")
    assert answer == {
        "ok": False,
        "error": {"code": "UNKNOWN_OPERATION", "message": answer["error"]["message"], "retryable": False},
    }
    assert "convert" in answer["error"]["message"]


def test_a_missing_value_names_the_key() -> None:
    answer = run("convert", amount="1")
    assert answer["error"]["code"] == "MISSING_VALUE" and answer["error"]["retryable"] is True
    assert "rate" in answer["error"]["message"]


@pytest.mark.parametrize("bad", ["abc", "1e5", "NaN", "Infinity", "", " 1", "1,5", "+1", "1.", ".5", "0x10", "1" * 100])
def test_a_malformed_number_is_invalid(bad: str) -> None:
    answer = build_calculate_tool().invoke({"operation": "convert", "values": {"amount": bad, "rate": "1"}})
    assert answer["error"]["code"] == "INVALID_NUMBER" and answer["error"]["retryable"] is True


@pytest.mark.parametrize(
    ("operation", "values"),
    [
        ("percent_diff", {"base": "0", "other": "5"}),
        ("implied_markup_pct", {"reference_rate": "0", "applied_rate": "5"}),
        (
            "fx_gap_breakdown",
            {"units": "1", "charge_rate": "1", "refund_reference_rate": "0", "refund_applied_rate": "1"},
        ),
    ],
)
def test_division_by_zero_is_reported(operation: str, values: dict) -> None:
    answer = build_calculate_tool().invoke({"operation": operation, "values": values})
    assert answer["error"]["code"] == "DIVISION_BY_ZERO" and answer["error"]["retryable"] is False


def test_a_number_given_as_a_json_number_is_refused_before_any_work() -> None:
    answer = build_calculate_tool().invoke({"operation": "convert", "values": {"amount": 1.5, "rate": "2"}})
    assert "INVALID_INPUT" in str(answer)
    assert "INVALID_INPUT" in str(build_calculate_tool().invoke({"operation": "convert", "values": {}, "decimals": 7}))


# --- inconsistent inputs, refused before the arithmetic -------------------------------------------
# A real defect (gpt-4.1-mini, 2 of 8 S01 runs): the model copied `amount_minor` (10000) into `units` without
# dividing by 100, and the result came out 100 times larger. In 3 of 8 `refund_reference_rate` was the rate of
# the charge date. A sum with a wrong value looks right, so the tool refuses what is inconsistent.

# Each money field, per operation, with the rest of the input consistent.
MONEY_FIELDS = {
    "convert": ({"amount": "100.00", "rate": "5.6339"}, ["amount"]),
    "fee": ({"gross": "100.00", "percent": "2.9", "fixed_per_item": "15.00", "items": "2"}, ["gross"]),
    "net_settlement": ({"gross": "100.00", "refunds": "1.00", "fees": "2.00"}, ["gross", "refunds", "fees"]),
    "fx_gap_breakdown": (
        {
            "units": "100.00",
            "charge_rate": "5.6679",
            "refund_reference_rate": "5.6339",
            "refund_applied_rate": "5.4931",
        },
        ["units"],
    ),
}
MONEY_CASES = [(op, field) for op, (_, fields) in MONEY_FIELDS.items() for field in fields]


@pytest.mark.parametrize(("operation", "field"), MONEY_CASES)
def test_an_amount_that_looks_like_minor_units_is_refused_with_the_fix(operation: str, field: str) -> None:
    values = {**MONEY_FIELDS[operation][0], field: "10000"}
    answer = build_calculate_tool().invoke({"operation": operation, "values": values})
    assert answer["ok"] is False and answer["error"]["code"] == "SUSPECTED_MINOR_UNITS"
    assert answer["error"]["retryable"] is True
    message = answer["error"]["message"]
    assert f"'{field}'" in message and "minor units" in message and "'100.00'" in message


def test_the_minor_units_guard_has_an_exact_boundary_and_an_escape() -> None:
    values = MONEY_FIELDS["convert"][0]
    ok_999 = build_calculate_tool().invoke({"operation": "convert", "values": {**values, "amount": "999"}})
    assert ok_999["ok"] and ok_999["data"]["result"] == "5628.27"  # three digits: still an amount in units
    assert code_of("convert", amount="1000", rate="2") == "SUSPECTED_MINOR_UNITS"  # four digits with no point
    escaped = build_calculate_tool().invoke({"operation": "convert", "values": {**values, "amount": "10000.00"}})
    assert escaped["ok"] and escaped["data"]["result"] == "56339.00"  # with a decimal point, 10000.00 really is money


def test_a_rate_is_never_mistaken_for_an_amount() -> None:
    answer = build_calculate_tool().invoke({"operation": "convert", "values": {"amount": "5.00", "rate": "12000"}})
    assert answer["ok"] and answer["data"]["result"] == "60000.00"


def test_a_refund_rate_above_the_reference_means_the_roles_are_swapped() -> None:
    values = {**MONEY_FIELDS["fx_gap_breakdown"][0], "refund_reference_rate": "5.4931", "refund_applied_rate": "5.6339"}
    answer = build_calculate_tool().invoke({"operation": "fx_gap_breakdown", "values": values})
    assert answer["ok"] is False and answer["error"]["code"] == "SWAPPED_RATES"
    assert answer["error"]["retryable"] is True
    assert "refund_reference_rate" in answer["error"]["message"] and "refund_applied_rate" in answer["error"]["message"]


def test_equal_reference_and_applied_rates_mean_no_markup_and_are_accepted() -> None:
    values = {**MONEY_FIELDS["fx_gap_breakdown"][0], "refund_applied_rate": "5.6339"}
    answer = build_calculate_tool().invoke({"operation": "fx_gap_breakdown", "values": values})
    assert answer["ok"] and answer["data"]["result"]["markup"] == "0.00"


# --- format, evidence, description -----------------------------------------------------------


def test_the_formula_shows_the_values() -> None:
    formula = run("convert", amount="100.00", rate="5.6339")["data"]["formula"]
    assert "100.00" in formula and "5.6339" in formula and "563.39" in formula


def test_the_envelope_and_the_evidence_ids_count_successful_calls() -> None:
    tool = build_calculate_tool()
    first = tool.invoke({"operation": "difference", "values": {"a": "2", "b": "1"}})
    failed = tool.invoke({"operation": "difference", "values": {"a": "2"}})
    second = tool.invoke({"operation": "difference", "values": {"a": "3", "b": "1"}})
    assert set(first) == {"ok", "evidence_ids", "data"} and set(first["data"]) == {"operation", "result", "formula"}
    assert [first["evidence_ids"], second["evidence_ids"]] == [["calc:1"], ["calc:2"]]
    assert failed["ok"] is False and set(failed) == {"ok", "error"}
    assert all(EVIDENCE.match(e) for e in first["evidence_ids"])


def test_the_answer_is_json_safe_and_has_no_floats() -> None:
    answer = run("convert", amount="1.10", rate="3")
    assert json.loads(json.dumps(answer)) == answer
    assert isinstance(answer["data"]["result"], str) and NUMBER.match(answer["data"]["result"])


def test_the_tool_is_described_for_the_model() -> None:
    tool = build_calculate_tool()
    assert tool.name == "calculate"
    assert "Never do arithmetic yourself" in tool.description
    for operation in OPERATIONS:
        assert operation in tool.description
    assert set(tool.args) == {"operation", "values", "decimals"}
    assert tool.args["decimals"]["default"] == 2


def test_the_values_argument_tells_the_model_the_units_and_the_role_of_each_rate() -> None:
    # The tool description is fixed (docs/contracts/tools.md repeats it); what the model reads about units goes here.
    text = build_calculate_tool().args["values"]["description"]
    for needed in ("MAJOR units", "amount_minor", "REFUND date", "never above refund_reference_rate"):
        assert needed in text, needed


# --- properties, compared with exact rationals ------------------------------------------------


def decimal_text(rng: random.Random, places: int, low: int = 0, high: int = 10**7) -> str:
    return format(Decimal(rng.randint(low, high)).scaleb(-places), "f")


def exact(value: str) -> Fraction:
    return Fraction(Decimal(value))


def half_even(fraction: Fraction, places: int) -> str:
    """Rounds a rational to `places` places, half to even, without going through float."""
    scaled = fraction * 10**places
    floor = scaled.numerator // scaled.denominator
    rest = scaled - floor
    rounded = floor + (1 if rest > Fraction(1, 2) or (rest == Fraction(1, 2) and floor % 2 == 1) else 0)
    text = format(Decimal(rounded).scaleb(-places), "f")
    return text if rounded != 0 else format(Decimal(0).scaleb(-places), "f") if places else "0"


@pytest.mark.parametrize("seed", range(5))
def test_property_results_equal_the_exact_rational_computation(seed: int) -> None:
    rng = random.Random(seed)
    for _ in range(60):
        places = rng.randint(0, 6)
        a, b = decimal_text(rng, rng.randint(0, 6)), decimal_text(rng, rng.randint(0, 6), 1)
        percent, fixed = decimal_text(rng, 2, 0, 1500), decimal_text(rng, 2)
        items = str(rng.randint(0, 20))
        cases = {
            "convert": ({"amount": a, "rate": b}, exact(a) * exact(b)),
            "difference": ({"a": a, "b": b}, exact(a) - exact(b)),
            "percent_diff": ({"base": b, "other": a}, (exact(b) - exact(a)) / exact(b) * 100),
            "implied_markup_pct": ({"reference_rate": b, "applied_rate": a}, (1 - exact(a) / exact(b)) * 100),
            "fee": (
                {"gross": a, "percent": percent, "fixed_per_item": fixed, "items": items},
                exact(a) * exact(percent) / 100 + exact(fixed) * exact(items),
            ),
            "net_settlement": ({"gross": a, "refunds": b, "fees": fixed}, exact(a) - exact(b) - exact(fixed)),
        }
        for operation, (values, expected) in cases.items():
            assert compute(operation, values, places)[0] == half_even(expected, places), (operation, values, places)


@pytest.mark.parametrize("seed", range(5))
def test_property_the_gap_breakdown_adds_up(seed: int) -> None:
    rng = random.Random(100 + seed)
    for _ in range(80):
        places = 2
        units = decimal_text(rng, 2, 1)
        reference = decimal_text(rng, 4, 10_000, 90_000)
        applied = format(Decimal(reference) * Decimal(rng.randint(9_500, 10_000)) / 10_000, ".4f")
        charge_rate = decimal_text(rng, 4, 10_000, 90_000)
        result, _ = compute(
            "fx_gap_breakdown",
            {
                "units": units,
                "charge_rate": charge_rate,
                "refund_reference_rate": reference,
                "refund_applied_rate": applied,
            },
            places,
        )
        keys = ("charge", "refund", "gap", "rate_move", "markup")
        charge, refund, gap, move, markup = (Decimal(result[k]) for k in keys)
        assert gap == move + markup  # the identity holds with the places shown
        assert gap == charge - refund  # and the gap is the real money difference
        assert charge == Decimal(half_even(exact(units) * exact(charge_rate), places))
        assert refund == Decimal(half_even(exact(units) * exact(applied), places))
        assert markup == Decimal(half_even(exact(units) * (exact(reference) - exact(applied)), places))


def test_the_rounding_mode_is_half_even_in_the_decimal_context() -> None:
    assert Decimal("0.125").quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN) == Decimal("0.12")
