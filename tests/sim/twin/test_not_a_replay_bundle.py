"""A run of the twin is not a bundle of the agent: the two published catalogs are untouched by a run of the twin.

What they guarantee, and why: (a) a run of the twin writes no directory under `data/eval/replay/` and none
under `data/eval/replay-real/`, because the two published catalogs hold the recordings of the agent and
nothing else, and a run of the twin is a simulation and not a recording of the agent; (b) the export of the
site still passes after a run of the twin, because the catalogs are untouched.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from ledgerlens.sim.twin.config import TwinConfig
from ledgerlens.sim.twin.run import run_twin

ROOT = Path(__file__).resolve().parents[3]
REPLAY = ROOT / "data" / "eval" / "replay"
REPLAY_REAL = ROOT / "data" / "eval" / "replay-real"


def _catalogs() -> set[str]:
    """The directories of the two published catalogs, for the check that they are untouched."""
    return {str(path) for root in (REPLAY, REPLAY_REAL) for path in root.glob("*") if path.is_dir()}


def test_a_run_of_the_twin_writes_nothing_into_the_published_catalogs() -> None:
    """The catalogs hold the recordings of the agent, and a run of the twin is not one of them."""
    before = _catalogs()
    run_twin(
        TwinConfig(seed=42, horizon_minutes=60),
        truth_path=ROOT / "data" / "scenarios.json",
        commit="abc123",
    )

    assert _catalogs() == before


def test_the_export_of_the_site_still_passes_after_a_run_of_the_twin() -> None:
    """The catalogs are untouched, and the export of the site says so."""
    run_twin(
        TwinConfig(seed=42, horizon_minutes=60),
        truth_path=ROOT / "data" / "scenarios.json",
        commit="abc123",
    )
    proc = subprocess.run(
        ["uv", "run", "python", "scripts/export_replay_site.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
