"""The committed data agrees with the code: the lock, the sample, the fixtures and the manifest."""

from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

from ledgerlens.sim.config import SimConfig
from ledgerlens.sim.pipeline import build_ledger

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"
MAX_COMMITTED_BYTES = 5 * 1024 * 1024


@pytest.fixture(scope="module")
def committed() -> dict:
    return json.loads((DATA / "scenarios.json").read_text(encoding="utf-8"))


def test_lock_records_url_size_checksum_and_license_for_each_raw_file():
    lock = json.loads((DATA / "sources.lock.json").read_text())
    assert set(lock["sources"]) == {"uci_online_retail_ii", "bin_list", "ecb_eurofxref_hist"}
    for name, entry in lock["sources"].items():
        assert re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]), name
        assert entry["bytes"] > 0 and entry["url"].startswith("https://") and entry["license"]
        assert isinstance(entry["redistributable"], bool)
    assert lock["sources"]["uci_online_retail_ii"]["license"] == "CC BY 4.0"


def test_raw_files_stay_out_of_git():
    ignore = (REPO / ".gitignore").read_text()
    assert "data/raw/" in ignore and "data/ledger.db" in ignore


def test_committed_files_stay_under_the_size_limit():
    committed_files = [
        *(DATA / "fixtures").rglob("*"),
        DATA / "sample" / "invoices_sample.jsonl",
        DATA / "scenarios.json",
        DATA / "sources.lock.json",
    ]
    for path in committed_files:
        if path.is_file():
            assert path.stat().st_size < MAX_COMMITTED_BYTES, path


def test_notice_credits_every_source_and_the_derived_files():
    notice = (REPO / "NOTICE").read_text()
    for needle in (
        "UCI Online Retail II",
        "CC BY 4.0",
        "bin-list-data",
        "European Central Bank",
        "Banco Central do Brasil",
        "Nager.Date",
    ):
        assert needle in notice, needle
    for derived in (
        "data/sample/invoices_sample.jsonl",
        "data/fixtures/bins.json",
        "data/fixtures/fx",
        "data/fixtures/holidays",
    ):
        assert derived in notice, derived


def test_sample_metadata_carries_the_license_and_the_source_checksum():
    first = json.loads((DATA / "sample" / "invoices_sample.jsonl").read_text(encoding="utf-8").splitlines()[0])["_meta"]
    lock = json.loads((DATA / "sources.lock.json").read_text())
    assert first["license"] == "CC BY 4.0" and "10.24432/C5CG6D" in first["derived_from"]
    assert first["source_sha256"] == lock["sources"]["uci_online_retail_ii"]["sha256"]


def test_the_sample_rebuilds_the_committed_ledger_and_manifest_exactly(committed):
    result = build_ledger(SimConfig(source="sample"))
    assert result.manifest["db_canonical_sha256"] == committed["db_canonical_sha256"]
    assert result.manifest == committed, "regenerate data/scenarios.json with `ledgerlens-sim --source sample`"


def test_the_manifest_records_the_measured_cancellation_matching_rate():
    manifest = json.loads((DATA / "scenarios.json").read_text(encoding="utf-8"))
    selection = manifest["transform"]["selection"]
    assert (
        selection["cancellations_in_window"] == selection["cancellations_linked"] + selection["cancellations_unlinked"]
    )
    assert 0 < selection["matching_rate"] < 1 and 0 < selection["matching_rate_whole_window"] <= 1
    assert manifest["counts"]["public_origin_transactions"] > 2000


def test_the_committed_manifest_has_the_tx_2048_truth(committed):
    s01 = next(item for item in committed["scenarios"] if item["id"] == "S01")["truth"]
    assert [Decimal(s01[key]) for key in ("charge_brl", "refund_brl", "gap_brl", "rate_move_brl", "markup_brl")] == [
        Decimal("566.79"),
        Decimal("549.31"),
        Decimal("17.48"),
        Decimal("3.40"),
        Decimal("14.08"),
    ]
