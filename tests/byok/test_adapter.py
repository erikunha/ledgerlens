"""The provider adapter: the endpoint the server may call, the model built for one run and the fake of the tests.

What they guarantee, and why: (a) the endpoint check is a pure function of the text of the endpoint, so a test
proves it without a network, and the refusal names the reason with a machine-readable code (FR-017); (b) in public
mode a link-local address such as 169.254.169.254 and a loopback address are refused, because they reach the
machine that runs the demo and not the provider (FR-017); (c) an endpoint that the provider does not publish is
refused, whatever the visitor asks for (FR-017); (d) the adapter is built per run and the credential goes into the
constructor of the client, so the process environment and the global settings are never touched (FR-007); (e) the
fake adapter answers what the test tells it to answer and raises what the test tells it to raise, so no test of
this feature opens a socket (FR-018); (f) the error of the provider leaves the adapter without the credential of
the run, in the message and in the traceback (FR-018, SC-001); (g) the real adapter scrubs the error of the provider
too, and not only the fake, and the error it raises has no cause and no context, so the traceback of the caller
cannot print the error of the provider a second time (FR-018); (h) an error whose text is not built from its
arguments is refused by the last resort of the scrub, because the generic path cannot rewrite that text (FR-018).

Everything offline, with no key and no network. The real adapter is exercised with a client that raises, and the
client is put in the place of the factory of LangChain, so the path of the real adapter runs without a socket.

This section covers the contract that carries a tool calling turn, the part the agent of the demo needs to reach
the caller of the run: (i) the request carries the schemas of the tools the model may call and a message that is
the answer of a tool, with the identifier of the call it answers; (ii) the response carries the calls the provider
asked for, with the arguments as the text the provider sent, so that the budget and the trace never hold a float
where a number belongs (FR-012); and the type of the arguments is a rule of the domain and not a hope: a text
passes through unchanged, a mapping becomes the JSON text of the same values, and a number is refused, because a
number that arrives as a number has already lost the exact text of the amount; (iii) the converters between the
domain and the wire of the provider are pure functions that round-trip, so what the provider sent comes back
exactly; (iv) the fake adapter scripts a tool call, so the bridge over the caller of the run is testable with no
key and no network.

This section also pins the fix of the raw text of the arguments on the path of the real provider: the fake answers
like a real client, with the raw text of the arguments next to the parsed call, and the adapter of a real provider
reads that raw text, so the exact text of the amount survives the client (FR-012). And it pins the rule of the
arguments: the rule is public and it is one rule, `arguments_text` of the package, and a text that looks like a
number is a text and stays that text (FR-012).
"""

from __future__ import annotations

import copy
import os
import traceback
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import PrivateAttr

from ledgerlens.byok.adapter import (
    ALLOWED_ENDPOINTS,
    ENDPOINT_LINK_LOCAL,
    ENDPOINT_LOOPBACK,
    ENDPOINT_NOT_A_URL,
    ENDPOINT_NOT_HTTPS,
    ENDPOINT_NOT_PUBLISHED,
    ENDPOINT_UNKNOWN_PROVIDER,
    EndpointRefused,
    FakeProviderAdapter,
    LangChainProviderAdapter,
    ProviderMessage,
    ProviderRequest,
    ProviderResponse,
    ToolCall,
    ToolSchema,
    build_adapter,
    endpoint_refusal,
    endpoint_verdict,
    request_from_wire,
    request_to_wire,
    response_from_wire,
    response_to_wire,
    validate_endpoint,
)
from ledgerlens.byok.errors import ByokError, ProviderCallFailed

# The marker of the credential of the run: a shape that no known pattern of the repository matches, so only the
# adapter that holds the key can scrub it out of a text.
MARKER = "ledgerlens-marker-" + "4f3a9c2b7e1d"
# The marker of a key of a known shape: the helper `redact` of the observability package removes it on its own.
SHAPED_MARKER = "sk-" + "test-marker-0123456789abcdef"


class WeirdError(Exception):
    """An error whose text does not come from its arguments, the way some SDKs build their errors.

    Why this error exists in the tests: the generic path of the scrub rewrites the arguments of an error, and an
    error whose `__str__` ignores them keeps the key in the text the caller reads. That is the case the last resort
    of the scrub exists for (FR-018).
    """

    def __init__(self, text: str) -> None:
        super().__init__("nothing")
        self._text = text

    def __str__(self) -> str:
        return self._text


class RaisingChatModel(BaseChatModel):
    """The chat model of a client that always answers with an error.

    It is the client of the provider of the tests of the real adapter: the factory of LangChain is replaced by it,
    so the path of the real adapter runs without a socket and without a key (FR-018).
    """

    _error: Any = PrivateAttr(default=None)

    @property
    def _llm_type(self) -> str:
        """The name of the model in the traces, so the model of the test is never mistaken for a provider."""
        return "ledgerlens-raising"

    def _generate(
        self,
        messages: list[Any],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> Any:
        raise self._error


def _raising_client(monkeypatch: pytest.MonkeyPatch, error: BaseException) -> None:
    """Puts a client that answers with this error in the place of the factory of LangChain."""
    model = RaisingChatModel()
    model._error = error
    monkeypatch.setattr("langchain.chat_models.init_chat_model", lambda *args, **kwargs: model)


def _refusing_client(monkeypatch: pytest.MonkeyPatch, error: BaseException) -> None:
    """Puts a client that refuses to be built in the place of the factory of LangChain."""

    def _refuse(*args: Any, **kwargs: Any) -> None:
        raise error

    monkeypatch.setattr("langchain.chat_models.init_chat_model", _refuse)


class CapturingChatModel(BaseChatModel):
    """The client of the provider of the tests that watch what the adapter sends and what it reads back.

    It keeps the messages it received and answers with the message the test gave it, so the path of the real
    adapter runs without a socket and the test can see the turn that reached the provider (FR-012).
    """

    _sent: Any = PrivateAttr(default=None)
    _answer: Any = PrivateAttr(default=None)

    @property
    def _llm_type(self) -> str:
        """The name of the model in the traces, so the model of the test is never mistaken for a provider."""
        return "ledgerlens-capturing"

    def _generate(
        self,
        messages: list[Any],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        self._sent = list(messages)
        return ChatResult(generations=[ChatGeneration(message=self._answer)])

    def bind_tools(self, tools: Any, **kwargs: Any) -> CapturingChatModel:  # type: ignore[override]
        """The same model: the tools do not change the client of the test."""
        return self


def _capturing_client(monkeypatch: pytest.MonkeyPatch, answer: AIMessage) -> CapturingChatModel:
    """Puts a client that watches and answers in the place of the factory of LangChain."""
    model = CapturingChatModel()
    model._answer = answer
    monkeypatch.setattr("langchain.chat_models.init_chat_model", lambda *args, **kwargs: model)
    return model


def _trace_of(error: BaseException) -> str:
    """The traceback of an error, the way the caller of the adapter sees it."""
    return "".join(traceback.format_exception(type(error), error, error.__traceback__))


def test_the_endpoint_check_is_a_pure_function_of_the_text() -> None:
    """FR-017: the check reads the endpoint and the mode and returns a reason, and nothing else."""
    assert endpoint_refusal("openai", "https://api.openai.com/v1") is None
    assert endpoint_refusal("openai", "https://api.openai.com/v1") == endpoint_refusal(
        "openai", "https://api.openai.com/v1"
    )
    assert endpoint_refusal("openai", "not a url") is not None


def test_a_link_local_endpoint_is_refused_in_public_mode() -> None:
    """FR-017: the metadata address of a cloud machine is refused, and the reason says so."""
    reason = endpoint_refusal("openai", "http://169.254.169.254/latest/meta-data")

    assert reason is not None
    assert "link-local" in reason


def test_a_loopback_endpoint_is_refused_in_public_mode() -> None:
    """FR-017: the loopback of the machine is refused, by address and by name."""
    for endpoint in ("https://127.0.0.1/v1", "https://localhost:11434/v1", "https://[::1]/v1"):
        reason = endpoint_refusal("openai", endpoint)
        assert reason is not None
        assert "loopback" in reason


def test_an_endpoint_that_is_not_https_is_refused() -> None:
    """FR-017: the key of the visitor travels in the request and must not travel in the clear."""
    reason = endpoint_refusal("openai", "http://api.openai.com/v1")

    assert reason is not None
    assert "https" in reason


def test_the_refusal_of_an_endpoint_carries_a_machine_readable_code() -> None:
    """FR-017: the code is what a caller decides with, and a word of a message is not a value.

    The case of the https rule is a published host with a scheme that is not https: no other rule would catch it,
    so the code of the verdict tells the https rule apart from the rule of the allowlist.
    """
    verdict = endpoint_verdict("openai", "http://api.openai.com/v1")

    assert verdict is not None
    assert verdict.code == ENDPOINT_NOT_HTTPS


def test_each_rule_of_the_endpoint_check_has_its_own_code() -> None:
    """FR-017: the rules of the check are told apart by their code."""
    cases = (
        ("openai", "not a url", ENDPOINT_NOT_A_URL),
        ("openai", "http://169.254.169.254/latest/meta-data", ENDPOINT_LINK_LOCAL),
        ("openai", "https://127.0.0.1:11434/v1", ENDPOINT_LOOPBACK),
        ("openai", "https://evil.example.com/v1", ENDPOINT_NOT_PUBLISHED),
        ("not-a-provider", "https://api.openai.com/v1", ENDPOINT_UNKNOWN_PROVIDER),
    )

    for provider, endpoint, code in cases:
        verdict = endpoint_verdict(provider, endpoint)

        assert verdict is not None, endpoint
        assert verdict.code == code, endpoint


def test_the_refusal_of_the_endpoint_carries_the_code_of_the_rule() -> None:
    """FR-017: the refusal that the caller catches carries the code of the rule that refused it."""
    with pytest.raises(EndpointRefused) as refused:
        validate_endpoint("openai", "http://api.openai.com/v1")

    assert refused.value.code == ENDPOINT_NOT_HTTPS


def test_an_endpoint_the_provider_does_not_publish_is_refused() -> None:
    """FR-017: the server calls what the provider publishes and nothing else."""
    reason = endpoint_refusal("openai", "https://evil.example.com/v1")

    assert reason is not None
    assert "not an allowed endpoint" in reason


def test_an_unknown_provider_is_refused() -> None:
    """FR-017: a provider with no published endpoint has no endpoint the server may call."""
    reason = endpoint_refusal("not-a-provider", "https://api.openai.com/v1")

    assert reason is not None
    assert "no published endpoint" in reason


def test_the_allowed_endpoints_of_every_provider_are_https_except_the_local_one() -> None:
    """The key of the visitor travels in the request, so the hosted providers publish https only."""
    for provider, endpoints in ALLOWED_ENDPOINTS.items():
        if provider == "local":
            continue
        assert all(endpoint.startswith("https://") for endpoint in endpoints)


def test_the_local_provider_publishes_its_own_endpoints() -> None:
    """FR-017: the local provider is the machine of the operator, and it has published endpoints too.

    The loopback of the local provider is refused in public mode and allowed in private mode, and the endpoint is
    published either way.
    """
    assert "local" in ALLOWED_ENDPOINTS
    assert endpoint_refusal("local", "http://127.0.0.1:11434/v1", public_mode=False) is None

    verdict = endpoint_verdict("local", "http://127.0.0.1:11434/v1", public_mode=True)

    assert verdict is not None
    assert verdict.code == ENDPOINT_LOOPBACK


def test_validate_endpoint_raises_a_refusal_that_names_the_reason() -> None:
    """FR-017: the refusal of the endpoint names the reason and the address."""
    with pytest.raises(EndpointRefused) as refused:
        validate_endpoint("openai", "https://169.254.169.254/latest")

    assert "link-local" in str(refused.value)


def test_the_fake_adapter_answers_what_the_test_tells_it_to_answer() -> None:
    """The fake is scripted: the answers come out in the order the test wrote them."""
    adapter = FakeProviderAdapter().script_answer("first", input_tokens=10, output_tokens=5)
    adapter.script_answer("second")

    first = adapter.complete(ProviderRequest(model_id="gpt-4.1-mini"))
    second = adapter.complete(ProviderRequest(model_id="gpt-4.1-mini"))

    assert first.content == "first"
    assert first.input_tokens == 10
    assert first.output_tokens == 5
    assert second.content == "second"
    assert adapter.calls[0].model_id == "gpt-4.1-mini"


def test_the_fake_adapter_raises_what_the_test_tells_it_to_raise() -> None:
    """A provider failure is proved by the fake, without a network."""
    adapter = FakeProviderAdapter().script_failure(RuntimeError("the provider refused the key"))

    with pytest.raises(RuntimeError, match="the provider refused the key"):
        adapter.complete(ProviderRequest(model_id="gpt-4.1-mini"))


def test_the_fake_adapter_reports_the_tokens_the_provider_counted() -> None:
    """The observed cost of a run comes from the tokens the provider reported (FR-010)."""
    adapter = FakeProviderAdapter().script_answer("answer", input_tokens=42, output_tokens=7)

    response = adapter.complete(ProviderRequest(model_id="gpt-4.1-mini"))

    assert response.input_tokens == 42
    assert response.output_tokens == 7


def test_the_fake_adapter_also_answers_as_a_chat_model() -> None:
    """The fake is a chat model too, so the agent of the run can be driven without a network."""
    adapter = FakeProviderAdapter().script_answer("answer", input_tokens=3, output_tokens=4)

    model = adapter.chat_model("gpt-4.1-mini")
    answer = model.invoke([HumanMessage("the question")])

    assert answer.content == "answer"
    assert answer.usage_metadata == {"input_tokens": 3, "output_tokens": 4, "total_tokens": 7}


def test_the_fake_adapter_raises_the_scripted_failure_as_a_chat_model_too() -> None:
    """A provider failure is proved by the fake on both paths."""
    adapter = FakeProviderAdapter().script_failure(RuntimeError("the provider refused the key"))

    model = adapter.chat_model("gpt-4.1-mini")

    with pytest.raises(RuntimeError, match="the provider refused the key"):
        model.invoke([HumanMessage("the question")])


def test_the_adapter_is_built_per_run_and_does_not_touch_the_environment() -> None:
    """FR-007: the adapter of a run never writes the credential of the visitor in the process environment."""
    before = dict(os.environ)

    adapter = build_adapter("openai", "sk-visitor-key-not-real")

    assert isinstance(adapter, LangChainProviderAdapter)
    assert dict(os.environ) == before
    assert "sk-visitor-key-not-real" not in repr(adapter)


def test_two_visitors_on_two_providers_do_not_share_a_client() -> None:
    """FR-007: each run builds its own adapter, so the key of one visitor never reaches the run of another."""
    first = build_adapter("openai", "sk-first-not-real")
    second = build_adapter("anthropic", "sk-second-not-real")

    assert first is not second
    assert first.provider == "openai"
    assert second.provider == "anthropic"
    assert "sk-first-not-real" not in repr(first)
    assert "sk-second-not-real" not in repr(second)


def test_the_endpoint_is_refused_before_the_adapter_is_built() -> None:
    """FR-017: an endpoint the server may not call never reaches the client of the visitor."""
    with pytest.raises(EndpointRefused):
        build_adapter("openai", "sk-visitor-key-not-real", endpoint="https://169.254.169.254/latest")


def test_the_endpoint_is_checked_again_when_the_client_of_the_provider_is_built() -> None:
    """FR-017: the client of the provider is never built with an endpoint the server may not call."""
    adapter = LangChainProviderAdapter("openai", "sk-visitor-key-not-real", endpoint="http://169.254.169.254/latest")

    with pytest.raises(EndpointRefused) as refused:
        adapter.chat_model("gpt-4.1-mini")

    assert refused.value.code == ENDPOINT_LINK_LOCAL


# --- the credential of the run never shows in the adapter ----------------------------------------------


def test_no_attribute_of_the_adapter_shows_the_key() -> None:
    """FR-007: the key of the visitor is not a plain attribute that a debug print would show."""
    adapter = build_adapter("openai", MARKER)

    for name, value in vars(adapter).items():
        assert MARKER not in str(value), name
        assert MARKER not in repr(value), name


def test_the_representation_of_the_adapter_carries_no_key() -> None:
    """FR-007 and FR-018: a representation ends up in the logs, so it never shows the key."""
    adapter = build_adapter("openai", MARKER)

    assert MARKER not in repr(adapter)
    assert MARKER not in str(adapter)


# --- the error of the provider leaves the adapter without the key --------------------------------------


def test_a_provider_error_that_carries_the_key_leaves_the_adapter_without_it() -> None:
    """SC-001 and FR-018: the key never leaves the adapter inside an error.

    The error is raised through the adapter, and not written by hand, because the adapter is the boundary where
    the key is still alive: the message and the traceback that the caller sees carry no key at all.
    """
    adapter = FakeProviderAdapter(api_key=MARKER)
    adapter.script_failure(RuntimeError(f"401 invalid api key {MARKER} for the model gpt-4.1-mini"))

    with pytest.raises(RuntimeError) as raised:
        adapter.complete(ProviderRequest(model_id="gpt-4.1-mini"))

    message = str(raised.value)
    trace = "".join(traceback.format_exception(type(raised.value), raised.value, raised.value.__traceback__))

    assert MARKER not in message
    assert MARKER not in trace
    assert "[REDACTED]" in message


def test_a_provider_error_of_the_client_leaves_the_adapter_without_the_key() -> None:
    """SC-001 and FR-018: the path of the chat model scrubs the key out of the error too."""
    adapter = FakeProviderAdapter(api_key=MARKER)
    adapter.script_failure(RuntimeError(f"401 invalid api key {MARKER}"))
    model = adapter.chat_model("gpt-4.1-mini")

    with pytest.raises(RuntimeError) as raised:
        model.invoke([HumanMessage("the question")])

    assert MARKER not in str(raised.value)


def test_the_error_of_the_provider_keeps_its_type_and_its_reason() -> None:
    """FR-018: the scrub takes the key out of the error and nothing else."""
    adapter = FakeProviderAdapter(api_key=MARKER)
    adapter.script_failure(RuntimeError("the provider refused the request"))

    with pytest.raises(RuntimeError, match="the provider refused the request"):
        adapter.complete(ProviderRequest(model_id="gpt-4.1-mini"))


# --- the whole chain of the error is scrubbed ------------------------------------------------------------


def test_the_cause_of_the_error_of_the_provider_is_scrubbed_too() -> None:
    """FR-018 and SC-001: a provider that wraps its own error carries the key in the cause.

    The chain is scrubbed, and not only the error of the run: the cause of the error is an object of the provider
    too, and a traceback prints it.
    """
    cause = RuntimeError(f"the sdk says: 401 invalid api key {MARKER}")
    top = RuntimeError("the provider refused the call")
    top.__cause__ = cause
    adapter = FakeProviderAdapter(api_key=MARKER)
    adapter.script_failure(top)

    with pytest.raises(RuntimeError) as raised:
        adapter.complete(ProviderRequest(model_id="gpt-4.1-mini"))

    assert MARKER not in str(raised.value)
    assert MARKER not in _trace_of(raised.value)
    # The cause itself no longer carries the key: the scrub reaches every link of the chain.
    assert MARKER not in str(cause)


def test_the_detail_of_a_refusal_in_the_chain_is_scrubbed() -> None:
    """FR-018: a refusal of the family carries its detail in an attribute, and that attribute is read by the caller.

    The detail of a refusal is a text of its own, so the scrub has to reach it and not only the message of the
    error.
    """
    refusal = ProviderCallFailed(f"the provider said: {MARKER}")
    top = RuntimeError("the provider refused the call")
    top.__cause__ = refusal
    adapter = FakeProviderAdapter(api_key=MARKER)
    adapter.script_failure(top)

    with pytest.raises(RuntimeError) as raised:
        adapter.complete(ProviderRequest(model_id="gpt-4.1-mini"))

    assert MARKER not in refusal.detail
    assert MARKER not in str(raised.value)


def test_the_shape_based_redact_is_applied_to_the_error_of_the_provider() -> None:
    """FR-018: the adapter applies the helper of the repository too, so a key of a known shape is removed.

    The key of this error is not the key of the run, so only the helper of the repository can remove it.
    """
    adapter = FakeProviderAdapter(api_key=MARKER)
    adapter.script_failure(RuntimeError(f"the provider said: {SHAPED_MARKER} is not a valid key"))

    with pytest.raises(RuntimeError) as raised:
        adapter.complete(ProviderRequest(model_id="gpt-4.1-mini"))

    assert SHAPED_MARKER not in str(raised.value)
    assert "[REDACTED]" in str(raised.value)


# --- the last resort of the scrub ------------------------------------------------------------------------


def test_an_error_whose_text_is_not_built_from_its_arguments_is_refused_by_the_last_resort() -> None:
    """FR-018 and SC-001: the generic path cannot rewrite an error whose text ignores its arguments.

    The error is replaced by a refusal of the family, so the key never reaches the caller, and neither the message
    nor the traceback of the refusal carries it.
    """
    adapter = FakeProviderAdapter(api_key=MARKER)
    adapter.script_failure(WeirdError(f"401 invalid api key {MARKER}"))

    with pytest.raises(ProviderCallFailed) as raised:
        adapter.complete(ProviderRequest(model_id="gpt-4.1-mini"))

    assert MARKER not in str(raised.value)
    assert MARKER not in _trace_of(raised.value)
    assert "[REDACTED]" in str(raised.value)


# --- the error leaves the adapter without a cause and without a context ---------------------------------


def test_the_error_of_the_provider_leaves_the_adapter_without_a_cause_and_without_a_context() -> None:
    """FR-018: the error that leaves the adapter is an error of its own.

    The error of the provider is not the answer of the adapter: it is raised without a cause and without a context,
    so the traceback of the caller cannot print the error of the provider a second time, with a text the generic
    path of the scrub could not rewrite.
    """
    adapter = FakeProviderAdapter(api_key=MARKER)
    adapter.script_failure(WeirdError(f"401 invalid api key {MARKER}"))

    with pytest.raises(ProviderCallFailed) as raised:
        adapter.complete(ProviderRequest(model_id="gpt-4.1-mini"))

    assert raised.value.__cause__ is None
    assert raised.value.__suppress_context__ is True


# --- the real adapter scrubs the error of the provider too ------------------------------------------------


def test_the_real_adapter_scrubs_the_error_of_the_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-018 and SC-001: the real adapter scrubs the error of the provider, and not only the fake.

    The client of the provider is put in the place of the factory of LangChain, so the path of the real adapter
    runs without a socket and without a key.
    """
    _raising_client(monkeypatch, RuntimeError(f"401 invalid api key {MARKER} for the model gpt-4.1-mini"))
    adapter = LangChainProviderAdapter("openai", MARKER)

    with pytest.raises(RuntimeError) as raised:
        adapter.complete(ProviderRequest(model_id="gpt-4.1-mini"))

    assert MARKER not in str(raised.value)
    assert MARKER not in _trace_of(raised.value)
    assert "[REDACTED]" in str(raised.value)


def test_the_real_adapter_leaves_the_error_without_a_cause_and_without_a_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-018: the error of the real adapter leaves without a cause and without a context."""
    _raising_client(monkeypatch, RuntimeError(f"401 invalid api key {MARKER}"))
    adapter = LangChainProviderAdapter("openai", MARKER)

    with pytest.raises(RuntimeError) as raised:
        adapter.complete(ProviderRequest(model_id="gpt-4.1-mini"))

    assert raised.value.__cause__ is None
    assert raised.value.__suppress_context__ is True


def test_the_real_adapter_scrubs_the_error_of_the_client_of_the_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-018 and SC-001: the error of the client of the provider is scrubbed before it leaves the adapter.

    The key is handed to the client of the provider, so the error of the client may carry it, and the client is
    built inside the adapter (FR-007, FR-018).
    """
    _refusing_client(monkeypatch, RuntimeError(f"the client refused the key {MARKER}"))
    adapter = LangChainProviderAdapter("openai", MARKER)

    with pytest.raises(RuntimeError) as raised:
        adapter.chat_model("gpt-4.1-mini")

    assert MARKER not in str(raised.value)
    assert MARKER not in _trace_of(raised.value)


def test_the_real_adapter_refuses_an_error_of_the_client_whose_text_is_not_built_from_its_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-018 and SC-001: the last resort of the scrub holds on the path of the client too.

    The error of the client is replaced by a refusal of the family, and the traceback of that refusal carries no
    key, not in the cause and not in the context.
    """
    _refusing_client(monkeypatch, WeirdError(f"401 invalid api key {MARKER}"))
    adapter = LangChainProviderAdapter("openai", MARKER)

    with pytest.raises(ProviderCallFailed) as raised:
        adapter.chat_model("gpt-4.1-mini")

    assert MARKER not in str(raised.value)
    assert MARKER not in _trace_of(raised.value)


def test_the_real_adapter_refuses_an_error_whose_text_is_not_built_from_its_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-018 and SC-001: the last resort of the scrub holds on the path of the real adapter too.

    The error of the client is replaced by a refusal of the family, and the traceback of that refusal carries no
    key, not in the cause and not in the context.
    """
    _raising_client(monkeypatch, WeirdError(f"401 invalid api key {MARKER}"))
    adapter = LangChainProviderAdapter("openai", MARKER)

    with pytest.raises(ProviderCallFailed) as raised:
        adapter.complete(ProviderRequest(model_id="gpt-4.1-mini"))

    assert MARKER not in str(raised.value)
    assert MARKER not in _trace_of(raised.value)


# --- the contract that carries a tool calling turn ---------------------------------------------------------


def _tool_schema() -> ToolSchema:
    """The schema of the tool the tests use: a name, a description and the parameters it takes."""
    return ToolSchema(
        name="search_ledger",
        description="search the ledger of the case",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    )


def _tool_call() -> ToolCall:
    """The call of a tool the provider asked for: an identifier, a name and the arguments as a text."""
    return ToolCall(id="call_1", name="search_ledger", arguments='{"query": "tx-2048"}')


def test_the_request_carries_the_schemas_of_the_tools_the_model_may_call() -> None:
    """FR-012: the request names the tools the model may call, with the parameters of each one.

    The agent of the demo binds its tools to the model, and the model can only call a tool it was told about.
    """
    request = ProviderRequest(model_id="gpt-4.1-mini", tools=(_tool_schema(),))

    assert request.tools[0].name == "search_ledger"
    assert request.tools[0].description == "search the ledger of the case"
    assert request.tools[0].parameters["properties"]["query"] == {"type": "string"}


def test_the_request_carries_the_answer_of_a_tool_and_the_call_it_answers() -> None:
    """FR-012: the request carries a whole turn, and not only the role and the content of a message.

    The agent asks the model, the model asks for a tool, the tool answers, and the answer of the tool goes back to
    the model with the identifier of the call it answers.
    """
    request = ProviderRequest(
        model_id="gpt-4.1-mini",
        messages=(
            ProviderMessage(role="user", content="find the payment"),
            ProviderMessage(role="assistant", content="", tool_calls=(_tool_call(),)),
            ProviderMessage(role="tool", content="three rows", tool_call_id="call_1"),
        ),
    )

    assert request.messages[0].role == "user"
    assert request.messages[1].tool_calls[0].id == "call_1"
    assert request.messages[2].role == "tool"
    assert request.messages[2].tool_call_id == "call_1"
    assert request.messages[2].content == "three rows"


def test_a_message_of_the_domain_is_also_a_mapping() -> None:
    """The code that reads a request today reads the content of a message with `get`, and it keeps working."""
    message = ProviderMessage(role="tool", content="three rows", tool_call_id="call_1")

    assert message.get("content", "") == "three rows"
    assert message["role"] == "tool"
    assert message.get("tool_call_id") == "call_1"


def test_the_response_carries_the_tool_calls_the_provider_asked_for() -> None:
    """FR-012: the answer of the provider says which tools it wants, with the identifier of each call."""
    response = ProviderResponse(content="", tool_calls=(_tool_call(),))

    assert response.tool_calls[0].id == "call_1"
    assert response.tool_calls[0].name == "search_ledger"
    assert response.tool_calls[0].arguments == '{"query": "tx-2048"}'


def test_the_arguments_of_a_tool_stay_a_text_and_never_become_a_number() -> None:
    """FR-012: the arguments of a call arrive as a text and they stay a text.

    The provider sends the arguments as a JSON text, and a domain that parsed that text would hold a float where
    the provider sent a number with two decimals. The budget and the trace of the run read these arguments.
    """
    call = ToolCall(id="call_1", name="refund", arguments='{"amount": 12.50, "currency": "BRL"}')

    assert isinstance(call.arguments, str)
    assert call.arguments == '{"amount": 12.50, "currency": "BRL"}'

    again = response_from_wire(response_to_wire(ProviderResponse(content="", tool_calls=(call,))))

    assert again.tool_calls[0].arguments == '{"amount": 12.50, "currency": "BRL"}'


def test_the_arguments_of_a_call_that_arrive_as_a_text_stay_that_text() -> None:
    """FR-012: a text of arguments passes through the domain unchanged, character for character.

    The text is what the provider sent, and the domain does not touch it.
    """
    call = ToolCall(id="call_1", name="refund", arguments='{"amount": 12.50, "currency": "BRL"}')

    assert isinstance(call.arguments, str)
    assert call.arguments == '{"amount": 12.50, "currency": "BRL"}'


def test_the_arguments_of_a_call_that_arrive_as_a_mapping_become_a_json_text() -> None:
    """FR-012: a client that parsed the arguments hands over a mapping, and the domain writes it back as a text.

    The JSON text carries the values the mapping holds. The exact text of the provider is not restored, because the
    client that parsed it is the one that lost it, and the domain does not pretend otherwise.
    """
    call = ToolCall(id="call_1", name="refund", arguments={"amount": "12.50", "currency": "BRL"})

    assert isinstance(call.arguments, str)
    assert call.arguments == '{"amount": "12.50", "currency": "BRL"}'


def test_the_arguments_of_a_call_that_arrive_as_a_number_are_refused() -> None:
    """FR-012: a number is refused, because the domain cannot write back the text of a number.

    A float that arrives as a float has already lost the exact text of the amount: the domain cannot write '12.50'
    back for a 12.5, and a text the domain invented would be a text the provider never sent. The budget and the
    trace of the run would read it as if it were true.
    """
    with pytest.raises(ProviderCallFailed) as refused:
        ToolCall(id="call_1", name="refund", arguments=10.5)  # type: ignore[arg-type]

    assert isinstance(refused.value, ByokError)
    assert "float" in str(refused.value)
    assert "refund" in str(refused.value)
    assert "the arguments of a call are the text the provider sent" in str(refused.value)


def test_the_arguments_of_a_call_that_arrive_as_an_integer_are_refused() -> None:
    """FR-012: an integer is refused the same way a float is, because the arguments are a text and not a number."""
    with pytest.raises(ProviderCallFailed) as refused:
        ToolCall(id="call_1", name="refund", arguments=10)  # type: ignore[arg-type]

    assert isinstance(refused.value, ByokError)
    assert "int" in str(refused.value)


def test_the_arguments_of_a_call_of_a_provider_that_arrive_as_a_number_are_refused() -> None:
    """FR-012: the shape the providers send is refused too, so a number never reaches the domain.

    The call arrives as a mapping of the provider, with the arguments in the shape the provider chose, and a
    number in that shape is a number the domain cannot read.
    """
    with pytest.raises(ProviderCallFailed) as refused:
        ProviderResponse(
            content="",
            tool_calls=({"id": "call_1", "function": {"name": "refund", "arguments": 10.5}},),
        )

    assert isinstance(refused.value, ByokError)
    assert "float" in str(refused.value)


def test_the_response_of_the_provider_never_holds_a_number_in_the_arguments_of_a_call() -> None:
    """FR-012: the answer of the provider holds texts in the arguments of its calls, whatever the provider sent."""
    with pytest.raises(ProviderCallFailed):
        ProviderResponse(content="", tool_calls=({"id": "call_1", "name": "refund", "arguments": 10.5},))


def test_the_request_survives_the_round_trip_to_the_wire() -> None:
    """What the provider sent comes back exactly: the turn, the tools and the model are the same."""
    request = ProviderRequest(
        model_id="gpt-4.1-mini",
        messages=(
            ProviderMessage(role="system", content="you are the investigator"),
            ProviderMessage(role="user", content="find the payment"),
            ProviderMessage(role="assistant", content="", tool_calls=(_tool_call(),)),
            ProviderMessage(role="tool", content="three rows", tool_call_id="call_1"),
        ),
        tools=(_tool_schema(),),
    )

    assert request_from_wire(request_to_wire(request)) == request


def test_a_request_without_tools_survives_the_round_trip_to_the_wire() -> None:
    """A request that names no tool is a request like any other, and it comes back the same."""
    request = ProviderRequest(
        model_id="gpt-4.1-mini", messages=(ProviderMessage(role="user", content="find the payment"),)
    )

    assert request_from_wire(request_to_wire(request)) == request


def test_the_response_survives_the_round_trip_to_the_wire() -> None:
    """The answer of the provider comes back exactly, with the tokens it counted."""
    response = ProviderResponse(
        content="the answer",
        input_tokens=11,
        output_tokens=7,
        model_id="gpt-4.1-mini",
        tool_calls=(_tool_call(),),
    )

    assert response_from_wire(response_to_wire(response)) == response


def test_the_wire_carries_the_arguments_of_a_call_as_the_text_the_provider_sent() -> None:
    """The wire is the shape of the provider, and the provider sends the arguments as a text."""
    request = ProviderRequest(
        model_id="gpt-4.1-mini",
        messages=(ProviderMessage(role="assistant", content="", tool_calls=(_tool_call(),)),),
    )

    sent = request_to_wire(request)["messages"][0]["tool_calls"][0]

    assert sent["id"] == "call_1"
    assert sent["function"]["name"] == "search_ledger"
    assert sent["function"]["arguments"] == '{"query": "tx-2048"}'


def test_the_converters_of_the_wire_are_pure() -> None:
    """The converters read and they build, and they never write what they are given."""
    payload = {
        "model": "gpt-4.1-mini",
        "messages": [{"role": "tool", "tool_call_id": "call_1", "content": "three rows"}],
        "tools": [
            {
                "type": "function",
                "function": {"name": "search_ledger", "description": "search", "parameters": {}},
            }
        ],
    }
    before = copy.deepcopy(payload)

    first = request_from_wire(payload)
    second = request_from_wire(payload)

    assert payload == before
    assert first == second


def test_a_provider_answer_that_cannot_be_read_is_refused() -> None:
    """A provider that answers without a choice is a provider that broke, and the run has to know."""
    with pytest.raises(ProviderCallFailed):
        response_from_wire({"choices": []})


# --- the fake adapter scripts a tool call ------------------------------------------------------------------


def test_the_fake_adapter_scripts_a_tool_call() -> None:
    """The bridge over the caller of the run is tested with the fake, with no key and no network (FR-012)."""
    adapter = FakeProviderAdapter().script_tool_call("search_ledger", '{"query": "tx-2048"}', call_id="call_1")

    response = adapter.complete(ProviderRequest(model_id="gpt-4.1-mini"))

    assert response.tool_calls[0].id == "call_1"
    assert response.tool_calls[0].name == "search_ledger"
    assert response.tool_calls[0].arguments == '{"query": "tx-2048"}'


def test_the_fake_adapter_answers_a_tool_call_as_a_chat_model_too() -> None:
    """The fake is a chat model too, and its answer carries the call of the tool."""
    adapter = FakeProviderAdapter().script_tool_call("search_ledger", '{"query": "tx-2048"}', call_id="call_1")

    answer = adapter.chat_model("gpt-4.1-mini").invoke([HumanMessage("the question")])

    assert answer.tool_calls[0]["name"] == "search_ledger"
    assert answer.tool_calls[0]["id"] == "call_1"
    assert answer.tool_calls[0]["args"] == {"query": "tx-2048"}


# --- the raw text of the arguments travels with the call ----------------------------------------------------


def test_the_fake_answers_a_tool_call_with_the_raw_text_next_to_the_parsed_call() -> None:
    """F1: the fake answers like a real client: the raw text sits next to the parsed call.

    A real provider sends the arguments of a call as a text, and the client of LangChain parses that text into a
    mapping. The two live side by side in the answer, and the raw text is the one the domain reads (FR-012).
    """
    adapter = FakeProviderAdapter().script_tool_call("refund", '{"amount": 10.50}', call_id="call_1")

    answer = adapter.chat_model("gpt-4.1-mini").invoke([HumanMessage("the question")])

    raw = answer.additional_kwargs["tool_calls"][0]
    assert raw["id"] == "call_1"
    assert raw["function"]["name"] == "refund"
    assert raw["function"]["arguments"] == '{"amount": 10.50}'


def test_the_real_adapter_reads_the_raw_text_of_the_arguments_through_the_fake(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F1: the path of the real provider keeps the exact text of the amount.

    The client of the provider is the fake, so the path of the real adapter runs without a socket. The parsed call
    of the client has already lost the decimals of the amount, and the raw text is what saves them (FR-012).
    """
    fake = FakeProviderAdapter().script_tool_call("refund", '{"amount": 10.50}', call_id="call_1")
    monkeypatch.setattr(
        "langchain.chat_models.init_chat_model",
        lambda *args, **kwargs: fake.chat_model("gpt-4.1-mini"),
    )
    adapter = LangChainProviderAdapter("openai", "sk-visitor-key-not-real")

    response = adapter.complete(ProviderRequest(model_id="gpt-4.1-mini"))

    assert response.tool_calls[0].arguments == '{"amount": 10.50}'
    assert isinstance(response.tool_calls[0].arguments, str)


def test_the_real_adapter_keeps_the_raw_text_of_the_arguments_of_a_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F1: the answer of a real provider carries the raw text, and the domain reads it.

    The client of the provider answers the way a provider answers: the parsed call and the raw text, side by side.
    The branch that reads the raw text is the one that keeps the decimals of the amount (FR-012).
    """
    _capturing_client(
        monkeypatch,
        AIMessage(
            content="",
            tool_calls=[{"name": "refund", "args": {"amount": 10.5}, "id": "call_1"}],
            additional_kwargs={
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "refund", "arguments": '{"amount": 10.50}'},
                    }
                ]
            },
        ),
    )
    adapter = LangChainProviderAdapter("openai", "sk-visitor-key-not-real")

    response = adapter.complete(ProviderRequest(model_id="gpt-4.1-mini"))

    assert response.tool_calls[0].arguments == '{"amount": 10.50}'
    assert isinstance(response.tool_calls[0].arguments, str)


def test_the_arguments_of_a_call_that_look_like_a_number_stay_that_text() -> None:
    """F3: a text that looks like a number is a text and stays that text.

    The text '10.50' is not a number the domain may hold: a float would have lost the decimals of the amount, and
    the budget and the trace of the run read exactly what the provider sent (FR-012).
    """
    call = ToolCall(id="c1", name="refund", arguments="10.50")

    assert isinstance(call.arguments, str)
    assert call.arguments == "10.50"


def test_the_arguments_of_a_call_are_always_a_text() -> None:
    """F3: the arguments of a call are a text in every shape the domain accepts.

    The shape the providers send is a text too, and the rule holds for it exactly as it holds for the plain shape.
    """
    call = ToolCall.from_any({"id": "c1", "function": {"name": "refund", "arguments": "10.50"}})

    assert isinstance(call.arguments, str)
    assert call.arguments == "10.50"


def test_the_rule_of_the_arguments_of_a_call_is_public_in_the_package() -> None:
    """F2: the rule of the arguments is one rule, and it is a public name of the package.

    The bridge of the API layer reads the calls of the model, and it must read them with the rule of the domain
    and not with a copy of it: a copy that is more forgiving would let a number through (FR-012).
    """
    from ledgerlens import byok
    from ledgerlens.byok.adapter import arguments_text

    assert "arguments_text" in byok.__all__
    assert byok.arguments_text is arguments_text


def test_the_public_rule_keeps_a_text_that_looks_like_a_number_as_it_is() -> None:
    """F2 and F3: the public rule passes a text through unchanged, character for character."""
    from ledgerlens.byok.adapter import arguments_text

    assert arguments_text("10.50") == "10.50"
    assert isinstance(arguments_text("10.50"), str)


def test_the_public_rule_refuses_a_number() -> None:
    """F2: the public rule refuses a number, because a float has already lost the exact text of the amount."""
    from ledgerlens.byok.adapter import arguments_text

    with pytest.raises(ProviderCallFailed) as refused:
        arguments_text(10.5, name="refund")

    assert isinstance(refused.value, ByokError)
    assert "float" in str(refused.value)
    assert "refund" in str(refused.value)


def test_the_real_adapter_sends_the_answer_of_a_tool_and_reads_the_call_it_asked_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-012: the real adapter carries a whole turn to the provider and reads the calls of the answer back."""
    model = _capturing_client(
        monkeypatch,
        AIMessage(content="", tool_calls=[{"name": "search_ledger", "args": {"query": "tx-2048"}, "id": "call_1"}]),
    )
    adapter = LangChainProviderAdapter("openai", "sk-visitor-key-not-real")
    request = ProviderRequest(
        model_id="gpt-4.1-mini",
        messages=(
            ProviderMessage(role="user", content="find the payment"),
            ProviderMessage(role="assistant", content="", tool_calls=(_tool_call(),)),
            ProviderMessage(role="tool", content="three rows", tool_call_id="call_1"),
        ),
        tools=(_tool_schema(),),
    )

    response = adapter.complete(request)

    sent = model._sent
    assert sent[0].type == "human"
    assert sent[1].type == "ai"
    assert sent[2].type == "tool"
    assert sent[2].tool_call_id == "call_1"
    assert response.tool_calls[0].id == "call_1"
    assert response.tool_calls[0].name == "search_ledger"
