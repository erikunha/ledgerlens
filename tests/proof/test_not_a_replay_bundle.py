"""The export of the proofs writes nothing under the two published catalogs.

What they guarantee, and why: the export of the proofs writes nothing under `data/eval/replay/` and nothing
under `data/eval/replay-real/`, and `uv run python scripts/export_replay_site.py --check` still passes for
the two catalogs, because the two catalogs are read by this milestone and never written.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from ledgerlens.proof.export import build_proof_export, write_proof_export

ROOT = Path(__file__).resolve().parents[2]
REPLAY = ROOT / "data" / "eval" / "replay"
REPLAY_REAL = ROOT / "data" / "eval" / "replay-real"


def _catalogs() -> set[str]:
    """The files of the two published catalogs, for the check that they are untouched."""
    return {str(path) for root in (REPLAY, REPLAY_REAL) for path in root.rglob("*") if path.is_file()}


def test_the_export_of_the_proofs_writes_nothing_under_the_published_catalogs(tmp_path) -> None:
    """The catalogs are read and never written, and the export of the proofs says so."""
    before = _catalogs()
    write_proof_export(build_proof_export(ROOT), tmp_path / "proof")

    assert _catalogs() == before


def test_the_export_of_the_replay_site_still_passes_after_the_export_of_the_proofs(tmp_path) -> None:
    """The catalogs are untouched, and the export of the replay site says so."""
    write_proof_export(build_proof_export(ROOT), tmp_path / "proof")
    proc = subprocess.run(
        ["uv", "run", "python", "scripts/export_replay_site.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
