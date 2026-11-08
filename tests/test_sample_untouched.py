"""`data/sample/` holds only the versioned sample: nothing writes a database there.

What these tests guarantee, and why: (a) the folder has only `invoices_sample.jsonl`, so a stray `ledger.db`
(empty or not) shows up as a failure; (b) opening a missing database read-only fails and does not create the file,
which was how an empty file used to appear next to the sample. The `sample_directory_stays_untouched` fixture
in `conftest.py` points at the test that wrote there.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from ledgerlens.tools.sql import open_readonly

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "data" / "sample"


def test_the_sample_folder_holds_only_the_committed_sample() -> None:
    assert sorted(p.name for p in SAMPLE_DIR.iterdir()) == ["invoices_sample.jsonl"]


def test_opening_a_missing_ledger_read_only_fails_and_creates_nothing(tmp_path: Path) -> None:
    missing = tmp_path / "ledger.db"
    with pytest.raises(sqlite3.OperationalError):
        open_readonly(missing)
    assert not missing.exists()
