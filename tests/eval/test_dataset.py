"""Evaluation set: about 30 cases, 12 from the planted scenarios and the rest from the generated database.

What they guarantee, and why: (a) there are 30 cases with unique ids, 12 from the manifest and 18 natural;
(b) each scenario's expected trajectory is the manifest's; (c) every case has expected facts and a
trajectory; (d) the committed file is exactly what the build produces today, so the answer key does not go
stale silently; (e) the facts of the natural cases come from the tables, not from hand-written text.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pytest

from ledgerlens.eval.dataset import (
    CASES_PATH,
    EvalCase,
    build_cases,
    build_sample_ledger,
    expected_verdict,
    load_cases,
    load_verification_cases,
)

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = {s["id"]: s for s in json.loads((ROOT / "data" / "scenarios.json").read_text("utf-8"))["scenarios"]}


@pytest.fixture(scope="module")
def ledger_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_sample_ledger(tmp_path_factory.mktemp("eval_ledger") / "ledger.db")


@pytest.fixture(scope="module")
def cases(ledger_db: Path) -> list[EvalCase]:
    return build_cases(ledger_db)


def test_thirty_cases_twelve_from_the_scenarios(cases: list[EvalCase]) -> None:
    assert len(cases) == 30
    assert len({c.id for c in cases}) == 30
    assert Counter(c.kind for c in cases) == {"scenario": 12, "natural": 18}
    assert [c.scenario for c in cases if c.kind == "scenario"] == sorted(SCENARIOS)


def test_scenario_trajectories_are_the_manifest_ones(cases: list[EvalCase]) -> None:
    for case in (c for c in cases if c.kind == "scenario"):
        assert case.expected_tools == SCENARIOS[case.scenario]["expected_tools"], case.scenario
        assert case.question in SCENARIOS[case.scenario]["questions"], case.scenario


def test_every_case_has_facts_a_trajectory_and_a_scripted_answer(cases: list[EvalCase]) -> None:
    for case in cases:
        assert case.expected_facts, case.id
        assert [s.tool for s in case.steps] == case.expected_tools, case.id
        assert all(fact in case.answer for fact in case.expected_facts), case.id
        assert sum(s.tool == "query_ledger" for s in case.steps) == sum(bool(s.sql) for s in case.steps), case.id


def test_natural_cases_cover_status_settlement_and_policy(cases: list[EvalCase]) -> None:
    natural = [c for c in cases if c.kind == "natural"]
    first_tools = Counter(c.expected_tools[0] for c in natural)
    assert first_tools == {"get_ledger_record": 6, "query_ledger": 6, "search_policies": 6}


def test_natural_facts_come_from_the_tables(cases: list[EvalCase], ledger_db: Path) -> None:
    import sqlite3

    conn = sqlite3.connect(ledger_db)
    for case in (c for c in cases if c.kind == "natural" and c.expected_tools[0] == "query_ledger"):
        settlement_id = re.search(r"ST-\d{4}", case.question).group(0)
        net_minor = conn.execute("SELECT net_minor FROM settlements WHERE id = ?", (settlement_id,)).fetchone()[0]
        assert str(net_minor) in case.expected_facts, case.id
    conn.close()


def test_the_committed_file_is_what_the_build_produces(cases: list[EvalCase]) -> None:
    assert load_cases(CASES_PATH) == cases


def test_the_file_is_one_json_object_per_line() -> None:
    lines = CASES_PATH.read_text("utf-8").splitlines()
    assert len(lines) == 30 and all(json.loads(line)["id"] for line in lines)


def test_only_record_lookups_declare_an_equivalence_group(cases: list[EvalCase]) -> None:
    for case in cases:
        lookup = case.kind == "natural" and case.expected_tools == ["get_ledger_record"]
        assert case.equivalent_tools == ([["get_ledger_record", "query_ledger"]] if lookup else []), case.id
    assert sum(bool(c.equivalent_tools) for c in cases) == 6


def test_every_verification_case_has_an_expected_verdict() -> None:
    cases = load_verification_cases()
    assert len(cases) == 43 and len({c["id"] for c in cases}) == 43
    verdicts = {expected_verdict(c) for c in cases}
    assert verdicts == {"supported", "contradicted", "not_enough_evidence"}
    planted = [c for c in cases if c["type"] == "coherence" and c["planted"]]
    assert planted and all(expected_verdict(c) == "contradicted" for c in planted)
    clean = [c for c in cases if c["type"] == "coherence" and not c["planted"]]
    assert clean and all(expected_verdict(c) == "supported" for c in clean)


def test_a_stored_net_settlement_is_answered_by_the_ledger_query_alone(cases: list[EvalCase], ledger_db: Path) -> None:
    """EC-19 to EC-24 also expected `calculate`, but the question is the net amount the table already keeps.

    The model read `net_minor` from the row and did not recompute it: the value comes from a tool, the coherence
    rule checks `net = gross - refunds - fees` by itself, and `calculate` would only redo the sum with the same
    three columns.
    """
    import sqlite3

    settlements = [c for c in cases if c.kind == "natural" and "payout" in c.question]
    assert [c.id for c in settlements] == [f"EC-{n}" for n in range(19, 25)]
    conn = sqlite3.connect(ledger_db)
    for case in settlements:
        assert case.expected_tools == ["query_ledger"], case.id
        settlement_id = re.search(r"ST-\d{4}", case.question).group(0)
        gross, refunds, fees, net = conn.execute(
            "SELECT gross_minor, refunds_minor, fees_minor, net_minor FROM settlements WHERE id = ?", (settlement_id,)
        ).fetchone()
        assert net == gross - refunds - fees, (
            case.id
        )  # the premise of the decision: the stored column is the sum already done
    conn.close()


def test_the_scenario_that_asks_how_a_settlement_was_calculated_still_expects_calculate(
    cases: list[EvalCase],
) -> None:
    assert "calculate" in next(c for c in cases if c.scenario == "S08").expected_tools


def test_the_changed_expectations_stay_visible() -> None:
    from ledgerlens.eval.dataset import EXPECTATION_CHANGES

    [change] = EXPECTATION_CHANGES
    assert change.cases == [f"EC-{n}" for n in range(19, 25)]
    assert change.before == ["query_ledger", "calculate"] and change.after == ["query_ledger"]
    assert "net_minor" in change.reason
