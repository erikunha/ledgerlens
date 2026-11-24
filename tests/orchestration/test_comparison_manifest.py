"""The manifest of the comparison of the orchestration studio.

What they guarantee, and why: (a) the manifest is a set of records that the manifest of the datasets can pin, so the
pre-registration cannot move under the result without the check of the datasets noticing; (b) the manifest names the
set, the denominator, the two arms, the measures and the rule that decides the result, because a comparison that
does not say what it measures is not a comparison; (c) the digests the manifest names are the digests of the files of
the disk, so the two arms of the comparison cannot read two different ledgers; (d) the manifest is registered with
the role `held_out`, so that only the final scoring of the comparison reads it.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ledgerlens.eval.manifest import MANIFEST_PATH, load_manifests

ROOT = Path(__file__).resolve().parents[2]
COMPARISON = ROOT / "data" / "runtime" / "orchestration" / "comparison.json"

# The identifier of the dataset that carries the manifest of the comparison.
DATASET_ID = "orchestration_comparison"


def _records() -> list[dict[str, object]]:
    """The records of the manifest of the comparison, one per line."""
    text = COMPARISON.read_text(encoding="utf-8")
    records = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        record = json.loads(line)
        assert isinstance(record, dict), f"the line {number} of the manifest is not a record"
        records.append(record)
    return records


def _of(section: str) -> list[dict[str, object]]:
    """The records of one section of the manifest."""
    return [record for record in _records() if record.get("section") == section]


def test_the_manifest_of_the_comparison_is_a_set_of_records() -> None:
    """Every line of the file is a record, so that the manifest of the datasets can count them."""
    assert COMPARISON.is_file(), f"the manifest of the comparison is missing: {COMPARISON}"

    records = _records()
    assert records
    assert len({record["section"] for record in records}) >= 5


def test_the_manifest_names_the_set_the_denominator_and_the_two_arms() -> None:
    """The set, the denominator and the two arms are named, because a comparison that does not say what it
    compares is not a comparison."""
    sets = _of("set")
    assert len(sets) == 1
    the_set = sets[0]
    assert the_set["dataset_id"] == "eval_cases"
    assert the_set["records_count"] == 31
    assert the_set["denominator"] == 31

    arms = _of("arm")
    assert [arm["name"] for arm in arms] == ["single_agent", "orchestration_studio"]


def test_the_manifest_names_the_measures_and_the_rule_that_decides_the_result() -> None:
    """The measures and the rule are named, and the rule says that the flag stays off when it is not met."""
    measures = _of("measure")
    assert {measure["name"] for measure in measures} == {
        "correct_cases",
        "cost_per_correct_case_usd",
        "latency_p95_ms",
        "tool_calls",
    }
    for measure in measures:
        assert measure["direction"] in {"higher_is_better", "lower_is_better"}

    rules = _of("rule")
    assert len(rules) == 1
    decision = str(rules[0]["decision"])
    assert "the flag stays off" in decision.lower()
    assert rules[0]["threshold_cases"] == 2


def test_the_digests_the_manifest_names_are_the_digests_of_the_disk() -> None:
    """The set and the ledger of the comparison are the ones of the disk, so the two arms cannot read two ledgers."""
    the_set = _of("set")[0]
    digest = hashlib.sha256((ROOT / str(the_set["path"])).read_bytes()).hexdigest()
    assert the_set["sha256"] == digest

    snapshot = _of("snapshot")[0]
    scenarios = json.loads((ROOT / "data" / "scenarios.json").read_text(encoding="utf-8"))
    assert snapshot["ledger_sha256"] == scenarios["db_canonical_sha256"]
    assert snapshot["same_snapshot_for_both_arms"] is True


def test_the_manifest_is_registered_with_the_role_that_only_the_scoring_reads() -> None:
    """The manifest is a dataset of the manifest of the datasets, and its role is `held_out`."""
    manifests = load_manifests(MANIFEST_PATH)
    entry = next((manifest for manifest in manifests if manifest.dataset_id == DATASET_ID), None)

    assert entry is not None, f"the manifest of the datasets does not declare {DATASET_ID}"
    assert entry.split_role == "held_out"
    assert entry.path == "data/runtime/orchestration/comparison.json"
    assert entry.sha256 == hashlib.sha256(COMPARISON.read_bytes()).hexdigest()
    assert entry.records_count == len(_records())
