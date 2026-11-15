"""The adapter of a provider: the endpoint the server is allowed to call, the model built for one run, and the
boundary where the credential of the run is scrubbed out of the errors of the provider.

Why it exists: the visitor brings a key, and the server calls the provider with it. Two things have to hold. The
server has to call an endpoint it knows, because an endpoint that a visitor can point anywhere is a way into the
network of the machine that runs the demo (FR-017). And the client has to be built for the run and for that run
only, because a client that lives in the process environment would carry the key of one visitor into the run of
another (FR-007).

Why the adapter is also the boundary of the credential: the adapter holds the key it injected into the client, so
it is the last place where the key is alive. A provider that answers with an error that carries the key is an error
that would carry the key out of the process, into the log, into the trace and into the answer of the interface. The
adapter therefore scrubs the key out of the error, in the message and in the chain of the error, before the error
leaves the adapter (FR-018, SC-001). The scrub of the vault is the second layer, and it is the tool of the facade of
the live mode, which is the task of the next milestone.

The endpoint check is a pure function of the text of the endpoint: it resolves nothing and opens nothing, so a test
proves it without a network and the refusal names the reason that stopped it (FR-017). The refusal carries a
machine-readable code, the way the refusals of the sandbox carry one, so a caller decides with the code and reads
the message. The address families that are refused in public mode are the ones that reach the machine itself: the
link-local range, where the metadata of a cloud machine lives, and the loopback range, where the services of the
host live.

The fake adapter is the one the tests use: it answers what the test tells it to answer, and it raises what the test
tells it to raise, and it scrubs the credential of the run out of that error exactly like the real one, so the
adversarial test of the key exists without a network. No test of this feature ever opens a socket.
"""

from __future__ import annotations

import ipaddress
import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import PrivateAttr, SecretStr

from ledgerlens.byok.errors import ByokError, ProviderCallFailed, UnknownProvider
from ledgerlens.observability.callbacks import redact

log = logging.getLogger(__name__)

__all__ = [
    "ALLOWED_ENDPOINTS",
    "ENDPOINT_LINK_LOCAL",
    "ENDPOINT_LOOPBACK",
    "ENDPOINT_NOT_A_URL",
    "ENDPOINT_NOT_HTTPS",
    "ENDPOINT_NOT_PUBLISHED",
    "ENDPOINT_UNKNOWN_PROVIDER",
    "EndpointRefused",
    "EndpointVerdict",
    "FakeProviderAdapter",
    "LangChainProviderAdapter",
    "ProviderAdapter",
    "ProviderRequest",
    "ProviderResponse",
    "UnknownProvider",
    "build_adapter",
    "endpoint_refusal",
    "endpoint_verdict",
    "validate_endpoint",
]

# The endpoints the server is allowed to call, per provider. The server calls nothing else: an endpoint that is
# not on this list is refused, whatever the visitor asks for (FR-017). The local provider is the server of the
# operator's own machine, so it is plain http and it lives on the loopback, which the public demo refuses.
ALLOWED_ENDPOINTS: Mapping[str, tuple[str, ...]] = {
    "openai": ("https://api.openai.com/v1",),
    "anthropic": ("https://api.anthropic.com/v1",),
    "google": ("https://generativelanguage.googleapis.com/v1beta",),
    "local": ("http://127.0.0.1:11434/v1", "http://localhost:11434/v1"),
}

# The machine-readable codes of the refusals of an endpoint. Each rule of the check has its own, the way the rules
# of the sandbox have their own, and the code is what a caller decides with (FR-017).
ENDPOINT_NOT_A_URL = "not_a_url"
ENDPOINT_LINK_LOCAL = "link_local"
ENDPOINT_LOOPBACK = "loopback"
ENDPOINT_NOT_HTTPS = "not_https"
ENDPOINT_NOT_PUBLISHED = "not_published"
ENDPOINT_UNKNOWN_PROVIDER = "unknown_provider"

# The marker that replaces the credential of the run in a text.
_REDACTED = "[REDACTED]"


class EndpointRefused(ByokError):
    """The endpoint of the provider is not one the server is allowed to call.

    The message names the reason, because the visitor reads it and a refusal without a reason is not an answer
    (FR-017).

    Why the code is an attribute and not only a word of the message: a caller decides with the code, and a word in
    a text is not a value a program can read.
    """

    reason = "the provider endpoint is refused"

    def __init__(self, detail: str | None = None, code: str = ENDPOINT_NOT_PUBLISHED) -> None:
        super().__init__(detail)
        self.code = code


@dataclass(frozen=True)
class EndpointVerdict:
    """The verdict of the check of an endpoint: the code of the rule and the message a visitor reads."""

    code: str
    message: str


@dataclass(frozen=True)
class ProviderRequest:
    """What the run asks of the provider: the model, the messages and the tools."""

    model_id: str
    messages: tuple[Mapping[str, str], ...] = ()
    tools: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class ProviderResponse:
    """What the provider answered: the text and the tokens it counted.

    The tokens are the ones the provider reported, and they are the only source of the observed cost of a run
    (FR-010). A provider that reports no token count reports zero, and the interface says so.
    """

    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    model_id: str = ""


class _Credential:
    """The credential of one run, held so that no representation of it ever shows it.

    Why the key is not a plain attribute: a plain string attribute is a key that a debug print, a `vars` call or a
    traceback with the locals of the adapter shows. The value is held in a masked container, so the only way to
    read it is the one that asks for it on purpose (FR-007, FR-018).
    """

    def __init__(self, api_key: str) -> None:
        self._secret = SecretStr(api_key)

    @property
    def text(self) -> str:
        """The exact text of the key, for the client of the provider."""
        return self._secret.get_secret_value()

    def scrub(self, text: str) -> str:
        """The text without the key of this run.

        Why the exact text comes first: a key of a provider that the repository does not know has a shape that the
        helper `redact` never matches, and only the run knows the exact text of the key it holds (FR-018).
        """
        secret = self._secret.get_secret_value()
        if secret and secret in text:
            text = text.replace(secret, _REDACTED)
        return redact(text)

    def __repr__(self) -> str:
        """The credential without its text, because a representation ends up in the logs."""
        return "Credential([REDACTED])"

    __str__ = __repr__


def _error_chain(error: BaseException) -> list[BaseException]:
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


def _scrubbed_error(error: BaseException, credential: _Credential | None) -> BaseException:
    """The error of the provider without the credential of the run, in the message and in the chain.

    Why the chain is scrubbed too: a traceback prints the cause and the context of an error, and a provider that
    wraps its own error would carry the key in the cause (FR-018).
    """
    if credential is None:
        return error
    for current in _error_chain(error):
        try:
            current.args = (credential.scrub(str(current)),)
        except Exception:  # noqa: BLE001 - an error whose arguments cannot be set is replaced by the refusal below
            continue
        # A refusal of the family carries its detail in an attribute, and that attribute is read by the caller.
        detail = getattr(current, "detail", None)
        if isinstance(detail, str):
            try:
                current.detail = credential.scrub(detail)
            except Exception:  # noqa: BLE001 - the attribute is read only when the error could be set
                continue
    if credential.text and credential.text in str(error):
        # The error keeps the key in a text that the generic path cannot reach, so it is replaced by a refusal.
        return ProviderCallFailed(credential.scrub(str(error)))
    return error


class ProviderAdapter(ABC):
    """The interface every provider adapter implements.

    The adapter is built for one run and carries the credential of that run. It never reads the credential from the
    environment and never writes it there (FR-007).

    Why the credential lives in the adapter: the adapter is the boundary where the key is still alive, and the
    error of the provider is scrubbed there, before the error leaves (FR-018).
    """

    provider: str

    def __init__(self, provider: str, api_key: str | None = None) -> None:
        self.provider = provider
        # The credential is absent when the adapter has no key of a run, and the scrub then covers only the shapes
        # of the keys that the repository knows.
        self._credential = _Credential(api_key) if api_key else None

    @abstractmethod
    def complete(self, request: ProviderRequest) -> ProviderResponse:
        """One call of the provider, with the answer and the tokens it counted."""

    @abstractmethod
    def chat_model(self, model_id: str) -> BaseChatModel:
        """The chat model of this run for the given model, with the credential of the run inside it."""

    def scrub(self, text: str) -> str:
        """The text without the credential of the run."""
        if self._credential is None:
            return redact(text)
        return self._credential.scrub(text)

    def _scrub_error(self, error: BaseException) -> BaseException:
        """The error of the provider without the credential of the run (FR-018)."""
        return _scrubbed_error(error, self._credential)


def _is_link_local(host: str) -> bool:
    """True when the host is an address of the link-local range.

    The link-local range is where the metadata of a cloud machine lives, so a request that goes there reads the
    credentials of the machine instead of the answer of the provider (FR-017).
    """
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_link_local


def _is_loopback(host: str) -> bool:
    """True when the host is the loopback of the machine, by address or by name."""
    if host.lower() == "localhost":
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_loopback


def endpoint_verdict(provider: str, endpoint: str, *, public_mode: bool = True) -> EndpointVerdict | None:
    """The verdict of the check of an endpoint, or None when the endpoint is one the server may call.

    The function is pure: it reads the text of the endpoint and the flag of the mode and returns a verdict. It
    resolves no name and opens no connection, so the check is proved by a test and not by a network (FR-017).

    The verdict carries a code and a message: the code is what a caller decides with, and the message is what a
    visitor reads. The rules are named so that the refusal can be read: a link-local address, a loopback address, a
    scheme that is not https, and an endpoint the provider does not publish.
    """
    parts = urlsplit(endpoint)
    host = (parts.hostname or "").lower()

    if not parts.scheme or not host:
        return EndpointVerdict(ENDPOINT_NOT_A_URL, f"the endpoint '{endpoint}' is not a URL with a host")

    if public_mode:
        if _is_link_local(host):
            return EndpointVerdict(
                ENDPOINT_LINK_LOCAL,
                f"the endpoint '{endpoint}' points to the link-local address {host}, "
                f"which the public demo refuses because it reaches the machine itself",
            )
        if _is_loopback(host):
            return EndpointVerdict(
                ENDPOINT_LOOPBACK,
                f"the endpoint '{endpoint}' points to the loopback address {host}, "
                f"which the public demo refuses because it reaches the machine itself",
            )

    published = ALLOWED_ENDPOINTS.get(provider, ())
    if not published:
        return EndpointVerdict(
            ENDPOINT_UNKNOWN_PROVIDER,
            f"the provider '{provider}' has no published endpoint that the server may call",
        )
    # A provider that publishes https endpoints only accepts https: the key of the visitor travels in the
    # request and must not travel in the clear.
    if any(item.startswith("https://") for item in published) and parts.scheme != "https":
        return EndpointVerdict(
            ENDPOINT_NOT_HTTPS,
            f"the endpoint '{endpoint}' is not https, and the provider '{provider}' publishes only https endpoints",
        )

    if endpoint.rstrip("/") not in {item.rstrip("/") for item in published}:
        return EndpointVerdict(
            ENDPOINT_NOT_PUBLISHED,
            f"the endpoint '{endpoint}' is not an allowed endpoint of the provider '{provider}', "
            f"whose published endpoints are: {', '.join(published)}",
        )
    return None


def endpoint_refusal(provider: str, endpoint: str, *, public_mode: bool = True) -> str | None:
    """Why the endpoint is refused, or None when the endpoint is one the server may call.

    The function is pure: it reads the text of the endpoint and the flag of the mode and returns a reason. It
    resolves no name and opens no connection, so the check is proved by a test and not by a network (FR-017).

    Why the message and not the verdict: a caller that only shows the reason to a visitor reads the message, and
    the code of the rule is carried by `endpoint_verdict` and by the refusal itself.
    """
    verdict = endpoint_verdict(provider, endpoint, public_mode=public_mode)
    return None if verdict is None else verdict.message


def validate_endpoint(provider: str, endpoint: str, *, public_mode: bool = True) -> str:
    """The endpoint when the server may call it, and a refusal that names the reason when it may not.

    The endpoint is compared with the published endpoints of the provider, so a path that a visitor adds to a
    known host is refused as well: the server calls what the provider publishes and nothing else (FR-017).
    """
    if provider not in ALLOWED_ENDPOINTS:
        raise UnknownProvider(
            f"the provider '{provider}' has no published endpoint that the server may call"
        )
    verdict = endpoint_verdict(provider, endpoint, public_mode=public_mode)
    if verdict is not None:
        raise EndpointRefused(verdict.message, verdict.code)
    return endpoint


class LangChainProviderAdapter(ProviderAdapter):
    """The adapter of a real provider, built for one run with the credential of that run.

    The credential goes into the constructor of the chat model and nowhere else: the process environment and the
    global settings of the configuration are never touched, so the key of one visitor cannot reach the run of
    another (FR-007). The endpoint was checked when the adapter was built (FR-017).
    """

    def __init__(self, provider: str, api_key: str, *, endpoint: str | None = None, public_mode: bool = True) -> None:
        super().__init__(provider, api_key)
        self._endpoint = endpoint
        self._public_mode = public_mode

    def __repr__(self) -> str:
        """The adapter without the credential, because a representation ends up in the logs."""
        return f"LangChainProviderAdapter(provider={self.provider!r}, endpoint={self._endpoint!r})"

    def chat_model(self, model_id: str) -> BaseChatModel:
        """The chat model of this run, built with the credential in its constructor."""
        from langchain.chat_models import init_chat_model

        endpoint = self._endpoint
        if endpoint is not None:
            endpoint = validate_endpoint(self.provider, endpoint, public_mode=self._public_mode)
        try:
            options: dict[str, Any] = {"api_key": self._credential.text if self._credential else ""}
            if endpoint is not None:
                options["base_url"] = endpoint
            return init_chat_model(f"{self.provider}:{model_id}", **options)
        except Exception as error:
            # The key is handed to the client of the provider, so an error of the client may carry it (FR-018).
            raise self._scrub_error(error) from None

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        """One call of the provider, with the tokens it counted.

        The usage of the answer is what the provider reported. A provider that reports none reports zero, and the
        report of the run says so (FR-010).
        """
        try:
            model = self.chat_model(request.model_id)
            if request.tools:
                model = model.bind_tools(list(request.tools))
            answer: AIMessage = model.invoke(_as_messages(request.messages))  # type: ignore[assignment]
        except Exception as error:
            # The provider answered with an error, and the error may carry the key of the run (FR-018, SC-001).
            raise self._scrub_error(error) from None
        usage = answer.usage_metadata or {}
        return ProviderResponse(
            content=str(answer.content),
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
            model_id=request.model_id,
        )


def _as_messages(messages: Sequence[Mapping[str, str]]) -> list[BaseMessage]:
    """The messages of a request as the messages of LangChain.

    The adapter does not build the prompt of the agent: it carries what the run decided to say, and the shape of
    the message is the one of the core.
    """
    built: list[BaseMessage] = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        if role == "system":
            built.append(SystemMessage(content=content))
        elif role == "assistant":
            built.append(AIMessage(content=content))
        else:
            built.append(HumanMessage(content=content))
    return built


@dataclass(frozen=True)
class _ScriptedAnswer:
    """One scripted answer of the fake adapter: the text, the tokens or the exception to raise."""

    content: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    error: BaseException | None = None


class _ScriptedChatModel(BaseChatModel):
    """The chat model of the fake adapter: it replays the script of the adapter, one answer per call.

    It is private to the module because it is the machinery of the fake and not a thing the rest of the product
    may build. The script is a private attribute and not a field, because the field would be copied by the
    validation of the model and the adapter would hand out a different list than the one the test filled.

    The credential of the run travels with the model, so an error that the script raises is scrubbed exactly like
    the error of a real provider (FR-018).
    """

    model_id: str = "fake-model"

    _script: list[_ScriptedAnswer] = PrivateAttr(default_factory=list)
    _credential: Any = PrivateAttr(default=None)

    @property
    def _llm_type(self) -> str:
        """The name of the model in the traces, so the fake is never mistaken for a real provider."""
        return "ledgerlens-fake"

    def _generate(
        self,
        messages: list[Any],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        if not self._script:
            raise RuntimeError("the fake adapter has no scripted answer left for this call")
        answer = self._script.pop(0)
        if answer.error is not None:
            raise _scrubbed_error(answer.error, self._credential) from None
        message = AIMessage(
            content=answer.content,
            usage_metadata={
                "input_tokens": answer.input_tokens,
                "output_tokens": answer.output_tokens,
                "total_tokens": answer.input_tokens + answer.output_tokens,
            },
        )
        return ChatResult(generations=[ChatGeneration(message=message)])

    def bind_tools(self, tools: Any, **kwargs: Any) -> _ScriptedChatModel:  # type: ignore[override]
        """The same model: the script does not change when the tools are bound."""
        return self


class FakeProviderAdapter(ProviderAdapter):
    """The adapter of the tests: it answers what the test tells it to answer and never opens a socket.

    The script is a queue of answers. A test adds the answers it wants, in the order it wants them, and the
    adapter hands them out one per call. An answer may carry the exception to raise, which is how a test proves
    that a provider failure is handled without a network (FR-018).

    The fake holds the credential of the run when the test gives it one, and it scrubs that credential out of the
    error it raises, exactly like the real adapter does. The adversarial test of the key therefore exists without a
    network and without a key (FR-018, SC-001).
    """

    def __init__(self, provider: str = "fake", api_key: str | None = None) -> None:
        super().__init__(provider, api_key)
        self.script: list[_ScriptedAnswer] = []
        self.calls: list[ProviderRequest] = []

    def script_answer(
        self,
        content: str = "",
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> FakeProviderAdapter:
        """Adds an answer to the script and returns the adapter, so the calls can be chained."""
        self.script.append(
            _ScriptedAnswer(content=content, input_tokens=input_tokens, output_tokens=output_tokens)
        )
        return self

    def script_failure(self, error: BaseException) -> FakeProviderAdapter:
        """Adds the exception to raise on the next call and returns the adapter."""
        self.script.append(_ScriptedAnswer(error=error))
        return self

    def chat_model(self, model_id: str) -> BaseChatModel:
        """The chat model that replays the script of the adapter."""
        model = _ScriptedChatModel(model_id=model_id)
        model._script = self.script
        model._credential = self._credential
        return model

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        """One call of the fake, which takes the next answer of the script."""
        self.calls.append(request)
        if not self.script:
            raise RuntimeError("the fake adapter has no scripted answer left for this call")
        answer = self.script.pop(0)
        if answer.error is not None:
            # The scripted error stands for the error of a provider, and it leaves the adapter scrubbed (FR-018).
            raise self._scrub_error(answer.error) from None
        return ProviderResponse(
            content=answer.content,
            input_tokens=answer.input_tokens,
            output_tokens=answer.output_tokens,
            model_id=request.model_id,
        )


def build_adapter(
    provider: str,
    api_key: str,
    *,
    endpoint: str | None = None,
    public_mode: bool = True,
) -> ProviderAdapter:
    """The adapter of one run, with the endpoint checked before anything is built.

    The adapter is built per run and the credential goes into it, so two visitors on two providers never share a
    client (FR-007). The endpoint is checked here, so an endpoint the server may not call is refused before the
    key of the visitor is used anywhere (FR-017).
    """
    if endpoint is not None:
        endpoint = validate_endpoint(provider, endpoint, public_mode=public_mode)
    log.debug("adapter built for the provider %s", provider)
    return LangChainProviderAdapter(provider, api_key, endpoint=endpoint, public_mode=public_mode)
