"""The measurement of the comparison of the studio: the script, the registration and the decision.

What they guarantee, and why: (a) the script of the measurement refuses to run offline, because the single agent
replays the script of the case when the model is scripted and a comparison over scripted answers measures the
plumbing and not the runtime; (b) the manifest of the experiment is pinned by the first run, and a manifest
written after the first run is refused, because a registration that may be rewritten after the run is not a
registration; (c) the decision that follows the result is the rule the manifest registered, and not a decision
of the reader; (d) the arm of the studio runs offline with the scripted model, with the real tools of the
repository and the real verifier, so the plumbing of the arm is tested with no key and no network.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from ledgerlens.eval.dataset import CASES_PATH, EvalCase, load_cases
from ledgerlens.eval.evaluators import correctness
from ledgerlens.eval.routing_comparison import ComparisonWorld
from ledgerlens.offline import ScriptedChatModel
from ledgerlens.orchestration.comparison import (
    ArmMeasures,
    CaseMeasures,
    ComparisonRefused,
    build_report,
    decide,
    ensure_preregistered,
    record_run,
    render_markdown,
    run_studio_arm,
    specialist_for,
)
from ledgerlens.schemas import Entities, PlanStep, Triage

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "data" / "runtime" / "orchestration" / "comparison.json"


def _manifest(path: Path, body: str = '{"section": "experiment", "experiment_id": "x"}\n') -> Path:
    """A manifest of an experiment in a temporary folder."""
    path.write_text(body, encoding="utf-8")
    return path


def _measures(
    case_id: str,
    *,
    correctness: float = 1.0,
    tool_calls: int = 3,
    latency_ms: int = 1200,
    usd: Decimal | None = Decimal("0.0024"),
    money_reason: str = "",
) -> CaseMeasures:
    """The measures of one case, with the numbers a run would report."""
    return CaseMeasures(
        case_id=case_id,
        answer="an answer",
        correctness=correctness,
        missing_facts=(),
        tool_calls=tool_calls,
        latency_ms=latency_ms,
        input_tokens=1000,
        output_tokens=500,
        usd=usd,
        money_reason=money_reason,
    )


def _arm(name: str, cases: list[CaseMeasures]) -> ArmMeasures:
    """The measures of an arm over its cases."""
    return ArmMeasures(name=name, description=f"The arm {name}.", cases=tuple(cases))


def _world(tmp_path: Path) -> ComparisonWorld:
    """A world with a ledger file, for the digest of the report."""
    ledger = tmp_path / "ledger.db"
    ledger.write_bytes(b"the ledger of the test")
    return ComparisonWorld(root=tmp_path, db_path=ledger)


def test_the_script_of_the_measurement_refuses_to_run_offline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The comparison calls a real model, so it refuses offline and says why."""
    from scripts.measure_orchestration import measure

    monkeypatch.setenv("LEDGERLENS_OFFLINE", "1")
    with pytest.raises(RuntimeError, match="cannot run offline"):
        measure(tmp_path)


def test_the_first_run_pins_the_manifest_and_the_same_manifest_runs_again(tmp_path: Path) -> None:
    """The registration may be amended before the first run, and the first run pins it."""
    manifest = _manifest(tmp_path / "comparison.json")
    runs = tmp_path / "runs.jsonl"

    ensure_preregistered(manifest, runs)  # no run happened yet: the registration may still be amended
    record_run(runs, manifest_path=manifest, commit="abc123", result_name="result.json")
    ensure_preregistered(manifest, runs)  # the same manifest runs again


def test_the_manifest_written_after_the_first_run_is_refused(tmp_path: Path) -> None:
    """A registration that may be rewritten after the run is not a registration."""
    manifest = _manifest(tmp_path / "comparison.json")
    runs = tmp_path / "runs.jsonl"
    record_run(runs, manifest_path=manifest, commit="abc123", result_name="result.json")

    _manifest(manifest, '{"section": "experiment", "experiment_id": "rewritten"}\n')
    with pytest.raises(ComparisonRefused, match="written after the first run"):
        ensure_preregistered(manifest, runs)


def test_the_decision_keeps_the_flag_off_when_the_difference_is_a_trend() -> None:
    """A difference of 0 or 1 case is a trend and not a gain, whatever the money says."""
    decision = decide(
        difference_cases=1,
        threshold_cases=2,
        interval={"low": 0.01, "high": 0.05},
        money_known=True,
        single_cost=Decimal("0.01"),
        studio_cost=Decimal("0.005"),
    )

    assert decision["outcome"] == "the flag stays off"
    assert "trend" in decision["reason"]


def test_the_decision_keeps_the_flag_off_when_the_interval_covers_zero() -> None:
    """An interval that covers zero keeps the flag off, because the difference is not established."""
    decision = decide(
        difference_cases=2,
        threshold_cases=2,
        interval={"low": -0.02, "high": 0.15},
        money_known=True,
        single_cost=Decimal("0.01"),
        studio_cost=Decimal("0.005"),
    )

    assert decision["outcome"] == "the flag stays off"
    assert "covers zero" in decision["reason"]


def test_the_decision_keeps_the_flag_off_when_the_money_is_unknown() -> None:
    """When the money of an arm is unknown, the comparison of the money is not established."""
    decision = decide(
        difference_cases=3,
        threshold_cases=2,
        interval={"low": 0.02, "high": 0.15},
        money_known=False,
        single_cost=None,
        studio_cost=None,
    )

    assert decision["outcome"] == "the flag stays off"
    assert "not established" in decision["reason"]


def test_the_decision_keeps_the_flag_off_when_the_studio_costs_more() -> None:
    """A studio that costs more and answers the same is not a gain."""
    decision = decide(
        difference_cases=3,
        threshold_cases=2,
        interval={"low": 0.02, "high": 0.15},
        money_known=True,
        single_cost=Decimal("0.005"),
        studio_cost=Decimal("0.01"),
    )

    assert decision["outcome"] == "the flag stays off"
    assert "costs more" in decision["reason"]


def test_the_decision_is_a_gain_only_when_the_rule_is_met() -> None:
    """The gain asks for the threshold, the interval and the money, all of them."""
    decision = decide(
        difference_cases=3,
        threshold_cases=2,
        interval={"low": 0.02, "high": 0.15},
        money_known=True,
        single_cost=Decimal("0.01"),
        studio_cost=Decimal("0.005"),
    )

    assert decision["outcome"] == "gain"
    assert "the experiment that is registered here" in decision["reason"]


def test_the_specialist_of_a_tool_outside_the_registry_is_a_refusal() -> None:
    """A step that no specialist may run is a step outside the policy of the studio."""
    assert specialist_for("query_ledger") == "ledger_reader"
    with pytest.raises(ComparisonRefused, match="no specialist"):
        specialist_for("drop_table")


def test_the_money_of_the_dated_name_of_a_model_is_the_money_of_the_alias() -> None:
    """The provider serves the dated snapshot of the alias, and the price of the alias is its price."""
    from ledgerlens.byok.registry import ProviderRegistry
    from ledgerlens.orchestration.comparison import _money_of_usage

    registry = ProviderRegistry()
    dated = _money_of_usage(
        registry,
        {"gpt-4.1-mini-2025-04-14": {"input_tokens": 1000, "output_tokens": 500}},
    )
    alias = _money_of_usage(registry, {"gpt-4.1-mini": {"input_tokens": 1000, "output_tokens": 500}})

    assert dated == alias
    assert dated[0] is not None


def _policy_case() -> EvalCase:
    """A case of a policy question: one step, one tool, and the fact is the chunk of the policy."""
    return next(case for case in load_cases(CASES_PATH) if case.expected_tools == ["search_policies"])


def _triage_of(case: EvalCase, tools: list[str]) -> str:
    """The triage of the case, with one step per tool and a last one with no tool, which writes the answer."""
    plan = [
        PlanStep(id=f"S{index}", goal=f"use {tool}", tool=tool, depends_on=[f"S{index - 1}"] if index > 1 else [])
        for index, tool in enumerate(tools, start=1)
    ]
    plan.append(PlanStep(id=f"S{len(tools) + 1}", goal="write the answer with evidence", depends_on=[plan[-1].id]))
    return Triage(intent="other", entities=Entities(), urgency="normal", plan=plan).model_dump_json()


def test_the_studio_arm_answers_a_case_offline_with_the_scripted_model(tmp_path: Path) -> None:
    """The arm of the studio runs with no key: the scripted model, the real tools and the real verifier.

    Why the oracle is the judge of the repository: the score of the case is the score of the deterministic
    judge over the answer the arm produced, and not a number the test made up.
    """
    from ledgerlens.eval.run import build_offline_world

    case = _policy_case()
    world = build_offline_world(tmp_path)
    model = ScriptedChatModel(
        script=[
            _triage_of(case, ["search_policies"]),
            json.dumps({"query": case.question, "k": 8, "transform": "none"}),
        ]
    )
    from ledgerlens.config import Settings

    outcomes = run_studio_arm(
        [case],
        ComparisonWorld(root=world.root, db_path=world.db_path),
        settings=Settings(orchestration_studio=True),
        model=model,
        model_name="openai:gpt-4.1-mini",
        query_model=model,
        policy_model=model,
        index_root=world.index_root,
        embeddings=world.embeddings,
        concurrency=1,
    )

    outcome = outcomes.cases[0]
    assert outcome.answer
    assert outcome.tool_calls == 1
    assert outcome.reason == ""
    assert outcome.usd is None
    assert "no usage" in outcome.money_reason
    expected = correctness(outputs={"answer": outcome.answer}, reference_outputs={"facts": list(case.expected_facts)})
    assert outcome.correctness == expected["score"]
    assert outcome.correctness == 1.0


def test_the_studio_arm_refuses_a_plan_with_a_tool_outside_the_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A plan with a tool outside the registry is a case that did not run, and the reason names the tool.

    Why the registry is emptied for the test: the schema of the triage only names the tools of the contract, so
    the way a plan meets a tool with no specialist is a registry that lost the specialist of the tool.
    """
    from ledgerlens.config import Settings
    from ledgerlens.eval.run import build_offline_world
    from ledgerlens.orchestration.specialists import SPECIALISTS

    monkeypatch.delitem(SPECIALISTS, "calculator")
    case = _policy_case()
    world = build_offline_world(tmp_path)
    model = ScriptedChatModel(script=[_triage_of(case, ["calculate"])])

    outcomes = run_studio_arm(
        [case],
        ComparisonWorld(root=world.root, db_path=world.db_path),
        settings=Settings(orchestration_studio=True),
        model=model,
        model_name="openai:gpt-4.1-mini",
        query_model=model,
        policy_model=model,
        index_root=world.index_root,
        embeddings=world.embeddings,
        concurrency=1,
    )

    outcome = outcomes.cases[0]
    assert outcome.correctness == 0.0
    assert outcome.answer == ""
    assert "calculate" in outcome.reason


def _report(tmp_path: Path, single: ArmMeasures, studio: ArmMeasures) -> dict:
    """The report of the comparison over three fabricated cases."""
    cases = load_cases(CASES_PATH)[:3]
    return build_report(
        single,
        studio,
        cohort=cases,
        world=_world(tmp_path),
        cases_path=CASES_PATH,
        manifest_path=MANIFEST,
        model_name="openai:gpt-4.1-mini",
        commit="abc123",
        threshold_cases=2,
        rule_text="the rule of the manifest",
        uncertainty_text="the uncertainty of the manifest",
    )


def test_the_report_carries_the_denominator_the_uncertainty_and_the_decision(tmp_path: Path) -> None:
    """Every number of the report carries the set it was measured over and the decision that follows it."""
    cases = load_cases(CASES_PATH)[:3]
    single = _arm(
        "single_agent",
        [_measures(case.id, correctness=1.0 if index < 2 else 0.0) for index, case in enumerate(cases)],
    )
    studio = _arm("orchestration_studio", [_measures(case.id) for case in cases])

    report = _report(tmp_path, single, studio)

    assert report["cohort"]["cases"] == 3
    assert report["arms"]["single_agent"]["correct_cases"] == {"cases": 2, "of": 3}
    assert report["arms"]["orchestration_studio"]["correct_cases"] == {"cases": 3, "of": 3}
    assert report["difference"]["cases"] == 1
    assert report["difference"]["interval"]["low"] <= report["difference"]["interval"]["high"]
    assert report["decision"]["outcome"] == "the flag stays off"
    assert report["uncertainty"] == "the uncertainty of the manifest"


def test_the_page_carries_the_two_arms_the_denominator_the_uncertainty_and_the_decision(tmp_path: Path) -> None:
    """The page of the result names the two arms, the denominator, the uncertainty and the decision."""
    cases = load_cases(CASES_PATH)[:3]
    single = _arm("single_agent", [_measures(case.id) for case in cases])
    studio = _arm("orchestration_studio", [_measures(case.id) for case in cases])

    text = render_markdown(_report(tmp_path, single, studio))

    assert "## The arm `single_agent`" in text
    assert "## The arm `orchestration_studio`" in text
    assert "the denominator of every measure is the 3 cases of the set" in text
    assert "The interval of the difference of the correctness is" in text
    assert "The decision: **the flag stays off**" in text
    assert "is not a generalization" in text
