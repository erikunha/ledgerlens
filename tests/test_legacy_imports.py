"""Smoke test for the legacy LangChain names the project demonstrates.

Fails when a release moves a name or when the installed versions drift from `uv.lock`.
"""

from __future__ import annotations

import importlib
import tomllib
import warnings
from importlib.metadata import version
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

PINNED = (
    "langchain",
    "langchain-core",
    "langchain-classic",
    "langchain-community",
    "langchain-openai",
    "langsmith",
    "faiss-cpu",
    "fastembed",
)

# (module, name): every legacy API the project demonstrates.
LEGACY_NAMES = (
    ("langchain_classic.agents", "initialize_agent"),
    ("langchain_classic.agents", "AgentType"),
    ("langchain_classic.agents", "AgentExecutor"),
    ("langchain_classic.agents", "create_openai_tools_agent"),
    ("langchain_classic.memory", "ConversationBufferMemory"),
    ("langchain_classic.memory", "ConversationSummaryBufferMemory"),
    ("langchain_classic.chains.router", "LLMRouterChain"),
    ("langchain_classic.chains.router", "MultiPromptChain"),
    ("langchain_core.runnables.history", "RunnableWithMessageHistory"),
    ("langchain_core.runnables", "chain"),
    ("langchain.chat_models", "init_chat_model"),
    ("langchain_community.vectorstores", "FAISS"),
)


def _locked_versions() -> dict[str, str]:
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    return {pkg["name"]: pkg["version"] for pkg in lock["package"]}


@pytest.mark.parametrize(("module", "name"), LEGACY_NAMES)
def test_legacy_name_imports(module: str, name: str) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mod = importlib.import_module(module)
    assert hasattr(mod, name), f"{module} no longer exports {name}"


@pytest.mark.parametrize("package", PINNED)
def test_installed_version_matches_lock(package: str) -> None:
    locked = _locked_versions()
    assert package in locked, f"{package} missing from uv.lock"
    assert version(package) == locked[package]


def test_classic_agent_names_do_not_come_from_langchain() -> None:
    """The legacy names must be imported from langchain_classic, not from langchain 1.x."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from langchain_classic.agents import AgentExecutor

    assert AgentExecutor.__module__.startswith("langchain_classic")
