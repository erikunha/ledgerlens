"""The comparison of the studio against the single agent: two arms over the same cases and the same snapshot.

Why it exists: ADR-P007 keeps the studio behind a flag until a paired comparison measures a gain, and this module
is the measurement. It runs the two arms over the same set of cases, over the same ledger and with the same model,
and it writes the measures with their denominator, the uncertainty of the difference and the decision that follows
the result, whether the result is a gain or a loss (FR-002 of the spec of the studio).

Why the comparison refuses to run offline: the single agent replays the script of the case when the model is
scripted, so a comparison over scripted answers measures the plumbing of the two runtimes and not the runtimes.

Why the manifest is pinned before the first run: a registration that may be rewritten after the run is not a
registration, so the first run pins the digest of the manifest and a run whose manifest changed is refused.

Why the answer of the studio is composed and not written by a model: the studio of the first version is a
dispatcher with deterministic specialists, and its summary renders the evidence the verifier supported. The page
of the result says so, because a reader has to know what the arm answered before it reads the number.

Why the latency of a case is the wall time of the run of the case: the two arms do different work inside the same
second, and the wall time of the case is the only latency that means the same thing in the two of them.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from langchain_core.callbacks import get_usage_metadata_callback
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage

from ledgerlens.agents.integrator import build_integrator, investigate, plan_to_follow
from ledgerlens.agents.modern import build_investigation_tools
from ledgerlens.agents.routing import SLOT_AGENT, SLOT_POLICY, SLOT_SQL, SLOT_TRIAGE, SLOTS
from ledgerlens.byok.budget import BudgetCoordinator, BudgetExceededError
from ledgerlens.byok.registry import ProviderRegistry
from ledgerlens.chains.parsers import TriageError
from ledgerlens.chains.triage import build_triage_declarative
from ledgerlens.config import PROJECT_ROOT, Settings
from ledgerlens.eval.dataset import EvalCase
from ledgerlens.eval.evaluators import correctness
from ledgerlens.eval.routing_comparison import ComparisonWorld
from ledgerlens.memory.long_term import CaseMemory
from ledgerlens.orchestration.dispatcher import Permissions
from ledgerlens.orchestration.join import join_results
from ledgerlens.orchestration.plan import PlanRefused, steps_in_order
from ledgerlens.orchestration.scheduler import run_plan
from ledgerlens.orchestration.specialists import SPECIALISTS
from ledgerlens.orchestration.studio import open_studio
from ledgerlens.orchestration.verify_stage import VerificationRefused, verify_before_summary
from ledgerlens.run_context import SHIPPED_RUN_BUDGET
from ledgerlens.schemas import (
    Claim,
    Coherence,
    Evidence,
    InvestigationResult,
    OrchestrationPlan,
    OrchestrationStep,
)
from ledgerlens.tools.fx import FxClient
from ledgerlens.verify import verify_result
from ledgerlens.verify.claims import render_premise
from ledgerlens.verify.nli import StubNli

__all__ = [
    "ARMS",
    "PAGE_RELATIVE",
    "RESULT_RELATIVE",
    "RUNS_RELATIVE",
    "ArmMeasures",
    "CaseMeasures",
    "ComparisonRefused",
    "build_report",
    "decide",
    "ensure_preregistered",
    "manifest_digest",
    "record_run",
    "render_markdown",
    "run_single_arm",
    "run_studio_arm",
    "specialist_for",
]

# The names of the two arms of the comparison, in the order the prose tells them.
ARM_SINGLE = "single_agent"
ARM_STUDIO = "orchestration_studio"
ARMS = (ARM_SINGLE, ARM_STUDIO)

# Where the runs of the comparison are recorded, where the result of the last run is written and where the page of
# the result lives. The runs file is the evidence that the registration came before the run.
RUNS_RELATIVE = Path("data") / "runtime" / "orchestration" / "runs.jsonl"
RESULT_RELATIVE = Path("data") / "runtime" / "orchestration" / "result.json"
PAGE_RELATIVE = Path("docs") / "orchestration" / "comparison.md"

# What judged the two arms, published with the numbers. The absolute numbers of this comparison are not the
# numbers of the published online report, and a reader of the JSON alone has to know it before it reads them.
JUDGE: Mapping[str, Any] = {
    "correctness": "the deterministic judge of the repository",
    "nli": "the stub of the NLI of the repository, the real model of the NLI is not called",
    "fx": "the fixtures of the exchange of the repository",
    "runs_per_case": 1,
    "comparable_with": "the other arm of this comparison and not with the published online report",
}


class ComparisonRefused(Exception):
    """The comparison may not run, and the message says why."""


# --- the registration of the experiment ---------------------------------------------------------------------


def manifest_digest(path: Path) -> str:
    """The sha256 of the manifest of the experiment: the registration is the bytes of the file."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ensure_preregistered(manifest_path: Path, runs_path: Path) -> None:
    """Refuses the run when the manifest of the experiment was written after the first run.

    Why the digest and not the date: a date can be rewritten with the file, and the digest of the bytes is the
    registration itself. Why a missing runs file allows the run: no run happened yet, so the registration may
    still be amended; the first run is the one that pins it.
    """
    runs_path = Path(runs_path)
    if not runs_path.is_file():
        return
    lines = [line for line in runs_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return
    first = json.loads(lines[0])
    pinned = str(first.get("manifest_sha256", ""))
    current = manifest_digest(manifest_path)
    if pinned != current:
        raise ComparisonRefused(
            "the manifest of the experiment was written after the first run: the first run pinned the digest "
            f"{pinned} and the manifest of today is {current}, and a registration that may be rewritten after "
            "the run is not a registration"
        )


def record_run(runs_path: Path, *, manifest_path: Path, commit: str, result_name: str) -> None:
    """Appends the run to the record of the runs, with the digest of the manifest it ran against."""
    runs_path = Path(runs_path)
    runs_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "run_on": datetime.now(UTC).isoformat(timespec="seconds"),
        "manifest_sha256": manifest_digest(manifest_path),
        "commit": commit,
        "result": result_name,
    }
    with runs_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


# --- the measures of a case and of an arm -------------------------------------------------------------------


@dataclass(frozen=True)
class CaseMeasures:
    """What one case cost and what it answered, under one arm of the comparison.

    Why the money is a number or nothing: the price of a model that nobody verified is unknown, and unknown is
    never zero (ADR-078). Why the answer travels with the measures: a reader of the report checks a number
    against the answer that produced it and not only against the total of the arm.
    """

    case_id: str
    answer: str
    correctness: float
    missing_facts: tuple[str, ...]
    tool_calls: int
    latency_ms: int
    input_tokens: int
    output_tokens: int
    usd: Decimal | None
    money_reason: str = ""
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        """The case as a dictionary, for the report."""
        return {
            "case": self.case_id,
            "correctness": self.correctness,
            "missing_facts": list(self.missing_facts),
            "tool_calls": self.tool_calls,
            "latency_ms": self.latency_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": None if self.usd is None else str(self.usd),
            "money_reason": self.money_reason,
            "reason": self.reason,
            "answer": self.answer,
        }


@dataclass(frozen=True)
class ArmMeasures:
    """The measures of one arm over the whole set, each with the number of cases behind it."""

    name: str
    description: str
    cases: tuple[CaseMeasures, ...]

    @property
    def correct_cases(self) -> int:
        """The cases whose answer carried every expected fact, by the oracle of the repository."""
        return sum(1 for case in self.cases if case.correctness >= 1.0)

    @property
    def tool_calls(self) -> int:
        """The calls of the tools that the arm made over the set."""
        return sum(case.tool_calls for case in self.cases)

    @property
    def priced_usd(self) -> Decimal | None:
        """The money of the arm, or None when one of its cases has no known money (ADR-078)."""
        total = Decimal("0")
        for case in self.cases:
            if case.usd is None:
                return None
            total += case.usd
        return total

    @property
    def money_reason(self) -> str:
        """Why the money of the arm is unknown, and the empty string when it is known."""
        for case in self.cases:
            if case.usd is None:
                return case.money_reason
        return ""

    @property
    def latency_p95_ms(self) -> int:
        """The p95 of the latency of the cases of the arm, by the nearest rank."""
        return _percentile([case.latency_ms for case in self.cases], 0.95)

    def cost_per_correct_case(self) -> Decimal | None:
        """The money of a correct case of the arm, or None when there is no such money.

        Why None and not a number of zero when no case was correct: the money of a correct case is the money of
        a case that does not exist, and a number of zero would say that the arm was free.
        """
        priced = self.priced_usd
        if priced is None or not self.correct_cases:
            return None
        return (priced / self.correct_cases).quantize(Decimal("0.000001"))


def _percentile(values: Sequence[int], percentile: float) -> int:
    """The percentile of a list of numbers, by the nearest rank.

    Why the nearest rank and not an interpolation: a latency is the measurement of one run, and the number of a
    run is the number of a run, not a point between two runs.
    """
    if not values:
        return 0
    ordered = sorted(values)
    rank = math.ceil(percentile * len(ordered))
    index = max(0, min(len(ordered) - 1, rank - 1))
    return ordered[index]


def _money_of_usage(registry: ProviderRegistry, usage: Mapping[str, Mapping[str, int]]) -> tuple[Decimal | None, str]:
    """The money of the calls of a run, or None and the reason why it is unknown.

    Why a run without usage is unknown and not zero: a number of zero would say that the call was free, and a
    run that reported no usage is a run whose money nobody counted (ADR-078).

    Why the date of the served name is dropped before the price is read: the provider serves the dated
    snapshot of the alias the deployment declared (`gpt-4.1-mini-2025-04-14` for `gpt-4.1-mini`), and the
    price of the alias is the price of the snapshot it serves.
    """
    if not usage:
        return None, "the run reported no usage of the models"
    total = Decimal("0")
    unpriced: list[str] = []
    tokens = 0
    for model, counts in usage.items():
        bare = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", model.split(":", 1)[-1])
        tokens += int(counts.get("input_tokens", 0)) + int(counts.get("output_tokens", 0))
        if registry.price_for(bare) is None:
            unpriced.append(model)
            continue
        money = registry.estimate_usd(
            bare,
            input_tokens=int(counts.get("input_tokens", 0)),
            output_tokens=int(counts.get("output_tokens", 0)),
        )
        total += money or Decimal("0")
    if unpriced:
        return None, f"the price of {', '.join(sorted(unpriced))} was never verified"
    if tokens == 0:
        return None, "the run reported no usage of the models"
    return total, ""


def _missing_of(scores: Mapping[str, Any]) -> tuple[str, ...]:
    """The facts the answer did not carry, read from the comment of the evaluator."""
    comment = str(scores.get("comment", ""))
    if not comment.startswith("missing: "):
        return ()
    return tuple(item.strip() for item in comment[len("missing: ") :].split(", ") if item.strip())


# --- the arm of the single agent ------------------------------------------------------------------------------


def run_single_arm(
    cases: Sequence[EvalCase],
    world: ComparisonWorld,
    *,
    model_name: str,
    index_root: Path | str,
    embeddings: Any,
    registry: ProviderRegistry | None = None,
) -> ArmMeasures:
    """The arm of the shipped path: one agent, six tools and the deterministic verifier, one case at a time.

    Why the arm is the shipped code with no change: the baseline of the comparison is the path the repository
    ships, and a baseline that was changed for the comparison is not a baseline (the risk the plan names).
    """
    from functools import partial

    from ledgerlens.config import get_chat_model

    registry = registry or ProviderRegistry()
    models = {slot: get_chat_model(model=model_name, temperature=0) for slot in SLOTS}
    outcomes: list[CaseMeasures] = []
    for case in cases:
        started = time.perf_counter()
        memory = CaseMemory(world.root / "memory" / ARM_SINGLE / case.id, embeddings=embeddings)
        agent = build_integrator(
            models[SLOT_AGENT],
            db_path=world.db_path,
            verifier=partial(verify_result, nli=StubNli(), ledger_db=world.db_path),
            query_model=models[SLOT_SQL],
            triage_model=models[SLOT_TRIAGE],
            policy_model=models[SLOT_POLICY],
            fx_client=FxClient(mode="fixtures", fault=case.fx_fault, sleep=lambda _: None),
            case_memory=memory,
            model_names={slot: model_name for slot in SLOTS},
        )
        with get_usage_metadata_callback() as counter:
            result = investigate(agent, case.question, thread_id=f"orchestration-single-{case.id}")
        latency_ms = max(0, round((time.perf_counter() - started) * 1000))
        scores = correctness(outputs={"answer": result.answer}, reference_outputs={"facts": list(case.expected_facts)})
        usd, reason = _money_of_usage(registry, dict(counter.usage_metadata))
        outcomes.append(
            CaseMeasures(
                case_id=case.id,
                answer=result.answer,
                correctness=float(scores["score"]),
                missing_facts=_missing_of(scores),
                tool_calls=len(result.tool_trace),
                latency_ms=latency_ms,
                input_tokens=sum(int(u.get("input_tokens", 0)) for u in counter.usage_metadata.values()),
                output_tokens=sum(int(u.get("output_tokens", 0)) for u in counter.usage_metadata.values()),
                usd=usd,
                money_reason=reason,
            )
        )
    return ArmMeasures(
        name=ARM_SINGLE,
        description="The path that the repository ships: one agent of ledgerlens/agents/integrator.py with its "
        "six tools and the deterministic verifier of ledgerlens/verify/.",
        cases=tuple(outcomes),
    )


# --- the arm of the studio ------------------------------------------------------------------------------------


def specialist_for(tool: str) -> str:
    """The specialist of the registry whose allowlist holds the tool, and a refusal when there is none.

    Why an unknown tool refuses the plan: a step that no specialist may run is a step outside the policy of the
    studio, and a plan with a step outside the policy is a plan the dispatcher refuses (FR-004).
    """
    for name, spec in SPECIALISTS.items():
        if tool in spec.tools:
            return name
    raise ComparisonRefused(
        f"the registry of the specialists has no specialist for the tool {tool!r}, and the tools of the registry "
        f"are {sorted(tool for spec in SPECIALISTS.values() for tool in spec.tools)}"
    )


def _content_of(tool: str, data: Mapping[str, Any], evidence_id: str) -> str:
    """The content of one evidence as JSON: the item that has the id when the call returned several.

    Why the content is the JSON and not a rendering: the verifier renders the premise it reads from the JSON
    (`render_premise`), and a content that was already flattened would be a premise of one line that the NLI
    cannot check line by line.
    """
    key = {"search_policies": "chunk_id", "recall_cases": "case_id"}.get(tool)
    if key is not None:
        for item in data.get("results", []):
            if isinstance(item, Mapping) and evidence_id.split(":", 1)[1] == str(item.get(key)):
                return json.dumps(item, ensure_ascii=False)
    return json.dumps(data, ensure_ascii=False)


def _fill_prompt(question: str, step: OrchestrationStep, tool: Any, dependencies: Mapping[str, list[str]]) -> str:
    """The prompt of the fill of the arguments of a step: the question, the goal, the tool and the dependencies.

    Why the outputs of the dependencies go into the prompt: the arguments of a step are read from the outputs of
    the steps before it, and a fill that saw nothing would invent the values (the rule of the agent: only values
    that came from the question or from another tool).
    """
    schema = tool.args_schema.model_json_schema() if tool.args_schema is not None else {}
    outputs = []
    for dependency in step.depends_on:
        for content in dependencies.get(dependency, []):
            outputs.append(f"- {dependency}: {content}")
    seen = "\n".join(outputs) if outputs else "none, this step depends on nothing"
    return (
        "You fill the arguments of one tool of a payments investigation.\n\n"
        f"The question of the investigation: {question}\n\n"
        f"The step of the plan: {step.goal}\n"
        f"The tool of the step: {step.tool}\n"
        f"What the tool does: {tool.description}\n"
        f"The schema of the arguments of the tool: {json.dumps(schema, ensure_ascii=False)}\n\n"
        f"The outputs of the steps this step depends on:\n{seen}\n\n"
        "Rules:\n"
        "- Answer with a JSON object only, with the arguments of the tool, and with no prose and no markdown.\n"
        "- Use only values that came from the question or from the outputs above. Never invent a date, an "
        "identifier or a number.\n"
        "- Before asking for an FX rate, use the payment or refund date that the outputs carry."
    )


def _parse_arguments(text: str) -> dict[str, Any]:
    """The arguments of the fill, read from the answer of the model. A answer with no JSON is a failure."""
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ComparisonRefused(f"the fill of the arguments answered with no JSON object: {text[:120]!r}")
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ComparisonRefused(f"the fill of the arguments answered with a JSON that does not parse: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ComparisonRefused(f"the fill of the arguments answered with {type(parsed).__name__} and not an object")
    return parsed


def run_studio_arm(
    cases: Sequence[EvalCase],
    world: ComparisonWorld,
    *,
    settings: Settings,
    model: BaseChatModel,
    model_name: str,
    index_root: Path | str,
    embeddings: Any,
    query_model: BaseChatModel | None = None,
    policy_model: BaseChatModel | None = None,
    registry: ProviderRegistry | None = None,
    concurrency: int = 2,
) -> ArmMeasures:
    """The arm of the studio: the triage writes the plan, the dispatcher runs it and the verifier closes it.

    Why the studio opens through the door of the flag: the comparison is the experiment that ADR-P007 asks for,
    and the studio runs only with the flag on and the experiment registered (FR-001).

    Why every step fills its arguments with the model of the run: the plan of the triage names the tools and the
    dependencies and not the arguments, and the fill is the work the agent loop does when it reads the
    observations. The fill is a call of the model of the run, reserved against the same budget of the run.
    """
    registry = registry or ProviderRegistry()
    open_studio(settings)  # the door of the studio: the flag and the registered experiment (ADR-P007)
    outcomes: list[CaseMeasures] = []
    for case in cases:
        outcomes.append(
            _run_studio_case(
                case,
                world,
                model=model,
                model_name=model_name,
                query_model=query_model or model,
                policy_model=policy_model or model,
                index_root=index_root,
                embeddings=embeddings,
                registry=registry,
                concurrency=concurrency,
            )
        )
    return ArmMeasures(
        name=ARM_STUDIO,
        description="The experimental variant: a plan of steps dispatched to specialists under the budget of the "
        "run, with the same tools, the same verifier and the same model of the single agent.",
        cases=tuple(outcomes),
    )


def _run_studio_case(
    case: EvalCase,
    world: ComparisonWorld,
    *,
    model: BaseChatModel,
    model_name: str,
    query_model: BaseChatModel,
    policy_model: BaseChatModel,
    index_root: Path | str,
    embeddings: Any,
    registry: ProviderRegistry,
    concurrency: int,
) -> CaseMeasures:
    """The run of one case under the studio: triage, plan, dispatch, join, verification and summary."""
    from ledgerlens.tools.policies import build_search_policies_tool

    started = time.perf_counter()
    coordinator = BudgetCoordinator(SHIPPED_RUN_BUDGET, registry)
    failures: list[str] = []
    memory = CaseMemory(world.root / "memory" / ARM_STUDIO / case.id, embeddings=embeddings)
    tools = build_investigation_tools(
        query_model=query_model,
        db_path=world.db_path,
        fx_client=FxClient(mode="fixtures", fault=case.fx_fault, sleep=lambda _: None),
        index_root=index_root,
        embeddings=embeddings,
        case_memory=memory,
    )
    # The policy tool with the model of the run for the rewrite, the same the single agent carries (ADR-037).
    policies = build_search_policies_tool(index_root=index_root, embeddings=embeddings, llm=policy_model)
    tools = [policies if tool.name == "search_policies" else tool for tool in tools]
    by_name = {tool.name: tool for tool in tools}

    def stopped(reason: str, usage: Mapping[str, Mapping[str, int]]) -> CaseMeasures:
        """The case that did not produce an answer: the reason is named and the case stays in the denominator."""
        usd, money_reason = _money_of_usage(registry, usage)
        return CaseMeasures(
            case_id=case.id,
            answer="",
            correctness=0.0,
            missing_facts=tuple(case.expected_facts),
            tool_calls=0,
            latency_ms=max(0, round((time.perf_counter() - started) * 1000)),
            input_tokens=sum(int(u.get("input_tokens", 0)) for u in usage.values()),
            output_tokens=sum(int(u.get("output_tokens", 0)) for u in usage.values()),
            usd=usd,
            money_reason=money_reason,
            reason=reason,
        )

    with get_usage_metadata_callback() as counter:
        # The triage of the case: the same chain and the same model of the single agent.
        try:
            coordinator.reserve_model_call(model_name)
        except BudgetExceededError as exc:
            return stopped(f"the run stopped at the cap {exc.cap}", counter.usage_metadata)
        triage_out = None
        try:
            triage_out = build_triage_declarative(model).invoke({"complaint": case.question})
        except Exception as exc:  # a triage that failed is a case with no plan, not a crash of the arm
            return stopped(f"the triage failed: {type(exc).__name__}: {exc}", counter.usage_metadata)
        if isinstance(triage_out, TriageError):
            return stopped(f"the triage was unreadable: {triage_out.code}", counter.usage_metadata)
        plan = plan_to_follow(triage_out)
        if plan is None:
            return stopped("the triage gave no plan", counter.usage_metadata)

        # The plan of the studio: one step per planned tool, with the specialist of the registry.
        try:
            steps = [
                OrchestrationStep(
                    id=step.id,
                    goal=step.goal,
                    tool=step.tool,
                    specialist=specialist_for(step.tool),
                    depends_on=list(step.depends_on),
                    # The fill context of the step: the wrapper of the tool fills the arguments with the model
                    # of the run, because the plan of the triage names the tools and not the arguments. The id of
                    # the step travels in the context because the registry of the tools is keyed by the tool and
                    # two steps of the same tool are two fills.
                    arguments={
                        "step_id": step.id,
                        "question": case.question,
                        "goal": step.goal,
                        "depends_on": list(step.depends_on),
                    },
                )
                for step in plan.plan
                if step.tool
            ]
            orchestration = OrchestrationPlan(steps=steps, snapshot=world.digest())
            ordered = steps_in_order(orchestration)
        except (PlanRefused, ComparisonRefused, ValueError) as exc:
            return stopped(str(exc), counter.usage_metadata)

        # The tools of the studio: the fill of the arguments, the call of the tool and the capture of the evidence.
        contents: dict[str, str] = {}
        evidence_tools: dict[str, str] = {}
        step_outputs: dict[str, list[str]] = {step.id: [] for step in ordered}
        steps_by_id = {step.id: step for step in ordered}
        tool_calls = 0

        def fill_and_call() -> Any:
            def run(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
                nonlocal tool_calls
                context = dict(arguments)
                step = steps_by_id[str(context["step_id"])]
                question = str(context.get("question", case.question))
                try:
                    coordinator.reserve_model_call(model_name)
                    prompt = _fill_prompt(question, step, by_name[step.tool], step_outputs)
                    answer = model.invoke([HumanMessage(prompt)])
                    filled = _parse_arguments(str(answer.content))
                except (BudgetExceededError, ComparisonRefused) as exc:
                    failures.append(f"{step.id}: {exc}")
                    return {"evidence_refs": [], "spend_usd": Decimal("0")}
                except Exception as exc:  # a model that failed is a step with no evidence, not a crash of the run
                    failures.append(f"{step.id}: the fill failed: {type(exc).__name__}: {exc}")
                    return {"evidence_refs": [], "spend_usd": Decimal("0")}
                try:
                    envelope = by_name[step.tool].invoke(filled)
                except Exception as exc:  # the wall behind the tools: a bug of a tool is a failed step
                    failures.append(f"{step.id}: {step.tool} failed: {type(exc).__name__}: {exc}")
                    return {"evidence_refs": [], "spend_usd": Decimal("0")}
                tool_calls += 1
                if isinstance(envelope, str):
                    envelope = json.loads(envelope)
                if not envelope.get("ok"):
                    failure = envelope.get("error") or {}
                    failures.append(f"{step.id}: {step.tool} failed: {failure.get('code', 'UNKNOWN')}")
                    return {"evidence_refs": [], "spend_usd": Decimal("0")}
                data = envelope.get("data") or {}
                refs = [str(ref) for ref in envelope.get("evidence_ids") or []]
                for ref in refs:
                    contents[ref] = _content_of(step.tool, data, ref)
                    evidence_tools[ref] = step.tool
                    step_outputs[step.id].append(json.dumps(data, ensure_ascii=False))
                return {"evidence_refs": refs, "spend_usd": Decimal("0")}

            return run

        outcome = run_plan(
            orchestration,
            permissions=Permissions(tools=frozenset(by_name), accounts=frozenset()),
            tools={step.tool: fill_and_call() for step in ordered},
            budget=coordinator,
            concurrency=concurrency,
        )

        results = outcome.results
        records = [ref for result in results for ref in result.evidence_refs]
        joined = join_results(results, snapshot=world.digest(), records=records, recompute=lambda row: None)

        # The verification before the summary: the verifier of the repository decides the claims of the steps,
        # and the summary renders only the lines the verifier supported (FR-009). The claims are the lines of
        # the evidence as the verifier reads it (`render_premise`), because a claim that restates a line of the
        # evidence is a claim the verifier can check, and a claim that dumps the whole record is not.
        now = datetime.now(UTC)
        source_by_prefix = {
            "sql": "sql",
            "api": "ledger_api",
            "policy": "policy",
            "fx": "fx",
            "calc": "calc",
            "case": "case",
            "doc": "doc",
        }
        evidence = [
            Evidence(
                id=ref,
                source_type=source_by_prefix[ref.split(":", 1)[0]],  # type: ignore[arg-type]
                tool=evidence_tools[ref],  # type: ignore[arg-type]
                content=contents[ref],
                ref=ref,
                retrieved_at=now,
            )
            for ref in records
        ]
        refs_in_order = [ref for result in results for ref in result.evidence_refs]
        lines_of = {
            ref: [line.strip() for line in render_premise(contents[ref]).splitlines() if line.strip()]
            for ref in refs_in_order
        }
        claim_refs = [(ref, line) for ref in refs_in_order for line in lines_of[ref]]

        def verifier(claims: Sequence[Any]) -> Sequence[Any]:
            # The text of a claim carries no citation: the citation lives in `evidence_ids`, and a bracket in
            # the text would be tokens the evidence does not have, which the NLI reads as a conflict.
            assembled_claims = [
                Claim(id=f"CL{index}", text=line, kind="fact", evidence_ids=[ref])
                for index, (ref, line) in enumerate(claim_refs, 1)
            ]
            assembled = InvestigationResult(
                session_id=f"orchestration-studio-{case.id}",
                question=case.question,
                answer=" ".join(f"{line} [{ref}]." for ref, line in claim_refs),
                claims=assembled_claims,
                evidence=evidence,
                verdicts=[],
                coherence=Coherence(passed=True),
                recommended_action="none",
                requires_human_review=False,
            )
            return verify_result(assembled, nli=StubNli(), ledger_db=world.db_path).verdicts

        def summary_of(verdicts: Sequence[Any], _join: Any) -> str:
            supported = {str(verdict.claim_id) for verdict in verdicts if verdict.label == "supported"}
            return " ".join(
                f"{line} [{ref}]."
                for index, (ref, line) in enumerate(claim_refs, 1)
                if f"CL{index}" in supported
            )

        try:
            verification = verify_before_summary(results, join=joined, verifier=verifier, summary_of=summary_of)
        except VerificationRefused as exc:
            # A run with no verdict has no summary: the case is scored on the empty answer and the reason is named.
            failures.append(str(exc))
            verification = None

    answer = verification.summary if verification is not None and verification.summary else ""
    latency_ms = max(0, round((time.perf_counter() - started) * 1000))
    scores = correctness(outputs={"answer": answer}, reference_outputs={"facts": list(case.expected_facts)})
    usd, money_reason = _money_of_usage(registry, dict(counter.usage_metadata))
    reason = "; ".join(failures)
    if outcome.cut_by is not None:
        reason = f"the run stopped at the cap {outcome.cut_by}" + (f"; {reason}" if reason else "")
    return CaseMeasures(
        case_id=case.id,
        answer=answer,
        correctness=float(scores["score"]),
        missing_facts=_missing_of(scores),
        tool_calls=tool_calls,
        latency_ms=latency_ms,
        input_tokens=sum(int(u.get("input_tokens", 0)) for u in counter.usage_metadata.values()),
        output_tokens=sum(int(u.get("output_tokens", 0)) for u in counter.usage_metadata.values()),
        usd=usd,
        money_reason=money_reason,
        reason=reason,
    )


# --- the decision and the report ----------------------------------------------------------------------------


def decide(
    *,
    difference_cases: int,
    threshold_cases: int,
    interval: Mapping[str, float],
    money_known: bool,
    single_cost: Decimal | None,
    studio_cost: Decimal | None,
) -> dict[str, str]:
    """The decision that follows the result, by the rule the manifest registered before the run.

    Why the decision is a function of the measures and not of the reader: the rule was written before the run,
    and a decision that may be negotiated after the run is not a decision (FR-002).
    """
    if difference_cases < threshold_cases:
        return {
            "outcome": "the flag stays off",
            "reason": f"the difference of {difference_cases} case(s) is a trend and not a gain: the rule asks "
            f"for a difference of at least {threshold_cases} cases",
        }
    if interval["low"] <= 0 <= interval["high"]:
        return {
            "outcome": "the flag stays off",
            "reason": "the interval of the difference of the correctness covers zero, and an interval that covers "
            "zero keeps the flag off",
        }
    if not money_known or single_cost is None or studio_cost is None:
        return {
            "outcome": "the flag stays off",
            "reason": "the money of an arm is unknown, so the comparison of the money is not established and the "
            "flag stays off",
        }
    if studio_cost > single_cost:
        return {
            "outcome": "the flag stays off",
            "reason": "a studio that costs more and answers the same is not a gain",
        }
    return {
        "outcome": "gain",
        "reason": "the flag of the studio may open for the experiment that is registered here and for nothing else",
    }


def _arm_report(arm: ArmMeasures) -> dict[str, Any]:
    """The numbers of one arm, each with the number of cases behind it."""
    priced = arm.priced_usd
    cost = arm.cost_per_correct_case()
    return {
        "arm": {"name": arm.name, "description": arm.description},
        "correct_cases": {"cases": arm.correct_cases, "of": len(arm.cases)},
        "cost_per_correct_case_usd": {
            "usd": None if cost is None else str(cost),
            "known": priced is not None and cost is not None,
            "money_unknown_reason": arm.money_reason
            if priced is None
            else ("" if cost is not None else "no case of the arm carried every expected fact"),
            "total_usd": None if priced is None else str(priced),
        },
        "latency_p95_ms": {"value": arm.latency_p95_ms, "cases": len(arm.cases)},
        "tool_calls": {"calls": arm.tool_calls, "cases": len(arm.cases)},
        "cases": [case.to_dict() for case in arm.cases],
    }


def build_report(
    single: ArmMeasures,
    studio: ArmMeasures,
    *,
    cohort: Sequence[EvalCase],
    world: ComparisonWorld,
    cases_path: Path,
    manifest_path: Path,
    model_name: str,
    commit: str,
    threshold_cases: int,
    rule_text: str,
    uncertainty_text: str,
    note: str = "",
) -> dict[str, Any]:
    """The report of the comparison, with the denominator and the uncertainty of every number."""
    total = len(cohort)
    difference = studio.correct_cases - single.correct_cases
    studio_only = sum(
        1
        for s, g in zip(studio.cases, single.cases, strict=True)
        if s.correctness >= 1.0 and g.correctness < 1.0
    )
    single_only = sum(
        1
        for s, g in zip(studio.cases, single.cases, strict=True)
        if g.correctness >= 1.0 and s.correctness < 1.0
    )
    # The interval of the difference of the correctness of the two arms over the same cases: the standard error
    # of the paired difference, with the discordant cases of the two arms.
    error = math.sqrt((studio_only + single_only) / total) / total if total else 0.0
    centre = difference / total if total else 0.0
    interval = {
        "low": round(centre - 1.96 * error, 4),
        "high": round(centre + 1.96 * error, 4),
        "method": "the paired difference of the correctness, with the standard error of the discordant cases "
        "and the normal approximation of 95 percent",
    }
    decision = decide(
        difference_cases=difference,
        threshold_cases=threshold_cases,
        interval=interval,
        money_known=single.priced_usd is not None and studio.priced_usd is not None,
        single_cost=single.cost_per_correct_case(),
        studio_cost=studio.cost_per_correct_case(),
    )
    return {
        "mode": "online",
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": commit,
        "model": model_name,
        "judge": dict(JUDGE),
        "cohort": {
            "cases": total,
            "ids": [case.id for case in cohort],
            "digest": hashlib.sha256(Path(cases_path).read_bytes()).hexdigest(),
            "source": Path(cases_path).name,
        },
        "ledger": {"sha256": world.digest(), "source": "the versioned sample of the repository"},
        "manifest": {
            "path": str(Path(manifest_path).relative_to(PROJECT_ROOT))
            if Path(manifest_path).is_relative_to(PROJECT_ROOT)
            else Path(manifest_path).name,
            "sha256": manifest_digest(manifest_path),
        },
        "arms": {ARM_SINGLE: _arm_report(single), ARM_STUDIO: _arm_report(studio)},
        "difference": {
            "cases": difference,
            "studio_only": studio_only,
            "single_only": single_only,
            "interval": interval,
        },
        "rule": {"decision": rule_text, "threshold_cases": threshold_cases},
        "decision": decision,
        "uncertainty": uncertainty_text,
        "note": note,
    }


def render_markdown(report: dict[str, Any]) -> str:
    """The report as the page of the comparison, with the decision that follows the result."""
    cohort = report["cohort"]
    lines = [
        "# The comparison of the studio against the single agent",
        "",
        f"> {report['note']}",
        "",
        f"The set of the comparison is {cohort['cases']} cases (`{cohort['source']}`, digest "
        f"`{cohort['digest']}`), the denominator of every measure is the {cohort['cases']} cases of the set, and "
        f"the ledger of the two arms is `{report['ledger']['sha256']}`. The model of the two arms is "
        f"`{report['model']}`, the commit of the run is `{report['commit']}` and the manifest of the experiment "
        f"is `{report['manifest']['path']}` (digest `{report['manifest']['sha256']}`), registered before the run.",
        "",
        "The judge of the two arms is the deterministic judge of the repository, with the stub of the NLI and the "
        "fixtures of the exchange: the absolute numbers of this page are not the numbers of the published online "
        "report, and the two arms are the ones that are comparable with each other.",
        "",
    ]
    for name in ARMS:
        arm = report["arms"][name]
        lines += [f"## The arm `{name}`", "", str(arm["arm"]["description"]), ""]
        correct = arm["correct_cases"]
        cost = arm["cost_per_correct_case_usd"]
        latency = arm["latency_p95_ms"]
        calls = arm["tool_calls"]
        money = (
            f"{cost['usd']} dollars"
            if cost["usd"] is not None
            else f"unknown, because {cost['money_unknown_reason']}"
        )
        lines += [
            f"- The correct cases: {correct['cases']} of {correct['of']}.",
            f"- The cost per correct case: {money}.",
            f"- The p95 of the latency: {latency['value']} ms over {latency['cases']} cases.",
            f"- The calls of the tools: {calls['calls']} over {calls['cases']} cases.",
            "",
        ]
    difference = report["difference"]
    interval = difference["interval"]
    lines += [
        "## The difference of the arms",
        "",
        f"The studio resolved {difference['cases']} more case(s) than the single agent: "
        f"{difference['studio_only']} case(s) only the studio resolved and {difference['single_only']} case(s) "
        f"only the single agent resolved. The interval of the difference of the correctness is "
        f"[{interval['low']}, {interval['high']}] ({interval['method']}).",
        "",
        "## The rule and the decision",
        "",
        f"The rule of the manifest: {report['rule']['decision']}",
        "",
        f"The decision: **{report['decision']['outcome']}**. {report['decision']['reason']}.",
        "",
        "## The uncertainty",
        "",
        str(report["uncertainty"]),
        "",
        "The number of this page was measured over the set it names and is not a generalization: it says what the "
        "two arms did over these cases, with this model and with this snapshot, and nothing else.",
        "",
    ]
    return "\n".join(lines) + "\n"
