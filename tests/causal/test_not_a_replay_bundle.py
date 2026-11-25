"""A run of the causal engine is not a bundle of the agent: the two published catalogs are untouched by a run.

What they guarantee, and why: (a) a run of the engine writes no directory under `data/eval/replay/` and none
under `data/eval/replay-real/`, because the two published catalogs hold the recordings of the agent and
nothing else, and a result of a simulation is not a bundle of the agent; (b) the export of the site still
passes after a run of the engine, because the catalogs are untouched.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import subprocess
from datetime import date
from decimal import Decimal
from pathlib import Path

from ledgerlens.causal.engine import run_and_write
from ledgerlens.causal.intervention import Intervention

ROOT = Path(__file__).resolve().parents[2]
REPLAY = ROOT / "data" / "eval" / "replay"
REPLAY_REAL = ROOT / "data" / "eval" / "replay-real"


def _catalogs() -> set[str]:
    """The directories of the two published catalogs, for the check that they are untouched."""
    return {str(path) for root in (REPLAY, REPLAY_REAL) for path in root.glob("*") if path.is_dir()}


def test_a_run_of_the_engine_writes_nothing_into_the_published_catalogs(world, tmp_path: Path) -> None:
    """The catalogs hold the recordings of the agent, and a result of a simulation is not one of them."""
    before = _catalogs()
    path = run_and_write(
        world,
        Intervention("fx.reference_rate", Decimal("6.00"), day=date(2024, 1, 10)),
        tmp_path / "out",
    )

    assert path.is_file()
    assert _catalogs() == before


def test_the_export_of_the_site_still_passes_after_a_run_of_the_engine(world, tmp_path: Path) -> None:
    """The catalogs are untouched, and the export of the site says so."""
    run_and_write(
        world,
        Intervention("fx.reference_rate", Decimal("6.00"), day=date(2024, 1, 10)),
        tmp_path / "out",
    )
    proc = subprocess.run(
        ["uv", "run", "python", "scripts/export_replay_site.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
