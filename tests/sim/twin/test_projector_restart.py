"""The restart of the projector of the twin: the digest of the projected tables survives a rebuild.

What they guarantee, and why: the digest of the projected tables after a rebuild of the projector is the
digest before the rebuild, and the order of the ids of the events is the same, because the projection of the
ledger is a pure function of the event log, and a rebuild that changed the digest would be a rebuild of
another world.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from ledgerlens.eval.dataset import build_sample_ledger
from ledgerlens.sim.projector import canonical_hash
from ledgerlens.sim.twin.run import rebuild_projection


def test_the_digest_of_the_projected_tables_survives_a_rebuild(tmp_path: Path) -> None:
    """The rebuild of the projector gives the same digest as the projection it rebuilt."""
    ledger = build_sample_ledger(tmp_path / "ledger.db")
    before = canonical_hash(sqlite3.connect(f"file:{ledger}?mode=ro", uri=True))

    after = rebuild_projection(ledger)

    assert after == before


def test_the_order_of_the_ids_of_the_events_survives_a_rebuild(tmp_path: Path) -> None:
    """The order of the ids of the events of the log is the same after the rebuild."""
    ledger = build_sample_ledger(tmp_path / "ledger.db")
    conn = sqlite3.connect(f"file:{ledger}?mode=ro", uri=True)
    before = [row[0] for row in conn.execute("SELECT event_id FROM events ORDER BY event_id").fetchall()]
    conn.close()

    rebuilt = rebuild_projection(ledger)
    conn = sqlite3.connect(f"file:{ledger}?mode=ro", uri=True)
    after = [row[0] for row in conn.execute("SELECT event_id FROM events ORDER BY event_id").fetchall()]
    conn.close()

    assert after == before
    assert rebuilt
