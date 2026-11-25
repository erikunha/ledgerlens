"""The script of the laboratory: it refuses to run with a key in the environment, and the results carry the six fields.

What they guarantee, and why: (a) the script of the laboratory refuses to run with a key in the environment,
because the exercises run in the offline mode with the fake provider, so an attack never spends the money of
anybody, and a run with a key in the environment is a run that could spend it; (b) the result of every
exercise carries the six fields, because a result that misses one of them is a result a reader cannot check.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_adversarial_lab import run_lab


def test_the_script_refuses_to_run_with_a_key_in_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A run with a key in the environment is a run that could spend the money of somebody."""
    monkeypatch.setenv("OPENAI_API_KEY", "a-key-that-is-not-a-key")

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        run_lab(tmp_path)


def test_the_results_of_every_exercise_carry_the_six_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The surface, the boundary, the trace, the blocked actions, the open risk and the count."""
    for variable in ("OPENAI_API_KEY", "LANGSMITH_API_KEY", "LANGCHAIN_API_KEY"):
        monkeypatch.delenv(variable, raising=False)

    written = run_lab(tmp_path)

    assert written
    for path in written:
        result = json.loads(path.read_text(encoding="utf-8"))
        assert result["surface"]
        assert result["expected_boundary"]
        assert result["trace_ref"]
        assert result["blocked_actions"]
        assert result["open_risk"]
        assert result["unauthorized_actions"] == 0
