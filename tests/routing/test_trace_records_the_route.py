"""The trace records the route: the bundle of a routed run names the model of each slot next to the task.

What they guarantee, and why: a routed run records the decision of the routing, and the record is the manifest
of the bundle of the run. The manifest names the model of each slot next to the task the slot did, so a reader
of the recording sees the division of the work and not only the model that wrote the answer (ADR-078).

Everything here runs offline, with no key and with no network: the bundle is the published bundle of a real run
under `data/eval/replay-real/s01/`.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "data" / "eval" / "replay-real" / "s01"

# The four slots of a run, and the task of each one, as the routing page names them.
SLOT_TASKS = {
    "triage": "read the question and write the plan of the investigation",
    "policy": "rewrite the question of the analyst into the words of the corpus of the policies",
    "sql": "write the statement that reads the ledger",
    "agent": "plan the investigation and answer with the tools",
}


def _manifest() -> dict:
    return json.loads((BUNDLE / "manifest.json").read_text(encoding="utf-8"))


def test_the_bundle_of_a_routed_run_names_the_model_of_each_slot() -> None:
    """The manifest of the bundle names the model of each of the four slots of the run."""
    manifest = _manifest()
    profiles = manifest["model_profiles"]

    assert set(profiles) == set(SLOT_TASKS)
    for slot, model in profiles.items():
        assert model, f"the slot {slot} names no model"
        assert SLOT_TASKS[slot], f"the slot {slot} names no task"


def test_the_route_the_bundle_records_is_the_route_of_the_cascade() -> None:
    """The model of each slot is the model the cascade of the deployment chooses for the task of the slot."""
    profiles = _manifest()["model_profiles"]

    # The light tasks ran on the light model of the cascade, and the robust tasks ran on the capable one.
    assert profiles["triage"] == "openai:gpt-4.1-mini"
    assert profiles["policy"] == "openai:gpt-4.1-mini"
    assert profiles["agent"] == "openai:gpt-4.1"
    assert profiles["sql"] == "openai:gpt-4.1"
