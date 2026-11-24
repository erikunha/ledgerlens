"""The budget of a live run: the caps it must not break, the counters of every model it used and its two costs.

Why it exists: the visitor pays for the run, and the run has to stop before the money of the visitor is gone.
The caps live in the `RunBudget` of the run context, which is the same object the rest of the core uses (FR-025),
and the coordinator is the only thing that enforces them. The interface can ask for a budget; it cannot raise it.

The coordinator counts the calls of every model the run uses, and not only of the model the run declared: the
triage model, the generator of the SQL and any judge model are all part of the bill, so the cap on the money has to
count them all (FR-012). A model identifier the run did not declare is counted as well, because the cap is about
the money and not about the model. A call that nobody reserved is a call of the run too: it happened and it was
paid for, so it counts against the cap of the calls of the models, and the mismatch is named in the report.

The counts the provider reports are checked the way the counts the run plans are checked, because the provider is
untrusted input. A count that is negative or that is not a number is refused and the run stops, because a count that
cannot be counted launders the cap on the tokens and the cap on the money (FR-009). The tokens that were really
reported are recorded anyway, so the report says what the provider said, and the refusal names the rule that could
not be honoured, which is the cap on the tokens of that kind.

Two costs, never mixed (FR-010). The observed cost is what the provider reported: the tokens it counted and the
price of the registry. The estimated cost is what the run planned: the tokens the caller reserved and the price of
the registry. When the registry has no verified price for a model of the run, neither cost is a number, the report
says the price is unknown and no dollar amount appears anywhere (FR-011). A guessed dollar amount is worse than
none, and a partial sum would hide the model whose price is missing.

A run that called no model has no price at all: the cost of a run that never called is not a price of anything,
and a zero would read as "the model was free". The report of such a run says that the price is unknown and shows
no dollar amount (FR-010, FR-011).

The caps are checked before the call and again after it. The wall clock is checked before a call of a model, before
a call of a tool and after a call, because a run that spends its time in the tools of the agent spends it without
calling a model (SC-003). The cap on the money is checked against the tokens the run planned and again against the
tokens the provider reported, because the provider is the only one who knows what the call really cost (FR-009).

The clock is injected. The wall clock cap is therefore proved by moving a clock in a test, not by waiting for it
(FR-009, SC-003).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal

from ledgerlens.byok.errors import ByokError
from ledgerlens.byok.registry import ProviderRegistry
from ledgerlens.run_context import RunBudget

__all__ = [
    "BudgetCoordinator",
    "BudgetExceededError",
    "BudgetRefused",
    "CostReport",
    "UsageRefused",
]

# The tokens of one million, the unit the prices of the registry are quoted in.
TOKENS_PER_MILLION = Decimal(1_000_000)


class BudgetExceededError(ByokError):
    """A cap of the budget would break, so the run stops.

    The message names the cap that stopped the run, because the interface has to say which limit was reached
    (FR-009) and a visitor who is not told cannot tell a broken run from a broken model.

    Why the cap is an attribute and not only a word in the message: the coordinator and the caller have to agree
    on which limit was reached, and a word in a text is not a value a program can read.
    """

    reason = "the budget of the run is exhausted"

    def __init__(self, cap: str, detail: str | None = None) -> None:
        super().__init__(detail)
        self.cap = cap


class BudgetRefused(ByokError):
    """The reservation itself is refused, before anything is reserved.

    Why this is not a cap that was reached: a reservation that carries a count of tokens that is negative is not a
    run that broke a limit, it is a request that cannot be counted. The run stops anyway, because a plan that
    cannot be counted is a plan the caps cannot hold (FR-009).
    """

    reason = "the reservation of the budget was refused"


class UsageRefused(BudgetExceededError):
    """The usage the provider reported cannot be counted, so the run stops.

    Why this is a refusal of the family of the caps: the count of the tokens of that kind cannot be evaluated, so
    the cap on that kind of tokens cannot hold the run either, and the cap is the rule that stopped the run
    (FR-009).

    Why the reason is not the reason of the budget: the budget was not exhausted, a count that nobody can count
    stopped the run, and the provider is untrusted input.
    """

    reason = "the reported usage was refused"

    def __init__(self, cap: str, detail: str | None = None) -> None:
        super().__init__(cap, detail)


@dataclass(frozen=True)
class CostReport:
    """What a run consumed: the calls, the tokens, the elapsed time and the two costs.

    The observed cost and the estimated cost are separate numbers and never one number dressed as the other
    (FR-010). Either of them is None when the registry has no verified price for a model of the run, and the
    report then says so through `price_known` (FR-011). `cut_by` names the cap that stopped the run, when one did
    (FR-009).

    `usage_without_reservation` names the models that reported a usage without a reservation: the counting of
    every model is right, and a call that nobody reserved is a call the run did not plan, so the caller has to
    see the mismatch (FR-012). That call counts against the cap of the calls of the models all the same, because
    the money of it was spent (SC-004).
    """

    model_calls: int
    tool_calls: int
    calls_by_model: Mapping[str, int]
    input_tokens: int
    output_tokens: int
    elapsed_seconds: float
    observed_cost_usd: Decimal | None
    estimated_cost_usd: Decimal | None
    price_known: bool
    money_cap_authoritative: bool
    cut_by: str | None
    usage_without_reservation: tuple[str, ...] = ()


@dataclass
class _Ledger:
    """The counters of a run, one entry per model.

    The breakdown per model is what proves that the triage model and the generator of the SQL were counted and not
    only the model of the declaration (FR-012).
    """

    planned_input_tokens: dict[str, int] = field(default_factory=dict)
    planned_output_tokens: dict[str, int] = field(default_factory=dict)
    observed_input_tokens: dict[str, int] = field(default_factory=dict)
    observed_output_tokens: dict[str, int] = field(default_factory=dict)
    calls_by_model: dict[str, int] = field(default_factory=dict)
    # The reservations that no usage answered yet. A usage that finds no reservation is a call that nobody
    # planned, and it is counted all the same (FR-012).
    pending_reservations: dict[str, int] = field(default_factory=dict)
    # The models that reported a usage without a reservation. The run did not plan those calls, and the caller
    # has to see the mismatch (FR-012).
    unreserved_models: set[str] = field(default_factory=set)

    def models(self) -> set[str]:
        """Every model the run touched, planned or observed."""
        return (
            set(self.planned_input_tokens)
            | set(self.planned_output_tokens)
            | set(self.observed_input_tokens)
            | set(self.observed_output_tokens)
        )


class BudgetCoordinator:
    """The enforcement of the caps of a run and the accounting of what it consumed.

    The coordinator is asked before a call whether the call is allowed (`reserve_model_call`, `reserve_tool_call`)
    and told after it what the provider reported (`record_model_usage`). The separation matters: the cap has to be
    checked before the money is spent, and the observed tokens only exist after the provider answered.

    Every model of the run goes through the same counters, whatever its identifier (FR-012). The price of a model
    comes from the registry, and a model without a verified price makes the money of the run unknown instead of
    estimated (FR-011). A model that reports a usage without a reservation is named in the report, because the
    counting is right and the mismatch is what the caller has to see (FR-012).

    What an unreserved call does to the cap of the calls of the models: it counts against it, and it consumes it for
    the calls that come after it. The call happened and the money of the visitor was spent, whatever the plan of the
    run said, so the counter of the calls of the run is one counter and an unreserved call is one more call of that
    counter. The run stops when the number of calls passes the cap, the way it stops for any other call (SC-004).
    """

    def __init__(
        self,
        budget: RunBudget,
        registry: ProviderRegistry,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._budget = budget
        self._registry = registry
        self._clock = clock
        self._start = clock()
        self._ledger = _Ledger()
        self._model_calls = 0
        self._tool_calls = 0
        self._cut_by: str | None = None

    def elapsed_seconds(self) -> float:
        """How long the run took, as the injected clock sees it."""
        return self._clock() - self._start

    @property
    def caps(self) -> RunBudget:
        """The caps the coordinator enforces, for the trace that names the budget a step had.

        Why it is a property and not a second copy of the value: a caller that published its own copy of the caps
        could publish the caps of another run, and the trace would name a budget that is not the one that was spent.
        """
        return self._budget

    def restart(self) -> None:
        """Anchors the elapsed time again, for a run that starts now."""
        self._start = self._clock()

    def reserve_model_call(
        self,
        model_id: str,
        *,
        planned_input_tokens: int | None = None,
        planned_output_tokens: int | None = None,
    ) -> None:
        """Reserves one call of a model, or refuses the run when the call would break a cap.

        The refusal happens before the provider is called, so the money of the visitor is not spent on a call that
        the budget does not allow (FR-009). The model identifier is the one the call really uses, and every model
        of the run is counted the same way (FR-012).

        Why a planned count of zero is a plan and a negative one is not: a count of zero says that no token is
        planned, and a caller that plans nothing may say it with a zero or by not giving a count at all. A negative
        count is not a plan: it would take the accounting of the run backwards and it would launder the cap on the
        tokens (FR-009).
        """
        planned_input = self._check_planned_count(planned_input_tokens, "input")
        planned_output = self._check_planned_count(planned_output_tokens, "output")
        self._check_model_call_cap()
        self._check_wall_clock_cap()
        self._check_token_caps(planned_input, planned_output)
        self._check_money_cap(model_id, planned_input, planned_output)

        self._model_calls += 1
        self._ledger.calls_by_model[model_id] = self._ledger.calls_by_model.get(model_id, 0) + 1
        self._ledger.pending_reservations[model_id] = self._ledger.pending_reservations.get(model_id, 0) + 1
        self._ledger.planned_input_tokens[model_id] = self._ledger.planned_input_tokens.get(model_id, 0) + planned_input
        self._ledger.planned_output_tokens[model_id] = (
            self._ledger.planned_output_tokens.get(model_id, 0) + planned_output
        )

    def reserve_tool_call(self) -> None:
        """Reserves one call of a tool, or refuses the run when the call would break a cap.

        Why the wall clock is checked here too: a run that spends its time in the tools of the agent spends it
        without calling a model, and the cap on the wall clock is a cap on the run and not on the calls of the
        models (SC-003).
        """
        self._check_wall_clock_cap()
        self._check_tool_call_cap()
        self._tool_calls += 1

    def record_model_usage(self, model_id: str, *, input_tokens: int = 0, output_tokens: int = 0) -> None:
        """Records what the provider reported for a call of a model.

        These are the observed tokens: the ones the provider counted, and not the ones the run planned (FR-010).

        Why the caps are checked again here: the provider is the only one who knows how many tokens it produced,
        and the cap on the money is a promise about what the run may spend (FR-009, SC-003).

        Why a count that is not a number is refused before anything is recorded: there is nothing to record, and a
        count nobody can count cannot be added to the accounting of the run. Why a negative count is refused after
        the tokens are recorded: the tokens the provider really said are kept, so the report shows what happened,
        and the run stops all the same, because a negative count launders the cap on the tokens and the cap on the
        money (FR-009).

        Why an unreserved call counts against the cap of the calls of the models: the call happened and it was paid
        for, so it is a call of the run, and the counter of the calls is one counter (FR-012, SC-004).
        """
        self._require_a_reported_number(input_tokens, "input")
        self._require_a_reported_number(output_tokens, "output")
        self._ledger.observed_input_tokens[model_id] = (
            self._ledger.observed_input_tokens.get(model_id, 0) + input_tokens
        )
        self._ledger.observed_output_tokens[model_id] = (
            self._ledger.observed_output_tokens.get(model_id, 0) + output_tokens
        )
        self._refuse_a_negative_reported_count(input_tokens, "input")
        self._refuse_a_negative_reported_count(output_tokens, "output")
        pending = self._ledger.pending_reservations.get(model_id, 0)
        if pending > 0:
            # The usage answers a reservation of the run, so the call was already counted.
            self._ledger.pending_reservations[model_id] = pending - 1
        else:
            # The provider reported a usage for a call that nobody reserved. The counting is right and the
            # mismatch is named, because a call that nobody reserved is a call nobody planned (FR-012).
            self._ledger.unreserved_models.add(model_id)
            # The call counts against the cap of the calls of the models and it shows in the breakdown, because
            # the cap is about the money and not about the plan of the run (FR-012, SC-004).
            self._model_calls += 1
            self._ledger.calls_by_model[model_id] = self._ledger.calls_by_model.get(model_id, 0) + 1
            self._check_model_call_cap_passed()
        self._check_observed_token_caps()
        self._check_observed_money_cap()
        self._check_wall_clock_cap()

    def report(self) -> CostReport:
        """What the run consumed, with the two costs apart and the cap that stopped it named.

        The report is built by the code and never by the model, and the money is a Decimal or nothing at all
        (FR-010, FR-011).

        Why a run that called no model shows no amount: the price of a run that never called is not a price of
        anything, and a zero would read as "the model was free" (FR-011).
        """
        models = self._ledger.models()
        price_known = bool(models) and all(self._registry.price_for(model_id) is not None for model_id in models)
        observed = (
            self._cost(self._ledger.observed_input_tokens, self._ledger.observed_output_tokens) if price_known else None
        )
        estimated = (
            self._cost(self._ledger.planned_input_tokens, self._ledger.planned_output_tokens) if price_known else None
        )
        return CostReport(
            model_calls=self._model_calls,
            tool_calls=self._tool_calls,
            calls_by_model=dict(self._ledger.calls_by_model),
            input_tokens=sum(self._ledger.observed_input_tokens.values()),
            output_tokens=sum(self._ledger.observed_output_tokens.values()),
            elapsed_seconds=self.elapsed_seconds(),
            observed_cost_usd=observed,
            estimated_cost_usd=estimated,
            price_known=price_known,
            money_cap_authoritative=self._budget.max_estimated_usd is not None and price_known,
            cut_by=self._cut_by,
            usage_without_reservation=tuple(sorted(self._ledger.unreserved_models)),
        )

    # The two costs, computed from the price of the registry over the tokens of each model.
    def _cost(self, input_tokens: Mapping[str, int], output_tokens: Mapping[str, int]) -> Decimal | None:
        """The money of a set of tokens, or None when a model of the run has no verified price.

        A partial sum would be a lie: the visitor would see a number that does not include a model of the run
        (FR-011). The decision lives here and not in the caller, so the guard is the one that holds: the caller
        asks for the money of these tokens and gets nothing when one of the models has no price.

        Why an empty set of tokens costs nothing: the money of no token is no money, and the caller that asks for
        the money of a run that never called a model gets the number zero of the tokens it planned.
        """
        total = Decimal("0")
        for model_id in sorted(set(input_tokens) | set(output_tokens)):
            price = self._registry.price_for(model_id)
            if price is None:
                return None
            total += price.input_per_1m_usd * Decimal(input_tokens.get(model_id, 0)) / TOKENS_PER_MILLION
            total += price.output_per_1m_usd * Decimal(output_tokens.get(model_id, 0)) / TOKENS_PER_MILLION
        return total

    # The caps, one method each, so the refusal always names the cap that stopped the run.
    def _check_planned_count(self, count: int | None, kind: str) -> int:
        """The planned count of a kind of tokens, or a refusal when the count is negative.

        Why zero is a plan and not a refusal: a count of zero says that no token is planned, and a caller that
        plans nothing may say it with a zero or by not giving a count at all. A negative count is not a plan: it
        would take the accounting of the run backwards and it would launder the cap on the tokens (FR-009).
        """
        if count is None:
            return 0
        if count < 0:
            raise BudgetRefused(
                f"the planned count of the {kind} tokens is {count}, and a planned count cannot be negative"
            )
        return count

    def _require_a_reported_number(self, count: int, kind: str) -> None:
        """Refuses a count the provider reported that is not a number at all.

        Why the refusal happens before anything is recorded: a count that is not a number cannot be added to the
        accounting of the run, and the caps of the run cannot hold a count nobody can count (FR-009).
        """
        if isinstance(count, bool) or not isinstance(count, int):
            self._refuse_a_reported_count(count, kind, f"max_{kind}_tokens", "a reported count has to be a number")

    def _refuse_a_negative_reported_count(self, count: int, kind: str) -> None:
        """Refuses a count the provider reported that is negative.

        Why the tokens are recorded before the refusal: the report has to say what the provider really reported,
        and the run stops all the same, because a negative count takes the accounting of the run backwards and it
        launders the cap on the tokens and the cap on the money (FR-009).

        Why the refusal names the cap of that kind of tokens: the count cannot be evaluated, so the cap on that
        kind of tokens cannot hold the run either, and the rule that stopped the run is the one the caller has to
        see (FR-009).
        """
        if count < 0:
            self._refuse_a_reported_count(count, kind, f"max_{kind}_tokens", "a reported count cannot be negative")

    def _refuse_a_reported_count(self, count: object, kind: str, cap: str, why: str) -> None:
        """Records the rule that stopped the run and raises the refusal that names it.

        The rule is the cap on the tokens of that kind, even when the budget of the run carries no such cap: the
        count could not be counted, so the rule of that kind is the one that could not be honoured (FR-009).
        """
        self._cut_by = cap
        raise UsageRefused(
            cap,
            f"the cap '{cap}' stopped the run: the reported count of the {kind} tokens is {count}, and {why}",
        )

    def _check_model_call_cap(self) -> None:
        """The cap on the calls of the models. Every model of the run counts against it (FR-012)."""
        cap = self._budget.max_model_calls
        if cap is not None and self._model_calls >= cap:
            self._refuse("max_model_calls", f"the run reached the cap of {cap} model calls, so the run stops")

    def _check_model_call_cap_passed(self) -> None:
        """The cap on the calls of the models, checked after a call that nobody reserved.

        Why the comparison is not the one of the check that runs before a call: a call that nobody reserved already
        happened, so the run stops when the number of calls passes the cap and not when it reaches it. A run that
        made exactly as many calls as the cap allows used its budget and did not break it (FR-012, SC-004).
        """
        cap = self._budget.max_model_calls
        if cap is not None and self._model_calls > cap:
            self._refuse(
                "max_model_calls",
                f"the run made {self._model_calls} model calls, which passes the cap of {cap} model calls, "
                "so the run stops",
            )

    def _check_tool_call_cap(self) -> None:
        """The cap on the calls of the tools."""
        cap = self._budget.max_tool_calls
        if cap is not None and self._tool_calls >= cap:
            self._refuse("max_tool_calls", f"the run reached the cap of {cap} tool calls, so the run stops")

    def _check_wall_clock_cap(self) -> None:
        """The cap on the wall clock, as the injected clock sees it (SC-003)."""
        cap = self._budget.max_wall_seconds
        if cap is not None and self.elapsed_seconds() >= cap:
            self._refuse("max_wall_seconds", f"the run reached the cap of {cap} seconds, so the run stops")

    def _check_token_caps(self, planned_input_tokens: int, planned_output_tokens: int) -> None:
        """The caps on the tokens, checked before the call that would break them."""
        input_cap = self._budget.max_input_tokens
        if input_cap is not None:
            planned = sum(self._ledger.planned_input_tokens.values()) + planned_input_tokens
            if planned > input_cap:
                self._refuse(
                    "max_input_tokens",
                    f"the run would pass the cap of {input_cap} input tokens, so the run stops",
                )
        output_cap = self._budget.max_output_tokens
        if output_cap is not None:
            planned = sum(self._ledger.planned_output_tokens.values()) + planned_output_tokens
            if planned > output_cap:
                self._refuse(
                    "max_output_tokens",
                    f"the run would pass the cap of {output_cap} output tokens, so the run stops",
                )

    def _check_observed_token_caps(self) -> None:
        """The caps on the tokens, checked on what the provider really reported.

        The breach is found after the call, because the provider is the only one who knows how many tokens it
        produced. The run stops anyway: the cap is a promise about the money of the visitor.
        """
        input_cap = self._budget.max_input_tokens
        if input_cap is not None:
            observed = sum(self._ledger.observed_input_tokens.values())
            if observed > input_cap:
                self._refuse(
                    "max_input_tokens",
                    f"the run passed the cap of {input_cap} input tokens, so the run stops",
                )
        output_cap = self._budget.max_output_tokens
        if output_cap is not None:
            observed = sum(self._ledger.observed_output_tokens.values())
            if observed > output_cap:
                self._refuse(
                    "max_output_tokens",
                    f"the run passed the cap of {output_cap} output tokens, so the run stops",
                )

    def _check_money_cap(self, model_id: str, planned_input_tokens: int, planned_output_tokens: int) -> None:
        """The cap on the money, checked before the call that would break it.

        The cap only has a meaning when the price of the model is verified. When it is not, the money cap is not
        authoritative and the other caps of the run hold the execution instead (FR-011).
        """
        cap = self._budget.max_estimated_usd
        if cap is None:
            return
        price = self._registry.price_for(model_id)
        if price is None:
            return
        planned = self._cost(self._ledger.planned_input_tokens, self._ledger.planned_output_tokens)
        if planned is None:
            return
        incoming = price.input_per_1m_usd * Decimal(planned_input_tokens) / TOKENS_PER_MILLION
        incoming += price.output_per_1m_usd * Decimal(planned_output_tokens) / TOKENS_PER_MILLION
        if planned + incoming > cap:
            self._refuse("max_estimated_usd", f"the run would pass the cap of {cap} US$, so the run stops")

    def _check_observed_money_cap(self) -> None:
        """The cap on the money, checked again against what the provider really reported.

        The provider is the only one who knows what the call cost. A provider that reports far more tokens than
        the run planned would otherwise spend the money of the visitor under a cap that was supposed to hold the
        run (FR-009, FR-010).
        """
        cap = self._budget.max_estimated_usd
        if cap is None:
            return
        observed = self._cost(self._ledger.observed_input_tokens, self._ledger.observed_output_tokens)
        if observed is None:
            # The price of one model of the run is not known, so the money of the run is unknown too (FR-011).
            return
        if observed > cap:
            self._refuse(
                "max_estimated_usd",
                f"the run spent {observed} US$, which passes the cap of {cap} US$, so the run stops",
            )

    def _refuse(self, cap: str, message: str) -> None:
        """Records which cap stopped the run and raises the refusal that names it."""
        self._cut_by = cap
        raise BudgetExceededError(cap, f"the cap '{cap}' stopped the run: {message}")
