"""Configuration: reads the environment and `.env`, decides offline mode and builds the model and embeddings.

Why it exists: the rest of the project asks here "am I offline?" and "which model do I use?", so switching
providers or running with no key needs no change to any tool.

Offline mode (`LEDGERLENS_OFFLINE=1`) swaps the providers and nothing else: a scripted chat model, fastembed
embeddings and recorded HTTP responses. Online mode builds the model named in `LEDGERLENS_MODEL` with
`init_chat_model`; no provider is named in the code.

Keys live in `SecretStr`, so `repr`, logs and `model_dump` show a mask. Errors coming from a provider are
raised again with every known key replaced by `[redacted]`.

Configurable paths: the ledger database (`LEDGERLENS_LEDGER_DB`) and the vector index folder
(`LEDGERLENS_INDEX_DIR`). Both default to `data/`.

The sandbox store: `LEDGERLENS_SANDBOX_DATABASE_URL` names the database of the branches. It is empty by default, and
an empty url means the file backed store.

The limits of the sandbox: `LEDGERLENS_SANDBOX_SESSION_BRANCH_CAP` is the number of live branches one session may
hold, `LEDGERLENS_SANDBOX_RATE_LIMIT_REQUESTS` is the number of requests one session may make in the window, and
`LEDGERLENS_SANDBOX_RATE_LIMIT_WINDOW_SECONDS` is the length of that window (ADR-047).

The limits of one branch: `LEDGERLENS_SANDBOX_MAX_COMMITTED_MUTATIONS` is the number of the mutations a branch may
commit and `LEDGERLENS_SANDBOX_MAX_EVENTS` is the number of the events its log may hold. Their defaults are the limits
of the branch layer, so a deployment that declares nothing keeps the limits of today.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from dotenv import dotenv_values
from langchain.chat_models import init_chat_model
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, ConfigDict, SecretStr

from ledgerlens.embeddings import FastEmbedEmbeddings, openai_embeddings
from ledgerlens.offline import ScriptedChatModel, ScriptItem

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EMBEDDING_CHOICES = ("fastembed", "openai")
_TRUE = {"1", "true", "yes", "on"}


class ConfigError(RuntimeError):
    """The configuration cannot do what was asked. The message never contains a key."""


class Settings(BaseModel):
    """Everything read from the environment. Immutable; keys are masked in `repr` and dumps."""

    model_config = ConfigDict(frozen=True)

    offline: bool = False
    model: str | None = None
    embeddings: Literal["fastembed", "openai"] = "fastembed"
    openai_api_key: SecretStr | None = None
    langsmith_api_key: SecretStr | None = None
    langsmith_project: str | None = None
    langsmith_tracing: bool = False
    ledger_api_url: str | None = None
    runtime_dir: Path = PROJECT_ROOT / "data" / "runtime"
    ledger_db: Path = PROJECT_ROOT / "data" / "ledger.db"
    index_dir: Path = PROJECT_ROOT / "data" / "index"
    # The life of a sandbox branch: one hour of idleness and four hours in absolute terms. The folder of the file
    # backed store is `runtime_dir / "sandbox"`, so it stays out of git with the rest of the runtime material.
    sandbox_branch_idle_ttl_seconds: int = 3600
    sandbox_branch_absolute_ttl_seconds: int = 14400
    # The url of the database of the sandbox store. Empty means the file backed store, which is the one the fast
    # unit tests use. The url points at the container of `docker-compose.yml`.
    sandbox_database_url: str | None = None
    # The cap of the LIVE branches of one session. A branch that is already dead does not count, and a fork of a
    # scenario the session already holds creates no branch, so it is never refused by the cap (ADR-047).
    sandbox_session_branch_cap: int = 5
    # The rate of the requests of one session, in a sliding window. The limit is per process: a deployment with more
    # than one worker allows that many times the quota (ADR-047).
    sandbox_rate_limit_requests: int = 120
    sandbox_rate_limit_window_seconds: int = 60
    # The resources of one branch (FR-025). The mutations of a branch are the ones that were committed, and an undone
    # mutation stays counted, because the revision goes back and the count of the committed mutations does not. The
    # events of a branch are counted against its log, and the marker of an undo is an event of that log.
    # The two defaults are the limits of the branch layer, so a deployment that declares nothing keeps them.
    sandbox_max_committed_mutations: int = 20
    sandbox_max_events: int = 200
    # The origins of the browser that may call the backend from another origin, with the cookie of the session. The
    # list is empty by default: a deployment that declares no origin installs no CORS at all, and the backend
    # answers exactly as it answers today (ADR-040).
    cors_origins: tuple[str, ...] = ()

    def secrets(self) -> list[str]:
        """The key values held, for redaction. Never log this list."""
        values = (self.openai_api_key, self.langsmith_api_key)
        return [v.get_secret_value() for v in values if v is not None and v.get_secret_value()]


def _flag(value: str | None) -> bool:
    return (value or "").strip().lower() in _TRUE


def _text(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _secret(value: str | None) -> SecretStr | None:
    value = _text(value)
    return SecretStr(value) if value else None


def _origins(value: str | None) -> tuple[str, ...]:
    """The origins of the CORS, read from a comma separated list of exact origins.

    Why the wildcard is refused: a wildcard with credentials is illegal in the Fetch specification, and it would let
    any site of the internet drive the API with the session of the visitor (ADR-040).
    """
    origins = tuple(part.strip() for part in (value or "").split(",") if part.strip())
    if any("*" in origin for origin in origins):
        raise ConfigError(
            "LEDGERLENS_CORS_ORIGINS must name the exact origins of the browser, and never the wildcard, because a "
            "wildcard with credentials is illegal and would let any site drive the API with the session of the visitor"
        )
    return origins


def _redact(text: str, settings: Settings) -> str:
    for secret in settings.secrets():
        text = text.replace(secret, "[redacted]")
    return text


def get_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Read settings. Process environment wins over the `.env` file.

    The file is `LEDGERLENS_ENV_FILE` when set, else `.env` in the project root. A missing file is
    fine. `env` replaces the process environment (used by tests of this module).
    """
    environ = dict(os.environ if env is None else env)
    env_file = Path(environ.get("LEDGERLENS_ENV_FILE") or PROJECT_ROOT / ".env")
    values: dict[str, str | None] = dict(dotenv_values(env_file)) if env_file.is_file() else {}
    values.update(environ)

    embeddings = (_text(values.get("LEDGERLENS_EMBEDDINGS")) or "fastembed").lower()
    if embeddings not in EMBEDDING_CHOICES:
        raise ConfigError(f"LEDGERLENS_EMBEDDINGS must be one of {', '.join(EMBEDDING_CHOICES)}")

    runtime_dir = _text(values.get("LEDGERLENS_RUNTIME_DIR"))
    ledger_db = _text(values.get("LEDGERLENS_LEDGER_DB"))
    index_dir = _text(values.get("LEDGERLENS_INDEX_DIR"))
    idle_ttl = _text(values.get("LEDGERLENS_SANDBOX_BRANCH_IDLE_TTL_SECONDS"))
    absolute_ttl = _text(values.get("LEDGERLENS_SANDBOX_BRANCH_ABSOLUTE_TTL_SECONDS"))
    sandbox_database_url = _text(values.get("LEDGERLENS_SANDBOX_DATABASE_URL"))
    session_branch_cap = _text(values.get("LEDGERLENS_SANDBOX_SESSION_BRANCH_CAP"))
    rate_limit_requests = _text(values.get("LEDGERLENS_SANDBOX_RATE_LIMIT_REQUESTS"))
    rate_limit_window = _text(values.get("LEDGERLENS_SANDBOX_RATE_LIMIT_WINDOW_SECONDS"))
    max_committed_mutations = _text(values.get("LEDGERLENS_SANDBOX_MAX_COMMITTED_MUTATIONS"))
    max_events = _text(values.get("LEDGERLENS_SANDBOX_MAX_EVENTS"))
    cors_origins = _text(values.get("LEDGERLENS_CORS_ORIGINS"))
    settings = Settings(
        offline=_flag(values.get("LEDGERLENS_OFFLINE")),
        model=_text(values.get("LEDGERLENS_MODEL")),
        embeddings=embeddings,  # type: ignore[arg-type]
        openai_api_key=_secret(values.get("OPENAI_API_KEY")),
        langsmith_api_key=_secret(values.get("LANGSMITH_API_KEY")),
        langsmith_project=_text(values.get("LANGSMITH_PROJECT")),
        langsmith_tracing=_flag(values.get("LANGSMITH_TRACING")),
        ledger_api_url=_text(values.get("LEDGERLENS_LEDGER_API_URL")),
        # Only what came from the environment goes into the constructor; the rest keeps the model default.
        **({"runtime_dir": Path(runtime_dir)} if runtime_dir else {}),
        **({"ledger_db": Path(ledger_db)} if ledger_db else {}),
        **({"index_dir": Path(index_dir)} if index_dir else {}),
        **({"sandbox_branch_idle_ttl_seconds": int(idle_ttl)} if idle_ttl else {}),
        **({"sandbox_branch_absolute_ttl_seconds": int(absolute_ttl)} if absolute_ttl else {}),
        **({"sandbox_database_url": sandbox_database_url} if sandbox_database_url else {}),
        **({"sandbox_session_branch_cap": int(session_branch_cap)} if session_branch_cap else {}),
        **({"sandbox_rate_limit_requests": int(rate_limit_requests)} if rate_limit_requests else {}),
        **({"sandbox_rate_limit_window_seconds": int(rate_limit_window)} if rate_limit_window else {}),
        **({"sandbox_max_committed_mutations": int(max_committed_mutations)} if max_committed_mutations else {}),
        **({"sandbox_max_events": int(max_events)} if max_events else {}),
        **({"cors_origins": _origins(cors_origins)} if cors_origins else {}),
    )
    log.debug("settings loaded: %r", settings)
    return settings


def offline(settings: Settings | None = None) -> bool:
    """True when `LEDGERLENS_OFFLINE` is set to 1, true, yes or on."""
    return (settings or get_settings()).offline


def http_mode(settings: Settings | None = None) -> Literal["fixtures", "live"]:
    """Where HTTP tools get their answers: recorded fixtures offline, the network online."""
    return "fixtures" if offline(settings) else "live"


def get_chat_model(
    settings: Settings | None = None, *, script: list[ScriptItem] | None = None, **kwargs: Any
) -> BaseChatModel:
    """The chat model for the current mode.

    Offline: a `ScriptedChatModel` replaying `script` (empty by default). Online: the model named in
    `LEDGERLENS_MODEL` as `<provider>:<name>`, built by `init_chat_model` with `kwargs`.
    """
    settings = settings or get_settings()
    if settings.offline:
        log.debug("chat model: scripted (offline), %d scripted message(s)", len(script or []))
        return ScriptedChatModel(script=list(script or []))

    if not settings.model:
        raise ConfigError("LEDGERLENS_MODEL is not set; name the chat model as '<provider>:<model>'")
    model = _with_provider(settings.model)
    if settings.openai_api_key is not None and model.split(":", 1)[0] == "openai":
        kwargs.setdefault("api_key", settings.openai_api_key.get_secret_value())
    log.debug("chat model: %s (online)", model)
    try:
        return init_chat_model(model, **kwargs)
    except Exception as exc:
        raise ConfigError(f"could not build chat model '{model}': {_redact(str(exc), settings)}") from None


# Prefixes that init_chat_model assigns to OpenAI when the name comes with no provider.
_OPENAI_PREFIXES = ("gpt-", "o1", "o3", "o4", "chatgpt-")


def _with_provider(name: str) -> str:
    """Adds `openai:` to a name such as `gpt-4.1-mini`.

    Why: the key comes from `.env`, which does not go into `os.environ`. It is passed on only when the
    provider is known; with no prefix, the model would be built with no authentication.
    """
    if ":" in name or not name.startswith(_OPENAI_PREFIXES):
        return name
    return f"openai:{name}"


def model_profile(settings: Settings | None = None) -> str:
    """The name of the model with the provider that serves it, as the provenance of a recording states it.

    Why it exists: the recording of a real model names the model that produced it, and the name in the environment
    carries no provider when the provider is the one that everybody uses. The profile is empty when the environment
    names no model, because a profile that is invented is worse than a profile that is absent.
    """
    settings = settings or get_settings()
    name = (settings.model or "").strip()
    return _with_provider(name) if name else ""


def get_embeddings(settings: Settings | None = None) -> Embeddings:
    """The embeddings for the current mode: fastembed offline, `LEDGERLENS_EMBEDDINGS` online."""
    settings = settings or get_settings()
    if settings.offline or settings.embeddings == "fastembed":
        log.debug("embeddings: fastembed")
        return FastEmbedEmbeddings()
    if settings.openai_api_key is None:
        raise ConfigError("OPENAI_API_KEY is not set; it is required for LEDGERLENS_EMBEDDINGS=openai")
    log.debug("embeddings: openai")
    return openai_embeddings(api_key=settings.openai_api_key.get_secret_value())
