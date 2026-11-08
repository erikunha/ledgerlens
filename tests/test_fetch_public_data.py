"""fetch_public_data.py downloads to data/raw, records SHA-256 in the lock file and refuses a changed checksum.

Every download goes to a local HTTP server fixture; nothing here touches the network.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fetch_public_data.py"


def _load():
    spec = importlib.util.spec_from_file_location("fetch_public_data", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module  # dataclasses look the module up by name
    spec.loader.exec_module(module)
    return module


fetch = _load()


def _source(server, name: str = "toy", path: str = "/toy.csv", **overrides):
    values = {
        "name": name,
        "url": f"{server.base_url}{path}",
        "filename": "toy.csv",
        "license": "CC BY 4.0",
        "redistributable": True,
        "attribution": "Toy data",
    }
    values.update(overrides)
    return fetch.Source(**values)


def test_download_writes_file_and_records_checksum(local_http, tmp_path):
    body = b"a,b\n1,2\n"
    local_http.add("/toy.csv", body)
    raw, lock = tmp_path / "raw", tmp_path / "sources.lock.json"

    results = fetch.fetch_sources([_source(local_http)], raw_dir=raw, lock_path=lock)

    assert (raw / "toy.csv").read_bytes() == body
    entry = json.loads(lock.read_text())["sources"]["toy"]
    assert entry["sha256"] == hashlib.sha256(body).hexdigest()
    assert entry["bytes"] == len(body)
    assert entry["license"] == "CC BY 4.0"
    assert entry["redistributable"] is True
    assert entry["url"].endswith("/toy.csv")
    assert entry["fetched_at"]
    assert results[0].status == "downloaded"


def test_second_run_verifies_without_downloading(local_http, tmp_path):
    local_http.add("/toy.csv", b"x\n")
    raw, lock = tmp_path / "raw", tmp_path / "sources.lock.json"
    fetch.fetch_sources([_source(local_http)], raw_dir=raw, lock_path=lock)
    before = lock.read_text()
    local_http.requests.clear()

    results = fetch.fetch_sources([_source(local_http)], raw_dir=raw, lock_path=lock)

    assert results[0].status == "verified"
    assert local_http.requests == []
    assert lock.read_text() == before


def test_changed_checksum_on_download_is_refused(local_http, tmp_path):
    local_http.add("/toy.csv", b"version one\n")
    raw, lock = tmp_path / "raw", tmp_path / "sources.lock.json"
    fetch.fetch_sources([_source(local_http)], raw_dir=raw, lock_path=lock)
    locked = lock.read_text()
    (raw / "toy.csv").unlink()
    local_http.add("/toy.csv", b"version two\n")

    with pytest.raises(fetch.ChecksumMismatch) as excinfo:
        fetch.fetch_sources([_source(local_http)], raw_dir=raw, lock_path=lock)

    assert "toy" in str(excinfo.value)
    assert lock.read_text() == locked, "the lock must not change on a refusal"
    assert not (raw / "toy.csv").exists(), "a rejected download must not be kept as the raw file"


def test_local_file_that_no_longer_matches_the_lock_is_refused(local_http, tmp_path):
    local_http.add("/toy.csv", b"original\n")
    raw, lock = tmp_path / "raw", tmp_path / "sources.lock.json"
    fetch.fetch_sources([_source(local_http)], raw_dir=raw, lock_path=lock)
    (raw / "toy.csv").write_bytes(b"tampered\n")

    with pytest.raises(fetch.ChecksumMismatch):
        fetch.fetch_sources([_source(local_http)], raw_dir=raw, lock_path=lock)


def test_update_lock_accepts_a_new_checksum(local_http, tmp_path):
    local_http.add("/toy.csv", b"version one\n")
    raw, lock = tmp_path / "raw", tmp_path / "sources.lock.json"
    fetch.fetch_sources([_source(local_http)], raw_dir=raw, lock_path=lock)
    (raw / "toy.csv").unlink()
    local_http.add("/toy.csv", b"version two\n")

    results = fetch.fetch_sources([_source(local_http)], raw_dir=raw, lock_path=lock, update_lock=True)

    entry = json.loads(lock.read_text())["sources"]["toy"]
    assert entry["sha256"] == hashlib.sha256(b"version two\n").hexdigest()
    assert results[0].status == "downloaded"


def test_http_error_reports_the_source_and_keeps_nothing(local_http, tmp_path):
    local_http.add("/toy.csv", b"gone", status=503)
    raw, lock = tmp_path / "raw", tmp_path / "sources.lock.json"

    with pytest.raises(fetch.FetchError) as excinfo:
        fetch.fetch_sources([_source(local_http)], raw_dir=raw, lock_path=lock, retries=1)

    assert "toy" in str(excinfo.value) and "503" in str(excinfo.value)
    assert not (raw / "toy.csv").exists()
    assert not lock.exists()


def test_lock_keeps_other_sources_and_is_sorted(local_http, tmp_path):
    local_http.add("/a.csv", b"a\n")
    local_http.add("/b.csv", b"b\n")
    raw, lock = tmp_path / "raw", tmp_path / "sources.lock.json"
    fetch.fetch_sources([_source(local_http, "zeta", "/a.csv", filename="a.csv")], raw_dir=raw, lock_path=lock)
    fetch.fetch_sources([_source(local_http, "alpha", "/b.csv", filename="b.csv")], raw_dir=raw, lock_path=lock)

    names = list(json.loads(lock.read_text())["sources"])
    assert names == ["alpha", "zeta"]


def test_default_sources_cover_uci_bins_and_ecb():
    by_name = {source.name: source for source in fetch.SOURCES}
    assert set(by_name) == {"uci_online_retail_ii", "bin_list", "ecb_eurofxref_hist"}
    assert by_name["uci_online_retail_ii"].url == "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
    assert by_name["uci_online_retail_ii"].license == "CC BY 4.0"
    assert by_name["bin_list"].license == "CC BY 4.0"
    assert by_name["ecb_eurofxref_hist"].url.startswith("https://www.ecb.europa.eu/")
    for source in by_name.values():
        assert source.filename and source.attribution


def test_main_only_selects_sources(local_http, tmp_path, monkeypatch):
    local_http.add("/toy.csv", b"z\n")
    monkeypatch.setattr(
        fetch, "SOURCES", (_source(local_http), _source(local_http, "other", "/missing", filename="o.csv"))
    )

    code = fetch.main(["--only", "toy", "--raw-dir", str(tmp_path / "raw"), "--lock", str(tmp_path / "l.json")])

    assert code == 0
    assert (tmp_path / "raw" / "toy.csv").exists()
    assert not (tmp_path / "raw" / "o.csv").exists()


def test_main_returns_nonzero_on_refusal(local_http, tmp_path, monkeypatch, capsys):
    local_http.add("/toy.csv", b"one\n")
    monkeypatch.setattr(fetch, "SOURCES", (_source(local_http),))
    args = ["--raw-dir", str(tmp_path / "raw"), "--lock", str(tmp_path / "l.json")]
    assert fetch.main(args) == 0
    (tmp_path / "raw" / "toy.csv").write_bytes(b"changed\n")

    assert fetch.main(args) == 1
    assert "toy" in capsys.readouterr().err
