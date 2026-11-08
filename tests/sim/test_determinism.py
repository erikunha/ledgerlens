"""`ledgerlens-sim` is deterministic: same seed and source give the same hash, another seed differs,
and the committed sample reproduces the public run it was derived from."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from ledgerlens.sim.cli import main
from ledgerlens.sim.projector import canonical_hash

MINI = Path(__file__).resolve().parents[1] / "fixtures" / "uci_mini.csv"


def run(tmp_path: Path, name: str, *args: str) -> tuple[int, Path, Path]:
    db, manifest = tmp_path / f"{name}.db", tmp_path / f"{name}.json"
    code = main([*args, "--db", str(db), "--manifest", str(manifest)])
    return code, db, manifest


def digest(db: Path) -> str:
    conn = sqlite3.connect(db)
    try:
        return canonical_hash(conn)
    finally:
        conn.close()


SYNTHETIC = ("--source", "synthetic", "--max-transactions", "150", "--seed", "7")


def test_same_seed_and_source_give_the_same_hash_and_manifest(tmp_path):
    code_a, db_a, man_a = run(tmp_path, "a", *SYNTHETIC)
    code_b, db_b, man_b = run(tmp_path, "b", *SYNTHETIC)

    assert code_a == code_b == 0
    assert digest(db_a) == digest(db_b)
    assert man_a.read_bytes() == man_b.read_bytes()
    assert json.loads(man_a.read_text())["db_canonical_sha256"] == digest(db_a)


def test_the_event_logs_are_identical_row_for_row(tmp_path):
    _, db_a, _ = run(tmp_path, "a", *SYNTHETIC)
    _, db_b, _ = run(tmp_path, "b", *SYNTHETIC)
    query = "SELECT event_uid, occurred_at, type, aggregate_id, payload, origin FROM events ORDER BY event_id"
    rows = []
    for path in (db_a, db_b):
        conn = sqlite3.connect(path)
        rows.append(conn.execute(query).fetchall())
        conn.close()
    assert rows[0] == rows[1] and len(rows[0]) > 500


def test_another_seed_changes_the_data_but_not_the_scenarios(tmp_path):
    _, db_a, man_a = run(tmp_path, "a", *SYNTHETIC)
    _, db_b, man_b = run(tmp_path, "b", "--source", "synthetic", "--max-transactions", "150", "--seed", "8")

    assert digest(db_a) != digest(db_b)
    scenarios_a = json.loads(man_a.read_text())["scenarios"]
    scenarios_b = json.loads(man_b.read_text())["scenarios"]
    for first, second in zip(scenarios_a, scenarios_b, strict=True):
        if first["id"] in {"S08"}:
            continue  # the settlement amounts include natural traffic of the merchant
        assert first == second, first["id"]


def test_the_sample_reproduces_the_public_run_it_came_from(tmp_path):
    sample = tmp_path / "sample" / "invoices_sample.jsonl"
    code, db_public, man_public = run(
        tmp_path, "public", "--source", "public", "--raw", str(MINI), "--write-sample", str(sample)
    )
    assert code == 0 and sample.exists()

    code, db_sample, man_sample = run(tmp_path, "sample", "--source", "sample", "--sample", str(sample))

    assert code == 0
    assert digest(db_public) == digest(db_sample)
    public, derived = json.loads(man_public.read_text()), json.loads(man_sample.read_text())
    assert (public["source"], derived["source"]) == ("public", "sample")
    assert public["counts"] == derived["counts"]
    assert derived["transform"]["sample_meta"]["license"] == "CC BY 4.0"
    assert public["transform"]["time_shift_days"] == derived["transform"]["time_shift_days"]
    for document in (public, derived):
        document.pop("source")
        document["transform"].pop("sample_meta", None)
    assert public == derived, "the sample run differs from the public run only in `source` and `sample_meta`"


def test_the_sample_metadata_says_what_was_changed(tmp_path):
    sample = tmp_path / "invoices_sample.jsonl"
    run(tmp_path, "public", "--source", "public", "--raw", str(MINI), "--write-sample", str(sample))
    meta = json.loads(sample.read_text().splitlines()[0])["_meta"]
    assert meta["license"] == "CC BY 4.0" and "10.24432/C5CG6D" in meta["derived_from"]
    assert "time-shifted" in meta["changes"] and "merchants" in meta["changes"]
    assert meta["invoices"] == len(sample.read_text().splitlines()) - 1


def test_auto_prefers_public_then_sample_then_synthetic(tmp_path, capsys):
    sample = tmp_path / "invoices_sample.jsonl"
    run(tmp_path, "seed", "--source", "public", "--raw", str(MINI), "--write-sample", str(sample))
    missing = str(tmp_path / "no-such.zip")

    capsys.readouterr()
    run(tmp_path, "auto1", "--raw", str(MINI), "--sample", str(sample))
    assert "source: public" in capsys.readouterr().out
    run(tmp_path, "auto2", "--raw", missing, "--sample", str(sample))
    assert "source: sample" in capsys.readouterr().out
    run(tmp_path, "auto3", "--raw", missing, "--sample", str(tmp_path / "no-sample.jsonl"), "--max-transactions", "80")
    assert "source: synthetic" in capsys.readouterr().out


def test_asking_for_a_missing_source_fails_with_the_way_to_get_it(tmp_path, capsys):
    code, db, _ = run(tmp_path, "x", "--source", "public", "--raw", str(tmp_path / "no-such.zip"))
    err = capsys.readouterr().err
    assert code == 1 and "fetch_public_data.py" in err
    assert not db.exists()


def test_end_moves_the_last_day(tmp_path):
    _, db, manifest = run(
        tmp_path, "e", "--source", "public", "--raw", str(MINI), "--end", "2026-10-31", "--scenarios", "none"
    )
    conn = sqlite3.connect(db)
    last = conn.execute("SELECT max(created_at) FROM transactions").fetchone()[0]
    conn.close()
    assert last.startswith("2026-10-")
    assert json.loads(manifest.read_text())["end"] == "2026-10-31"


def test_scenario_selection_and_validation(tmp_path, capsys):
    code, _, manifest = run(tmp_path, "s", *SYNTHETIC, "--scenarios", "S01,S03")
    assert code == 0
    assert [s["id"] for s in json.loads(manifest.read_text())["scenarios"]] == ["S01", "S03"]
    code, _, manifest = run(tmp_path, "n", *SYNTHETIC, "--scenarios", "none")
    assert json.loads(manifest.read_text())["scenarios"] == []

    capsys.readouterr()
    with pytest.raises(SystemExit) as stop:  # argparse rejects the value itself
        run(tmp_path, "bad", *SYNTHETIC, "--scenarios", "S99")
    assert stop.value.code == 2 and "S99" in capsys.readouterr().err
    assert run(tmp_path, "big", "--source", "synthetic", "--max-transactions", "999999")[0] == 2


def test_days_limits_the_window(tmp_path):
    _, db, manifest = run(
        tmp_path, "d", "--source", "public", "--raw", str(MINI), "--days", "20", "--scenarios", "none"
    )
    info = json.loads(manifest.read_text())
    assert info["days"] == 20
    assert info["transform"]["selection"]["window_first"] == "2011-11-02"
    assert info["counts"]["transactions"] == info["transform"]["selection"]["sales_selected"]


def test_the_entry_point_is_declared():
    text = (Path(__file__).resolve().parents[2] / "pyproject.toml").read_text()
    assert 'ledgerlens-sim = "ledgerlens.sim.cli:main"' in text


def test_help_lists_every_option(capsys):
    with pytest.raises(SystemExit) as stop:
        main(["--help"])
    assert stop.value.code == 0
    out = capsys.readouterr().out
    for option in ("--days", "--seed", "--scenarios", "--source", "--max-transactions", "--end"):
        assert option in out
