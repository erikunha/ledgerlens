"""The capture of a recording of a real model: what it refuses and what it writes.

What they guarantee, and why: (a) the capture refuses an offline machine and a machine without a key, because a
recording without a real model is the recording of the other catalog; (b) the whole catalog is left out of the
check of the tree and not only the folder of the scenario, because the script records the ten scenarios of the
catalog in one run and the bundle of the first one would otherwise block the second one; (c) the model of each
slot of the run is chosen by the task the slot does, and the recording names the model that wrote the answer.

Everything here runs with no key and with no network: the cases replace the settings and the check of the tree, so
no model is called and no file is written.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from ledgerlens.replay.capture import CaptureError

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "capture_live_replay.py"


def _load_script():
    """The script of the capture, loaded as a module so that the test can drive its command line."""
    spec = importlib.util.spec_from_file_location("capture_live_replay", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


capture_live_replay = _load_script()


class _StopHere(Exception):
    """The marker that stops the capture in the middle, so that no model is ever called."""


def _online_settings():
    """The settings of a machine that has a key, is not offline and declares a cascade of two models."""
    return SimpleNamespace(
        offline=False,
        openai_api_key=SimpleNamespace(get_secret_value=lambda: "sk-test-key-not-real"),
        model="gpt-4.1",
        model_cascade=("gpt-4.1-mini", "gpt-4.1"),
    )


def test_the_capture_refuses_an_offline_machine(monkeypatch: pytest.MonkeyPatch) -> None:
    """An offline machine runs the scripted model, and the label of the recording would be a lie."""
    monkeypatch.setattr(
        capture_live_replay,
        "get_settings",
        lambda: SimpleNamespace(offline=True, openai_api_key=None),
    )

    with pytest.raises(SystemExit) as refusal:
        capture_live_replay.capture("S01", ROOT / "data" / "eval" / "replay-real")
    assert "offline" in str(refusal.value)


def test_the_capture_refuses_a_machine_without_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """A recording without a model is the recording of the other catalog."""
    monkeypatch.setattr(
        capture_live_replay,
        "get_settings",
        lambda: SimpleNamespace(offline=False, openai_api_key=None),
    )

    with pytest.raises(SystemExit) as refusal:
        capture_live_replay.capture("S01", ROOT / "data" / "eval" / "replay-real")
    assert "key" in str(refusal.value)


def test_the_capture_leaves_the_whole_catalog_out_of_the_check_of_the_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    """The ten scenarios are recorded in one run, and the bundle of the first one must not block the second one."""
    monkeypatch.setattr(capture_live_replay, "get_settings", _online_settings)
    seen: list[Path] = []

    def _refuse(root: Path, out: Path | None = None) -> None:
        seen.append(Path(out) if out is not None else Path())
        raise CaptureError("the check of the tree stops the capture here")

    monkeypatch.setattr(capture_live_replay, "ensure_clean_tree", _refuse)
    catalog = ROOT / "data" / "eval" / "replay-real"

    with pytest.raises(SystemExit):
        capture_live_replay.capture("S01", catalog)

    assert seen == [catalog], "the check of the tree has to leave the whole catalog out, and not one scene of it"


def test_the_capture_writes_the_bundle_of_the_scenario_inside_the_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    """The bundle of a scenario lives in the folder of that scenario, inside the catalog."""
    monkeypatch.setattr(capture_live_replay, "get_settings", _online_settings)
    monkeypatch.setattr(capture_live_replay, "ensure_clean_tree", lambda root, out=None: None)
    monkeypatch.setattr(capture_live_replay, "get_chat_model", lambda *args, **kwargs: None)
    monkeypatch.setattr(capture_live_replay, "build_integrator", lambda *args, **kwargs: None)
    monkeypatch.setattr(capture_live_replay, "investigate", lambda *args, **kwargs: None)
    written: list[Path] = []

    def _record(directory: Path, *args: object, **kwargs: object) -> None:
        written.append(directory)
        raise _StopHere()

    monkeypatch.setattr(capture_live_replay, "write_bundle", _record)
    catalog = ROOT / "data" / "eval" / "replay-real"

    with pytest.raises(_StopHere):
        capture_live_replay.capture("S07", catalog)

    assert written == [catalog / "s07"]
