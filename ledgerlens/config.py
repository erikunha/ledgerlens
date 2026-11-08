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
