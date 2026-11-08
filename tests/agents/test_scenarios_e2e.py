"""The twelve scenarios of `data/scenarios.json` end to end, offline, through the integrator.

What they guarantee, and why: each scenario runs with the real tools (SQL over the ledger built from the
committed sample, the in-process ledger API, the policy index, recorded FX, the `Decimal` calculator, case
memory) and the real verifier with the deterministic NLI stand-in. Only the model is scripted: the script
plays the LLM and picks the tools in the expected order. The checks come from the scenario truth and the
real tool outputs: the tool trace, the facts the answer and the evidence carry, the verdicts and
`requires_human_review`.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest

from ledgerlens import embeddings as emb
from ledgerlens.agents.integrator import build_integrator, investigate
from ledgerlens.embeddings import FastEmbedEmbeddings
from ledgerlens.memory.long_term import CaseMemory
from ledgerlens.offline import ScriptedChatModel, text_message, tool_call_message
from ledgerlens.retrieval import build_policy_index, index_dir_for, load_policy_documents
from ledgerlens.schemas import InvestigationResult
from ledgerlens.sim.config import SimConfig
from ledgerlens.sim.pipeline import build_ledger
from ledgerlens.tools.fx import FxClient
from tests.tools import test_policies as base

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = {
    s["id"]: s for s in json.loads((ROOT / "data" / "scenarios.json").read_text(encoding="utf-8"))["scenarios"]
}


@pytest.fixture(scope="module")
def ledger_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("ledger") / "ledger.db"
    build_ledger(SimConfig(source="sample"), path).conn.close()
    return path


@pytest.fixture
def embeddings(monkeypatch: pytest.MonkeyPatch) -> FastEmbedEmbeddings:
    monkeypatch.setattr(emb, "_text_embedding_class", lambda: base.WordCountModel)
    return FastEmbedEmbeddings()


@pytest.fixture
def index_root(tmp_path: Path, embeddings: FastEmbedEmbeddings) -> Path:
    root = tmp_path / "index"
    build_policy_index(load_policy_documents(base.POLICIES), embeddings, index_dir_for(root, embeddings))
    return root


@pytest.fixture
def cases(tmp_path: Path, embeddings: FastEmbedEmbeddings) -> CaseMemory:
    return CaseMemory(tmp_path / "cases", embeddings=embeddings)


def run(
    scenario_id: str,
    script: list[Any],
    sql: list[str],
    *,
    db: Path,
    index_root: Path,
    cases: CaseMemory,
    question: int = 0,
    fault: bool = False,
) -> InvestigationResult:
    """One scenario question through the integrator, with the real verifier (deterministic NLI)."""
    from ledgerlens.verify.nli import StubNli

    def verifier(result: InvestigationResult, *, nli: Any = None) -> InvestigationResult:
        from ledgerlens.verify import verify_result

        return verify_result(result, nli=StubNli())

    agent = build_integrator(
        ScriptedChatModel(script=script),
        db_path=db,
        verifier=verifier,
        query_model=ScriptedChatModel(script=sql),
        fx_client=FxClient(mode="fixtures", fault=fault, sleep=lambda _: None),
        index_root=index_root,
        case_memory=cases,
    )
    return investigate(agent, SCENARIOS[scenario_id]["questions"][question], thread_id=f"t-{scenario_id}")


def rows_of(result: InvestigationResult, evidence_id: str) -> list[dict[str, Any]]:
    """The rows of a `query_ledger` evidence, as objects."""
    data = json.loads(next(e for e in result.evidence if e.id == evidence_id).content)
    return [dict(zip(data["columns"], row, strict=True)) for row in data["rows"]]


def tools_of(result: InvestigationResult) -> list[str]:
    return [record.tool for record in result.tool_trace]


def labels(result: InvestigationResult) -> list[str]:
    return [v.label for v in result.verdicts]


def explain(result: InvestigationResult) -> str:
    """What the verifier decided, so the failure message says which claim failed and why."""
    return (
        "\n".join(
            f"{c.id} [{v.label}] {c.text!r} {v.note or ''}" for c, v in zip(result.claims, result.verdicts, strict=True)
        )
        + f"\ncoherence={result.coherence.issues} missing={result.missing_information}"
    )


def all_supported(result: InvestigationResult) -> None:
    assert result.verdicts and set(labels(result)) == {"supported"}, explain(result)
    assert result.coherence.passed, explain(result)


@pytest.fixture
def ctx(ledger_db: Path, index_root: Path, cases: CaseMemory) -> dict[str, Any]:
    return {"db": ledger_db, "index_root": index_root, "cases": cases}


# ---- S01 and S11: the same case, with and without the FX source -------------------------------------

FX_SQL = "SELECT kind, applied_rate, applied_at FROM fx_applied WHERE transaction_id = 'TX-2048' ORDER BY applied_at"


def s01_script() -> list[Any]:
    truth = SCENARIOS["S01"]["truth"]
    return [
        tool_call_message("query_ledger", {"question": "fx rates applied to TX-2048"}),
        tool_call_message("search_policies", {"query": "refund in another currency", "transform": "none"}),
        tool_call_message("get_reference_fx", {"from_currency": "EUR", "to_currency": "BRL", "date": "2026-10-20"}),
        tool_call_message(
            "calculate",
            {
                "operation": "fx_gap_breakdown",
                "values": {
                    "units": "100.00",
                    "charge_rate": truth["charge_rate"],
                    "refund_reference_rate": truth["reference_rate_refund_date"],
                    "refund_applied_rate": truth["applied_rate"],
                },
            },
        ),
        text_message(
            f"The refund paid out R$ {truth['refund_brl']} against R$ {truth['charge_brl']} charged [calc:1]. "
            f"The markup of the acquirer was R$ {truth['markup_brl']} [calc:1]."
        ),
    ]


@pytest.mark.parametrize("question", [0, 1])
def test_s01_the_fx_gap_is_explained_with_exact_numbers(ctx: dict[str, Any], question: int) -> None:
    s = SCENARIOS["S01"]
    result = run("S01", s01_script(), [FX_SQL], question=question, **ctx)

    assert tools_of(result) == s["expected_tools"]
    all_supported(result)
    assert result.requires_human_review is s["requires_human_review"]
    assert result.recommended_action == s["expected_action"]
    # the gap numbers come from the calculator, which uses Decimal on the rates read from the ledger
    gap = json.loads(next(e for e in result.evidence if e.id == "calc:1").content)["result"]
    assert (gap["charge"], gap["refund"], gap["gap"], gap["markup"], gap["rate_move"]) == (
        s["truth"]["charge_brl"],
        s["truth"]["refund_brl"],
        s["truth"]["gap_brl"],
        s["truth"]["markup_brl"],
        s["truth"]["rate_move_brl"],
    )
    # the applied rate the calculation got is the ledger's, not a made-up one
    ledger = {r["kind"]: r["applied_rate"] for r in rows_of(result, "sql:1")}
    assert ledger == {"charge": s["truth"]["charge_rate"], "refund": s["truth"]["applied_rate"]}
    assert any(v.method == "numeric" for v in result.verdicts)


def test_s11_without_the_fx_source_the_answer_stays_with_what_the_ledger_shows(ctx: dict[str, Any]) -> None:
    s = SCENARIOS["S11"]
    script = [
        tool_call_message("query_ledger", {"question": "payment and refund of TX-2048"}),
        tool_call_message("get_reference_fx", {"from_currency": "EUR", "to_currency": "BRL", "date": "2026-10-20"}),
        text_message("The ledger row shows payout_amount_minor 54931 for R-0731 [sql:1]."),
    ]
    sql = ["SELECT id, payout_amount_minor, payout_currency FROM refunds WHERE transaction_id = 'TX-2048'"]
    result = run("S11", script, sql, fault=True, **ctx)

    assert tools_of(result) == s["expected_tools"]
    assert result.tool_trace[-1].ok is False and result.tool_trace[-1].error_code == s["truth"]["fault_error"]
    assert result.requires_human_review is s["requires_human_review"]
    assert result.recommended_action == s["expected_action"]
    assert any("get_reference_fx" in item for item in result.missing_information)
    assert all(e.tool != "get_reference_fx" for e in result.evidence)
    assert "54931" in result.answer and "markup" not in result.answer.lower()


# ---- S02 to S06: questions answered by the ledger and the policies ---------------------------------


def test_s02_the_duplicate_charge_is_visible_in_the_ledger_rows(ctx: dict[str, Any]) -> None:
    s = SCENARIOS["S02"]
    t = s["truth"]
    script = [
        tool_call_message("query_ledger", {"question": "TX-2051 and TX-2052"}),
        tool_call_message(
            "search_policies",
            {
                "query": "two captures count as duplicates same merchant same card same amount same currency within "
                "5 minutes",
                "transform": "none",
            },
        ),
        text_message("TX-2052 and TX-2051 have amount_minor 4990 currency USD [sql:1]."),
    ]
    sql = [
        "SELECT id, merchant_id, card_fingerprint, amount_minor, currency, created_at FROM transactions "
        "WHERE id IN ('TX-2051', 'TX-2052') ORDER BY created_at"
    ]
    result = run("S02", script, sql, **ctx)

    assert tools_of(result) == s["expected_tools"]
    first, second = rows_of(result, "sql:1")
    assert (first["id"], second["id"]) == (t["original"], t["duplicate"])
    assert (first["merchant_id"], first["card_fingerprint"], first["amount_minor"], first["currency"]) == (
        second["merchant_id"],
        second["card_fingerprint"],
        second["amount_minor"],
        second["currency"],
    )
    assert second["amount_minor"] == t["refund_minor"] and t["currency"] == second["currency"]
    gap = datetime.fromisoformat(second["created_at"]) - datetime.fromisoformat(first["created_at"])
    assert gap.total_seconds() == t["seconds_apart"]
    assert "policy:duplicate-charges#detection-rule" in [e.id for e in result.evidence]
    assert result.requires_human_review is s["requires_human_review"], explain(result)
    assert result.recommended_action == s["expected_action"]


CHARGEBACK_SQL = "SELECT id, amount_minor, reason_code, stage, deadline FROM chargebacks WHERE id = 'CB-0310'"


def test_s03_the_chargeback_deadline_and_stage_come_from_the_ledger(ctx: dict[str, Any]) -> None:
    s = SCENARIOS["S03"]
    t = s["truth"]
    script = [
        tool_call_message("query_ledger", {"question": "chargeback CB-0310"}),
        tool_call_message("search_policies", {"query": "chargeback deadline", "transform": "none"}),
        text_message("CB-0310 has stage evidence_requested and deadline 2026-11-09 [sql:1]."),
    ]
    sql = [CHARGEBACK_SQL]
    result = run("S03", script, sql, **ctx)

    assert tools_of(result) == s["expected_tools"]
    (row,) = rows_of(result, "sql:1")
    assert (row["stage"], row["deadline"], row["reason_code"]) == (t["stage"], t["deadline"], t["reason_code"])
    assert f"{row['amount_minor'] / 100:.2f}" == t["amount"]
    assert (date.fromisoformat(t["deadline"]) - date.fromisoformat(t["as_of"])).days == t["days_to_deadline"]
    assert "contradicted" not in labels(result), explain(result)


def test_s03_a_critical_deadline_requires_human_review(ctx: dict[str, Any]) -> None:
    script = [
        tool_call_message("query_ledger", {"question": "chargeback CB-0310"}),
        tool_call_message("search_policies", {"query": "chargeback deadline", "transform": "none"}),
        text_message("CB-0310 has stage evidence_requested and deadline 2026-11-09 [sql:1]."),
    ]
    sql = [CHARGEBACK_SQL]
    result = run("S03", script, sql, **ctx)
    assert result.requires_human_review is SCENARIOS["S03"]["requires_human_review"]
    assert result.recommended_action == SCENARIOS["S03"]["expected_action"]
    assert any("policy:escalation-and-review#deadline-within-2-days" in m for m in result.missing_information)


def test_s04_an_unknown_id_is_an_empty_answer_not_an_error(ctx: dict[str, Any]) -> None:
    s = SCENARIOS["S04"]
    script = [
        tool_call_message("query_ledger", {"question": "status of TX-9999"}),
        text_message("The sql for TX-9999 has row_count 0 [sql:1]."),
    ]
    result = run("S04", script, ["SELECT id, status FROM transactions WHERE id = 'TX-9999'"], **ctx)

    assert tools_of(result) == s["expected_tools"]
    assert rows_of(result, "sql:1") == [] and json.loads(result.evidence[0].content)["row_count"] == 0
    assert result.requires_human_review is s["requires_human_review"], explain(result)
    assert result.recommended_action == s["expected_action"]
    assert result.missing_information == []


def test_s05_two_matches_in_different_merchants_are_both_returned(ctx: dict[str, Any]) -> None:
    s = SCENARIOS["S05"]
    script = [
        tool_call_message("query_ledger", {"question": "payments of C-0205 of 75.00 EUR"}),
        text_message("C-0205 has TX-2060 at M-03 and TX-2061 at M-17, both status captured [sql:1]."),
    ]
    sql = [
        "SELECT id, merchant_id, status, amount_minor, currency FROM transactions "
        "WHERE customer_id = 'C-0205' AND amount_minor = 7500 AND currency = 'EUR' ORDER BY id"
    ]
    result = run("S05", script, sql, **ctx)

    assert tools_of(result) == s["expected_tools"]
    found = [{"merchant_id": r["merchant_id"], "transaction_id": r["id"]} for r in rows_of(result, "sql:1")]
    assert found == s["truth"]["matches"]
    assert len({m["merchant_id"] for m in found}) == 2  # different merchants: not a duplicate
    assert result.requires_human_review is s["requires_human_review"], explain(result)
    assert result.recommended_action == s["expected_action"]


def test_s06_the_refund_outside_the_window_is_rejected_by_policy(ctx: dict[str, Any]) -> None:
    s = SCENARIOS["S06"]
    t = s["truth"]
    script = [
        tool_call_message("query_ledger", {"question": "refund R-0740 and its transaction"}),
        tool_call_message(
            "search_policies",
            {
                "query": "refunds accepted for 30 calendar days after capture, request after the window "
                "rejected outside_refund_window",
                "transform": "none",
            },
        ),
        text_message("R-0740 has status rejected and reason outside_refund_window [sql:1]."),
    ]
    sql = [
        "SELECT r.id, r.status, r.reason, t.captured_at, r.created_at FROM refunds r "
        "JOIN transactions t ON t.id = r.transaction_id WHERE r.id = 'R-0740'"
    ]
    result = run("S06", script, sql, question=1, **ctx)

    assert tools_of(result) == s["expected_tools"]
    (row,) = rows_of(result, "sql:1")
    assert (row["status"], row["reason"]) == (t["status"], t["reason"])
    captured, requested = date.fromisoformat(row["captured_at"][:10]), date.fromisoformat(row["created_at"][:10])
    assert (requested - captured).days == t["days_since_capture"] > t["refund_window_days"]
    assert f"policy:{t['policy_chunk']}" in [e.id for e in result.evidence]
    all_supported(result)
    assert result.requires_human_review is s["requires_human_review"]
    assert result.recommended_action == s["expected_action"]


# ---- S07 and S08: the arithmetic stays with the calculator ------------------------------------------


def test_s07_a_full_refund_has_no_difference(ctx: dict[str, Any]) -> None:
    s = SCENARIOS["S07"]
    t = s["truth"]
    script = [
        tool_call_message("query_ledger", {"question": "TX-2030 and refund R-0720"}),
        tool_call_message("calculate", {"operation": "difference", "values": {"a": t["charge"], "b": t["refund"]}}),
        text_message(f"The difference between charge and refund is {t['difference']} {t['currency']} [calc:1]."),
    ]
    sql = [
        "SELECT t.id, t.amount_minor, r.id AS refund_id, r.payout_amount_minor FROM transactions t "
        "JOIN refunds r ON r.transaction_id = t.id WHERE t.id = 'TX-2030'"
    ]
    result = run("S07", script, sql, **ctx)

    assert tools_of(result) == s["expected_tools"]
    (row,) = rows_of(result, "sql:1")
    assert f"{row['amount_minor'] / 100:.2f}" == t["charge"]
    assert f"{row['payout_amount_minor'] / 100:.2f}" == t["refund"]
    assert json.loads(result.evidence[-1].content)["result"] == t["difference"]
    all_supported(result)
    assert result.requires_human_review is s["requires_human_review"]
    assert result.recommended_action == s["expected_action"]


SETTLEMENT_SQL = (
    "SELECT id, merchant_id, gross_minor, refunds_minor, fees_minor, net_minor, expected_payout_date "
    "FROM settlements WHERE id = 'ST-0044'"
)


def s08_script() -> list[Any]:
    return [
        tool_call_message("query_ledger", {"question": "settlement ST-0044"}),
        tool_call_message("search_policies", {"query": "settlement schedule payout", "transform": "none"}),
        tool_call_message(
            "calculate",
            {"operation": "net_settlement", "values": {"gross": "30919.54", "refunds": "0.00", "fees": "926.67"}},
        ),
        text_message("The net settlement of ST-0044 is 29992.87 BRL [calc:1]."),
    ]


def test_s08_the_settlement_arithmetic_matches_the_ledger(ctx: dict[str, Any]) -> None:
    s = SCENARIOS["S08"]
    t = s["truth"]
    result = run("S08", s08_script(), [SETTLEMENT_SQL], **ctx)

    assert tools_of(result) == s["expected_tools"]
    (row,) = rows_of(result, "sql:1")
    assert (row["gross_minor"], row["refunds_minor"], row["fees_minor"], row["net_minor"]) == (
        t["gross_minor"],
        t["refunds_minor"],
        t["fees_minor"],
        t["net_minor"],
    )
    assert row["expected_payout_date"] == t["recomputed_payout_date"]
    assert row["net_minor"] == row["gross_minor"] - row["refunds_minor"] - row["fees_minor"]
    assert json.loads(next(e for e in result.evidence if e.id == "calc:1").content)["result"] == "29992.87"
    assert result.coherence.passed, explain(result)
    assert result.requires_human_review is s["requires_human_review"], explain(result)
    assert result.recommended_action == s["expected_action"]


def test_s08_a_settlement_whose_net_does_not_add_up_is_caught_by_the_coherence_rule(
    ctx: dict[str, Any], tmp_path: Path
) -> None:
    broken = tmp_path / "broken.db"
    shutil.copy(ctx["db"], broken)
    with sqlite3.connect(broken) as conn:
        conn.execute(
            "PRAGMA ignore_check_constraints = ON"
        )  # the real database refuses this; the rule is the second defense
        conn.execute("UPDATE settlements SET net_minor = net_minor + 1 WHERE id = 'ST-0044'")
    result = run("S08", s08_script(), [SETTLEMENT_SQL], **{**ctx, "db": broken})

    assert [i.rule for i in result.coherence.issues] == ["settlement_net"], explain(result)
    assert result.requires_human_review is True
    assert result.recommended_action == "escalate_to_human"


def test_s08_the_same_check_runs_on_the_ledger_api_settlements(ctx: dict[str, Any], tmp_path: Path) -> None:
    broken = tmp_path / "broken_api.db"
    shutil.copy(ctx["db"], broken)
    with sqlite3.connect(broken) as conn:
        conn.execute("PRAGMA ignore_check_constraints = ON")
        conn.execute("UPDATE settlements SET fees_minor = fees_minor + 1 WHERE id = 'ST-0044'")
    script = [
        tool_call_message(
            "get_ledger_record",
            {"kind": "merchant_settlements", "id": "M-03", "date_from": "2026-10-05", "date_to": "2026-10-11"},
        ),
        text_message("The settlements of M-03 were listed [api:1]."),
    ]
    result = run("S08", script, [], **{**ctx, "db": broken})
    assert "settlement_net" in {i.rule for i in result.coherence.issues}, explain(result)
    assert result.requires_human_review is True


# ---- S09 to S12 -------------------------------------------------------------------------------------


def test_s09_text_inside_data_is_reported_and_triggers_no_tool(ctx: dict[str, Any]) -> None:
    s = SCENARIOS["S09"]
    t = s["truth"]
    script = [
        tool_call_message("query_ledger", {"question": "status of refund R-0750"}),
        text_message("R-0750 has status requested [sql:1]."),
    ]
    sql = ["SELECT id, transaction_id, status, reason FROM refunds WHERE id = 'R-0750'"]
    result = run("S09", script, sql, **ctx)

    assert tools_of(result) == s["expected_tools"] == ["query_ledger"]
    (row,) = rows_of(result, "sql:1")
    assert row["reason"] == t["injected_text"] and row["status"] == t["status"]  # it arrived as data
    assert [r.tool for r in result.tool_trace if r.tool != "query_ledger"] == []  # and no order was followed
    assert result.requires_human_review is s["requires_human_review"], explain(result)
    assert result.recommended_action == s["expected_action"]
    assert any("policy:escalation-and-review#suspicious-text" in item for item in result.missing_information)


def test_s10_a_currency_the_source_does_not_publish_is_missing_information(ctx: dict[str, Any]) -> None:
    s = SCENARIOS["S10"]
    t = s["truth"]
    script = [
        tool_call_message("query_ledger", {"question": "TX-2099"}),
        tool_call_message("get_reference_fx", {"from_currency": "EUR", "to_currency": "ARS", "date": "2026-10-15"}),
        text_message("The reference rate for ARS is not available."),
    ]
    sql = ["SELECT id, amount_minor, currency, created_at FROM transactions WHERE id = 'TX-2099'"]
    result = run("S10", script, sql, **ctx)

    assert tools_of(result) == s["expected_tools"]
    assert result.tool_trace[-1].error_code == t["expected_error"]
    (row,) = rows_of(result, "sql:1")
    assert row["currency"] == t["currency"] and f"{row['amount_minor'] / 100:.2f}" == t["amount"]
    assert result.requires_human_review is s["requires_human_review"]
    assert result.recommended_action == s["expected_action"]
    assert any("get_reference_fx" in item for item in result.missing_information)


def test_s12_a_past_case_is_recalled_from_memory(ctx: dict[str, Any]) -> None:
    s = SCENARIOS["S12"]
    t = s["truth"]
    script = [
        tool_call_message("recall_cases", {"query": "fx markup on refunds", "merchant_id": "M-17"}),
        text_message(f"{t['finding']} [case:{t['case_id']}]."),
    ]
    result = run("S12", script, [], **ctx)

    assert tools_of(result) == s["expected_tools"]
    assert [e.id for e in result.evidence] == [f"case:{t['case_id']}"]
    recalled = json.loads(result.evidence[0].content)
    assert recalled["kind"] == t["kind"] and recalled["finding"] == t["finding"]
    assert result.requires_human_review is s["requires_human_review"], explain(result)
    assert result.recommended_action == s["expected_action"]


# ---- turns with no tool and answers with no citation ----------------------------------------------


def test_a_turn_without_tools_or_evidence_goes_through_the_real_verifier(ctx: dict[str, Any]) -> None:
    result = run("S01", [text_message("You are welcome. Can I help with anything else?")], [], **ctx)

    assert result.tool_trace == [] and result.evidence == []
    assert result.requires_human_review is True  # nothing was looked up: no factual answer holds
    assert result.coherence.passed and "contradicted" not in labels(result)


def test_a_factual_answer_without_citations_is_flagged_not_matched_by_content(ctx: dict[str, Any]) -> None:
    script = [
        tool_call_message("query_ledger", {"question": "status of TX-9999"}),
        text_message("The sql for TX-9999 has row_count 0."),  # the same sentence as S04, without the citation
    ]
    result = run("S04", script, ["SELECT id, status FROM transactions WHERE id = 'TX-9999'"], **ctx)

    assert labels(result) == ["not_enough_evidence"]
    assert result.requires_human_review is True
    assert any("row_count 0" in item for item in result.missing_information)


def test_the_integrator_prompt_tells_the_model_to_cite_evidence_ids_in_brackets() -> None:
    from ledgerlens.agents.integrator import INTEGRATOR_SYSTEM_PROMPT, build_integrator

    assert "[sql:1]" in INTEGRATOR_SYSTEM_PROMPT and "brackets" in INTEGRATOR_SYSTEM_PROMPT
    assert build_integrator(ScriptedChatModel(script=[])).system_prompt == INTEGRATOR_SYSTEM_PROMPT


def test_every_scenario_of_the_file_is_covered_by_a_test_here() -> None:
    covered = {f"S{n:02d}" for n in range(1, 13)}
    assert set(SCENARIOS) == covered
