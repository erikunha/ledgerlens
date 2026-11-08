"""Configuration: the offline switch picks the scripted model, local embeddings and fixture HTTP.

Keys never appear in `repr`, logs or errors.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from ledgerlens import config
from ledgerlens.config import ConfigError, Settings
from ledgerlens.embeddings import FastEmbedEmbeddings
from ledgerlens.offline import ScriptedChatModel

SECRET = "fake-value-for-redaction-tests"


def _never_called(*args: object, **kwargs: object) -> None:
    raise AssertionError("init_chat_model must not be called in offline mode")


# --- offline switch ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_offline_true_values(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("LEDGERLENS_OFFLINE", value)
    assert config.offline() is True


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off", "anything-else"])
def test_offline_false_values(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("LEDGERLENS_OFFLINE", value)
    assert config.offline() is False


def test_offline_unset_is_online(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LEDGERLENS_OFFLINE")
    assert config.offline() is False


def test_offline_selects_scripted_model_and_never_calls_init_chat_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "init_chat_model", _never_called)
    monkeypatch.setenv("LEDGERLENS_MODEL", "openai:gpt-4o-mini")  # ignored offline
    model = config.get_chat_model()
    assert isinstance(model, ScriptedChatModel)


def test_offline_model_replays_the_given_script() -> None:
    model = config.get_chat_model(script=["first", "second"])
    assert model.invoke("a").content == "first"
    assert model.invoke("b").content == "second"


def test_offline_selects_fastembed_even_when_openai_is_requested(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEDGERLENS_EMBEDDINGS", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    embeddings = config.get_embeddings()
    assert isinstance(embeddings, FastEmbedEmbeddings)


def test_offline_embeddings_do_not_load_a_model_at_construction() -> None:
    embeddings = config.get_embeddings()
    assert isinstance(embeddings, FastEmbedEmbeddings)
    assert embeddings.is_loaded is False


def test_http_mode_is_fixtures_offline_and_live_online(monkeypatch: pytest.MonkeyPatch) -> None:
    assert config.http_mode() == "fixtures"
    monkeypatch.setenv("LEDGERLENS_OFFLINE", "0")
    assert config.http_mode() == "live"


# --- online providers -------------------------------------------------------------------------


def test_online_chat_model_goes_through_init_chat_model(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[tuple, dict]] = []
    sentinel = object()

    def fake_init(*args: object, **kwargs: object) -> object:
        calls.append((args, kwargs))
        return sentinel

    monkeypatch.setattr(config, "init_chat_model", fake_init)
    monkeypatch.setenv("LEDGERLENS_OFFLINE", "0")
    monkeypatch.setenv("LEDGERLENS_MODEL", "openai:gpt-test")
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)

    assert config.get_chat_model(temperature=0) is sentinel
    ((args, kwargs),) = calls
    assert args == ("openai:gpt-test",)
    assert kwargs["temperature"] == 0
    assert kwargs["api_key"] == SECRET


@pytest.mark.parametrize("name", ["gpt-4.1-mini", "o4-mini"])
def test_an_openai_model_named_without_provider_still_gets_the_key(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    # The .env does not go to os.environ: without passing the key on, ChatOpenAI would have no authentication.
    calls: list[tuple[tuple, dict]] = []
    monkeypatch.setattr(config, "init_chat_model", lambda *a, **k: calls.append((a, k)) or object())
    monkeypatch.setenv("LEDGERLENS_OFFLINE", "0")
    monkeypatch.setenv("LEDGERLENS_MODEL", name)
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)

    config.get_chat_model()
    ((args, kwargs),) = calls
    assert args == (f"openai:{name}",)
    assert kwargs["api_key"] == SECRET


def test_online_chat_model_without_a_model_name_is_a_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEDGERLENS_OFFLINE", "0")
    with pytest.raises(ConfigError, match="LEDGERLENS_MODEL"):
        config.get_chat_model()


def test_online_openai_embeddings_need_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEDGERLENS_OFFLINE", "0")
    monkeypatch.setenv("LEDGERLENS_EMBEDDINGS", "openai")
    with pytest.raises(ConfigError, match="OPENAI_API_KEY"):
        config.get_embeddings()


def test_online_openai_embeddings_with_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from langchain_openai import OpenAIEmbeddings

    monkeypatch.setenv("LEDGERLENS_OFFLINE", "0")
    monkeypatch.setenv("LEDGERLENS_EMBEDDINGS", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    assert isinstance(config.get_embeddings(), OpenAIEmbeddings)


def test_online_default_embeddings_are_fastembed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEDGERLENS_OFFLINE", "0")
    assert isinstance(config.get_embeddings(), FastEmbedEmbeddings)


def test_unknown_embeddings_value_is_a_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEDGERLENS_EMBEDDINGS", "word2vec")
    with pytest.raises(ConfigError, match="fastembed"):
        config.get_settings()


# --- settings sources -------------------------------------------------------------------------


def test_env_file_supplies_values_and_the_environment_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env_file = tmp_path / "test.env"
    env_file.write_text("LEDGERLENS_MODEL=openai:from-file\nLANGSMITH_PROJECT=from-file\n", encoding="utf-8")
    monkeypatch.setenv("LEDGERLENS_ENV_FILE", str(env_file))
    monkeypatch.setenv("LANGSMITH_PROJECT", "from-env")
    settings = config.get_settings()
    assert settings.model == "openai:from-file"
    assert settings.langsmith_project == "from-env"


def test_missing_env_file_is_fine() -> None:
    settings = config.get_settings()
    assert settings.model is None
    assert settings.openai_api_key is None


def test_runtime_dir_comes_from_the_environment(offline_environment: Path) -> None:
    assert config.get_settings().runtime_dir == offline_environment


def test_default_runtime_dir_is_under_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LEDGERLENS_RUNTIME_DIR")
    assert config.get_settings().runtime_dir.parts[-2:] == ("data", "runtime")


def test_ledger_db_and_index_dir_default_to_the_data_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LEDGERLENS_LEDGER_DB", raising=False)
    monkeypatch.delenv("LEDGERLENS_INDEX_DIR", raising=False)
    settings = config.get_settings()
    assert settings.ledger_db == config.PROJECT_ROOT / "data" / "ledger.db"
    assert settings.index_dir == config.PROJECT_ROOT / "data" / "index"


def test_ledger_db_and_index_dir_come_from_the_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LEDGERLENS_LEDGER_DB", str(tmp_path / "other.db"))
    monkeypatch.setenv("LEDGERLENS_INDEX_DIR", str(tmp_path / "idx"))
    settings = config.get_settings()
    assert settings.ledger_db == tmp_path / "other.db"
    assert settings.index_dir == tmp_path / "idx"


def test_settings_are_immutable() -> None:
    settings = config.get_settings()
    with pytest.raises(Exception):  # noqa: B017  pydantic raises ValidationError for a frozen model
        settings.offline = False  # type: ignore[misc]


# --- keys stay out of repr, logs and errors ---------------------------------------------------


@pytest.fixture
def with_keys(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    monkeypatch.setenv("LANGSMITH_API_KEY", SECRET + "-ls")
    return config.get_settings()


def test_keys_are_not_in_repr_or_str(with_keys: Settings) -> None:
    for text in (repr(with_keys), str(with_keys), with_keys.model_dump_json(), str(with_keys.model_dump())):
        assert SECRET not in text


def test_keys_are_readable_only_through_the_secret_accessor(with_keys: Settings) -> None:
    assert with_keys.openai_api_key is not None
    assert with_keys.openai_api_key.get_secret_value() == SECRET


def test_keys_are_not_logged(caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    monkeypatch.setenv("LEDGERLENS_OFFLINE", "0")
    monkeypatch.setenv("LEDGERLENS_MODEL", "openai:gpt-test")
    monkeypatch.setattr(config, "init_chat_model", lambda *a, **k: object())
    with caplog.at_level(logging.DEBUG):
        config.get_chat_model()
        config.get_embeddings()
    assert caplog.records, "config should log what it selected"
    assert SECRET not in caplog.text


def test_keys_are_not_in_errors_raised_by_the_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_init(*args: object, **kwargs: object) -> object:
        raise ValueError(f"401 Unauthorized for key {SECRET}")

    monkeypatch.setattr(config, "init_chat_model", failing_init)
    monkeypatch.setenv("LEDGERLENS_OFFLINE", "0")
    monkeypatch.setenv("LEDGERLENS_MODEL", "openai:gpt-test")
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    with pytest.raises(ConfigError) as info:
        config.get_chat_model()
    assert SECRET not in str(info.value)
    assert info.value.__cause__ is None
    assert "[redacted]" in str(info.value)
