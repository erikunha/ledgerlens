"""Exercise A/A balance, denominators and incomplete observations before visitor enrollment."""

import pytest

from scripts.report_aa_readiness import audit, plan


def row(visitor, arm, exposed=True, resolved=True):
    return {"visitor": visitor, "arm": arm, "exposed": exposed, "resolved": resolved}


def test_missing_outcomes_and_exposures_stay_in_denominator():
    result = audit([row("a", "A"), row("b", "B", False, None)])
    assert result["arms"]["B"]["assigned"] == 1
    assert result["arms"]["B"]["missing_outcomes"] == 1
    assert result["arms"]["B"]["missing_exposures"] == 1
    assert result["instrumentation_findings"]


def test_balanced_fixture_cannot_establish_live_readiness():
    result = audit([row("a", "A"), row("b", "B")])
    assert result["instrumentation_findings"] == []
    assert result["arms"]["A"]["resolution_per_assigned"] == 1
    assert audit([])["instrumentation_findings"]
    assert audit([row(str(n), "A") for n in range(100)])["instrumentation_findings"]


@pytest.mark.parametrize(
    "rows",
    [
        [row("a", "A"), row("a", "B")],
        [row("a", "A", False, True)],
        [row("a", "A", resolved=1)],
        [dict(row("a", "B"), prompt="sample")],
    ],
)
def test_reject_invalid_records(rows):
    with pytest.raises(ValueError):
        audit(rows)


def test_smaller_effect_needs_more_visitors_and_invalid_plan_is_rejected():
    assert plan(0.5, 0.02) > plan(0.5, 0.05) > 100
    with pytest.raises(ValueError):
        plan(0.99, 0.05)


def test_identical_allocation_with_strong_outcome_imbalance_flags_aa():
    rows = [row(f"{arm}{i}", arm, resolved=arm == "A") for arm in ("A", "B") for i in range(12)]
    report = audit(rows)
    assert report["allocation_p_value"] == 1
    assert report["outcome_p_value"] < 0.01
    assert any("outcome rates" in finding for finding in report["instrumentation_findings"])


def test_large_balanced_allocation_and_identical_outcomes():
    rows = [row(f"{arm}{i}", arm, resolved=i % 2 == 0) for arm in ("A", "B") for i in range(100)]
    report = audit(rows)
    assert report["outcome_p_value"] == 1
    assert report["allocation_p_value"] == 1
    assert report["instrumentation_findings"] == []


def test_exact_allocation_matches_all_ten_on_one_side():
    assert audit([row(str(i), "A") for i in range(10)])["allocation_p_value"] == 2 / 1024


def test_sparse_large_sample_withholds_outcome_test():
    report = audit([row(f"{arm}{i}", arm, resolved=arm == "B" and i == 0) for arm in ("A", "B") for i in range(60)])
    assert report["outcome_p_value"] is None
    assert report["instrumentation_findings"]


def test_invalid_root_and_duplicate_fields_are_rejected(tmp_path):
    from ledgerlens.eval.json_input import read_experiment_json

    with pytest.raises(ValueError, match="array"):
        audit({})
    input_path = tmp_path / "invalid.json"
    input_path.write_text('[{"visitor":"v","arm":"A","arm":"B","exposed":true,"resolved":true}]')
    with pytest.raises(ValueError, match="duplicate"):
        read_experiment_json(input_path)
