"""The comparison of the routes: two arms over the same cases, with the denominator of every number.

What they guarantee, and why: (a) both arms run over the same cohort of cases and over the same ledger, so the
comparison compares two routes and not two problems; (b) every number of the report carries the set of cases it
was measured over and the number of cases behind it, because a share without its denominator is a number about
nothing in particular (FR-010); (c) the money of a model whose price nobody verified is unknown and never zero
(ADR-078), and the money of a run that reported no usage at all is unknown and not a number of zero; (d) the
answers are scored by the deterministic judge of the repository and not by a number of the test; (e) the script of
the measurement refuses to run offline, because a comparison over scripted answers measures the plumbing and not
the routing.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ledgerlens.byok.registry import ProviderRegistry
from ledgerlens.eval.dataset import EvalCase, build_sample_ledger, load_cases
from ledgerlens.eval.evaluators import correctness
from ledgerlens.eval.routing_comparison import (
    ARM_CASCADE,
    ARM_ONE_MODEL,
    Arm,
    ArmResult,
    CaseOutcome,
    _money_of,
    arms_of,
    build_report,
    build_world,
    render_markdown,
    run_arm,
)
from ledgerlens.offline import ScriptedChatModel, text_message

ROOT = Path(__file__).resolve().parents[2]
CASES_PATH = ROOT / "data" / "eval" / "eval_cases.jsonl"
SLOTS = ("agent", "triage", "sql", "policy")


@pytest.fixture(scope="module")
def cases() -> list[EvalCase]:
    """The cases of the evaluation, the ones the published report measured."""
    return load_cases(CASES_PATH)[:3]


@pytest.fixture(scope="module")
def world(tmp_path_factory: pytest.TempPathFactory):
    """The ledger of the comparison: the versioned sample, built once for the two arms."""
    root = tmp_path_factory.mktemp("routing")
    return build_world(root, db_path=build_sample_ledger(root / "ledger.db"))


def _outcome(
    case_id: str,
    *,
    model: str = "openai:gpt-4.1-mini",
    correctness: float = 1.0,
    calls: int = 4,
    tokens: int = 1200,
    usd: Decimal | None = Decimal("0.0024"),
    money_reason: str = "",
    intent: str = "refund_discrepancy",
) -> CaseOutcome:
    """One outcome of a case, with the numbers a run would report."""
    return CaseOutcome(
        case_id=case_id,
        intent=intent,
        correctness=correctness,
        missing_facts=(),
        calls={model: calls},
        input_tokens={model: tokens},
        output_tokens={model: tokens // 2},
        latency_ms=1500,
        usd=usd,
        money_reason=money_reason,
    )


def _arm(name: str, model: str) -> Arm:
    """An arm that puts one model in the four slots."""
    return Arm(name=name, description=f"One model in the four slots: {model}.", models={slot: model for slot in SLOTS})


def _result(arm: Arm, outcomes: list[CaseOutcome]) -> ArmResult:
    """The result of an arm, with the outcomes of its cases."""
    return ArmResult(arm=arm, cases=tuple(outcomes))


def _scripted_models(monkeypatch: pytest.MonkeyPatch) -> None:
    """Puts a scripted model in the four slots, so the comparison runs with no key and no network.

    Why the script is long enough for the whole run: the triage reads its answer twice when the first one does
    not parse, and the agent reads its answer once per turn of the graph.
    """
    from ledgerlens.eval import routing_comparison

    def models_of(arm: Arm) -> dict[str, Any]:
        return {slot: ScriptedChatModel(script=[text_message("No answer.")] * 6) for slot in arm.models}

    monkeypatch.setattr(routing_comparison, "_models_of", models_of)


def test_the_two_arms_run_over_the_same_cases_and_the_same_ledger(
    cases: list[EvalCase], world, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both arms see the same cohort and the same ledger: a comparison of two routes, not of two problems.

    Why the ledger is observed and not only the cases: two arms over two ledgers compare two routes over two
    problems, and the reader of the numbers cannot tell it from the number of the cases.
    """
    from ledgerlens.agents import integrator

    read: list[Path] = []
    original = integrator.build_integrator

    def spy(*args: Any, **kwargs: Any) -> Any:
        read.append(Path(kwargs["db_path"]))
        return original(*args, **kwargs)

    monkeypatch.setattr(integrator, "build_integrator", spy)
    _scripted_models(monkeypatch)
    arms = arms_of(("openai:gpt-4.1-mini", "openai:gpt-4.1"), one_model="openai:gpt-4.1-mini")
    results = [run_arm(arm, cases, world) for arm in arms]

    assert [result.arm.name for result in results] == [ARM_ONE_MODEL, ARM_CASCADE]
    assert {case.case_id for case in results[0].cases} == {case.case_id for case in results[1].cases}
    assert {case.case_id for case in results[0].cases} == {case.id for case in cases}
    assert read == [world.db_path] * (len(cases) * 2)
    assert len(set(read)) == 1


def test_the_answers_are_scored_by_the_deterministic_judge_of_the_repository(
    cases: list[EvalCase], world, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The score of a case is the score of the judge, and not a number the test made up.

    Why it matters: the accuracy of the comparison is only the accuracy of the judge, and a test that scores the
    answers with a number of its own proves nothing about the judge.
    """
    _scripted_models(monkeypatch)
    arm = _arm(ARM_ONE_MODEL, "openai:gpt-4.1-mini")
    result = run_arm(arm, cases, world)
    outcome = result.cases[0]

    expected = correctness(
        outputs={"answer": "No answer."},
        reference_outputs={"facts": list(cases[0].expected_facts)},
    )
    assert outcome.correctness == expected["score"]
    assert outcome.correctness < 1.0
    assert outcome.missing_facts


def test_the_money_of_a_run_that_reported_no_usage_is_unknown_and_never_zero(
    cases: list[EvalCase], world, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A run whose trace carries no usage has no money to state, and the money is unknown and not zero (ADR-078).

    Why it matters: the run of a scripted model reports no usage at all, and a money of zero for it would say
    that the arm was free, and the number of zero is the one number the repository never publishes as money.
    """
    _scripted_models(monkeypatch)
    arm = _arm(ARM_ONE_MODEL, "openai:gpt-4.1-mini")
    result = run_arm(arm, cases, world)
    outcome = result.cases[0]

    assert outcome.usd is None
    assert "no usage" in outcome.money_reason
    assert result.priced_usd is None


def test_every_number_of_the_report_carries_its_denominator_and_its_set(cases: list[EvalCase], world) -> None:
    """The report names the cohort, the ledger and the number of cases behind every share (FR-010)."""
    outcomes = [_outcome(case.id, correctness=1.0 if index < 2 else 0.5) for index, case in enumerate(cases)]
    arm = _arm(ARM_ONE_MODEL, "openai:gpt-4.1-mini")
    report = build_report([_result(arm, outcomes)], cohort=cases, world=world, cases_path=CASES_PATH)

    assert report["cohort"]["cases"] == len(cases)
    assert report["cohort"]["ids"] == [case.id for case in cases]
    assert report["cohort"]["digest"]
    assert report["ledger"]["sha256"] == world.digest()
    arm_report = report["arms"][ARM_ONE_MODEL]
    assert arm_report["accuracy"] == {"accuracy": round(2.5 / 3, 4), "cases": len(cases)}
    assert arm_report["correct_cases"] == {"cases": 2, "of": len(cases)}
    assert arm_report["latency_p95_ms"]["cases"] == len(cases)
    assert arm_report["cost_per_correct_case"]["correct_cases"] == 2
    assert arm_report["cost_per_correct_case"]["total_tokens"] == 1800 * len(cases)
    assert arm_report["fallback_rate"]["calls"] == 4 * len(cases)
    for values in arm_report["accuracy_by_intent"].values():
        assert values["cases"] == len(cases)
        assert 0.0 <= values["accuracy"] <= 1.0
    for values in arm_report["model_mix"].values():
        assert values["calls"] == 4 * len(cases)
        assert 0.0 <= values["share"] <= 1.0


def test_the_accuracy_by_intent_groups_the_cases_by_the_intent_of_the_run(cases: list[EvalCase], world) -> None:
    """Every intent of the run has its own group, with the cases behind it and the score of the group.

    Why it matters: the share of an intent is the share of the cases of that intent, and a report that groups
    every case under one name says nothing about the intents.
    """
    outcomes = [
        _outcome(cases[0].id, intent="refund_discrepancy", correctness=1.0),
        _outcome(cases[1].id, intent="refund_discrepancy", correctness=0.0),
        _outcome(cases[2].id, intent="policy_question", correctness=0.5),
    ]
    arm = _arm(ARM_ONE_MODEL, "openai:gpt-4.1-mini")
    report = build_report([_result(arm, outcomes)], cohort=cases, world=world, cases_path=CASES_PATH)
    by_intent = report["arms"][ARM_ONE_MODEL]["accuracy_by_intent"]

    assert set(by_intent) == {"refund_discrepancy", "policy_question"}
    assert by_intent["refund_discrepancy"] == {"accuracy": 0.5, "cases": 2}
    assert by_intent["policy_question"] == {"accuracy": 0.5, "cases": 1}


def test_the_report_carries_the_row_of_every_case_of_the_arm(cases: list[EvalCase], world) -> None:
    """A reader of the report checks a number against the case that produced it, and not only against the total."""
    arm = _arm(ARM_ONE_MODEL, "openai:gpt-4.1-mini")
    outcomes = [_outcome(case.id) for case in cases]
    report = build_report([_result(arm, outcomes)], cohort=cases, world=world, cases_path=CASES_PATH)
    rows = report["arms"][ARM_ONE_MODEL]["cases"]

    assert [row["case"] for row in rows] == [case.id for case in cases]
    assert all(row["calls_by_model"] for row in rows)
    assert all(row["latency_ms"] > 0 for row in rows)


def test_the_report_names_the_models_of_the_mix_the_way_the_arm_names_them(cases: list[EvalCase], world) -> None:
    """The report speaks one language: the names of the deployment, and not the bare names of the trace."""
    arm = _arm(ARM_ONE_MODEL, "openai:gpt-4.1-mini")
    outcomes = [_outcome(case.id, model="gpt-4.1-mini") for case in cases]
    report = build_report([_result(arm, outcomes)], cohort=cases, world=world, cases_path=CASES_PATH)
    arm_report = report["arms"][ARM_ONE_MODEL]

    assert set(arm_report["model_mix"]) == {"openai:gpt-4.1-mini"}
    assert arm_report["cases"][0]["calls_by_model"] == {"openai:gpt-4.1-mini": 4}


def test_the_report_says_that_the_rate_of_the_fallback_was_not_measured(cases: list[EvalCase], world) -> None:
    """A zero that nobody measured is not a zero that was measured."""
    arm = _arm(ARM_ONE_MODEL, "openai:gpt-4.1-mini")
    outcomes = [_outcome(case.id) for case in cases]
    report = build_report([_result(arm, outcomes)], cohort=cases, world=world, cases_path=CASES_PATH)
    fallback = report["arms"][ARM_ONE_MODEL]["fallback_rate"]

    assert fallback["measured"] is False
    assert fallback["reason"]
    assert "not measured" in render_markdown(report)


def test_the_report_names_the_judge_that_scored_the_arms(cases: list[EvalCase], world) -> None:
    """The report says what judged the arms, because the absolute numbers are not the online report's numbers."""
    arm = _arm(ARM_ONE_MODEL, "openai:gpt-4.1-mini")
    outcomes = [_outcome(case.id) for case in cases]
    report = build_report([_result(arm, outcomes)], cohort=cases, world=world, cases_path=CASES_PATH)

    assert report["judge"]["correctness"]
    assert report["judge"]["nli"]
    assert report["judge"]["runs_per_case"] == 1


def test_the_percentile_is_the_nearest_rank_and_not_a_rounded_one() -> None:
    """A percentile of 95 over 20 cases is the nineteenth case and not the twentieth."""
    from ledgerlens.eval.routing_comparison import _percentile

    values = list(range(1, 21))
    assert _percentile(values, 0.95) == 19
    assert _percentile(values, 0.5) == 10
    assert _percentile(list(range(1, 32)), 0.95) == 30


def test_the_money_of_a_model_nobody_priced_is_unknown_and_never_zero() -> None:
    """A price that was never verified is unknown, and the reason is named (ADR-078)."""
    registry = ProviderRegistry()

    priced = _money_of(
        registry,
        {"openai:gpt-4.1-mini": 2},
        {"openai:gpt-4.1-mini": 1000},
        {"openai:gpt-4.1-mini": 500},
    )
    assert priced[0] == Decimal("0.0012")
    assert priced[1] == "" and priced[2] == ()

    unpriced = _money_of(registry, {"openai:gpt-4.1": 2}, {"openai:gpt-4.1": 1000}, {"openai:gpt-4.1": 500})
    assert unpriced[0] is None
    assert "was never verified" in unpriced[1]
    assert unpriced[2] == ("openai:gpt-4.1",)

    silent = _money_of(registry, {"openai:gpt-4.1-mini": 2}, {"openai:gpt-4.1-mini": 0}, {"openai:gpt-4.1-mini": 0})
    assert silent[0] is None
    assert "no usage" in silent[1]

    uncounted = _money_of(registry, {}, {}, {})
    assert uncounted[0] is None
    assert "no usage" in uncounted[1]


def test_the_report_says_the_money_is_unknown_when_it_is(cases: list[EvalCase], world) -> None:
    """The report does not turn an absent price into a price of zero, and it says why."""
    arm = _arm(ARM_CASCADE, "openai:gpt-4.1")
    outcomes = [
        _outcome(case.id, model="openai:gpt-4.1", usd=None, money_reason="the price was never verified")
        for case in cases
    ]
    report = build_report([_result(arm, outcomes)], cohort=cases, world=world, cases_path=CASES_PATH)
    cost = report["arms"][ARM_CASCADE]["cost_per_correct_case"]

    assert cost["usd"] is None
    assert cost["usd_known"] is False
    assert cost["money_unknown_reason"]
    assert cost["tokens"] is not None


def test_an_arm_without_a_correct_case_has_no_money_per_correct_case(cases: list[EvalCase], world) -> None:
    """A money per correct case of an arm without a correct case is not a number and not a zero."""
    arm = _arm(ARM_ONE_MODEL, "openai:gpt-4.1-mini")
    outcomes = [_outcome(case.id, correctness=0.0) for case in cases]
    report = build_report([_result(arm, outcomes)], cohort=cases, world=world, cases_path=CASES_PATH)
    cost = report["arms"][ARM_ONE_MODEL]["cost_per_correct_case"]

    assert cost["correct_cases"] == 0
    assert cost["usd"] is None
    assert cost["usd_known"] is False
    assert "no case of the arm" in cost["money_unknown_reason"]
    assert cost["tokens"] is None


def test_the_arms_of_the_comparison_are_the_two_routes_the_deployment_declares() -> None:
    """The one model arm puts one model in the four slots, and the cascade arm routes by the task of the slot.

    Why the expectation comes from the router and not from a name written in the test: the cascade is a
    property of the allowlist and of the tiers of the slots, and a test that pins today's names passes when the
    router routes another way.
    """
    from ledgerlens.agents.routing import candidates_of, models_of, route
    from ledgerlens.byok.registry import ALLOWLIST, profiles_by_name

    cascade = ("openai:gpt-4.1-mini", "openai:gpt-4.1")
    expected = models_of(
        route(candidates_of(cascade, profiles_by_name(ALLOWLIST)), case_id="routing-comparison", case_type="cohort")
    )
    one, cascade_arm = arms_of(cascade, one_model="openai:gpt-4.1-mini")

    assert set(one.models.values()) == {"openai:gpt-4.1-mini"}
    assert cascade_arm.models == expected


def test_an_arm_that_names_no_model_for_a_slot_is_refused() -> None:
    """An arm with a slot without a model is a comparison nobody can read."""
    with pytest.raises(ValueError, match="names no model"):
        Arm(name="broken", description="x", models={"agent": "openai:gpt-4.1"})


def test_the_script_of_the_measurement_refuses_to_run_offline(tmp_path: Path) -> None:
    """The comparison calls a real model, so it refuses offline and says why."""
    from scripts.measure_routing import measure

    with pytest.raises(RuntimeError, match="cannot run offline"):
        measure(tmp_path)


def test_the_prose_of_the_comparison_carries_the_numbers_and_their_set(cases: list[EvalCase], world) -> None:
    """The markdown of the report names the cohort, the ledger and every arm with its numbers."""
    arm = _arm(ARM_ONE_MODEL, "openai:gpt-4.1-mini")
    outcomes = [_outcome(case.id) for case in cases]
    report = build_report([_result(arm, outcomes)], cohort=cases, world=world, cases_path=CASES_PATH)
    text = render_markdown(report)

    assert ARM_ONE_MODEL in text
    assert world.digest() in text
    assert json.loads(json.dumps(report)) == report
