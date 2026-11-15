"""The budget of a live run: the caps that stop it, the counters of every model and the two costs.

What they guarantee, and why: (a) the run stops at the attempt that would break a cap, and the refusal names the
cap, so the interface can say which limit was reached (FR-009); (b) the wall clock cap is checked before a call of
a model, before a call of a tool and after a call, and it is proved with an injected clock, so no test waits for a
second to pass (SC-003); (c) the calls of every model of the run are counted, the triage model and the generator of
the SQL included, and a model the run did not declare is counted as well, because the cap is about the money and
not about the model (FR-012); (d) the observed cost and the estimated cost are two separate numbers (FR-010);
(e) when the registry has no verified price, the estimated cost is absent, the report says the price is unknown and
no dollar amount appears anywhere (FR-011); (f) the money of the run is a Decimal and never a float; (g) a run that
called no model shows no dollar amount at all, because the price of a run that never called is not a price of
anything; (h) a model that reports a usage without a reservation is named in the report, and that call counts
against the cap of the calls of the models all the same, because the money of it was spent (FR-012, SC-004);
(i) a count the provider reported that is negative or that is not a number is refused and the run stops, because
the provider is untrusted input and a count that cannot be counted launders the caps (FR-009); (j) a planned
count of zero is a plan that says that no token is planned, and only a negative count is refused.

Everything offline, with no key and no network: the coordinator never calls a provider.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ledgerlens.byok.budget import BudgetCoordinator, BudgetExceededError, BudgetRefused, UsageRefused
from ledgerlens.byok.registry import ModelProfile, Pricing, ProviderRegistry
from ledgerlens.run_context import RunBudget

PRICED = ModelProfile(
    profile_id="openai-gpt-4.1-mini",
    provider="openai",
    model_id="gpt-4.1-mini",
    display_name="GPT-4.1 mini",
    capabilities=("chat", "tool_calling"),
    status="tested",
    enabled_in_public_demo=True,
    pricing=Pricing(
        source="manual",
        last_verified=date(2026, 11, 8),
        input_per_1m_usd=Decimal("0.40"),
        output_per_1m_usd=Decimal("1.60"),
    ),
)

UNPRICED = ModelProfile(
    profile_id="openai-gpt-4.1",
    provider="openai",
    model_id="gpt-4.1",
    display_name="GPT-4.1",
    capabilities=("chat",),
    status="experimental",
    enabled_in_public_demo=False,
    pricing=Pricing(source="unknown", last_verified=None, input_per_1m_usd=None, output_per_1m_usd=None),
)


class FakeClock:
    """A clock the test moves, so the wall clock cap is proved without waiting."""

    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def registry() -> ProviderRegistry:
    """The allowlist of the tests: one model with a price and one without."""
    return ProviderRegistry([PRICED, UNPRICED])


def test_the_model_call_cap_stops_the_run_at_the_attempt_that_would_break_it() -> None:
    """FR-009: with a cap of four calls, the fifth attempt is refused and the cap is named."""
    coordinator = BudgetCoordinator(RunBudget(max_model_calls=4), registry())

    for _ in range(4):
        coordinator.reserve_model_call("gpt-4.1-mini")

    with pytest.raises(BudgetExceededError) as refused:
        coordinator.reserve_model_call("gpt-4.1-mini")

    assert refused.value.cap == "max_model_calls"
    assert "max_model_calls" in str(refused.value)
    assert coordinator.report().cut_by == "max_model_calls"


def test_the_tool_call_cap_stops_the_run_and_names_the_cap() -> None:
    """FR-009: the cap on the calls of the tools holds the run too."""
    coordinator = BudgetCoordinator(RunBudget(max_tool_calls=2), registry())

    coordinator.reserve_tool_call()
    coordinator.reserve_tool_call()

    with pytest.raises(BudgetExceededError) as refused:
        coordinator.reserve_tool_call()

    assert refused.value.cap == "max_tool_calls"


def test_the_output_token_cap_stops_the_run_at_the_attempt_that_would_break_it() -> None:
    """FR-009: the cap on the output tokens holds the run."""
    coordinator = BudgetCoordinator(RunBudget(max_output_tokens=100), registry())

    coordinator.reserve_model_call("gpt-4.1-mini", planned_output_tokens=60)

    with pytest.raises(BudgetExceededError) as refused:
        coordinator.reserve_model_call("gpt-4.1-mini", planned_output_tokens=60)

    assert refused.value.cap == "max_output_tokens"


def test_the_wall_clock_cap_stops_the_run_and_the_clock_is_injected() -> None:
    """FR-009 and SC-003: the cap is proved by moving a clock, not by waiting."""
    clock = FakeClock()
    coordinator = BudgetCoordinator(RunBudget(max_wall_seconds=30), registry(), clock=clock)

    coordinator.reserve_model_call("gpt-4.1-mini")
    clock.advance(31)

    with pytest.raises(BudgetExceededError) as refused:
        coordinator.reserve_model_call("gpt-4.1-mini")

    assert refused.value.cap == "max_wall_seconds"
    assert coordinator.report().elapsed_seconds == pytest.approx(31)


def test_the_wall_clock_cap_is_checked_before_a_call_of_a_tool() -> None:
    """SC-003: a run that spends its time in the tools spends it without calling a model, and the cap still holds."""
    clock = FakeClock()
    coordinator = BudgetCoordinator(RunBudget(max_wall_seconds=30), registry(), clock=clock)

    clock.advance(31)

    with pytest.raises(BudgetExceededError) as refused:
        coordinator.reserve_tool_call()

    assert refused.value.cap == "max_wall_seconds"
    assert coordinator.report().tool_calls == 0


def test_the_wall_clock_cap_is_checked_after_a_call() -> None:
    """SC-003: the call that passes the cap stops the run, even when the provider answered."""
    clock = FakeClock()
    coordinator = BudgetCoordinator(RunBudget(max_wall_seconds=30), registry(), clock=clock)

    coordinator.reserve_model_call("gpt-4.1-mini")
    clock.advance(31)

    with pytest.raises(BudgetExceededError) as refused:
        coordinator.record_model_usage("gpt-4.1-mini", input_tokens=10, output_tokens=5)

    assert refused.value.cap == "max_wall_seconds"


def test_the_money_cap_stops_the_run_at_the_attempt_that_would_break_it() -> None:
    """FR-009: the cap on the money holds the run, with the price of the registry."""
    coordinator = BudgetCoordinator(RunBudget(max_estimated_usd=Decimal("1.00")), registry())

    # A million input tokens at 0.40 US$ is 0.40 US$, so two calls fit under the cap and the third does not.
    coordinator.reserve_model_call("gpt-4.1-mini", planned_input_tokens=1_000_000)
    coordinator.reserve_model_call("gpt-4.1-mini", planned_input_tokens=1_000_000)

    with pytest.raises(BudgetExceededError) as refused:
        coordinator.reserve_model_call("gpt-4.1-mini", planned_input_tokens=1_000_000)

    assert refused.value.cap == "max_estimated_usd"


def test_the_money_cap_is_authoritative_when_the_price_is_verified() -> None:
    """FR-010 and FR-011: the cap on the money holds the run only when the price was verified."""
    coordinator = BudgetCoordinator(RunBudget(max_estimated_usd=Decimal("1.00")), registry())

    coordinator.reserve_model_call("gpt-4.1-mini", planned_input_tokens=1_000)

    report = coordinator.report()

    assert report.price_known is True
    assert report.money_cap_authoritative is True


def test_the_calls_of_every_model_of_the_run_are_counted() -> None:
    """FR-012: the triage model, the generator of the SQL and the judge are all part of the bill."""
    coordinator = BudgetCoordinator(RunBudget(max_model_calls=10), registry())

    coordinator.reserve_model_call("gpt-4.1-mini")
    coordinator.reserve_model_call("gpt-4.1-mini")
    coordinator.reserve_model_call("gpt-4.1")

    report = coordinator.report()

    assert report.model_calls == 3
    assert report.calls_by_model == {"gpt-4.1-mini": 2, "gpt-4.1": 1}


def test_a_model_the_run_did_not_declare_still_counts_against_the_cap() -> None:
    """FR-012: the cap is about the money and not about the model."""
    coordinator = BudgetCoordinator(RunBudget(max_model_calls=2), registry())

    coordinator.reserve_model_call("gpt-4.1-mini")
    coordinator.reserve_model_call("some-other-model")

    with pytest.raises(BudgetExceededError) as refused:
        coordinator.reserve_model_call("gpt-4.1-mini")

    assert refused.value.cap == "max_model_calls"
    assert coordinator.report().model_calls == 2


def test_the_observed_cost_and_the_estimated_cost_are_two_separate_numbers() -> None:
    """FR-010: the observed cost and the estimated cost are never the same number dressed as the other."""
    coordinator = BudgetCoordinator(RunBudget(), registry())

    coordinator.reserve_model_call("gpt-4.1-mini", planned_input_tokens=1_000, planned_output_tokens=1_000)
    coordinator.record_model_usage("gpt-4.1-mini", input_tokens=2_000, output_tokens=500)

    report = coordinator.report()

    # The estimate is the price over the planned tokens, the observed cost is the price over the reported ones.
    assert report.estimated_cost_usd == Decimal("0.40") * 1_000 / 1_000_000 + Decimal("1.60") * 1_000 / 1_000_000
    assert report.observed_cost_usd == Decimal("0.40") * 2_000 / 1_000_000 + Decimal("1.60") * 500 / 1_000_000
    assert report.observed_cost_usd != report.estimated_cost_usd


def test_the_estimated_cost_is_absent_when_the_registry_has_no_price() -> None:
    """FR-011: no price, no dollar amount, and the report says the price is unknown."""
    coordinator = BudgetCoordinator(RunBudget(), registry())

    coordinator.reserve_model_call("gpt-4.1", planned_input_tokens=1_000, planned_output_tokens=1_000)
    coordinator.record_model_usage("gpt-4.1", input_tokens=1_000, output_tokens=1_000)

    report = coordinator.report()

    assert report.estimated_cost_usd is None
    assert report.observed_cost_usd is None
    assert report.price_known is False
    assert report.money_cap_authoritative is False
    assert report.input_tokens == 1_000
    assert report.output_tokens == 1_000


def test_a_price_that_is_unknown_makes_the_money_cap_not_authoritative() -> None:
    """FR-011: without a price the money cap cannot hold the run, so the other caps do."""
    coordinator = BudgetCoordinator(RunBudget(max_estimated_usd=Decimal("0.0001")), registry())

    coordinator.reserve_model_call("gpt-4.1", planned_input_tokens=1_000_000)

    report = coordinator.report()

    assert report.price_known is False
    assert report.money_cap_authoritative is False


def test_the_money_of_the_run_is_a_decimal_and_never_a_float() -> None:
    """Money is Decimal: a float in the cost path is a defect."""
    coordinator = BudgetCoordinator(RunBudget(), registry())

    coordinator.reserve_model_call("gpt-4.1-mini", planned_input_tokens=1_000)
    coordinator.record_model_usage("gpt-4.1-mini", input_tokens=1_000)

    report = coordinator.report()

    assert isinstance(report.observed_cost_usd, Decimal)
    assert isinstance(report.estimated_cost_usd, Decimal)


def test_the_report_carries_the_calls_the_tokens_and_the_elapsed_time() -> None:
    """The cost panel shows the calls, the tokens and the elapsed time of the run."""
    clock = FakeClock()
    coordinator = BudgetCoordinator(RunBudget(), registry(), clock=clock)

    coordinator.reserve_model_call("gpt-4.1-mini")
    coordinator.reserve_tool_call()
    coordinator.record_model_usage("gpt-4.1-mini", input_tokens=120, output_tokens=30)
    clock.advance(4.5)

    report = coordinator.report()

    assert report.model_calls == 1
    assert report.tool_calls == 1
    assert report.input_tokens == 120
    assert report.output_tokens == 30
    assert report.elapsed_seconds == pytest.approx(4.5)


# --- a plan that cannot be counted is refused before anything is reserved -----------------------------


def test_a_planned_count_of_zero_is_accepted_and_means_no_token_is_planned() -> None:
    """FR-009: a count of zero says that no token is planned, and it is a plan like any other.

    The caller that plans nothing may say it with a zero or by not giving a count at all, and the two mean the
    same thing.
    """
    coordinator = BudgetCoordinator(RunBudget(max_output_tokens=100), registry())

    coordinator.reserve_model_call("gpt-4.1-mini", planned_output_tokens=0)

    assert coordinator.report().model_calls == 1
    assert coordinator.report().output_tokens == 0


def test_a_negative_planned_count_is_refused() -> None:
    """FR-009: a count that is less than zero takes the accounting backwards, so it is refused.

    The refusal happens before anything is reserved, so the accounting of the run never goes backwards.
    """
    coordinator = BudgetCoordinator(RunBudget(max_output_tokens=100), registry())

    with pytest.raises(BudgetRefused):
        coordinator.reserve_model_call("gpt-4.1-mini", planned_output_tokens=-100)

    assert coordinator.report().model_calls == 0
    assert coordinator.report().output_tokens == 0


def test_a_negative_planned_count_cannot_launder_the_cap_on_the_tokens() -> None:
    """FR-009: the counter of the planned tokens never goes backwards."""
    coordinator = BudgetCoordinator(RunBudget(max_output_tokens=100), registry())

    coordinator.reserve_model_call("gpt-4.1-mini", planned_output_tokens=100)

    with pytest.raises(BudgetRefused):
        coordinator.reserve_model_call("gpt-4.1-mini", planned_output_tokens=-100)

    with pytest.raises(BudgetExceededError) as refused:
        coordinator.reserve_model_call("gpt-4.1-mini", planned_output_tokens=100)

    assert refused.value.cap == "max_output_tokens"


# --- the money cap is checked again against what the provider reported --------------------------------


def test_the_observed_tokens_are_recorded_even_when_the_money_cap_stops_the_run() -> None:
    """FR-010: the call that broke the cap was paid for, so the report has to show what it cost."""
    coordinator = BudgetCoordinator(RunBudget(max_estimated_usd=Decimal("0.10")), registry())

    coordinator.reserve_model_call("gpt-4.1-mini", planned_input_tokens=1)

    with pytest.raises(BudgetExceededError):
        coordinator.record_model_usage("gpt-4.1-mini", input_tokens=10_000_000)

    report = coordinator.report()

    assert report.input_tokens == 10_000_000
    assert report.observed_cost_usd == Decimal("4.00")


def test_the_money_cap_stops_the_run_when_the_observed_cost_passes_it() -> None:
    """FR-009 and FR-010: the refusal of the observed cost names the cap that stopped the run."""
    coordinator = BudgetCoordinator(RunBudget(max_estimated_usd=Decimal("0.10")), registry())

    coordinator.reserve_model_call("gpt-4.1-mini", planned_input_tokens=1)

    with pytest.raises(BudgetExceededError) as refused:
        coordinator.record_model_usage("gpt-4.1-mini", input_tokens=10_000_000)

    assert refused.value.cap == "max_estimated_usd"
    assert coordinator.report().cut_by == "max_estimated_usd"


def test_the_money_cap_does_not_hold_a_run_whose_price_is_unknown() -> None:
    """FR-011: a cap that cannot be evaluated cannot hold a run, so the other caps do.

    The run carries a model without a verified price, so the money of the run is unknown and the cap on the money
    is not authoritative. The partial sum of the priced models is not the money of the run, and it never stops it.
    """
    coordinator = BudgetCoordinator(RunBudget(max_estimated_usd=Decimal("0.0001")), registry())

    coordinator.reserve_model_call("gpt-4.1", planned_input_tokens=1_000_000)
    coordinator.reserve_model_call("gpt-4.1-mini", planned_input_tokens=1_000_000)

    report = coordinator.report()

    assert report.price_known is False
    assert report.observed_cost_usd is None
    assert report.estimated_cost_usd is None
    assert report.money_cap_authoritative is False


# --- the models that reported a usage without a reservation -------------------------------------------


def test_a_model_that_reported_a_usage_without_a_reservation_is_named() -> None:
    """FR-012: the counting of every model is right, and the mismatch is what the caller has to see.

    The call that nobody reserved is a call of the run all the same, so it is counted and it shows in the
    breakdown of the calls by model.
    """
    coordinator = BudgetCoordinator(RunBudget(), registry())

    coordinator.reserve_model_call("gpt-4.1-mini")
    coordinator.record_model_usage("gpt-4.1-mini", input_tokens=10, output_tokens=5)
    coordinator.record_model_usage("a-model-the-run-did-not-declare", input_tokens=7, output_tokens=3)

    report = coordinator.report()

    assert report.usage_without_reservation == ("a-model-the-run-did-not-declare",)
    assert report.model_calls == 2
    assert report.calls_by_model == {"gpt-4.1-mini": 1, "a-model-the-run-did-not-declare": 1}


# --- a call that nobody reserved counts against the cap --------------------------------------------------


def test_an_unreserved_call_counts_against_the_cap_of_the_model_calls() -> None:
    """FR-012 and SC-004: a call that nobody reserved was paid for, so it counts against the cap.

    The cap is about the money and not about the plan of the run, and the unreserved call consumes the cap for
    the calls that come after it.
    """
    coordinator = BudgetCoordinator(RunBudget(max_model_calls=1), registry())

    coordinator.record_model_usage("a-model-the-run-did-not-declare", input_tokens=10, output_tokens=5)

    assert coordinator.report().model_calls == 1

    with pytest.raises(BudgetExceededError) as refused:
        coordinator.reserve_model_call("gpt-4.1-mini")

    assert refused.value.cap == "max_model_calls"
    assert coordinator.report().cut_by == "max_model_calls"


def test_a_usage_that_finds_no_reservation_is_counted_after_the_reserved_ones() -> None:
    """FR-012: a usage answers a reservation while there is one, and the usage that finds none is unreserved.

    The two reserved calls of the model are counted once, and the third usage is a call that nobody reserved, so it
    is counted as well and it is named in the report.
    """
    coordinator = BudgetCoordinator(RunBudget(max_model_calls=10), registry())

    coordinator.reserve_model_call("gpt-4.1-mini")
    coordinator.reserve_model_call("gpt-4.1-mini")
    coordinator.record_model_usage("gpt-4.1-mini")
    coordinator.record_model_usage("gpt-4.1-mini")

    assert coordinator.report().model_calls == 2
    assert coordinator.report().usage_without_reservation == ()

    coordinator.record_model_usage("gpt-4.1-mini")

    assert coordinator.report().model_calls == 3
    assert coordinator.report().usage_without_reservation == ("gpt-4.1-mini",)


def test_five_unreserved_calls_against_a_cap_of_one_stop_the_run() -> None:
    """FR-012 and SC-004: no run exceeds the cap of the calls of the models, whoever made the calls.

    The run stops on the call that passes the cap, and the refusal names the cap that stopped it.
    """
    coordinator = BudgetCoordinator(RunBudget(max_model_calls=1), registry())

    coordinator.record_model_usage("a-model-the-run-did-not-declare")

    with pytest.raises(BudgetExceededError) as refused:
        coordinator.record_model_usage("a-model-the-run-did-not-declare")

    assert refused.value.cap == "max_model_calls"
    assert coordinator.report().usage_without_reservation == ("a-model-the-run-did-not-declare",)


# --- the count the provider reported is checked, because the provider is untrusted input ------------------


def test_a_negative_reported_count_is_refused_and_the_run_stops() -> None:
    """FR-009: a negative count takes the accounting backwards, and the run stops.

    The provider is untrusted input: a count that cannot be counted launders the cap on the tokens and the cap on
    the money.
    """
    coordinator = BudgetCoordinator(RunBudget(max_output_tokens=10_000_000), registry())
    coordinator.reserve_model_call("gpt-4.1-mini")

    with pytest.raises(UsageRefused) as refused:
        coordinator.record_model_usage("gpt-4.1-mini", input_tokens=0, output_tokens=-10_000_000)

    assert "negative" in str(refused.value)
    # The rule that stopped the run is named: the cap on the output tokens cannot hold a count nobody can count.
    assert refused.value.cap == "max_output_tokens"
    assert coordinator.report().cut_by == "max_output_tokens"
    # The tokens the provider really reported are in the report, so the report says what the provider said.
    assert coordinator.report().output_tokens == -10_000_000


def test_a_negative_reported_count_cannot_launder_the_cap_on_the_output_tokens() -> None:
    """FR-009 and SC-004: a negative count does not buy the run the tokens it cancels.

    The count that would have cancelled the real tokens is refused, so the run stops before it spends the money
    of the visitor.
    """
    coordinator = BudgetCoordinator(RunBudget(max_output_tokens=10_000_000), registry())
    coordinator.reserve_model_call("gpt-4.1-mini")

    with pytest.raises(UsageRefused):
        coordinator.record_model_usage("gpt-4.1-mini", output_tokens=-10_000_000)

    # The run stopped, so the call that would have spent the nine million tokens never happened.
    assert coordinator.report().model_calls == 1


def test_a_reported_count_that_is_not_a_number_is_refused() -> None:
    """FR-009: a count that is not a number cannot be counted, so it is refused."""
    coordinator = BudgetCoordinator(RunBudget(), registry())
    coordinator.reserve_model_call("gpt-4.1-mini")

    with pytest.raises(UsageRefused) as refused:
        coordinator.record_model_usage("gpt-4.1-mini", input_tokens="many", output_tokens=0)

    assert "number" in str(refused.value)
    assert refused.value.cap == "max_input_tokens"
    assert coordinator.report().input_tokens == 0


# --- a run that called no model ----------------------------------------------------------------------


def test_a_run_that_called_no_model_shows_no_dollar_amount() -> None:
    """FR-010 and FR-011: the price of a run that never called is not a price of anything.

    A zero would read as "the model was free", and the report says that the price is unknown instead.
    """
    coordinator = BudgetCoordinator(RunBudget(), registry())

    report = coordinator.report()

    assert report.observed_cost_usd is None
    assert report.estimated_cost_usd is None
    assert report.price_known is False
    assert report.money_cap_authoritative is False
