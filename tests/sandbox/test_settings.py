"""The settings of the sandbox: the two lives of a branch, read from the environment like the other paths.

Why the test lives here: the settings of the sandbox belong to the branch layer, and this suite is the one that
guards them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ledgerlens.config import get_settings

ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"


def test_the_idle_life_of_a_branch_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEDGERLENS_SANDBOX_BRANCH_IDLE_TTL_SECONDS", "99")
    assert get_settings().sandbox_branch_idle_ttl_seconds == 99


def test_the_absolute_life_of_a_branch_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEDGERLENS_SANDBOX_BRANCH_ABSOLUTE_TTL_SECONDS", "199")
    assert get_settings().sandbox_branch_absolute_ttl_seconds == 199


def test_the_defaults_are_one_hour_of_idleness_and_four_hours_in_absolute_terms() -> None:
    settings = get_settings()
    assert settings.sandbox_branch_idle_ttl_seconds == 3600
    assert settings.sandbox_branch_absolute_ttl_seconds == 14400


def test_the_env_example_names_the_two_settings_without_a_value() -> None:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "LEDGERLENS_SANDBOX_BRANCH_IDLE_TTL_SECONDS=" in text
    assert "LEDGERLENS_SANDBOX_BRANCH_ABSOLUTE_TTL_SECONDS=" in text
    for line in text.splitlines():
        if line.startswith("LEDGERLENS_SANDBOX_BRANCH_"):
            assert line.endswith("="), "the example file must not carry a value"
