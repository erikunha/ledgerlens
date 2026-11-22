"""The measurement of the budget of the published set: the size of the payload against the promise of the repository.

What they prove, and why: (a) the published set of the repository is inside the budget that the specification declares
(SC-004 of `specs/001-r1-public-replay/spec.md`: 400 kilobytes of compressed payload per scenario), because a promise
that nobody measures is a promise that nobody keeps; (b) the number of events of the recording is the number the
manifest of the scenario declares, because that count is what the visitor sees in the timeline; (c) the command exits
with 1 and names the budget when the budget is tightened, because a check that cannot fail is not a check.

Why the measurement matters at all: the site is a static export, so what the visitor downloads is exactly what the
repository publishes in `site/replay/`, and the size of that payload is a promise of the specification.

Everything here runs offline, with no key and with no network. The script reads the published artifacts of the
repository and writes nothing.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "measure_replay_budget.py"
SPEC = ROOT / "specs" / "001-r1-public-replay" / "spec.md"
PUBLISHED = ROOT / "site" / "replay"

__all__ = [
    "test_the_measurement_exits_with_one_when_the_budget_is_tightened",
    "test_the_number_of_events_of_the_recording_is_the_number_the_manifest_declares",
    "test_the_published_set_is_inside_the_budget_the_specification_declares",
]


def _load_script(name: str, path: Path):
    """A script of the repository, loaded as a module so the test can drive its command line."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


measure_replay_budget = _load_script("measure_replay_budget", SCRIPT)


def _line_of_the_specification() -> str:
    """The line of the specification that declares the budget of the payload of one scenario."""
    for line in SPEC.read_text(encoding="utf-8").splitlines():
        if "SC-004" in line:
            return line
    raise AssertionError("the specification does not declare SC-004")


def test_the_published_set_is_inside_the_budget_the_specification_declares(
    capsys: pytest.CaptureFixture[str],
):
    """The published set of the repository is inside the budget that the specification declares.

    Why the budget is read from the specification and not from the script: a script that declares its own budget
    proves nothing, the promise has to come from the document that states it.
    """
    assert measure_replay_budget.BUDGET_BYTES == 400 * 1024
    assert "SC-004" in measure_replay_budget.BUDGET_SOURCE
    assert "400 kilobytes" in _line_of_the_specification()

    files, scenarios, problems = measure_replay_budget.measure(PUBLISHED)

    assert problems == []
    assert files
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert scenario.slug == "s01"
    assert 0 < scenario.compressed < measure_replay_budget.BUDGET_BYTES

    assert measure_replay_budget.main(["--site", str(PUBLISHED)]) == 0
    assert capsys.readouterr().err == ""


def test_the_number_of_events_of_the_recording_is_the_number_the_manifest_declares():
    """The recording holds the 57 events its manifest declares, and the measurement counts them."""
    _files, scenarios, problems = measure_replay_budget.measure(PUBLISHED)

    assert problems == []
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert scenario.events == 57
    assert scenario.declared_events == 57


def test_the_measurement_exits_with_one_when_the_budget_is_tightened(
    capsys: pytest.CaptureFixture[str],
):
    """A budget of 1000 bytes is broken by the published set, and the command says so and exits with 1."""
    assert measure_replay_budget.main(["--site", str(PUBLISHED), "--limit", "1000"]) == 1

    refusal = capsys.readouterr().err
    assert "budget" in refusal
    assert "1000" in refusal
