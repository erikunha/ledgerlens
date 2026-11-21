"""The coordinator of a live run: the mode, the terminal event, the budget, the cancellation and the key.

What they guarantee, and why: (a) the run carries the mode `live_agent` and never `recorded_replay` (FR-024);
(b) every run ends with a terminal trace event, whatever the reason (FR-020, SC-006); (c) the trace carries the
provider and the identifier of the model (FR-026); (d) the budget of the request lives in the run context of the run
and the coordinator is the only thing that enforces it, so the run stops at the attempt that would break a cap
(FR-025, FR-009); (e) the key of the visitor never reaches the trace, the log or the answer of the run, even when
the provider raises an exception that carries it (FR-018, SC-001); (f) a cancelled run makes no further provider
call, ends with the terminal event of a cancellation and says that the cancellation of a call already in flight is
a best effort (FR-019, SC-010); (g) a provider that does not answer in time ends the run and the partial trace stays
(FR-032); (h) a handle of another session is refused and the run never reaches the provider (FR-006, SC-002);
(i) the model of a run may not change in the middle of it (FR-013); (j) the secret of a run is masked in every
representation of the run and is dropped when the run ends (FR-018, SC-001, FR-002); (k) the payload of every event of
a run is scrubbed with the secret of that run, the name of a tool included (FR-018); (l) the cap of the money holds the
run before the provider is called, and it is checked against the worst case that the caps of the run allow and not
against one call (FR-009, FR-010); (m) only a refusal of the key counts as a failure of the credential, a provider
that is busy does not drop a key that works, and a free text of an upstream failure that talks about a permission and
not about the key does not drop it either, and every wording with which a provider refuses the key itself is pinned
case by case in a table of data (FR-023); (n) a run that dies before its case
even started still leaves exactly one terminal event (FR-020, SC-006); (o) a run whose number of calls is not bounded
stops before the provider is called, because a cap of the money bounds a run only when the number of the calls is
bounded (FR-009); (p) the payload of an event is scrubbed at every depth, and a structure that nests a text that
carries the key never reaches the trace (FR-018, SC-001).

Everything offline, with no key and no network: the provider is the fake adapter of the domain, and the tests of
this file never open a socket.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest

from ledgerlens.api.live_run import (
    LIVE_MODE,
    LiveModeOffline,
    LiveRunCoordinator,
    LiveRunPlan,
    ModelChanged,
    resolve_profile,
)
from ledgerlens.byok.adapter import FakeProviderAdapter, ProviderAdapter, ProviderRequest, ProviderResponse
from ledgerlens.byok.errors import CapabilityMissing, CredentialUnknown
from ledgerlens.byok.registry import ModelNotAllowed, ModelProfile, Pricing, ProviderRegistry
from ledgerlens.byok.vault import CredentialVault
from ledgerlens.run_context import RunBudget

# The marker of the credential of the run: a shape that no known pattern of the repository matches, so only the
# vault and the adapter of the run can scrub it.
MARKER = "ledgerlens-marker-" + "4f3a9c2b7e1d"
OTHER_MARKER = "ledgerlens-marker-" + "88ce10"

SESSION = "sess-a"
OTHER_SESSION = "sess-b"
PROFILE_ID = "openai-gpt-4.1-mini"
MODEL_ID = "gpt-4.1-mini"

PRICED = ModelProfile(
    profile_id=PROFILE_ID,
    provider="openai",
    model_id=MODEL_ID,
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
    profile_id="openai-mystery",
    provider="openai",
    model_id="gpt-mystery",
    display_name="Mystery",
    capabilities=("chat", "tool_calling"),
    status="tested",
    enabled_in_public_demo=True,
    pricing=Pricing(source="unknown", last_verified=None, input_per_1m_usd=None, output_per_1m_usd=None),
)
WITHOUT_TOOLS = ModelProfile(
    profile_id="openai-chat-only",
    provider="openai",
    model_id="gpt-chat-only",
    display_name="Chat only",
    capabilities=("chat",),
    status="tested",
    enabled_in_public_demo=True,
    pricing=Pricing(source="unknown", last_verified=None, input_per_1m_usd=None, output_per_1m_usd=None),
)


def registry() -> ProviderRegistry:
    """The allowlist of the tests: a model with a price, one without and one without tool calling."""
    return ProviderRegistry([PRICED, UNPRICED, WITHOUT_TOOLS])


class RawAdapter(ProviderAdapter):
    """An adapter that raises the error of the provider as it is, without scrubbing it.

    Why it exists: the fake adapter of the domain scrubs the credential of the run at its own boundary, and that
    boundary is proved by the test of the adapter. This one leaves the key in the error, so the test proves the
    second layer: the facade scrubs what it writes (FR-018, SC-001).
    """

    def __init__(self, provider: str, api_key: str) -> None:
        super().__init__(provider, api_key)
        self.calls: list[ProviderRequest] = []

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        self.calls.append(request)
        raise RuntimeError(f"401 invalid api key {self._credential.text}")

    def chat_model(self, model_id: str) -> object:
        raise NotImplementedError


def _plan(handle: str, **overrides: object) -> LiveRunPlan:
    """A plan of a run: the question of a case and the caps of the visitor."""
    values: dict[str, object] = {
        "run_id": "run-test",
        "session_id": SESSION,
        "model_profile_id": PROFILE_ID,
        "credential_handle": handle,
        "question": "What happened to the refund of TX-2048?",
        "budget": RunBudget(max_model_calls=2, max_tool_calls=4, max_wall_seconds=30, max_output_tokens=512),
        "account_id": "C-0412",
        "scenario_id": "S01",
        "variant": "B",
    }
    values.update(overrides)
    return LiveRunPlan(**values)  # type: ignore[arg-type]


def _coordinator(
    adapter: ProviderAdapter,
    vault: CredentialVault,
    *,
    executor: object | None = None,
    call_timeout: float | None = None,
    clock: object | None = None,
) -> LiveRunCoordinator:
    """A coordinator over the fake provider of the test, with no socket anywhere."""
    return LiveRunCoordinator(
        registry=registry(),
        vault=vault,
        adapter_factory=lambda _provider, _key: adapter,
        executor=executor,  # type: ignore[arg-type]
        call_timeout=call_timeout,
        **({"clock": clock} if clock is not None else {}),
    )


def _pausing_calls(pause: threading.Event) -> object:
    """A case that asks the model three times and waits between the calls.

    Why the wait: the cancellation of the test has to arrive between two calls, and a case that asks the three
    questions back to back would leave nothing to cancel.
    """

    def executor(caller: object, plan: LiveRunPlan) -> str:
        answers = []
        for index in range(3):
            if index:
                pause.wait(5.0)
            response = caller.complete(  # type: ignore[attr-defined]
                ProviderRequest(model_id=MODEL_ID, messages=({"role": "user", "content": "?"},))
            )
            answers.append(response.content)
        return " ".join(answers)

    return executor


def _three_calls(caller: object, plan: LiveRunPlan) -> str:
    """A case that asks the model three times, one after the other."""
    answers = []
    for _ in range(3):
        response = caller.complete(  # type: ignore[attr-defined]
            ProviderRequest(model_id=MODEL_ID, messages=({"role": "user", "content": "?"},))
        )
        answers.append(response.content)
    return " ".join(answers)


def _wait_for(predicate: object, timeout: float = 5.0) -> bool:
    """Waits for a condition of the test, without sleeping longer than it has to."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():  # type: ignore[operator]
            return True
        time.sleep(0.01)
    return False


@pytest.fixture(autouse=True)
def online(monkeypatch: pytest.MonkeyPatch) -> None:
    """The product is online for the tests of the coordinator: a live run needs a live mode (FR-024)."""
    monkeypatch.setenv("LEDGERLENS_OFFLINE", "0")


# --- the mode and the terminal event ---------------------------------------------------------------


def test_the_run_ends_with_a_terminal_event_and_the_mode_live_agent() -> None:
    """FR-020, FR-024: the run ends with a terminal event and every event of it is a live event."""
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER).script_answer(
        "the refund is lower", input_tokens=100, output_tokens=20
    )
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle))
    result = coordinator.wait("run-test", timeout=5.0)

    assert result is not None
    assert result.status == "completed"
    events = coordinator.events("run-test")
    assert events[-1].event_type == "run.completed"
    assert {event.mode for event in events} == {LIVE_MODE}
    assert all(event.mode != "recorded_replay" for event in events)


def test_the_trace_carries_the_provider_and_the_model_identifier() -> None:
    """FR-026: the trace says which provider answered and which model ran."""
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER).script_answer("the answer")
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle))
    coordinator.wait("run-test", timeout=5.0)

    started = coordinator.events("run-test")[0]
    assert started.event_type == "run.started"
    assert started.payload["provider"] == "openai"
    assert started.payload["model_id"] == MODEL_ID
    assert started.payload["model_profile_id"] == PROFILE_ID


def test_the_budget_of_the_request_lives_in_the_run_context_of_the_run() -> None:
    """FR-025: the caps of the request are the budget of the run context."""
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER).script_answer("the answer")
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)
    budget = RunBudget(max_model_calls=1, max_tool_calls=2, max_wall_seconds=30, max_output_tokens=256)

    coordinator.start(_plan(handle.handle, budget=budget))
    result = coordinator.wait("run-test", timeout=5.0)

    assert result is not None
    assert result.context.budget == budget
    assert result.context.mode == LIVE_MODE


def test_the_run_stops_at_the_attempt_that_would_break_the_cap_of_the_model_calls() -> None:
    """FR-009: the cap of the calls of the models stops the run and the answer names the cap."""
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER)
    adapter.script_answer("one").script_answer("two")
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault, executor=_three_calls)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)
    budget = RunBudget(max_model_calls=1, max_tool_calls=4, max_wall_seconds=30, max_output_tokens=512)

    coordinator.start(_plan(handle.handle, budget=budget))
    result = coordinator.wait("run-test", timeout=5.0)

    assert result is not None
    assert result.status == "failed"
    assert result.report.cut_by == "max_model_calls"
    assert "max_model_calls" in (result.error or "")
    assert len(adapter.calls) == 1


# --- the key never leaves the run ------------------------------------------------------------------


def test_the_key_in_a_provider_exception_never_reaches_the_trace() -> None:
    """FR-018, SC-001: a provider that raises an error with the key does not put the key in the trace."""
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER)
    adapter.script_failure(RuntimeError(f"401 invalid api key {MARKER}"))
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle))
    result = coordinator.wait("run-test", timeout=5.0)

    assert result is not None
    assert result.status == "failed"
    text = json.dumps([event.to_dict() for event in coordinator.events("run-test")])
    assert MARKER not in text
    assert MARKER not in (result.error or "")
    assert MARKER not in result.answer


def test_the_facade_scrubs_what_it_writes_when_the_adapter_does_not_scrub() -> None:
    """FR-018: the second layer of the scrub is the facade, and it holds even without the adapter."""
    vault = CredentialVault()
    coordinator = _coordinator(RawAdapter("openai", MARKER), vault)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle))
    result = coordinator.wait("run-test", timeout=5.0)

    assert result is not None
    assert result.status == "failed"
    assert MARKER not in (result.error or "")
    text = json.dumps([event.to_dict() for event in coordinator.events("run-test")])
    assert MARKER not in text


def test_the_key_in_a_provider_exception_never_reaches_the_logs(caplog: pytest.LogCaptureFixture) -> None:
    """FR-018: the log of a failed run carries no key either."""
    caplog.set_level(logging.DEBUG)
    vault = CredentialVault()
    coordinator = _coordinator(RawAdapter("openai", MARKER), vault)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle))
    coordinator.wait("run-test", timeout=5.0)

    assert not any(MARKER in record.getMessage() for record in caplog.records)
    assert not any(MARKER in str(record.args) for record in caplog.records)


# --- the cancellation ------------------------------------------------------------------------------


def test_a_cancelled_run_makes_no_further_provider_call() -> None:
    """SC-010: after the cancellation is acknowledged, no further call reaches the provider."""
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER)
    adapter.script_answer("one").script_answer("two").script_answer("three")
    vault = CredentialVault()
    pause = threading.Event()
    coordinator = _coordinator(adapter, vault, executor=_pausing_calls(pause))
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle))
    assert _wait_for(lambda: len(adapter.calls) == 1)
    coordinator.cancel("run-test")
    pause.set()
    result = coordinator.wait("run-test", timeout=5.0)

    assert result is not None
    assert result.status == "cancelled"
    assert len(adapter.calls) == 1
    assert coordinator.events("run-test")[-1].event_type == "run.cancelled"


def test_the_cancellation_of_a_call_in_flight_is_a_best_effort() -> None:
    """FR-019: the cancellation cannot promise that a call already at the provider stops."""
    entered = threading.Event()
    release = threading.Event()

    class Blocking(FakeProviderAdapter):
        def complete(self, request: ProviderRequest) -> ProviderResponse:
            entered.set()
            release.wait(5.0)
            return super().complete(request)

    adapter = Blocking(provider="openai", api_key=MARKER)
    adapter.script_answer("one").script_answer("two")
    vault = CredentialVault()
    pause = threading.Event()
    coordinator = _coordinator(adapter, vault, executor=_pausing_calls(pause))
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle))
    assert entered.wait(5.0)
    coordinator.cancel("run-test")
    release.set()
    pause.set()
    result = coordinator.wait("run-test", timeout=5.0)

    assert result is not None
    assert result.status == "cancelled"
    assert result.best_effort is True
    assert len(adapter.calls) == 1


def test_a_cancelled_run_keeps_the_partial_trace() -> None:
    """FR-019: the trace of a cancelled run stays visible, up to the terminal event."""
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER)
    adapter.script_answer("one").script_answer("two").script_answer("three")
    vault = CredentialVault()
    pause = threading.Event()
    coordinator = _coordinator(adapter, vault, executor=_pausing_calls(pause))
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle))
    assert _wait_for(lambda: len(adapter.calls) == 1)
    coordinator.cancel("run-test")
    pause.set()
    coordinator.wait("run-test", timeout=5.0)

    types = [event.event_type for event in coordinator.events("run-test")]
    assert types[0] == "run.started"
    assert "span.ended" in types
    assert types[-1] == "run.cancelled"


# --- the refusals ----------------------------------------------------------------------------------


def test_the_run_refuses_a_model_outside_the_allowlist() -> None:
    """FR-027: the server refuses the model, and not only the interface."""
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER)
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    with pytest.raises(ModelNotAllowed) as refused:
        coordinator.start(_plan(handle.handle, model_profile_id="gpt-9-turbo"))

    assert "not in the allowlist" in str(refused.value)
    assert adapter.calls == []


def test_the_coordinator_refuses_a_run_while_the_product_is_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-001, FR-029: there is no live run while the product runs offline."""
    monkeypatch.setenv("LEDGERLENS_OFFLINE", "1")
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER)
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    with pytest.raises(LiveModeOffline) as refused:
        coordinator.start(_plan(handle.handle))

    assert "offline" in str(refused.value)
    assert adapter.calls == []


def test_the_run_refuses_a_model_that_lacks_the_capability_of_the_variant() -> None:
    """FR-015: the refusal names the capability that is missing."""
    with pytest.raises(CapabilityMissing) as refused:
        resolve_profile(registry(), "openai-chat-only", variant="B")

    assert "tool_calling" in str(refused.value)


def test_the_model_of_a_run_may_not_change() -> None:
    """FR-013: a run that asks for another model is refused and a new run identifier is required."""
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER).script_answer("one")
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle))
    coordinator.wait("run-test", timeout=5.0)

    with pytest.raises(ModelChanged) as refused:
        coordinator.start(_plan(handle.handle, model_profile_id="openai-mystery"))

    assert "new run" in str(refused.value)


def test_a_handle_of_another_session_never_reaches_the_provider() -> None:
    """FR-006, SC-002: the handle of another session is refused and the run calls nothing."""
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER).script_answer("one")
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault)
    handle = vault.accept(MARKER, "openai", session_id=OTHER_SESSION)

    coordinator.start(_plan(handle.handle, session_id=SESSION))
    result = coordinator.wait("run-test", timeout=5.0)

    assert result is not None
    assert result.status == "failed"
    assert "unknown" in (result.error or "")
    assert adapter.calls == []


def test_two_sessions_never_cross_their_credentials() -> None:
    """FR-006: two visitors on two providers do not share a credential."""
    vault = CredentialVault()
    first = vault.accept(MARKER, "openai", session_id=SESSION)
    second = vault.accept(OTHER_MARKER, "anthropic", session_id=OTHER_SESSION)

    assert vault.resolve(first.handle, session_id=SESSION) == MARKER
    with pytest.raises(CredentialUnknown):
        vault.resolve(first.handle, session_id=OTHER_SESSION)
    assert vault.resolve(second.handle, session_id=OTHER_SESSION) != MARKER


# --- the provider that does not answer -------------------------------------------------------------


def test_the_deadline_of_a_call_is_the_time_the_run_has_left() -> None:
    """SC-003: the deadline of a call is the wall clock of the run and not a guess of the coordinator."""
    class Slow(FakeProviderAdapter):
        def complete(self, request: ProviderRequest) -> ProviderResponse:
            time.sleep(0.2)
            return super().complete(request)

    adapter = Slow(provider="openai", api_key=MARKER).script_answer("the answer")
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)
    budget = RunBudget(max_model_calls=2, max_tool_calls=2, max_wall_seconds=30, max_output_tokens=512)

    coordinator.start(_plan(handle.handle, budget=budget))
    result = coordinator.wait("run-test", timeout=5.0)

    assert result is not None
    assert result.status == "completed"
    assert result.report.elapsed_seconds >= 0.2


def test_a_provider_that_does_not_answer_in_time_ends_the_run() -> None:
    """FR-032: the timeout of the provider is terminal for the run, and the partial trace stays."""
    release = threading.Event()

    class Hanging(FakeProviderAdapter):
        def complete(self, request: ProviderRequest) -> ProviderResponse:
            release.wait(5.0)
            return super().complete(request)

    adapter = Hanging(provider="openai", api_key=MARKER)
    adapter.script_answer("one")
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault, call_timeout=0.05)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle))
    result = coordinator.wait("run-test", timeout=5.0)

    assert result is not None
    assert result.status == "failed"
    assert "did not answer in time" in (result.error or "")
    events = coordinator.events("run-test")
    assert events[0].event_type == "run.started"
    assert events[-1].event_type == "run.failed"
    release.set()


# --- the key of a run whose credential died ------------------------------------------------------------


def test_the_key_never_reaches_the_trace_when_the_credential_died_in_the_middle_of_the_run(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """FR-018, SC-001: the coordinator holds the secret of the run and scrubs with it.

    Why the credential dies in the middle of the run: the visitor presses "forget key", the session ends, the time to
    live passes or the vault is full, and the vault does not keep the secret of a credential that is gone (ADR-033).
    The run has to be safe anyway, and the run is what holds the secret while it lives (FR-018).
    """
    caplog.set_level(logging.DEBUG)
    vault = CredentialVault()
    handle = vault.accept(MARKER, "openai", session_id=SESSION)
    adapter = RawAdapter("openai", MARKER)

    def executor(caller: object, plan: LiveRunPlan) -> str:
        """A case that drops the credential of the run and then asks the provider, which refuses the key."""
        vault.forget(handle.handle, session_id=SESSION)
        return str(caller.complete(ProviderRequest(model_id=MODEL_ID, messages=({"role": "user", "content": "?"},))))

    coordinator = _coordinator(adapter, vault, executor=executor)
    coordinator.start(_plan(handle.handle))
    result = coordinator.wait("run-test", timeout=5.0)

    assert result is not None
    assert result.status == "failed"
    assert MARKER not in (result.error or "")
    assert MARKER not in result.answer
    text = json.dumps([event.to_dict() for event in coordinator.events("run-test")])
    assert MARKER not in text
    assert not any(MARKER in record.getMessage() for record in caplog.records)


def test_the_run_scrubs_with_the_secrets_that_the_vault_holds() -> None:
    """FR-018: the run scrubs with the secret of its own run and with the secrets the vault holds.

    Why the secret of another credential: the vault holds the keys of the credentials of the process, and the texts
    that a run writes are scrubbed with all of them and not only with the one of the run (FR-018, SC-001).
    """

    class ForeignKeyAdapter(ProviderAdapter):
        """An adapter whose error carries the key of another credential of the vault."""

        def complete(self, request: ProviderRequest) -> ProviderResponse:
            raise RuntimeError(f"the provider said: {OTHER_MARKER}")

        def chat_model(self, model_id: str) -> object:
            raise NotImplementedError

    vault = CredentialVault()
    handle = vault.accept(MARKER, "openai", session_id=SESSION)
    vault.accept(OTHER_MARKER, "anthropic", session_id=SESSION)
    coordinator = _coordinator(ForeignKeyAdapter("openai", MARKER), vault)

    coordinator.start(_plan(handle.handle))
    result = coordinator.wait("run-test", timeout=5.0)

    assert result is not None
    assert result.status == "failed"
    assert OTHER_MARKER not in (result.error or "")
    text = json.dumps([event.to_dict() for event in coordinator.events("run-test")])
    assert OTHER_MARKER not in text


def test_a_failure_of_the_provider_counts_a_failure_of_the_credential() -> None:
    """FR-023: a key that the provider refuses does not live for the whole time to live."""
    vault = CredentialVault(max_failures=2)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)
    adapter = RawAdapter("openai", MARKER)
    coordinator = _coordinator(adapter, vault)

    coordinator.start(_plan(handle.handle, run_id="run-one"))
    first = coordinator.wait("run-one", timeout=5.0)
    assert first is not None
    assert first.status == "failed"
    assert len(vault) == 1

    coordinator.start(_plan(handle.handle, run_id="run-two"))
    second = coordinator.wait("run-two", timeout=5.0)
    assert second is not None
    assert second.status == "failed"

    # The bound of the failures is reached, so the credential is dropped (FR-023).
    assert len(vault) == 0


# --- the terminal event of a run that dies --------------------------------------------------------------


def test_a_case_that_raises_something_that_is_not_an_exception_still_ends_the_run() -> None:
    """FR-020, SC-006: the run ends with one terminal event, whatever the case raised.

    Why the case may raise more than an exception: the guard of the run catches what a case can raise, and a run
    that died without a terminal event leaves the cost route answering that the run is still running for ever.
    """
    vault = CredentialVault()
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER).script_answer("the answer")
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    def executor(caller: object, plan: LiveRunPlan) -> str:
        """A case that raises something that is not an exception."""
        raise KeyboardInterrupt("interrupted")

    coordinator = _coordinator(adapter, vault, executor=executor)
    coordinator.start(_plan(handle.handle))
    result = coordinator.wait("run-test", timeout=5.0)

    assert result is not None
    assert result.status == "failed"
    types = [event.event_type for event in coordinator.events("run-test")]
    assert [event_type for event_type in types if event_type in ("run.completed", "run.failed", "run.cancelled")] == [
        "run.failed"
    ]
    assert types[-1] == "run.failed"


# --- the model of the run --------------------------------------------------------------------------------


def test_a_call_with_another_model_is_refused_and_the_run_ends() -> None:
    """FR-013: a call whose model differs from the model of the run is refused, and the run stops.

    Why the refusal is in the caller and not only in the coordinator: the coordinator refuses a second run with the
    same identifier, and the facade mints a new identifier for every request, so the caller is the layer that
    really holds the rule (FR-013).
    """
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER).script_answer("one").script_answer("two")
    vault = CredentialVault()
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    def executor(caller: object, plan: LiveRunPlan) -> str:
        """A case that asks for another model in the middle of the run."""
        caller.complete(ProviderRequest(model_id=MODEL_ID, messages=({"role": "user", "content": "?"},)))
        other = ProviderRequest(model_id="gpt-mystery", messages=({"role": "user", "content": "?"},))
        return str(caller.complete(other))

    coordinator = _coordinator(adapter, vault, executor=executor)
    coordinator.start(_plan(handle.handle))
    result = coordinator.wait("run-test", timeout=5.0)

    assert result is not None
    assert result.status == "failed"
    assert "may not change" in (result.error or "")
    assert len(adapter.calls) == 1
    assert coordinator.events("run-test")[-1].event_type == "run.failed"


# --- the caps of the run ----------------------------------------------------------------------------------


def test_the_cap_of_the_calls_of_the_models_stops_the_run_for_every_cap_of_the_output_tokens() -> None:
    """FR-009, FR-025: the cap of the output tokens never preempts the cap of the calls of the models.

    Why every cap of the output tokens: the size of the answer is not known before the call, so the plan of a call
    may not promise more tokens than the cap allows, and the run has to reach the cap of the calls (FR-009).
    """
    for output_cap in (128, 512, 16000):
        adapter = FakeProviderAdapter(provider="openai", api_key=MARKER)
        for index in range(5):
            adapter.script_answer(f"the answer {index}", input_tokens=10, output_tokens=5)
        vault = CredentialVault()
        handle = vault.accept(MARKER, "openai", session_id=SESSION)
        coordinator = _coordinator(adapter, vault, executor=_five_calls)
        budget = RunBudget(
            max_model_calls=4, max_tool_calls=4, max_wall_seconds=30, max_output_tokens=output_cap
        )

        coordinator.start(_plan(handle.handle, budget=budget))
        result = coordinator.wait("run-test", timeout=5.0)

        assert result is not None, output_cap
        assert result.status == "failed", output_cap
        assert result.report.cut_by == "max_model_calls", output_cap
        assert len(adapter.calls) == 4, output_cap


def _five_calls(caller: object, plan: LiveRunPlan) -> str:
    """A case that asks the model five times, one after the other."""
    for _ in range(5):
        caller.complete(ProviderRequest(model_id=MODEL_ID, messages=({"role": "user", "content": "?"},)))
    return "done"


def test_the_cap_of_the_tools_stops_the_run_and_names_the_cap() -> None:
    """FR-009, FR-012: every call of a tool reserves one call of the budget of the run."""
    calls: list[str] = []

    def the_tool() -> str:
        """The tool of the test: it says that it ran."""
        calls.append("ledger.search")
        return "the tool answered"

    def executor(caller: object, plan: LiveRunPlan) -> str:
        """A case that uses the tool three times."""
        for _ in range(3):
            caller.call_tool("ledger.search", the_tool)
        return "done"

    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER).script_answer("the answer")
    vault = CredentialVault()
    handle = vault.accept(MARKER, "openai", session_id=SESSION)
    coordinator = _coordinator(adapter, vault, executor=executor)
    budget = RunBudget(max_model_calls=2, max_tool_calls=1, max_wall_seconds=30, max_output_tokens=512)

    coordinator.start(_plan(handle.handle, budget=budget))
    result = coordinator.wait("run-test", timeout=5.0)

    assert result is not None
    assert result.status == "failed"
    assert result.report.cut_by == "max_tool_calls"
    assert "max_tool_calls" in (result.error or "")
    assert result.report.tool_calls == 1
    assert calls == ["ledger.search"]


def test_the_wall_clock_of_the_run_is_the_deadline_of_a_call() -> None:
    """SC-003: the deadline of a call is the wall clock of the run, and a call with no time left never starts.

    Why the clock is scripted: the cap is proved by moving a clock in a test and not by waiting for it (FR-009).
    """
    moments = [0.0, 0.0, 100.0]

    def clock() -> float:
        """The clock of the test: it jumps over the cap of the run between the reservation and the call."""
        return moments.pop(0) if len(moments) > 1 else moments[0]

    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER).script_answer("the answer")
    vault = CredentialVault()
    handle = vault.accept(MARKER, "openai", session_id=SESSION)
    coordinator = _coordinator(adapter, vault, clock=clock)
    budget = RunBudget(max_model_calls=2, max_tool_calls=2, max_wall_seconds=30, max_output_tokens=512)

    coordinator.start(_plan(handle.handle, budget=budget))
    result = coordinator.wait("run-test", timeout=5.0)

    assert result is not None
    assert result.status == "failed"
    assert "wall clock" in (result.error or "")
    # The provider was never called: a call with no time left spends the money of the visitor for nothing.
    assert adapter.calls == []


# --- the shape of the secret of a run and the shape of the trace ---------------------------------------


def test_the_repr_of_a_live_run_carries_no_secret() -> None:
    """FR-018, SC-001: the representation of a run never shows the key of the visitor.

    Why a run that is alive: the secret of the run is held while the run lives, and the representation of a live run
    is the one that could leak into a debug print or into a traceback with the locals (FR-018, SC-001).
    """
    entered = threading.Event()
    release = threading.Event()

    class Blocking(FakeProviderAdapter):
        """An adapter that holds the call of the provider, so the run is alive while it is looked at."""

        def complete(self, request: ProviderRequest) -> ProviderResponse:
            entered.set()
            release.wait(5.0)
            return super().complete(request)

    adapter = Blocking(provider="openai", api_key=MARKER)
    adapter.script_answer("the answer")
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle))
    assert entered.wait(5.0)
    run = coordinator._runs["run-test"]
    holder = run.secret

    assert MARKER not in repr(run)
    assert MARKER not in repr(holder)
    assert "[REDACTED]" in repr(holder)

    release.set()
    coordinator.wait("run-test", timeout=5.0)
    # The run drops the secret of the run when it ends, and what it held is empty (FR-002, FR-003, FR-021).
    assert run.secret is None
    assert holder is not None
    assert holder.text == ""


def test_the_run_releases_the_secret_of_the_run_when_it_ends() -> None:
    """FR-002, FR-003: the key of the visitor lives in the memory of the process and nowhere else.

    Why the secret is dropped with the run: a run that is over has nothing left to protect, and the key of the
    visitor must not stay in the memory of the process after the run that used it (FR-002, FR-003).
    """
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER).script_answer("the answer")
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle))
    result = coordinator.wait("run-test", timeout=5.0)

    assert result is not None
    assert coordinator._runs["run-test"].secret is None


def test_the_trace_of_a_run_scrubs_the_name_of_a_tool_with_the_secret_of_the_run() -> None:
    """FR-018, SC-001: a tool whose name is the key of the visitor never reaches the trace of the run.

    Why the name of a tool: the name comes from the case, and a case that names a tool after the key would put the
    key in the trace of the run without ever touching the provider (FR-018, SC-001).
    """

    def executor(caller: object, plan: LiveRunPlan) -> str:
        """A case that names a tool after the key of the visitor."""
        caller.call_tool(MARKER, lambda: "the tool answered")  # type: ignore[attr-defined]
        return "done"

    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER).script_answer("the answer")
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault, executor=executor)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle))
    result = coordinator.wait("run-test", timeout=5.0)

    assert result is not None
    text = json.dumps([event.to_dict() for event in coordinator.events("run-test")])
    assert MARKER not in text
    assert "[REDACTED]" in text


def test_the_name_of_a_tool_is_scrubbed_with_the_secret_of_the_run_when_the_credential_died() -> None:
    """FR-018, SC-001: the secret of the run scrubs the trace even when the vault does not hold it anymore.

    Why the credential dies: the visitor presses "forget key" and the vault stops holding the secret of that
    credential on purpose (ADR-033). The run still holds the secret of its own credential while it lives, and the
    trace of the run must not carry it (FR-018, SC-001).
    """
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER).script_answer("the answer")
    vault = CredentialVault()
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    def executor(caller: object, plan: LiveRunPlan) -> str:
        """A case that drops the credential of the run and then names a tool after the key."""
        vault.forget(handle.handle, session_id=SESSION)
        caller.call_tool(MARKER, lambda: "the tool answered")  # type: ignore[attr-defined]
        return "done"

    coordinator = _coordinator(adapter, vault, executor=executor)
    coordinator.start(_plan(handle.handle))
    result = coordinator.wait("run-test", timeout=5.0)

    assert result is not None
    text = json.dumps([event.to_dict() for event in coordinator.events("run-test")])
    assert MARKER not in text
    assert "[REDACTED]" in text


def test_the_scrub_of_a_payload_reaches_the_structures_that_it_nests() -> None:
    """FR-018, SC-001: a payload is scrubbed at every depth, not only at its top.

    Why the depth matters: a payload of an event is a structure and not a text, and a structure that nests a text that
    carries the key would put the key in the trace of the run without ever touching the provider. The scrub may not
    depend on the payloads of the product being flat (FR-018, SC-001).

    Why the credential is forgotten: the vault stops holding the secret of a credential that is gone, so only the
    secret of the run can scrub the payload of the test (FR-018, SC-001).
    """
    entered = threading.Event()
    release = threading.Event()

    class Blocking(FakeProviderAdapter):
        """An adapter that holds the call of the provider, so the run is alive while its payload is scrubbed."""

        def complete(self, request: ProviderRequest) -> ProviderResponse:
            entered.set()
            release.wait(5.0)
            return super().complete(request)

    adapter = Blocking(provider="openai", api_key=MARKER)
    adapter.script_answer("the answer")
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle))
    assert entered.wait(5.0)
    run = coordinator._runs["run-test"]
    vault.forget(handle.handle, session_id=SESSION)

    scrubbed = coordinator._scrub_payload(
        {"outer": {"inner": MARKER}, "list": [MARKER, {"deep": MARKER}], "plain": MARKER},
        run,
    )
    release.set()
    coordinator.wait("run-test", timeout=5.0)

    text = json.dumps(scrubbed)
    assert MARKER not in text
    assert "[REDACTED]" in text


# --- the money of the run -------------------------------------------------------------------------------


def test_the_money_cap_stops_the_run_before_the_money_is_spent() -> None:
    """FR-009, FR-010: the cap of the money holds the run before the provider is called.

    Why a provider that reports far more tokens than the cap of the output tokens: the provider is the only one who
    knows what a call really costs, and a cap that is only checked after the call is a report of a bill and not a
    cap (FR-009, FR-010).
    """

    class Greedy(FakeProviderAdapter):
        """An adapter whose provider reports far more output tokens than the cap of the run allows."""

        def complete(self, request: ProviderRequest) -> ProviderResponse:
            self.calls.append(request)
            return ProviderResponse(
                content="the answer",
                input_tokens=1,
                output_tokens=10000,
                model_id=request.model_id,
            )

    adapter = Greedy(provider="openai", api_key=MARKER)
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)
    cap = Decimal("0.0003")
    budget = RunBudget(
        max_model_calls=2,
        max_tool_calls=4,
        max_wall_seconds=30,
        max_output_tokens=128,
        max_estimated_usd=cap,
    )

    coordinator.start(_plan(handle.handle, budget=budget))
    result = coordinator.wait("run-test", timeout=5.0)

    assert result is not None
    assert result.status == "failed"
    assert result.report.cut_by == "max_estimated_usd"
    # The provider was never called: the money of the visitor was never spent (FR-009).
    assert adapter.calls == []
    observed = result.report.observed_cost_usd
    assert observed is None or observed <= cap


def test_the_money_cap_lets_a_run_that_it_can_pay_for_go_on() -> None:
    """FR-009: a run whose worst case fits under the cap of the money runs, and the money is counted.

    Why this test exists: a cap that refuses everything is a cap that stops the live mode, and the rule has to hold
    the runs that the visitor can pay for and only those (FR-009).
    """
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER).script_answer("the answer", output_tokens=10)
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)
    budget = RunBudget(
        max_model_calls=2,
        max_tool_calls=4,
        max_wall_seconds=30,
        max_output_tokens=512,
        max_estimated_usd=Decimal("0.25"),
    )

    coordinator.start(_plan(handle.handle, budget=budget))
    result = coordinator.wait("run-test", timeout=5.0)

    assert result is not None
    assert result.status == "completed"
    assert len(adapter.calls) == 1
    assert result.report.observed_cost_usd is not None
    assert result.report.observed_cost_usd <= Decimal("0.25")


def test_the_money_cap_stops_the_run_before_the_provider_is_called_when_the_worst_case_passes_the_cap() -> None:
    """FR-009, FR-010: the cap of the money is checked against the worst case of the caps of the run.

    Why this configuration and not another: a cap that sits between the price of one call and the price of the worst
    case is the only one where the two rules differ. A cap under the price of one call is refused by the worst case
    and by the clamped plan of a call alike, so it cannot tell them apart, and a cap that the worst case fits tells
    nothing (FR-009, FR-010).

    Why the numbers: one call at the cap of the output tokens of the run costs 0.0256 US$ at the price of the
    registry, which fits under a cap of 0.05 US$, and the twenty calls that the cap of the calls allows cost
    0.512 US$, which does not (FR-010).
    """
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER).script_answer("the answer", output_tokens=10)
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)
    budget = RunBudget(
        max_model_calls=20,
        max_tool_calls=4,
        max_wall_seconds=30,
        max_output_tokens=16000,
        max_estimated_usd=Decimal("0.05"),
    )

    coordinator.start(_plan(handle.handle, budget=budget))
    result = coordinator.wait("run-test", timeout=5.0)

    assert result is not None
    assert result.status == "failed"
    assert result.report.cut_by == "max_estimated_usd"
    # The provider was never called: the money of the visitor was never spent (FR-009).
    assert adapter.calls == []
    observed = result.report.observed_cost_usd
    assert observed is None or observed <= Decimal("0.05")


def test_the_money_cap_lets_a_run_whose_worst_case_fits_the_cap_go_on() -> None:
    """FR-009: a run whose worst case fits under the cap of the money goes on, and spends at most the cap.

    Why this test is the twin of the one above: the rule has to hold the runs that the visitor can pay for and only
    those, and the cap is checked against the worst case of the caps of the run (FR-009, FR-010).
    """
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER).script_answer("the answer", output_tokens=10)
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)
    budget = RunBudget(
        max_model_calls=20,
        max_tool_calls=4,
        max_wall_seconds=30,
        max_output_tokens=16000,
        max_estimated_usd=Decimal("1.00"),
    )

    coordinator.start(_plan(handle.handle, budget=budget))
    result = coordinator.wait("run-test", timeout=5.0)

    assert result is not None
    assert result.status == "completed"
    assert len(adapter.calls) == 1
    assert result.report.observed_cost_usd is not None
    assert result.report.observed_cost_usd <= Decimal("1.00")


def test_the_cap_of_the_money_stops_a_run_whose_number_of_calls_is_not_bounded() -> None:
    """FR-009: a cap of the money bounds a run only when the number of the calls is bounded.

    Why this matters: without a cap of the calls there is no worst case to compare with the cap of the money, and a
    run that may call as many times as it wants cannot promise that the money of the visitor stays under the cap. The
    run stops before the provider is called (FR-009).
    """
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER).script_answer("the answer", output_tokens=10)
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)
    budget = RunBudget(
        max_model_calls=None,
        max_tool_calls=4,
        max_wall_seconds=30,
        max_output_tokens=16000,
        max_estimated_usd=Decimal("0.05"),
    )

    coordinator.start(_plan(handle.handle, budget=budget))
    result = coordinator.wait("run-test", timeout=5.0)

    assert result is not None
    assert result.status == "failed"
    assert result.report.cut_by == "max_estimated_usd"
    # The provider was never called: the money of the visitor was never spent (FR-009).
    assert adapter.calls == []
    observed = result.report.observed_cost_usd
    assert observed is None or observed <= Decimal("0.05")


# --- the credential and the provider ----------------------------------------------------------------------


def test_a_transient_failure_of_the_provider_does_not_kill_the_credential() -> None:
    """FR-023: a rate limit is not the fault of the key of the visitor.

    Why it matters: a provider that is busy must not take the credential of the visitor down with it, and four rate
    limits would otherwise drop a key that works perfectly (FR-023).
    """

    class Busy(ProviderAdapter):
        """An adapter whose provider answers with a rate limit."""

        def complete(self, request: ProviderRequest) -> ProviderResponse:
            raise RuntimeError("429 too many requests")

        def chat_model(self, model_id: str) -> object:
            raise NotImplementedError

    vault = CredentialVault(max_failures=2)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)
    coordinator = _coordinator(Busy("openai", MARKER), vault)

    for index in range(4):
        coordinator.start(_plan(handle.handle, run_id=f"run-{index}"))
        coordinator.wait(f"run-{index}", timeout=5.0)

    # The key still works, so the credential is still there (FR-023).
    assert len(vault) == 1


def test_a_refusal_of_the_key_counts_a_failure_of_the_credential() -> None:
    """FR-023: a key that the provider refuses does not live for the whole time to live."""

    class Refused(ProviderAdapter):
        """An adapter whose provider refuses the key."""

        def complete(self, request: ProviderRequest) -> ProviderResponse:
            raise RuntimeError("401 invalid api key")

        def chat_model(self, model_id: str) -> object:
            raise NotImplementedError

    vault = CredentialVault(max_failures=2)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)
    coordinator = _coordinator(Refused("openai", MARKER), vault)

    coordinator.start(_plan(handle.handle, run_id="run-one"))
    coordinator.wait("run-one", timeout=5.0)
    assert len(vault) == 1

    coordinator.start(_plan(handle.handle, run_id="run-two"))
    coordinator.wait("run-two", timeout=5.0)
    # The bound of the failures is reached, so the credential is dropped (FR-023).
    assert len(vault) == 0


def test_only_a_refusal_of_the_key_drops_the_credential_and_a_permission_of_the_provider_does_not() -> None:
    """FR-023: the rule tells a refusal of the key from a failure of the provider.

    Why the sentence about a permission: a provider that breaks upstream says that the request was unauthorized to
    read a bucket, and that sentence is about the permission of the provider and not about the key of the visitor.
    Four such failures must not drop a key that works, and a real refusal of the key still must (FR-023).
    """

    class Upstream(ProviderAdapter):
        """An adapter whose provider breaks with a sentence about a permission and not about the key."""

        def complete(self, request: ProviderRequest) -> ProviderResponse:
            raise RuntimeError("upstream failure: the request was unauthorized to read the bucket")

        def chat_model(self, model_id: str) -> object:
            raise NotImplementedError

    class Refused(ProviderAdapter):
        """An adapter whose provider refuses the key."""

        def complete(self, request: ProviderRequest) -> ProviderResponse:
            raise RuntimeError("401 invalid api key")

        def chat_model(self, model_id: str) -> object:
            raise NotImplementedError

    class Unauthorized(ProviderAdapter):
        """An adapter whose provider answers with the status of a refusal and without a status attribute."""

        def complete(self, request: ProviderRequest) -> ProviderResponse:
            raise RuntimeError("401 unauthorized")

        def chat_model(self, model_id: str) -> object:
            raise NotImplementedError

    vault = CredentialVault(max_failures=2)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)
    coordinator = _coordinator(Upstream("openai", MARKER), vault)

    for index in range(4):
        coordinator.start(_plan(handle.handle, run_id=f"run-upstream-{index}"))
        coordinator.wait(f"run-upstream-{index}", timeout=5.0)

    # The key was never refused, so the credential is still there (FR-023).
    assert len(vault) == 1

    other_vault = CredentialVault(max_failures=2)
    other_handle = other_vault.accept(MARKER, "openai", session_id=SESSION)
    other_coordinator = _coordinator(Refused("openai", MARKER), other_vault)

    for index in range(4):
        other_coordinator.start(_plan(other_handle.handle, run_id=f"run-refused-{index}"))
        other_coordinator.wait(f"run-refused-{index}", timeout=5.0)

    # The key was refused, so the credential is gone (FR-023).
    assert len(other_vault) == 0

    third_vault = CredentialVault(max_failures=2)
    third_handle = third_vault.accept(MARKER, "openai", session_id=SESSION)
    third_coordinator = _coordinator(Unauthorized("openai", MARKER), third_vault)

    for index in range(4):
        third_coordinator.start(_plan(third_handle.handle, run_id=f"run-unauthorized-{index}"))
        third_coordinator.wait(f"run-unauthorized-{index}", timeout=5.0)

    # The status of the refusal is in the text of the provider, so the credential is gone (FR-023).
    assert len(third_vault) == 0


# --- the wordings of a provider that refuses the key ----------------------------------------------------------

# The wordings with which a provider refuses the key itself. The table is data on purpose: every wording is a line
# here and not a test of its own, so the behaviour of the heuristic is pinned case by case and read in one place.
# The wordings come in families: a key that expired, a key that was revoked, a key that is malformed, a key that was
# never given and a key that is not the one the provider expects (FR-023).
REFUSALS_OF_THE_KEY = (
    # the wordings that a provider used before
    "invalid api key",
    "incorrect api key",
    "no api key",
    "missing api key",
    "authentication error",
    "authentication failed",
    "expired api key",
    "revoked api key",
    "authentication_error",
    "INVALID API KEY",
    # the wordings of a key that expired
    "your api key expired",
    "your api key has expired",
    "your api key was expired",
    "the api key you sent has expired",
    # the wordings of a key that was revoked
    "your api key was revoked",
    "your api key has been revoked",
    # the wordings of a key that is malformed
    "malformed api key",
    "your api key is malformed",
    "the api key header is malformed",
    # the wordings of a key that was never given
    "you didn't provide an api key",
    "you did not provide an api key",
    "you must provide an api key",
    "an api key is required",
    "api key required",
    "no such api key",
    "your api key is missing",
    "your api key was not provided",
    # the wordings of a key that is not the one the provider expects
    "your api key is invalid",
    "your api key is not valid",
    "your api key is no longer valid",
    "your api key is incorrect",
    "your api key was rejected",
    "your api key was refused",
    "your api key is unknown",
    "your api key was unrecognized",
    "your api key was not recognized",
    "your api key was disabled",
    "your api key was deleted",
    "your api key was terminated",
    "your api key is not active",
    "your api key is wrong",
    "your api key was denied",
    # the wordings of a provider that answers with the status of a refusal inside the text
    "unauthorized: the provider answered 401",
    # the wordings of a provider that names the credential in another way
    "your credential was rejected",
    "the access token has expired",
    "your auth token expired",
)
# The wordings with which a provider refuses something that is not the key of the visitor: a permission of the
# provider, a resource that is not there, a number that looks like the status of a refusal. None of them may drop a
# key that works (FR-023).
PERMISSIONS_OF_THE_PROVIDER = (
    "the request was unauthorized to read the bucket",
    "upstream failure: the request was unauthorized to read the bucket",
    "forbidden",
    "denied",
    "row 401 of the table is missing",
    "the bucket was not found",
    "the model is not found",
    "unauthorized: the provider answered 429",
)
# The statuses of a provider that mean that the key itself was refused. A rate limit, a timeout and an upstream
# failure are not among them: the provider had a bad day and the key of the visitor did not (FR-023).
REFUSALS_BY_STATUS = (401,)
# The statuses of a provider that say nothing about the key of the visitor (FR-023).
PERMISSIONS_BY_STATUS = (403, 429, 500, 504)


class Wording(ProviderAdapter):
    """An adapter whose provider answers with an error that the test asks for."""

    def __init__(self, provider: str, api_key: str, error: Callable[[], BaseException]) -> None:
        super().__init__(provider, api_key)
        self.error = error

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        raise self.error()

    def chat_model(self, model_id: str) -> object:
        raise NotImplementedError


class StatusError(Exception):
    """An error that carries the status of the answer of the provider."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


def _credentials_left_after(error: Callable[[], BaseException], attempts: int) -> int:
    """The number of credentials that are left in the vault after a provider answered with an error."""
    vault = CredentialVault(max_failures=1)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)
    coordinator = _coordinator(Wording("openai", MARKER, error), vault)
    for index in range(attempts):
        coordinator.start(_plan(handle.handle, run_id=f"run-wording-{index}"))
        coordinator.wait(f"run-wording-{index}", timeout=5.0)
    return len(vault)


def _credentials_left_after_the_wording(wording: str, attempts: int) -> int:
    """The number of credentials that are left in the vault after a provider answered with a wording."""
    return _credentials_left_after(lambda: RuntimeError(wording), attempts)


def _credentials_left_after_the_status(status: int, attempts: int) -> int:
    """The number of credentials that are left in the vault after a provider answered with a status."""
    return _credentials_left_after(lambda: StatusError(status, "something went wrong"), attempts)


@pytest.mark.parametrize("wording", REFUSALS_OF_THE_KEY)
def test_a_wording_that_refuses_the_key_drops_the_credential(wording: str) -> None:
    """FR-023: every wording with which a provider refuses the key itself drops the credential.

    Why one test per wording: the words of a provider change from a day to another, and a refusal that the
    heuristic does not see keeps a key that does not work alive (FR-023).
    """
    assert _credentials_left_after_the_wording(wording, attempts=1) == 0


@pytest.mark.parametrize("wording", PERMISSIONS_OF_THE_PROVIDER)
def test_a_wording_that_refuses_a_permission_does_not_drop_the_credential(wording: str) -> None:
    """FR-023: a wording that is about a permission of the provider and not about the key drops nothing.

    Why the wording matters: a provider that breaks upstream says that the request was unauthorized to read a bucket,
    and that sentence is about the provider and not about the key of the visitor (FR-023).
    """
    assert _credentials_left_after_the_wording(wording, attempts=2) == 1


@pytest.mark.parametrize("status", REFUSALS_BY_STATUS)
def test_a_status_that_refuses_the_key_drops_the_credential(status: int) -> None:
    """FR-023: the status of the answer of the provider is the truth about a refusal of the key.

    Why the status alone is enough: a provider that answers with the status of an authentication refuses the key,
    even when the sentence of the answer says nothing about the key (FR-023).
    """
    assert _credentials_left_after_the_status(status, attempts=1) == 0


@pytest.mark.parametrize("status", PERMISSIONS_BY_STATUS)
def test_a_status_that_is_not_a_refusal_does_not_drop_the_credential(status: int) -> None:
    """FR-023: a rate limit, a timeout and an upstream failure say nothing about the key of the visitor."""
    assert _credentials_left_after_the_status(status, attempts=2) == 1


# --- the cancellation of a call of a tool -------------------------------------------------------------------


def test_a_cancelled_run_makes_no_further_tool_call() -> None:
    """SC-010: after the cancellation is acknowledged, no further call of a tool happens."""
    ran: list[str] = []
    pause = threading.Event()

    def executor(caller: object, plan: LiveRunPlan) -> str:
        """A case that calls a tool, waits, and calls the tool again."""
        caller.call_tool("ledger.search", lambda: ran.append("the first call"))  # type: ignore[attr-defined]
        pause.wait(5.0)
        caller.call_tool("ledger.search", lambda: ran.append("the second call"))  # type: ignore[attr-defined]
        return "done"

    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER).script_answer("the answer")
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault, executor=executor)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle))
    assert _wait_for(lambda: ran == ["the first call"])
    coordinator.cancel("run-test")
    pause.set()
    result = coordinator.wait("run-test", timeout=5.0)

    assert result is not None
    assert result.status == "cancelled"
    assert ran == ["the first call"]
    assert coordinator.events("run-test")[-1].event_type == "run.cancelled"


# --- the run that dies before the case ----------------------------------------------------------------------


def test_a_run_that_dies_in_the_preamble_still_leaves_a_terminal_event() -> None:
    """FR-020, SC-006: every path of the run leaves exactly one terminal event.

    Why the preamble: the context of the run, the trace and the budget are built before the case runs, and a run that
    dies there used to leave no terminal event at all. The cost route then answered that the run was still running
    for ever (FR-020, SC-006).
    """
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER).script_answer("the answer")
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault)
    handle = vault.accept(MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle, session_id="a session that the context refuses"))
    result = coordinator.wait("run-test", timeout=5.0)

    assert result is not None
    assert result.status == "failed"
    types = [event.event_type for event in coordinator.events("run-test")]
    assert [event_type for event_type in types if event_type in ("run.completed", "run.failed", "run.cancelled")] == [
        "run.failed"
    ]
    assert types[-1] == "run.failed"
    assert adapter.calls == []
