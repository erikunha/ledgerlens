"""The coordinator of a live run: the credential, the client of the provider, the budget and the trace of one case.

Why it exists: the routes of the live mode need something that holds a run together. The visitor brings a key, the
server resolves it, builds the client of the provider, calls a real model inside a budget, writes a trace and tells
the visitor what the run consumed. The domain holds the rules (the vault, the registry, the budget, the adapter);
this module holds the wiring, and the wiring is where the promise of the live mode is kept: one run, one credential,
one client, one budget, one trace.

What it guarantees:

* the run carries the mode `live_agent` and never `recorded_replay` (FR-024);
* every run ends with exactly one terminal trace event, whatever the reason, whatever the case raised and whatever the
  preamble raised before the case even started (FR-020, SC-006);
* the trace carries the provider and the identifier of the model (FR-026);
* the budget of the request lives in the `RunContext` of the run, and the coordinator is the only thing that
  enforces it (FR-025, FR-009);
* the cap of the money holds the run before the provider is called, and the estimate of the check is the worst case
  that the caps of the run allow and not the clamped plan of a call (FR-009, FR-010);
* a run whose number of calls is not bounded stops before the provider is called, because a cap of the money bounds a
  run only when the number of the calls is bounded (FR-009);
* the client of the provider is built for the run and holds the credential of the run, so two visitors never share
  a client and neither the environment of the process nor the global settings are ever touched (FR-007);
* the cancellation stops the calls that have not started and says that the cancellation of a call already in flight
  is a best effort and not a guarantee (FR-019, SC-010);
* a provider that times out ends the run, and the partial trace stays visible (FR-032);
* a call whose model differs from the model of the run is refused, because a run that compared two models under one
  identifier would make its own trace lie (FR-013);
* only a refusal of the key counts as a failure of the credential: a provider that is busy or that breaks does not
  drop a key that works, and a free text of an upstream failure that talks about a permission and not about the key
  does not drop it either (FR-023);
* nothing the run writes carries the key: the adapter scrubs the error of the provider at its own boundary and the
  coordinator scrubs everything it writes with the secret of the run, which it holds while the run lives, at every
  depth of a payload (FR-018, SC-001);
* the trace of the run names the branch, the revision and the canonical hash of the ledger that was read, and the
  file of that ledger goes away when the run ends, on every path, and also when the run never starts at all (ADR-038);
* the case of a run travels with the run: a run that is started with a case runs that case, and the coordinator of the
  caller is never rewritten, so it keeps the case it was built with (ADR-038);
* the case of a run is told that the run is over, so a case that lives in a long lived process does not keep the
  context and the four bridges of every run it ever served (ADR-038).

Why the coordinator holds the secret of the run: the vault does not keep the secret of a credential that is gone, on
purpose (ADR-033), and a credential can die in the middle of a run (the visitor presses "forget key", the session
ends, the time to live passes, the vault is full). A run whose credential died must still be safe, so the
coordinator keeps the secret of the run in the memory of the process while the run lives, scrubs with it, and drops
it when the run ends (FR-018, SC-001).

Why the case is a seam and not a chain of this module: the coordinator drives the provider through the `ModelCaller`,
and the case is the code that decides what to ask the model. The default case asks the model once, with the question
of the request. The agent of the demo plugs into that seam later, and every call it makes goes through the same
caller, so the budget counts the triage model, the generator of the SQL and any judge model all the same (FR-012).
The same seam reaches the tools: a case that uses a tool calls it through the caller, and every call of a tool
reserves one call of the budget of the run (FR-009).

Why the deadline of a call is enforced here: a provider that never answers would hold the run forever, and a run
that never ends has no terminal event and no report (FR-020, SC-003). The call therefore runs in a thread of its
own and the run gives up on it when the wall clock of the run is over. The thread of the provider cannot be killed,
and the run says so instead of pretending.
"""

from __future__ import annotations

import logging
import re
import shutil
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Protocol

from ledgerlens.byok.adapter import ProviderAdapter, ProviderRequest, ProviderResponse, build_adapter
from ledgerlens.byok.budget import BudgetCoordinator, BudgetExceededError, CostReport
from ledgerlens.byok.errors import ByokError, CredentialRefused
from ledgerlens.byok.registry import ModelProfile, ProviderRegistry, required_capabilities
from ledgerlens.byok.vault import CredentialVault
from ledgerlens.config import offline
from ledgerlens.observability.trace_event import (
    InMemoryTraceSink,
    TraceEvent,
    TraceEventDraft,
    TraceEventStream,
)
from ledgerlens.run_context import RunBudget, RunContext
from ledgerlens.sandbox.ledger_view import LedgerView

log = logging.getLogger(__name__)

__all__ = [
    "CANCELLED",
    "CANCELLING",
    "COMPLETED",
    "DEFAULT_PLANNED_OUTPUT_TOKENS",
    "FAILED",
    "LIVE_MODE",
    "RUNNING",
    "CaseExecutor",
    "LiveRunCoordinator",
    "LiveModeOffline",
    "LiveRunError",
    "LiveRunPlan",
    "LiveRunResult",
    "ModelCaller",
    "ModelChanged",
    "ProviderTimeout",
    "RunCancelled",
    "default_executor",
    "remove_the_ledger_file",
    "remove_the_ledger_of_the_run",
    "resolve_profile",
]

# The mode of a run of the live mode. A replay is a replay and the deterministic sandbox is the sandbox: neither one
# is ever labelled live (FR-024).
LIVE_MODE = "live_agent"

# The number of characters that one token of a text is worth. The rule is rough and it is only used to plan the
# tokens of a call, never to report them: the observed tokens are the ones the provider counted (FR-010).
_CHARS_PER_TOKEN = 4
# The number of output tokens a call plans when the request says nothing. The plan is an estimate and the estimate
# is what the cap on the money is checked against, so it is bounded and small (FR-009).
DEFAULT_PLANNED_OUTPUT_TOKENS = 512
# The marker that replaces the secret of a run in a text.
_REDACTED = "[REDACTED]"
# The statuses of a run. A run is running, and then it is over: completed, failed or cancelled.
RUNNING = "running"
CANCELLING = "cancelling"
COMPLETED = "completed"
FAILED = "failed"
CANCELLED = "cancelled"

# The statuses of an answer of a provider that mean that the key itself was refused. A rate limit, a timeout and an
# upstream failure are not among them: the provider had a bad day and the key of the visitor did not (FR-023).
_KEY_REFUSAL_STATUSES = frozenset({401})
# The phrases a provider uses when it refuses the key itself. A phrase names the credential and says that it was
# refused, so it is a refusal of the key. A provider that answers with a message and without a status is common,
# and the phrase is what is left to tell a refusal of the key from a failure of the provider (FR-023).
_KEY_REFUSAL_PHRASES = (
    "invalid api key",
    "invalid_api_key",
    "invalid x-api-key",
    "incorrect api key",
    "api key not valid",
    "no api key",
    "missing api key",
    "authentication error",
    "authentication_error",
    "authentication failed",
    "invalid authentication",
    "expired api key",
    "revoked api key",
)
# The states of the credential itself. A provider that says that the key expired, that it was revoked, that it is
# malformed or that it was never given is refusing the key of the visitor. The wording changes from a provider to
# another and the order of the words changes with it: one provider writes "expired api key" and another one writes
# "your api key expired". The table is therefore a table of states of the credential and not a table of sentences
# (FR-023).
_CREDENTIAL_STATE_WORDS = (
    "expired",
    "revoked",
    "invalid",
    "incorrect",
    "malformed",
    "missing",
    "unknown",
    "unrecognized",
    "not recognized",
    "not valid",
    "no longer valid",
    "not active",
    "disabled",
    "deactivated",
    "deleted",
    "terminated",
    "not found",
    "not provided",
    "not present",
    "not supplied",
    "did not provide",
    "didn't provide",
    "must provide",
    "no such",
    "required",
    "rejected",
    "refused",
    "wrong",
)
# A state of the credential inside a text. The bounds keep the state whole: a state inside another word is not a
# state of the credential (FR-023).
_CREDENTIAL_STATE_IN_TEXT = re.compile(
    r"(?<![0-9a-z])(?:" + "|".join(re.escape(word) for word in _CREDENTIAL_STATE_WORDS) + r")(?![0-9a-z])"
)
# The words that name the credential itself. A refusal of the credential only counts when the text says which thing
# was refused: an upstream failure that says that the request was unauthorized to read a bucket is a permission of
# the provider and not a refusal of the key of the visitor (FR-023).
_CREDENTIAL_WORDS = (
    "api key",
    "api_key",
    "apikey",
    "x-api-key",
    "credential",
    "authentication",
    "auth token",
    "access token",
)
# The words that say that something was refused. On their own they say nothing about the key of the visitor, and a
# provider that breaks must never drop a key that works (FR-023).
_AUTHORIZATION_WORDS = (
    "unauthorized",
    "not authorized",
    "unauthenticated",
    "forbidden",
    "denied",
)
# The status of a refusal of the key, inside a text. A provider that answers with a message and without a status
# attribute is common, and the status inside the text is the machine-readable truth about the refusal (FR-023).
_KEY_REFUSAL_STATUS_IN_TEXT = re.compile(r"(?<![0-9a-z])401(?![0-9a-z])")

# The report of a run that never had a budget: nothing was called, nothing was consumed and no price is known
# (FR-010, FR-011).
_NO_CONSUMPTION = CostReport(
    model_calls=0,
    tool_calls=0,
    calls_by_model={},
    input_tokens=0,
    output_tokens=0,
    elapsed_seconds=0.0,
    observed_cost_usd=None,
    estimated_cost_usd=None,
    price_known=False,
    money_cap_authoritative=False,
    cut_by=None,
)


class LiveRunError(Exception):
    """The base of the outcomes that end a run without an answer.

    Why it is not a refusal of the domain: a refusal says that a request cannot be served, and these outcomes say
    that a run that was served did not finish. The facade turns them into the answer of the run.
    """

    reason = "the live run failed"

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail
        super().__init__(f"{self.reason}: {detail}" if detail else self.reason)


class RunCancelled(LiveRunError):
    """The visitor cancelled the run, so the calls that had not started never start."""

    reason = "the run was cancelled"


class ProviderTimeout(LiveRunError):
    """The provider did not answer in time, so the run ends and the partial trace stays (FR-032)."""

    reason = "the provider did not answer in time"


class ModelChanged(LiveRunError):
    """The model of a run may not change in the middle of it (FR-013).

    Why a new run is the answer: a run that changed its model would compare two models under one identifier, and the
    trace of the run would lie about what ran. A new run identifier is what separates the two.
    """

    reason = "the model of a run may not change"


class LiveModeOffline(LiveRunError):
    """The product runs offline, so there is no live run (FR-001, FR-029).

    Why the coordinator refuses it and not only the facade: the mode of a run is `live_agent`, and a run that cannot
    call a provider would be a run that lies about its own mode.
    """

    reason = "the live mode is off because the product runs offline"


@dataclass(frozen=True)
class LiveRunPlan:
    """What a run needs to know before it starts.

    The plan carries the identifier of the model and not the model itself: the coordinator resolves the identifier
    against the allowlist of the registry, so a request that skips the interface is refused exactly like one that
    goes through it (FR-016, FR-027).

    The plan carries the ledger of the visitor: the file the tools of the agent read, with the branch, the revision
    and the canonical hash of the state it holds. A plan without a ledger is a plan of a run that has no ledger of the
    visitor, and the case of that run refuses it, because the fallback would hand the model the rows of every account
    of the repository (ADR-038).
    """

    run_id: str
    session_id: str
    model_profile_id: str
    credential_handle: str
    question: str
    budget: RunBudget
    account_id: str | None = None
    scenario_id: str | None = None
    sandbox_id: str | None = None
    expected_revision: int | None = None
    variant: str | None = None
    messages: tuple[Mapping[str, str], ...] = ()
    ledger: LedgerView | None = None


@dataclass(frozen=True)
class LiveRunResult:
    """What a run left behind: the status, the answer, the report of the cost and the trace.

    The `context` is the run context of the run, so the caller can read the identity of the run and the budget it
    ran with (FR-025). It is None only for a run that died before its context existed: the run still ends with a
    terminal event, and the identity of a run that never started is nothing to report (FR-020).
    """

    run_id: str
    status: str
    answer: str
    error: str | None
    report: CostReport
    provider: str
    model_profile_id: str
    model_id: str
    context: RunContext | None = None
    best_effort: bool = False
    events: tuple[TraceEvent, ...] = ()


class CaseExecutor(Protocol):
    """The case of a run: the code that decides what to ask the model.

    Why it is a protocol and not a function of this module: the agent of the demo plugs into this seam, and the
    coordinator never learns what the case does. Every call the case makes goes through the `ModelCaller`, so the
    budget counts them all the same (FR-012).

    The seam reaches the provider and the tools: the case asks the model with `complete` and it runs a tool with
    `call_tool`, and every one of those calls is reserved, counted and traced by the caller (FR-009).
    """

    def __call__(self, caller: ModelCaller, plan: LiveRunPlan) -> str: ...


def default_executor(caller: ModelCaller, plan: LiveRunPlan) -> str:
    """The default case: one call to the model of the run, with the question of the request.

    Why the question alone: the seam exists so that the agent of the demo can be plugged in later, and the default
    case has to be honest about what it does. It asks the model and returns what the model answered.
    """
    messages = plan.messages or ({"role": "user", "content": plan.question},)
    response = caller.complete(ProviderRequest(model_id="", messages=messages))
    return response.content


def resolve_profile(registry: ProviderRegistry, model_profile_id: str, *, variant: str | None = None) -> ModelProfile:
    """The profile of the allowlist that the run may use, or a refusal that names the reason.

    The identifier is resolved against the server side allowlist and never against the text of the request, and a
    profile that lacks the capability the variant needs is refused with the capability named instead of being
    replaced by another model (FR-015, FR-016, FR-027).
    """
    profile = registry.require(model_profile_id)
    registry.require_capabilities(profile, required_capabilities(variant or "C"))
    return profile


class ModelCaller:
    """The way a run talks to the provider and to the tools: every call is reserved, counted, traced and cancellable.

    Why the reservation happens here and not in the case: the cap has to be checked before the money of the visitor
    is spent, and the case is code that a future agent writes (FR-009).

    Why the model of the call is compared with the model of the run: a run that asked the provider for another model
    would compare two models under one identifier, and the trace of the run would lie about what ran (FR-013).

    Why the plan of the output tokens never promises more than the cap still allows: the size of the answer is not
    known before the call, so a plan that promised more would stop the run before it ever reaches the provider, and
    the cap of the calls of the models would never be the cap that stops the run (FR-009, FR-025).
    """

    def __init__(
        self,
        *,
        adapter: ProviderAdapter,
        budget: BudgetCoordinator,
        trace: TraceEventStream,
        cancel: threading.Event,
        provider: str,
        model_id: str,
        call_timeout: Callable[[], float | None],
        max_output_tokens: int | None = None,
        on_provider_failure: Callable[[BaseException], None] | None = None,
        scrub: Callable[[Mapping[str, Any]], dict[str, Any]] | None = None,
        money_guard: Callable[[str, int], None] | None = None,
    ) -> None:
        self._adapter = adapter
        self._budget = budget
        self._trace = trace
        self._cancel = cancel
        self._provider = provider
        self._model_id = model_id
        self._call_timeout = call_timeout
        self._max_output_tokens = max_output_tokens
        self._on_provider_failure = on_provider_failure
        # The scrub of the run, applied to every payload this caller writes. The caller does not know the secret of
        # the run, so the coordinator hands it the scrub it uses (FR-018, SC-001).
        self._scrub = scrub if scrub is not None else (lambda payload: dict(payload))
        # The guard of the money, asked before the call whether the run may still spend the money of the visitor
        # (FR-009).
        self._money_guard = money_guard
        # The output tokens that the calls of this run reserved so far. The plan of the next call is compared with
        # the headroom that is left, and this counter is what knows the headroom (FR-009).
        self._planned_output_tokens = 0
        # Whether a call is in flight right now. The cancellation of a call in flight is a best effort, and the run
        # has to say so (FR-019).
        self.in_flight = False

    @property
    def model_id(self) -> str:
        """The model of the run, the one the request may not change (FR-013)."""
        return self._model_id

    @property
    def cancelled(self) -> bool:
        """True when the visitor asked for the end of the run."""
        return self._cancel.is_set()

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        """One call of the provider, inside the budget of the run.

        The order is the promise of the budget: the model is checked, the call is reserved, the call happens, and the
        observed tokens are recorded after it, because the provider is the only one who knows what the call really
        cost (FR-009, FR-010, FR-013).
        """
        if self._cancel.is_set():
            raise RunCancelled("the run was cancelled before the call to the provider started")
        model_id = request.model_id or self._model_id
        if model_id != self._model_id:
            # The refusal happens before the reservation, so the money of the visitor is not spent on a call that
            # the model of the run does not allow (FR-013).
            raise ModelChanged(
                f"the run runs the model '{self._model_id}', and the model of a run may not change: the call asked "
                f"for '{model_id}'"
            )
        planned_input, planned_output = self._plan_of(request)
        self._budget.reserve_model_call(
            model_id,
            planned_input_tokens=planned_input,
            planned_output_tokens=planned_output,
        )
        # The guard of the money is asked after the reservation and before the call: the reservation says that the
        # caps of the calls and of the tokens hold the run, and the guard says that the money of the visitor may
        # still pay for what the run is about to do (FR-009).
        if self._money_guard is not None:
            self._money_guard(model_id, planned_input)
        self._planned_output_tokens += planned_output
        self._trace.emit(
            TraceEventDraft(
                "span.started",
                self._payload({"name": "model.call", "provider": self._provider, "model_id": model_id}),
            )
        )
        self.in_flight = True
        try:
            response = self._call(request)
        finally:
            self.in_flight = False
        self._budget.record_model_usage(
            model_id,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )
        self._trace.emit(
            TraceEventDraft(
                "span.ended",
                self._payload(
                    {
                        "name": "model.call",
                        "provider": self._provider,
                        "model_id": model_id,
                        "input_tokens": response.input_tokens,
                        "output_tokens": response.output_tokens,
                        "status": "ok",
                    }
                ),
            )
        )
        self._emit_counters()
        return response

    def call_tool(self, name: str, tool: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
        """Runs one call of a tool, inside the budget of the run.

        Why the tool comes from the case: the case decides what the agent does, and the coordinator never learns
        what a tool is. What the caller owns is the cap: every call of a tool reserves one, and the run stops when
        the cap of the tools is reached, with the name of the cap (FR-009, FR-012).

        Why the name of the tool is given: the trace has to say which tool ran, and the name is what a reader of
        the trace needs (FR-026).
        """
        if self._cancel.is_set():
            raise RunCancelled("the run was cancelled before the call of the tool started")
        self._budget.reserve_tool_call()
        self._trace.emit(TraceEventDraft("span.started", self._payload({"name": "tool.call", "tool": name})))
        status = "ok"
        try:
            result = tool(*args, **kwargs)
        except BaseException:
            status = "failed"
            raise
        finally:
            self._trace.emit(
                TraceEventDraft("span.ended", self._payload({"name": "tool.call", "tool": name, "status": status}))
            )
        return result

    def _payload(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """The payload of an event of this caller, scrubbed with the secret of the run (FR-018, SC-001).

        Why every payload goes through the scrub: the name of a tool and the identifier of a model are texts that
        the case chooses, and a case that names a tool after the key of the visitor would put the key in the trace
        of the run without ever touching the provider (FR-018, SC-001).
        """
        return self._scrub(payload)

    def _plan_of(self, request: ProviderRequest) -> tuple[int, int]:
        """The planned tokens of a call: the size of the request and a bounded guess of the answer.

        Why the guess is bounded and small: the plan is what the cap on the money is checked against, and a plan that
        assumes the worst would stop every run before it starts (FR-009).

        Why the plan of the output tokens is the headroom that is left and never more: the size of the answer is not
        known before the call, so the plan may not promise more tokens than the cap still allows. The cap of the
        output tokens is therefore held by the tokens the provider reported, and the cap of the calls of the models
        is the cap that stops the run (FR-009, FR-010, FR-025).
        """
        characters = sum(len(str(message.get("content", ""))) for message in request.messages)
        planned_input = max(1, characters // _CHARS_PER_TOKEN)
        return planned_input, self._planned_output_of_the_next_call()

    def _planned_output_of_the_next_call(self) -> int:
        """The output tokens that the next call plans: the bounded default, and never more than the headroom.

        Why the headroom and not the cap: a plan of the whole cap would stop the second call of a run whose cap is
        small, and the run would never reach the cap of the calls of the models (FR-009, FR-025).
        """
        if self._max_output_tokens is None:
            return DEFAULT_PLANNED_OUTPUT_TOKENS
        headroom = self._max_output_tokens - self._planned_output_tokens
        return max(0, min(DEFAULT_PLANNED_OUTPUT_TOKENS, headroom))

    def _call(self, request: ProviderRequest) -> ProviderResponse:
        """The call of the provider, with the deadline of the run.

        Why the call runs in a thread of its own: a provider that never answers would hold the run forever, and a run
        that never ends has no terminal event (FR-020, FR-032). The thread of the provider cannot be killed, so the
        run gives up on it and says that the provider did not answer in time.

        Why a call with no time left is never made: the wall clock of the run is over, and a call that starts with no
        time left spends the money of the visitor for nothing (SC-003).
        """
        timeout = self._call_timeout()
        if timeout is None:
            return self._adapter.complete(request)
        if timeout <= 0:
            raise ProviderTimeout("the wall clock of the run is over, so the provider was not called")
        outcome: dict[str, Any] = {}

        def target() -> None:
            try:
                outcome["value"] = self._adapter.complete(request)
            except BaseException as error:  # noqa: BLE001 - the error travels to the thread that waits for it
                outcome["error"] = error
                # A provider that refused the key is a failure of the credential, and the bound of the failures
                # drops a key that does not work (FR-023). A provider that was busy or that broke is not the fault
                # of the key, and the coordinator decides with the error what really happened.
                if self._on_provider_failure is not None:
                    self._on_provider_failure(error)

        worker = threading.Thread(target=target, name="ledgerlens-provider-call", daemon=True)
        worker.start()
        worker.join(timeout)
        if worker.is_alive():
            raise ProviderTimeout(f"the provider did not answer in {timeout:.3f} seconds")
        if "error" in outcome:
            raise outcome["error"]
        return outcome["value"]

    def _emit_counters(self) -> None:
        """The counters of the run, as an event, so the interface sees the budget being consumed (T030)."""
        report = self._budget.report()
        self._trace.emit(
            TraceEventDraft(
                "run.status",
                self._payload(
                    {
                        "model_calls": report.model_calls,
                        "tool_calls": report.tool_calls,
                        "input_tokens": report.input_tokens,
                        "output_tokens": report.output_tokens,
                        "elapsed_seconds": round(report.elapsed_seconds, 3),
                    }
                ),
            )
        )


class _RunSecret:
    """The secret of a run, held so that no representation of it ever shows the key.

    Why the secret is not a plain text: a text prints itself, and the representation of a run ends up in a debug
    print and in a traceback with the locals. The domain holds the secret of a credential the same way, and the run
    holds the secret of its own credential the same way too (FR-003, FR-018).

    Why the bytes are wiped when the run ends: the key of the visitor lives in the memory of the process and nowhere
    else, and the run that is over has nothing left to protect (FR-002, FR-003, FR-021).
    """

    def __init__(self, text: str) -> None:
        self._bytes = bytearray(text.encode("utf-8"))

    @property
    def text(self) -> str:
        """The secret as text, for the code that scrubs with it and for the client of the provider."""
        return bytes(self._bytes).decode("utf-8")

    def wipe(self) -> None:
        """Overwrites the bytes of the secret and empties it, on a best effort basis (FR-021)."""
        for index in range(len(self._bytes)):
            self._bytes[index] = 0
        self._bytes = bytearray()

    def __repr__(self) -> str:
        """The holder without its content, because a representation ends up in the logs."""
        return "RunSecret([REDACTED])"

    __str__ = __repr__


@dataclass
class _Run:
    """The state of a run inside the coordinator: the plan, the status and the flags of the cancellation."""

    plan: LiveRunPlan
    profile: ModelProfile
    # The case of this run. It travels with the run, because a run that answered with another case would answer a
    # question that nobody asked (ADR-038).
    case: CaseExecutor
    status: str = RUNNING
    cancel: threading.Event = field(default_factory=threading.Event)
    done: threading.Event = field(default_factory=threading.Event)
    best_effort: bool = False
    # The caller of the run, once it exists. The cancellation needs it to know whether a call is in flight.
    caller: ModelCaller | None = None
    result: LiveRunResult | None = None
    thread: threading.Thread | None = None
    # The secret of this run, in the memory of the process and nowhere else. It is here so that the run scrubs what
    # it writes even when the credential of the run is gone: the vault does not keep the secret of a credential
    # that died, and a run whose credential died must still be safe (FR-018, SC-001). The run drops it when it ends.
    secret: _RunSecret | None = None


class LiveRunCoordinator:
    """The coordinator of the live runs of the process.

    Why the runs live in the process and not in a store: the key of the visitor lives in the memory of the process
    and nowhere else (FR-002, FR-003), and a run that outlived the process would have no client to answer.

    Why a run happens in a thread of its own: the visitor has to be able to cancel a run, and a cancellation that
    waits for the request that started the run would be a cancellation that never arrives (FR-019).

    Why the coordinator holds the secret of a run while the run lives: the vault does not keep the secret of a
    credential that is gone, and a run whose credential dies in the middle of it still has to write nothing that
    carries the key (FR-018, SC-001).

    Why the coordinator never changes its own case: the case of a run travels with the run, and a coordinator that
    the facade rewrote would change the case of every other caller of that coordinator as well (ADR-038).
    """

    def __init__(
        self,
        *,
        registry: ProviderRegistry,
        vault: CredentialVault,
        sink: InMemoryTraceSink | None = None,
        adapter_factory: Callable[[str, str], ProviderAdapter] | None = None,
        executor: CaseExecutor | None = None,
        clock: Callable[[], float] = time.monotonic,
        call_timeout: float | None = None,
    ) -> None:
        self._registry = registry
        self._vault = vault
        self._sink = sink if sink is not None else InMemoryTraceSink()
        self._adapter_factory = adapter_factory or _real_adapter
        self._executor = executor or default_executor
        self._clock = clock
        self._call_timeout = call_timeout
        self._runs: dict[str, _Run] = {}
        self._lock = threading.Lock()

    @property
    def sink(self) -> InMemoryTraceSink:
        """The sink of the trace of the runs, where the events are read from."""
        return self._sink

    def start(self, plan: LiveRunPlan, *, case: CaseExecutor | None = None) -> LiveRunResult | None:
        """Starts a run and answers what is known about it right now.

        The model of the run is resolved before the thread starts, so a model that is not in the allowlist is
        refused before anything happens (FR-027). The answer is None while the run is running: the run itself
        answers when it is over.

        The case of the run travels with the run: a caller that gives a case gets that case, and a caller that
        gives none gets the case this coordinator was built with. The coordinator is never rewritten, so the
        coordinator of the caller keeps the case it was built with (ADR-038).

        Why the file of the ledger goes away when the run never starts: a run that never starts has no thread and
        no end, and the rows of a visitor may not stay on the disk of the server for a run that never happened
        (ADR-038).
        """
        if offline():
            # The run never starts, so the file of the ledger of the run goes away with it (ADR-038).
            remove_the_ledger_of_the_run(plan.ledger)
            raise LiveModeOffline(
                "the live mode is off because the product runs offline (LEDGERLENS_OFFLINE=1); "
                "the replay and the sandbox keep working exactly as before"
            )
        try:
            profile = resolve_profile(self._registry, plan.model_profile_id, variant=plan.variant)
        except ByokError:
            # The run never starts, so the file of the ledger of the run goes away with it (ADR-038).
            remove_the_ledger_of_the_run(plan.ledger)
            raise
        with self._lock:
            existing = self._runs.get(plan.run_id)
            if existing is not None:
                if existing.profile.profile_id != profile.profile_id:
                    # This run never starts, and the file of the ledger of the request goes away with it (ADR-038).
                    remove_the_ledger_of_the_run(plan.ledger)
                    raise ModelChanged(
                        f"the run '{plan.run_id}' runs the model '{existing.profile.profile_id}', and the model of a "
                        "run may not change: start a new run with a new run identifier"
                    )
                return existing.result
            run = _Run(plan=plan, profile=profile, case=case if case is not None else self._executor)
            self._runs[plan.run_id] = run
        thread = threading.Thread(target=self._execute, args=(run,), name="ledgerlens-live-run", daemon=True)
        run.thread = thread
        thread.start()
        return None

    def wait(self, run_id: str, timeout: float = 10.0) -> LiveRunResult | None:
        """Waits for the end of a run and answers what it left behind, or None when it did not end in time."""
        with self._lock:
            run = self._runs.get(run_id)
        if run is None:
            return None
        run.done.wait(timeout)
        return run.result

    def result(self, run_id: str) -> LiveRunResult | None:
        """What a run left behind, or None when there is no such run or it is still running."""
        with self._lock:
            run = self._runs.get(run_id)
        return run.result if run is not None else None

    def status(self, run_id: str) -> str | None:
        """The status of a run, or None when there is no such run."""
        with self._lock:
            run = self._runs.get(run_id)
        return run.status if run is not None else None

    def session_of(self, run_id: str) -> str | None:
        """The session that owns a run, or None when there is no such run.

        Why the owner is known: a run belongs to the session that started it, and a session may only read its own
        runs (FR-006, SC-002).
        """
        with self._lock:
            run = self._runs.get(run_id)
        return run.plan.session_id if run is not None else None

    def cancel_requested(self, run_id: str) -> bool:
        """Whether the visitor already asked for the end of a run (FR-019)."""
        with self._lock:
            run = self._runs.get(run_id)
        return run.cancel.is_set() if run is not None else False

    def best_effort_of(self, run_id: str) -> bool:
        """Whether the cancellation of a run had to leave a call in flight at the provider (FR-019)."""
        with self._lock:
            run = self._runs.get(run_id)
        return run.best_effort if run is not None else False

    def cancel(self, run_id: str) -> bool:
        """Asks for the end of a run and answers whether there was a run to end.

        The calls that have not started never start (SC-010). A call that is already at the provider cannot be
        guaranteed to stop, so the run remembers that the cancellation was a best effort and says so (FR-019).
        """
        with self._lock:
            run = self._runs.get(run_id)
        if run is None:
            return False
        if run.status != RUNNING:
            return False
        run.cancel.set()
        # The run is stopping, and the interface has to be able to say so before the run is over.
        run.status = CANCELLING
        if run.caller is not None and run.caller.in_flight:
            run.best_effort = True
        return True

    def events(self, run_id: str, after_seq: int = 0, limit: int = 100) -> list[TraceEvent]:
        """The events of the trace of a run, after the given number."""
        return self._sink.read_from(run_id, after_seq, limit)

    # --- the run itself -----------------------------------------------------------------------------

    def _execute(self, run: _Run) -> None:
        """Runs the case and leaves the terminal event behind, whatever happened (FR-020)."""
        try:
            self._run_the_case(run)
        finally:
            if run.result is None:
                # The run failed in a way that left no answer at all. The status says so, because a run that never
                # ends is a run the visitor waits for forever (FR-020).
                run.status = FAILED
            run.done.set()

    def _run_the_case(self, run: _Run) -> None:
        """The case of the run, the trace of it and the report of what it consumed.

        The terminal event is written in a `finally`, so a run that ends in any way at all leaves exactly one terminal
        event behind (FR-020, SC-006). The guard catches what a case can raise, including the errors that are not
        exceptions, because a run that dies without a terminal event leaves the cost route answering that the run is
        still running for ever.

        Why the trace of the run is built before the context: a run that dies in the preamble, before its context
        exists, still has to leave a terminal event behind (FR-020, SC-006).

        Why the secret of the run is held here and not only in the vault: a credential can die in the middle of a
        run, and the vault does not keep the secret of a credential that is gone (ADR-033). The run keeps it while it
        lives and scrubs with it (FR-018, SC-001).
        """
        plan = run.plan
        profile = run.profile
        # The trace of the run exists before anything else, so that every path of the run leaves a terminal event.
        trace = TraceEventStream(plan.run_id, self._sink, mode=LIVE_MODE)
        status = FAILED
        answer = ""
        error: str | None = None
        cut_by: str | None = None
        context: RunContext | None = None
        budget: BudgetCoordinator | None = None
        try:
            context = RunContext(
                run_id=plan.run_id,
                session_id=plan.session_id,
                mode=LIVE_MODE,
                account_id=plan.account_id,
                branch_id=plan.sandbox_id,
                branch_revision=plan.expected_revision,
                model_profile_id=profile.profile_id,
                budget=plan.budget,
            )
            budget = BudgetCoordinator(plan.budget, self._registry, clock=self._clock)
            ledger = plan.ledger
            trace.emit(
                TraceEventDraft(
                    "run.started",
                    self._scrub_payload(
                        {
                            "provider": profile.provider,
                            "model_profile_id": profile.profile_id,
                            "model_id": profile.model_id,
                            "account_id": plan.account_id,
                            "scenario_id": plan.scenario_id,
                            "variant": plan.variant,
                            # The ledger that the run reads, with the branch, the revision and the hash of the state
                            # it holds: a reader of the trace knows which ledger answered the question (ADR-038).
                            "branch_id": None if ledger is None else ledger.branch_id,
                            "branch_revision": None if ledger is None else ledger.revision,
                            "canonical_hash": None if ledger is None else ledger.canonical_hash,
                            "budget": {
                                "max_model_calls": plan.budget.max_model_calls,
                                "max_tool_calls": plan.budget.max_tool_calls,
                                "max_wall_seconds": plan.budget.max_wall_seconds,
                                "max_output_tokens": plan.budget.max_output_tokens,
                                "max_input_tokens": plan.budget.max_input_tokens,
                                "max_estimated_usd": (
                                    None
                                    if plan.budget.max_estimated_usd is None
                                    else str(plan.budget.max_estimated_usd)
                                ),
                            },
                        },
                        run,
                    ),
                )
            )
            secret = _RunSecret(self._vault.resolve(plan.credential_handle, session_id=plan.session_id))
            # The coordinator holds the secret of this run while the run lives. The vault does not keep the secret of
            # a credential that is gone, and a run whose credential was dropped in the middle of it still has to be
            # safe (FR-018, SC-001).
            run.secret = secret
            adapter = self._adapter_factory(profile.provider, secret.text)
            caller = ModelCaller(
                adapter=adapter,
                budget=budget,
                trace=trace,
                cancel=run.cancel,
                provider=profile.provider,
                model_id=profile.model_id,
                call_timeout=lambda: self._timeout_of(run, budget),
                max_output_tokens=plan.budget.max_output_tokens,
                on_provider_failure=lambda failure: self._record_the_failure_of_the_credential(run, failure),
                scrub=lambda payload: self._scrub_payload(payload, run),
                money_guard=lambda model_id, planned_input: self._guard_the_money_of_the_run(
                    run, budget, model_id, planned_input
                ),
            )
            run.caller = caller
            answer = run.case(caller, plan)
            if run.cancel.is_set():
                # The visitor asked for the end of the run while the last call was at the provider. The run stops
                # and it says so, because the answer of a run that the visitor stopped is not the answer of a run
                # that finished (FR-019).
                raise RunCancelled("the run was cancelled while the last call was at the provider")
            status = COMPLETED
        except RunCancelled as cancelled:
            status = CANCELLED
            error = self._scrub(str(cancelled), run)
        except ProviderTimeout as timeout:
            status = FAILED
            error = self._scrub(str(timeout), run)
        except BudgetExceededError as exhausted:
            # The cap of the money stopped the run, and the report of the run has to name it (FR-009).
            status = FAILED
            cut_by = exhausted.cap
            error = self._scrub(str(exhausted), run)
        except ByokError as refusal:
            status = FAILED
            error = self._scrub(str(refusal), run)
        except ModelChanged as changed:
            status = FAILED
            error = self._scrub(str(changed), run)
        except BaseException as failure:  # noqa: BLE001 - the run ends with a reason and never crashes the process
            status = FAILED
            error = self._scrub(f"{type(failure).__name__}: {failure}", run)
            log.warning("the live run %s failed: %s", plan.run_id, error)
        finally:
            report = budget.report() if budget is not None else _NO_CONSUMPTION
            if cut_by is not None:
                report = replace(report, cut_by=cut_by)
            try:
                trace.finish(
                    status,  # type: ignore[arg-type]
                    self._scrub_payload(
                        {
                            "status": status,
                            "error": error,
                            "cut_by": report.cut_by,
                            "best_effort": run.best_effort,
                            "model_calls": report.model_calls,
                            "input_tokens": report.input_tokens,
                            "output_tokens": report.output_tokens,
                        },
                        run,
                    ),
                )
            except Exception as failure:  # noqa: BLE001 - a trace that cannot be written never fails the run
                log.warning("the terminal event of the live run %s could not be written: %s", plan.run_id, failure)
            run.result = LiveRunResult(
                run_id=plan.run_id,
                status=status,
                answer=self._scrub(answer, run),
                error=error,
                report=report,
                provider=profile.provider,
                model_profile_id=profile.profile_id,
                model_id=profile.model_id,
                context=context,
                best_effort=run.best_effort,
                events=tuple(self._sink.read_from(plan.run_id, 0, 1000)),
            )
            run.status = status
            # The run drops the secret of the run when it ends: the key of the visitor lives in the memory of the
            # process and nowhere else, and a run that is over has nothing left to protect (FR-002, FR-003).
            if run.secret is not None:
                run.secret.wipe()
            run.secret = None
            # The file of the ledger of the run goes away with the run, on every path: a file that outlives its run
            # holds the rows of a visitor on the disk of the server longer than the run needs it (ADR-038).
            remove_the_ledger_of_the_run(plan.ledger)
            # The case forgets the run when the run ends: the case holds a context and four bridges for every run
            # it ever served, and a long lived process would grow without end (ADR-038).
            _forget_the_run(run.case, plan.run_id)

    def _record_the_failure_of_the_credential(self, run: _Run, error: BaseException) -> None:
        """Counts a failure of the credential of the run, so a key that does not work dies sooner (FR-023).

        Why only a refusal of the key counts: a provider that is busy, that answers with a rate limit, that times out
        or that is broken is not the fault of the key, and a good key must not die because the provider had a bad
        day. Three rate limits must not drop a key that works (FR-023).

        The count is tolerant: a credential that is already gone cannot be counted, and a run that fails must not
        fail because of the count.
        """
        if not _is_a_refusal_of_the_key(error):
            return
        try:
            self._vault.record_failure(run.plan.credential_handle, session_id=run.plan.session_id)
        except ByokError:
            return

    def _guard_the_money_of_the_run(
        self,
        run: _Run,
        budget: BudgetCoordinator,
        model_id: str,
        planned_input: int,
    ) -> None:
        """The cap of the money, checked before the call against the worst case of the run (FR-009).

        Why the worst case and not the plan of the call: the plan of the output tokens of a call is clamped by the
        headroom that the cap of the output tokens leaves, and a clamp makes the money of the call look small. The
        provider may bill the whole cap of the output tokens of the run for one call, and the run may still make the
        calls that the cap of the calls allows, so what the run may spend is what the caps of the run allow at
        their worst.

        Why the check is before the call: the money of the visitor is spent when the provider answers and not
        before, so a check that comes after the call is a report of a bill and not a cap (FR-009, FR-010).

        Why the price of the registry is the only number here: the money is computed by the code and never by the
        model, and a model without a verified price makes the money of the run unknown instead of estimated
        (FR-010, FR-011).

        Why a run without a cap of the calls stops: a cap of the money bounds a run only when the number of the calls
        is bounded. A run without that cap has no worst case, so the money of the visitor cannot be promised to stay
        under the cap, and the run stops before the provider is called (FR-009).
        """
        cap = run.plan.budget.max_estimated_usd
        if cap is None:
            return
        if self._registry.price_for(model_id) is None:
            # The price of the model is not known, so the cap of the money is not authoritative and the other caps
            # of the run hold the execution instead (FR-011).
            return
        if run.plan.budget.max_model_calls is None:
            raise BudgetExceededError(
                "max_estimated_usd",
                f"the run may make an unbounded number of calls, which the cap of {cap} US$ cannot pay for, "
                "so the run stops",
            )
        report = budget.report()
        committed = report.estimated_cost_usd
        if committed is None:
            return
        output_cap = run.plan.budget.max_output_tokens
        if output_cap is None:
            output_cap = DEFAULT_PLANNED_OUTPUT_TOKENS
        one_call = self._registry.estimate_usd(model_id, input_tokens=planned_input, output_tokens=output_cap)
        if one_call is None:
            return
        # The call that is about to happen and the calls that the cap of the calls still allows. The cap of the calls
        # is read again here because the plan of the run is read again here, and the guard runs before every call.
        calls_left = 1
        if run.plan.budget.max_model_calls is not None:
            calls_left += max(0, run.plan.budget.max_model_calls - report.model_calls)
        worst = committed + one_call * calls_left
        if worst > cap:
            raise BudgetExceededError(
                "max_estimated_usd",
                f"the run may spend {worst} US$, which passes the cap of {cap} US$, so the run stops",
            )

    def _timeout_of(self, run: _Run, budget: BudgetCoordinator) -> float | None:
        """The time the call of the provider may take, or None when the run has no wall clock cap.

        Why the cap of the run is the deadline: the wall clock of the run is the promise to the visitor that the run
        ends (SC-003), and a call that hangs is the only thing that can break it.

        Why the elapsed time of the budget is the reference and not the clock of the process: the clock of the
        process counts from the moment it started, and the cap of the run counts from the moment the run started.

        Why there is no floor under the deadline: the cap of the wall clock bounds the run, and a call that is given
        time it does not have would spend the money of the visitor after the cap (SC-003).
        """
        if self._call_timeout is not None:
            return self._call_timeout
        cap = run.plan.budget.max_wall_seconds
        if cap is None:
            return None
        remaining = cap - budget.elapsed_seconds()
        return max(0.0, remaining)

    def _scrub(self, text: str, run: _Run | None = None) -> str:
        """The text without the secret of the run and without the secrets the vault holds (FR-018).

        Why the secret of the run comes first: the vault stops holding the secret of a credential that is gone, and a
        run whose credential died in the middle of it still has to be safe. The coordinator holds the secret of the
        run while the run lives, and the run drops it when the run ends (FR-018, SC-001).

        Why the scrub of the vault comes second: it covers the secrets of the credentials that are alive and the
        shapes of the keys the repository knows, and it is the layer of the texts the facade writes outside a run.
        """
        cleaned = text
        holder = run.secret if run is not None else None
        secret = holder.text if holder is not None else ""
        if secret and secret in cleaned:
            cleaned = cleaned.replace(secret, _REDACTED)
        return self._vault.scrub(cleaned)

    def _scrub_payload(self, payload: Mapping[str, Any], run: _Run | None = None) -> dict[str, Any]:
        """The payload of an event without the secret of the run and without the secrets of the vault (FR-018).

        Why the run is an argument and not only the vault: the vault stops holding the secret of a credential that is
        gone, and the run holds the secret of its own credential while the run lives. A payload of an event of a run
        is scrubbed with the secret of that run (FR-018, SC-001).

        Why every depth of the payload is scrubbed: a payload is a structure and not a text, and a structure that
        nests a text that carries the key would put the key in the trace of the run without ever touching the
        provider (FR-018, SC-001).
        """
        return {name: self._scrub_value(value, run) for name, value in payload.items()}

    def _scrub_value(self, value: Any, run: _Run | None = None) -> Any:
        """The value of a payload without the secret of the run, at any depth (FR-018, SC-001).

        Why the recursion: the payload of an event is a structure whose leaves are texts, and the texts are the ones
        that can carry the key of the visitor. A mapping or a sequence inside the payload is walked, so the scrub does
        not depend on the shape that the payloads of the product happen to have today (FR-018, SC-001).
        """
        if isinstance(value, str):
            return self._scrub(value, run)
        if isinstance(value, Mapping):
            return {name: self._scrub_value(item, run) for name, item in value.items()}
        if isinstance(value, (list, tuple)):
            items = [self._scrub_value(item, run) for item in value]
            return tuple(items) if isinstance(value, tuple) else items
        return value


def _real_adapter(provider: str, api_key: str) -> ProviderAdapter:
    """The client of a real provider, built for the run, with the credential in its constructor (FR-007)."""
    return build_adapter(provider, api_key)


def remove_the_ledger_of_the_run(ledger: LedgerView | None) -> None:
    """The file of the ledger of the run goes away when the run ends, on every path (ADR-038).

    Why the run removes it and not the facade: the facade does not wait for the end of the run, and a file that
    outlives its run holds the rows of a visitor on the disk of the server for longer than the run needs them.

    Why the removal never raises: the file is already gone or already unreadable, and the run has answered.

    Why this is public: the facade removes the file too when the coordinator refuses to start the run, and a run
    that never started has no thread of its own to remove it (ADR-038).
    """
    if ledger is None:
        return
    remove_the_ledger_file(ledger.path)


def _forget_the_run(case: CaseExecutor, run_id: str) -> None:
    """Tells the case of the run that the run is over, when the case knows how to forget a run (ADR-038).

    Why the check and not a change of the protocol: a case that is not the case of the demo has nothing to forget,
    and the seam of `CaseExecutor` has to keep working with every case (ADR-038).

    Why a failure is only logged: a case that cannot forget keeps a little more memory, and it must never fail a
    run that is already over (FR-020).
    """
    forget = getattr(case, "forget", None)
    if forget is None:
        return
    try:
        forget(run_id)
    except Exception as failure:  # noqa: BLE001 - a case that cannot forget never fails the run
        log.warning("the case of the live run %s could not forget the run: %s", run_id, failure)


def remove_the_ledger_file(path: Path | str) -> None:
    """The file of the ledger of a run goes away, and the folder that held it goes with it (ADR-038).

    Why the folder goes with it: the file is the only thing the folder holds, and a folder of nothing is left over
    from a run that nobody reads again.

    Why the temporary file goes too: the materialization writes the file under a temporary name, and that temporary
    file holds the rows of a visitor for as long as the file itself would hold them.

    Why a failure never fails the run: the file is already gone or already unreadable, and the run has answered.
    """
    target = Path(path)
    try:
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        else:
            target.unlink(missing_ok=True)
        target.with_name(target.name + ".tmp").unlink(missing_ok=True)
        folder = target.parent
        if folder.is_dir() and not any(folder.iterdir()):
            folder.rmdir()
    except OSError as failure:
        log.warning("the ledger file of the live run could not be removed: %s", failure)


def _is_a_refusal_of_the_key(error: BaseException) -> bool:
    """Whether the error of the provider means that the key itself was refused (FR-023).

    Why the distinction matters: a credential that the provider refuses is dead and has to die, but a provider that
    answers with a rate limit, a timeout or an upstream failure says nothing about the key, and three rate limits
    must not drop a key that works (FR-023).

    Why the status comes first: the status of the answer of the provider is the machine-readable truth about the
    refusal, and it is what the clients of the providers carry. Why the words come second: a provider that answers
    with a message and without a status is common, and the words are what is left to tell a refusal of the key from
    a failure of the provider.
    """
    for current in _chain_of(error):
        if isinstance(current, CredentialRefused):
            return True
        if any(status in _KEY_REFUSAL_STATUSES for status in _statuses_of(current)):
            return True
        for attribute in ("code", "type"):
            value = getattr(current, attribute, None)
            if isinstance(value, str) and _names_a_refusal_of_the_key(value):
                return True
        if _names_a_refusal_of_the_key(str(current)):
            return True
    return False


def _names_a_refusal_of_the_key(text: str) -> bool:
    """Whether a text of a provider says that the key itself was refused (FR-023).

    Why a phrase and not a single word: a word of refusal alone says nothing about the key. An upstream failure that
    says that the request was unauthorized to read a bucket is a permission of the provider, and it must not drop a
    key that works (FR-023).

    Why the second step exists: a word of refusal only counts when the text also names the credential or the status
    of the refusal, because a refusal of the credential names the credential or says that the provider answered with
    the status of an authentication (FR-023).

    Why the state of the credential is a step of its own: the table of the sentences is never complete, because the
    provider writes the words in another order ("your api key expired" and not only "expired api key"). A state of the
    credential counts when the text names the credential, and a permission of the provider never names it (FR-023).
    """
    lowered = text.lower()
    if any(phrase in lowered for phrase in _KEY_REFUSAL_PHRASES):
        return True
    if _names_a_state_of_the_credential(lowered):
        return True
    if not any(word in lowered for word in _AUTHORIZATION_WORDS):
        return False
    if any(word in lowered for word in _CREDENTIAL_WORDS):
        return True
    return _KEY_REFUSAL_STATUS_IN_TEXT.search(text) is not None


def _names_a_state_of_the_credential(lowered: str) -> bool:
    """Whether a text of a provider says that the credential itself is not usable (FR-023).

    Why the credential is required: a state of the provider says nothing about the key of the visitor. An upstream
    failure that says that the bucket was not found is a resource that is missing and not a key that is refused, and
    it must not drop a key that works (FR-023).
    """
    if not any(word in lowered for word in _CREDENTIAL_WORDS):
        return False
    return _CREDENTIAL_STATE_IN_TEXT.search(lowered) is not None


def _statuses_of(error: BaseException) -> tuple[int, ...]:
    """The HTTP statuses that an error of a provider carries, wherever the client of the provider put them."""
    found: list[int] = []
    for holder in (error, getattr(error, "response", None)):
        status = getattr(holder, "status_code", None)
        if isinstance(status, int) and not isinstance(status, bool):
            found.append(status)
    return tuple(found)


def _chain_of(error: BaseException) -> list[BaseException]:
    """The error and the causes and the contexts it carries, without a loop."""
    chain: list[BaseException] = []
    seen: set[int] = set()
    pending: list[BaseException] = [error]
    while pending:
        current = pending.pop(0)
        if id(current) in seen:
            continue
        seen.add(id(current))
        chain.append(current)
        pending.extend(item for item in (current.__cause__, current.__context__) if item is not None)
    return chain
