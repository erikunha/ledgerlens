"""The settings of the sandbox: the two lives of a branch and the limits of its resources, read from the environment.

Why the test lives here: the settings of the sandbox belong to the branch layer, and this suite is the one that
guards them.

The two limits of the resources of a branch are settings of the deployment like the two lives of a branch, and the
layer reads them the way it reads the lives: as arguments of its constructor. So the suite guards two things: the
settings carry the names and the defaults of the decision, and the layer takes the limits it is given.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ledgerlens.config import get_settings
from ledgerlens.sandbox.branch import MAX_COMMITTED_MUTATIONS, MAX_EVENTS, BranchLayer

ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"
# The names of the two settings of the limits, as the configuration reads them.
MUTATIONS_ENV = "LEDGERLENS_SANDBOX_MAX_COMMITTED_MUTATIONS"
EVENTS_ENV = "LEDGERLENS_SANDBOX_MAX_EVENTS"


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


# --- the limits of the resources of a branch -------------------------------------------------------------------


def test_the_limit_of_the_committed_mutations_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """The mutations a branch may commit are a setting of the deployment, not a number of the code."""
    monkeypatch.setenv(MUTATIONS_ENV, "3")
    assert get_settings().sandbox_max_committed_mutations == 3


def test_the_limit_of_the_events_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """The events of the log of a branch are a setting of the deployment, not a number of the code."""
    monkeypatch.setenv(EVENTS_ENV, "7")
    assert get_settings().sandbox_max_events == 7


def test_the_defaults_are_the_limits_of_today() -> None:
    """A deployment that declares nothing keeps the limits of today."""
    settings = get_settings()
    assert settings.sandbox_max_committed_mutations == 20
    assert settings.sandbox_max_events == 200


def test_the_defaults_of_the_settings_are_the_defaults_of_the_branch_layer() -> None:
    """The settings and the layer carry the same defaults, so a deployment declares nothing and changes nothing.

    Why the case exists: the number is written in two places, the settings of the configuration and the defaults of
    the layer, and the two places have to agree or a deployment that declares nothing would get two different sets
    of limits.
    """
    settings = get_settings()
    assert settings.sandbox_max_committed_mutations == MAX_COMMITTED_MUTATIONS
    assert settings.sandbox_max_events == MAX_EVENTS


def test_the_env_example_names_the_two_limits_without_a_value() -> None:
    """The example file names the two limits and carries no value, so a deployment declares what it wants."""
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert f"{MUTATIONS_ENV}=" in text
    assert f"{EVENTS_ENV}=" in text
    for line in text.splitlines():
        if line.startswith(("LEDGERLENS_SANDBOX_MAX_COMMITTED_MUTATIONS", "LEDGERLENS_SANDBOX_MAX_EVENTS")):
            assert line.endswith("="), "the example file must not carry a value"


def test_the_settings_of_the_configuration_reach_the_limits_of_the_branch(
    monkeypatch: pytest.MonkeyPatch, store, base_resolver, clock
) -> None:
    """The limits of the branch are the limits of the configuration, and the layer takes them (FR-025).

    Why the case exists: the settings of the configuration have to reach the domain without the domain reading the
    environment, and the way they reach it is the constructor of the layer, the way the two lives of a branch reach
    it. The layer never imports the configuration, and the case proves that the values of the settings are the
    values of the limits of the branch.
    """
    monkeypatch.setenv(MUTATIONS_ENV, "3")
    monkeypatch.setenv(EVENTS_ENV, "9")
    settings = get_settings()
    layer = BranchLayer(
        store,
        base_resolver,
        max_committed_mutations=settings.sandbox_max_committed_mutations,
        max_events=settings.sandbox_max_events,
        clock=clock,
    )

    assert layer.max_committed_mutations == settings.sandbox_max_committed_mutations == 3
    assert layer.max_events == settings.sandbox_max_events == 9


def test_a_layer_that_declares_nothing_keeps_the_limits_of_today(store, base_resolver, clock) -> None:
    """The defaults of the layer are the limits of today, so a deployment that declares nothing changes nothing."""
    layer = BranchLayer(store, base_resolver, clock=clock)

    assert layer.max_committed_mutations == MAX_COMMITTED_MUTATIONS
    assert layer.max_events == MAX_EVENTS
