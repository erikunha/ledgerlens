"""A replay of a published bundle writes nothing: the digest of the ledger of the base does not move.

What they guarantee, and why: a replay of a published bundle of `ledgerlens/replay/bundle.py` writes nothing,
and the digest of the ledger of the base is the same before and after the replay, because a replay is a reading
of a recording and never an execution, and a reading that wrote something would be a writing wearing the name
of a reading.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from ledgerlens.observability.trace_event import InMemoryTraceSink
from ledgerlens.replay.bundle import replay

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "data" / "eval" / "replay" / "s01"
LEDGER = ROOT / "data" / "ledger.db"


def _digest(path: Path) -> str:
    """The sha256 of the file, for the check of the test."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_a_replay_of_a_published_bundle_writes_nothing() -> None:
    """The replay reads the recording, and the ledger of the base is the same before and after."""
    before = _digest(LEDGER)

    events = replay(BUNDLE, InMemoryTraceSink())

    assert events
    assert _digest(LEDGER) == before
