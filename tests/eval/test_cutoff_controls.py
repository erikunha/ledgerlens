"""Keep the registered safety controls and the separate wording probes visible in the report."""

from scripts.report_cutoff_controls import run


def test_receipt_rule_preserves_mandatory_reviews():
    report = run()
    rows = report["rows"]
    assert len({(r["family"], r["currency"], r["condition"]) for r in rows}) == report["cases"] == 48
    assert sum(r["expected_review"] for r in rows) == 40
    assert report["errors"] == {
        "baseline": {"unsafe_release": 0, "unnecessary_review": 8},
        "candidate": {"unsafe_release": 0, "unnecessary_review": 0},
    }
    assert len(report["paraphrase_probes"]) == 8
    assert all(row["candidate_review"] for row in report["paraphrase_probes"])
