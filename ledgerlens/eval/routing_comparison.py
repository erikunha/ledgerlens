"""Compares two routes over the same cohort of cases, with the same ledger.

Why it exists: the router of ADR-078 chooses the model of each slot of a run by the task the slot does, and
nobody measured what that choice costs against one model for the whole run. A router that nobody measured is a
preference, and this module is the measurement: it runs the same cohort of cases twice, over the same ledger,
once with one model in the four slots of the run and once with the cascade of the deployment.

Why every number carries its denominator and its set: a share without the number of cases behind it is a number
about nothing in particular. The report names the cohort the measurement was made over, the digest of the ledger
the two arms read and the number of cases behind every share.

Why the money is text or nothing: the price of a model that nobody verified is unknown, and unknown is never
zero (ADR-078). The comparison states the dollars of the models whose price the allowlist verified and states
that the money of the others is unknown, instead of turning an absent price into a price of zero.

Why the judge is the deterministic one: the comparison is about the routing and not about the judge, and the
verdicts of the two arms have to come from the same judge for the numbers to be comparable.

Why the two arms read the same ledger: a comparison over two different ledgers compares two different problems.
The ledger is built once, from the versioned sample, and both arms read that file.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from ledgerlens.agents.routing import SLOT_AGENT, SLOT_POLICY, SLOT_SQL, SLOT_TRIAGE, SLOTS
from ledgerlens.byok.registry import ProviderRegistry
from ledgerlens.eval.dataset import EvalCase
from ledgerlens.eval.evaluators import correctness

__all__ = [
    "ARM_CASCADE",
    "ARM_ONE_MODEL",
    "Arm",
    "ArmResult",
    "CaseOutcome",
    "ComparisonWorld",
    "build_report",
    "build_world",
    "render_markdown",
    "run_arm",
    "run_comparison",
]

# The names of the two arms of the comparison. The first is the behaviour the product had before the router
# existed: one model in the four slots of the run. The second is the choice of the router, read from the
# cascade of the deployment.
ARM_ONE_MODEL = "one_model"
ARM_CASCADE = "cascade"

# What judged the two arms, published with the numbers. Why it is in the report and not only in the code: the
# absolute numbers of this comparison are not the numbers of the published online report, and a reader of the
# JSON alone has to know it before it reads the accuracy.
JUDGE: Mapping[str, Any] = {
    "correctness": "the deterministic judge of the repository",
    "nli": "the stub of the NLI of the repository, the real model of the NLI is not called",
    "fx": "the fixtures of the exchange of the repository",
    "runs_per_case": 1,
    "comparable_with": "the other arm of this comparison and not with the published online report",
}

# The root of the repository. The report of a comparison is published, and it names the files of the repository the
# way the repository names them.
ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Arm:
    """One route of the comparison: the model of each of the four slots of the run.

    Why the models are the names of the deployment and not the objects of a provider: the report of a comparison
    is read by a stranger, and a stranger wants the name of the model that ran, not a client that holds a key.
    """

    name: str
    description: str
    models: Mapping[str, str]

    def __post_init__(self) -> None:
        missing = [slot for slot in SLOTS if slot not in self.models]
        if missing:
            raise ValueError(f"the arm {self.name!r} names no model for the slot(s) {missing}")

    def to_dict(self) -> dict[str, Any]:
        """The arm as a dictionary, for the report."""
        return {
            "name": self.name,
            "description": self.description,
            "models": {slot: self.models[slot] for slot in SLOTS},
        }


@dataclass(frozen=True)
class CaseOutcome:
    """What one case cost and what it answered, under one arm.

    Why the money is a number or nothing: the price of a model that nobody verified is unknown, and a number of
    zero would say that the call was free. The `money_reason` says why the money is unknown, and the
    `unpriced_models` name the models whose price the allowlist does not carry.
    """

    case_id: str
    intent: str
    correctness: float
    missing_facts: tuple[str, ...]
    calls: Mapping[str, int]
    input_tokens: Mapping[str, int]
    output_tokens: Mapping[str, int]
    latency_ms: int
    usd: Decimal | None
    money_reason: str = ""
    unpriced_models: tuple[str, ...] = ()

    @property
    def total_tokens(self) -> int:
        """The tokens of every call of the case."""
        return sum(self.input_tokens.values()) + sum(self.output_tokens.values())

    def to_dict(self, names: Mapping[str, str] | None = None) -> dict[str, Any]:
        """The outcome as a dictionary, for the report.

        Why the names of the deployment and not the bare names of the trace: a reader of the report joins the
        models of the mix with the models of the slots, and a report with two vocabularies is a report that has
        to be translated before it can be read.
        """
        names = names or {}
        return {
            "case": self.case_id,
            "intent": self.intent,
            "correctness": self.correctness,
            "missing_facts": list(self.missing_facts),
            "calls_by_model": {names.get(model, model): count for model, count in self.calls.items()},
            "input_tokens_by_model": {
                names.get(model, model): count for model, count in self.input_tokens.items()
            },
            "output_tokens_by_model": {
                names.get(model, model): count for model, count in self.output_tokens.items()
            },
            "latency_ms": self.latency_ms,
            "cost_usd": None if self.usd is None else str(self.usd),
            "money_reason": self.money_reason,
            "unpriced_models": list(self.unpriced_models),
        }


@dataclass(frozen=True)
class ArmResult:
    """The outcomes of one arm over the whole cohort."""

    arm: Arm
    cases: tuple[CaseOutcome, ...]

    @property
    def correct_cases(self) -> int:
        """The cases whose answer carried every expected fact."""
        return sum(1 for case in self.cases if case.correctness >= 1.0)

    @property
    def total_tokens(self) -> int:
        """The tokens of every call of the arm."""
        return sum(case.total_tokens for case in self.cases)

    @property
    def priced_usd(self) -> Decimal | None:
        """The money of the calls whose price is known, or None when one of them has no price.

        Why None and not a number: a price that was never verified is unknown, and unknown is never zero
        (ADR-078).
        """
        total = Decimal("0")
        for case in self.cases:
            if case.usd is None:
                return None
            total += case.usd
        return total

    @property
    def unpriced_models(self) -> tuple[str, ...]:
        """The models the arm called whose price the allowlist does not carry."""
        names: set[str] = set()
        for case in self.cases:
            names.update(case.unpriced_models)
        return tuple(sorted(names))

    @property
    def money_reason(self) -> str:
        """Why the money of the arm is unknown, and the empty string when it is known."""
        for case in self.cases:
            if case.usd is None:
                return case.money_reason
        return ""


@dataclass
class ComparisonWorld:
    """What the two arms share: the ledger they read and the folder of the memories of the runs."""

    root: Path
    db_path: Path

    def digest(self) -> str:
        """The digest of the ledger the arms read, so the report names the file of the measurement."""
        return hashlib.sha256(self.db_path.read_bytes()).hexdigest()


def build_world(root: Path, *, db_path: Path | None = None) -> ComparisonWorld:
    """The ledger of the comparison: the versioned sample, built once and read by the two arms."""
    from ledgerlens.eval.dataset import build_sample_ledger

    root.mkdir(parents=True, exist_ok=True)
    ledger = Path(db_path) if db_path is not None else build_sample_ledger(root / "ledger.db")
    return ComparisonWorld(root=root, db_path=ledger)


def arms_of(cascade: Sequence[str], *, one_model: str) -> tuple[Arm, Arm]:
    """The two arms of the comparison, read from the cascade of the deployment and from its own model.

    Why the arms are built from the declaration of the deployment and not from a list of the code: the
    comparison is about what the deployment would pay, and the deployment is the one that declares the cascade
    and the model it runs when it declares none.
    """
    from ledgerlens.agents.routing import candidates_of, models_of, route
    from ledgerlens.byok.registry import ALLOWLIST, profiles_by_name
    from ledgerlens.config import model_name

    profiles = profiles_by_name(ALLOWLIST)
    decisions = route(
        candidates_of(cascade, profiles),
        case_id="routing-comparison",
        case_type="cohort",
    )
    routed = models_of(decisions)
    return (
        Arm(
            name=ARM_ONE_MODEL,
            description=f"One model in the four slots of the run: {model_name(one_model)}.",
            models={slot: model_name(one_model) for slot in SLOTS},
        ),
        Arm(
            name=ARM_CASCADE,
            description="The model of each slot, chosen by the task the slot does, read from the cascade.",
            models={slot: routed[slot] for slot in SLOTS},
        ),
    )


def _names_of(arm: Arm) -> dict[str, str]:
    """The name of the deployment of every model of the arm, by the bare name the trace carries.

    Why the report needs it: the trace names a model by its identifier and the deployment names it by its
    provider, and the report of a comparison has to speak one language.
    """
    return {model.split(":", 1)[-1]: model for model in arm.models.values()}


def _models_of(arm: Arm) -> dict[str, Any]:
    """A chat model per slot of the arm, at temperature 0 so the two arms are as repeatable as possible."""
    from ledgerlens.config import get_chat_model

    return {slot: get_chat_model(model=arm.models[slot], temperature=0) for slot in SLOTS}


def run_arm(
    arm: Arm,
    cases: Sequence[EvalCase],
    world: ComparisonWorld,
    *,
    registry: ProviderRegistry | None = None,
) -> ArmResult:
    """Runs the cohort under one arm and collects what each case cost and what it answered.

    Why the judge is the deterministic one: the comparison is about the routing, and the two arms have to be
    judged by the same judge for the numbers to mean something.
    """
    from functools import partial

    from ledgerlens.agents.integrator import build_integrator, investigate
    from ledgerlens.memory.long_term import CaseMemory
    from ledgerlens.observability.trace import Span
    from ledgerlens.tools.fx import FxClient
    from ledgerlens.verify import verify_result
    from ledgerlens.verify.nli import StubNli

    registry = registry or ProviderRegistry()
    models = _models_of(arm)
    names = _names_of(arm)
    outcomes: list[CaseOutcome] = []
    for case in cases:
        spans: list[Span] = []
        memory = CaseMemory(world.root / "memory" / arm.name / case.id)
        agent = build_integrator(
            models[SLOT_AGENT],
            db_path=world.db_path,
            verifier=partial(verify_result, nli=StubNli(), ledger_db=world.db_path),
            query_model=models[SLOT_SQL],
            triage_model=models[SLOT_TRIAGE],
            policy_model=models[SLOT_POLICY],
            fx_client=FxClient(mode="fixtures", fault=case.fx_fault, sleep=lambda _: None),
            case_memory=memory,
            # The names of the models of the slots, as the arm names them: they are the names the cascade of the
            # deployment holds, and they are what the retry of a failed model reads (ADR-084).
            model_names=dict(arm.models),
        )
        result = investigate(agent, case.question, thread_id=f"routing-{arm.name}-{case.id}", on_event=spans.append)
        calls, input_tokens, output_tokens = _calls_of(spans)
        usd, reason, unpriced = _money_of(registry, calls, input_tokens, output_tokens, names)
        scores = correctness(outputs={"answer": result.answer}, reference_outputs={"facts": list(case.expected_facts)})
        outcomes.append(
            CaseOutcome(
                case_id=case.id,
                intent=_intent_of(result),
                correctness=float(scores["score"]),
                missing_facts=_missing_of(scores),
                calls=calls,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=_latency_of(spans),
                usd=usd,
                money_reason=reason,
                unpriced_models=unpriced,
            )
        )
    return ArmResult(arm=arm, cases=tuple(outcomes))


def _calls_of(spans: Sequence[Any]) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    """The calls of the models of a run, with the tokens of the input and of the output of each one.

    Why the trace and not the client of the provider: the trace is what the run published, and the money of the
    run has to be the money the trace says.
    """
    calls: dict[str, int] = {}
    input_tokens: dict[str, int] = {}
    output_tokens: dict[str, int] = {}
    for span in spans:
        model = str(span.metadata.get("model", "") or "")
        counted = span.metadata.get("tokens")
        if not model or not counted:
            continue
        calls[model] = calls.get(model, 0) + 1
        input_tokens[model] = input_tokens.get(model, 0) + int(counted.get("prompt", 0))
        output_tokens[model] = output_tokens.get(model, 0) + int(counted.get("completion", 0))
    return calls, input_tokens, output_tokens


def _money_of(
    registry: ProviderRegistry,
    calls: Mapping[str, int],
    input_tokens: Mapping[str, int],
    output_tokens: Mapping[str, int],
    names: Mapping[str, str] | None = None,
) -> tuple[Decimal | None, str, tuple[str, ...]]:
    """The money of the calls of an arm, or None and the reason why it is unknown.

    Why the names of the unpriced models come with the None: a reader has to know which part of the money is
    missing, and not only that some of it is. Why a run without usage is unknown and not zero: a number of zero
    would say that the call was free, and a scripted model reports no usage at all. Why a run with no call at all is
    unknown and not zero: a trace that carries no model of a run that called models is a trace that lost them, and
    the money of a run nobody counted is not a money of zero.

    Why the names of the deployment and not the bare names of the trace: the price of a model is the price of its
    identifier, and the reader of the report has to see the name it sees in the rest of the report.
    """
    names = names or {}
    if not calls:
        return None, "the run reported no usage of the models", ()
    total = Decimal("0")
    unpriced: list[str] = []
    for model in calls:
        bare = model.split(":", 1)[-1]
        if registry.price_for(bare) is None:
            unpriced.append(names.get(bare, model))
            continue
        money = registry.estimate_usd(
            bare,
            input_tokens=input_tokens.get(model, 0),
            output_tokens=output_tokens.get(model, 0),
        )
        total += money or Decimal("0")
    if unpriced:
        return None, f"the price of {', '.join(sorted(unpriced))} was never verified", tuple(sorted(unpriced))
    if sum(input_tokens.values()) + sum(output_tokens.values()) == 0:
        return None, "the run reported no usage of the models", ()
    return total, "", ()


def _intent_of(result: Any) -> str:
    """The intent the triage of the run gave the question, and not the one the answer key expects.

    Why the intent of the run and not the one of the manifest: the grouping of the accuracy by intent has to
    come from the run that was measured, and the triage of the run is what the run decided.
    """
    triage = getattr(result, "triage", None)
    return str(getattr(triage, "intent", "") or "unknown")


def _missing_of(scores: Mapping[str, Any]) -> tuple[str, ...]:
    """The facts the answer did not carry, read from the comment of the evaluator."""
    comment = str(scores.get("comment", ""))
    if not comment.startswith("missing: "):
        return ()
    return tuple(item.strip() for item in comment[len("missing: ") :].split(", ") if item.strip())


def _latency_of(spans: Sequence[Any]) -> int:
    """The latency of the calls of the model of the run, in milliseconds."""
    return sum(int(span.latency_ms or 0) for span in spans if span.metadata.get("model"))


def _percentile(values: Sequence[int], percentile: float) -> int:
    """The percentile of a list of numbers, by the nearest rank.

    Why the nearest rank and not an interpolation: a latency is the measurement of one run, and the number of a
    run is the number of a run, not a point between two runs. The nearest rank is the ceil of the percentile
    times the count, minus one, and not a rounded one: a percentile of 95 over 31 cases is the thirtieth case and
    not the twenty-ninth.
    """
    if not values:
        return 0
    ordered = sorted(values)
    rank = math.ceil(percentile * len(ordered))
    index = max(0, min(len(ordered) - 1, rank - 1))
    return ordered[index]


def build_report(
    results: Sequence[ArmResult],
    *,
    cohort: Sequence[EvalCase],
    world: ComparisonWorld,
    cases_path: Path | None = None,
    note: str = "",
) -> dict[str, Any]:
    """The report of the comparison, with the denominator and the set of every number."""
    return {
        "mode": "online",
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "judge": dict(JUDGE),
        "cohort": {
            "cases": len(cohort),
            "ids": [case.id for case in cohort],
            "digest": _digest_of(cases_path),
            "source": _source_of(cases_path),
        },
        "ledger": {"sha256": world.digest(), "source": "the versioned sample of the repository"},
        "arms": {result.arm.name: _arm_report(result) for result in results},
        "note": note,
    }


def _digest_of(path: Path | None) -> str:
    """The digest of the file of the cases, or an empty string when the file is not known."""
    if path is None or not Path(path).is_file():
        return ""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _source_of(path: Path | None) -> str:
    """The path of the cases as the repository names it, never as the machine that measured names it.

    Why: the report is published, and a published file that carries the home directory of the machine that wrote it
    says something about the machine and not about the measurement.
    """
    if path is None:
        return "the cases of the evaluation"
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return Path(path).name


def _money_per_correct_case(priced: Decimal | None, correct: int) -> str | None:
    """The money of a correct case of an arm, or None when there is no such money.

    Why None and not a number of zero when no case of the arm was correct: the money of a correct case is the
    money of a case that does not exist, and a number of zero would say that the arm was free.
    """
    if priced is None or not correct:
        return None
    return str((priced / correct).quantize(Decimal("0.000001")))


def _money_reason(priced: Decimal | None, correct: int, reason: str) -> str:
    """Why the money of the arm is unknown, and the empty string when it is known.

    Why the reason of an arm without a correct case is not the reason of the price: the price of the models was
    verified and the money is known, and what is missing is a case to divide it by.
    """
    if priced is None:
        return reason
    if not correct:
        return "no case of the arm carried every expected fact, so there is no money per correct case"
    return ""


def _arm_report(result: ArmResult) -> dict[str, Any]:
    """The numbers of one arm, each with the number of cases behind it."""
    cases = result.cases
    by_intent: dict[str, list[float]] = {}
    for case in cases:
        by_intent.setdefault(case.intent, []).append(case.correctness)
    accuracy_by_intent = {
        intent: {"accuracy": round(sum(scores) / len(scores), 4), "cases": len(scores)}
        for intent, scores in sorted(by_intent.items())
    }
    accuracy = round(sum(case.correctness for case in cases) / len(cases), 4) if cases else 0.0
    correct = result.correct_cases
    priced = result.priced_usd
    calls_by_model: dict[str, int] = {}
    tokens_by_model: dict[str, int] = {}
    for case in cases:
        for model, count in case.calls.items():
            calls_by_model[model] = calls_by_model.get(model, 0) + count
        for model, count in case.input_tokens.items():
            tokens_by_model[model] = tokens_by_model.get(model, 0) + count
        for model, count in case.output_tokens.items():
            tokens_by_model[model] = tokens_by_model.get(model, 0) + count
    total_calls = sum(calls_by_model.values())
    latencies = [case.latency_ms for case in cases]
    names = _names_of(result.arm)
    return {
        "arm": result.arm.to_dict(),
        "accuracy": {"accuracy": accuracy, "cases": len(cases)},
        "accuracy_by_intent": accuracy_by_intent,
        "correct_cases": {"cases": correct, "of": len(cases)},
        "cost_per_correct_case": {
            "usd": _money_per_correct_case(priced, correct),
            "usd_known": priced is not None and correct > 0,
            "money_unknown_reason": _money_reason(priced, correct, result.money_reason),
            "unpriced_models": list(result.unpriced_models),
            "tokens": str(result.total_tokens // correct) if correct else None,
            "total_tokens": result.total_tokens,
            "correct_cases": correct,
        },
        "latency_p95_ms": {"value": _percentile(latencies, 0.95), "cases": len(latencies)},
        "fallback_rate": {
            "value": 0.0,
            "calls": total_calls,
            "fallbacks": 0,
            "measured": False,
            "reason": "the repository has no fallback with a budget in this path, so the rate was not measured",
        },
        "model_mix": {
            names.get(model, model): {
                "calls": count,
                "share": round(count / total_calls, 4) if total_calls else 0.0,
                "tokens": tokens_by_model.get(model, 0),
            }
            for model, count in sorted(calls_by_model.items())
        },
        # The row of every case, so that a reader of the report can check a number against the case that
        # produced it and not only against the total of the arm.
        "cases": [case.to_dict(names) for case in cases],
    }


def _arm_order(report: Mapping[str, Any]) -> list[str]:
    """The arms of the report in the order the prose tells them, and not in the order of the keys.

    Why the order is fixed: the report is written with the keys sorted, and a prose that followed the order of
    the keys would put the arm of the cascade before the arm of one model, and the same report would be read
    in two orders.
    """
    arms = report.get("arms", {})
    order = [ARM_ONE_MODEL, ARM_CASCADE]
    return [name for name in order if name in arms] + [name for name in arms if name not in order]


def render_markdown(report: dict[str, Any]) -> str:
    """The report as the markdown of the page of the routing."""
    lines = ["# The comparison of the routes", ""]
    if report.get("note"):
        lines += [str(report["note"]), ""]
    cohort = report.get("cohort", {})
    lines += [
        f"The cohort is {cohort.get('cases', 0)} cases, the digest of the file is `{cohort.get('digest', '')}` and "
        f"the ledger of the two arms is `{report.get('ledger', {}).get('sha256', '')}`.",
        "",
    ]
    for name in _arm_order(report):
        arm = report["arms"][name]
        lines += [f"## The arm `{name}`", "", str(arm.get("arm", {}).get("description", "")), ""]
        lines += ["| Slot | The model of the slot |", "| --- | --- |"]
        for slot, model in arm.get("arm", {}).get("models", {}).items():
            lines.append(f"| {slot} | {model} |")
        lines.append("")
        accuracy = arm.get("accuracy", {})
        lines.append(
            f"The accuracy is {accuracy.get('accuracy', 0)} over {accuracy.get('cases', 0)} cases, and "
            f"{arm.get('correct_cases', {}).get('cases', 0)} of them carried every expected fact."
        )
        lines.append("")
        lines += ["| Intent | The accuracy | The cases |", "| --- | --- | --- |"]
        for intent, values in arm.get("accuracy_by_intent", {}).items():
            lines.append(f"| {intent} | {values.get('accuracy')} | {values.get('cases')} |")
        lines.append("")
        cost = arm.get("cost_per_correct_case", {})
        money = cost.get("usd")
        lines.append(
            "The money per correct case is "
            + (
                f"{money} dollars"
                if money is not None
                else f"unknown, because {cost.get('money_unknown_reason') or 'the price was never verified'}"
            )
            + f", and the tokens per correct case are {cost.get('tokens')}."
        )
        lines.append("")
        latency = arm.get("latency_p95_ms", {})
        lines.append(f"The p95 of the latency is {latency.get('value', 0)} ms over {latency.get('cases', 0)} cases.")
        lines.append("")
        fallback = arm.get("fallback_rate", {})
        if fallback.get("measured") is False:
            lines.append(
                f"The rate of the fallback is {fallback.get('value')} over {fallback.get('calls')} calls, and the "
                f"number was not measured: {fallback.get('reason')}."
            )
        else:
            lines.append(
                f"The rate of the fallback is {fallback.get('value')} over {fallback.get('calls')} calls, and "
                f"{fallback.get('fallbacks')} of them were a fallback."
            )
        lines.append("")
        lines += ["| The model | The calls | The share | The tokens |", "| --- | --- | --- | --- |"]
        for model, values in arm.get("model_mix", {}).items():
            lines.append(f"| {model} | {values.get('calls')} | {values.get('share')} | {values.get('tokens')} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def run_comparison(
    arms: Sequence[Arm],
    cases: Sequence[EvalCase],
    world: ComparisonWorld,
    *,
    registry: ProviderRegistry | None = None,
) -> dict[str, Any]:
    """Runs the cohort under every arm and returns the report of the comparison."""
    results = [run_arm(arm, cases, world, registry=registry) for arm in arms]
    return build_report(results, cohort=cases, world=world)
