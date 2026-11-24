"""Integrator: the agent that brings the six tools together, verifies the answer and remembers what was proven.

Why it exists: it is the piece the end user uses. It gets a question, lets the model pick the
tools (`create_agent`, ADR-010), turns the conversation into an `InvestigationResult` and passes the result
through the verifier before delivering it. Flow of one question::

    question -> triage (intent, entities, plan)
             -> agent (model + six tools, plan as context, history per thread_id)
             -> assembled result: answer, tool trace, evidence, what was missing, plan deviations
             -> verifier: claims, verdicts, coherence
             -> if every verdict was supported, saves the case in long-term memory
             -> final result

What each part does and what it leaves to another:

- **Triage**: the `Triage` plan goes into the agent's context (a system message before the question). It is
  an intent, not a proof: the agent may revise it, and the code records in `plan_deviations` the planned step
  that did not run and the tool used outside the plan. A `needs_clarification` triage on the first
  message of the conversation sends the question back without calling the agent or the tools. On a later turn
  triage does not see the history and may find the request vague, so there it only stops giving a plan. If triage
  fails (network, unreadable answer), the agent answers with no plan and the failure goes to the log.
- **Short-term memory**: the `checkpointer` keeps the messages per `thread_id`. If none is given, the
  integrator uses an `InMemorySaver`, so the session's second question sees the first.
- **Single follow-up**: a real model skipped plan tools (FX and calculation in EC-11) and S11 was never exercised.
  If, at the end of the turn, a step with a tool did not run, the code asks the agent once to call the tool or say
  why it is not needed, and then builds the result from what came after. It never asks twice. The follow-up goes
  into `plan_deviations` (the step, the tool and whether the agent called it). If the follow-up call fails, the
  answer that already existed stands and the log and `plan_deviations` say the follow-up failed. The same single
  follow-up covers FX for a date with no origin: the agent queried the ledger, asked `get_reference_fx` for a day
  that no ledger date column carries and the question does not cite (the model made it up) and did not ask for any
  ledger date. The follow-up names the day, says to read the payment or refund date in the ledger, ask for its FX
  rate and redo the calculation. A plan step and such a date in the same turn share a single follow-up. The verifier
  still checks the date of the final answer (`fx_date_origin`).
- **The wall behind the tools**: the tools of the contract return the error envelope instead of raising, but a
  bug in a tool must not take the run down with it. An exception that escapes a tool becomes the `TOOL_FAILED`
  envelope, carried to the model as the result of that call, so the model reports what it could not get and the
  investigation ends with a result that goes to a human (`requires_human_review`), not with a stack trace.
- **The ceiling of the turn**: the loop of the agent has a limit, and the limit is the budget of the turn
  (`ledgerlens/agents/budget.py`, ADR-054). The caps live in the `RunBudget` of the run context
  (`SHIPPED_RUN_BUDGET`), the coordinator of the run context enforces them and the graph of the agent gets a
  `recursion_limit` computed from them. Every path that reaches the graph carries that limit, also the one
  that calls the integrator outside `investigate`. The follow-up spends what the turn has left and never gets a
  ceiling of its own. A turn that a cap cuts is a result and not an exception: the cap that stopped it is named
  in the missing information and the result goes to a human. A turn that nobody gave a cap of the calls of the
  models is not cut by a cap that nobody gave: the ceiling of the graph stops it and the sentence says so. What
  the turn spent travels in the trace.
- **Assembled result**: only what is known without judging. The trace (`tool_trace`) and the evidence come from
  the turn's tool messages; `claims`, `verdicts` and `coherence` come out empty and passing because they are the
  verifier's job, which also decides `recommended_action`. Here `requires_human_review` already goes up when a tool
  failed with no recovery or when nothing was looked up, and the verifier may add reasons.
- **Injected verifier**: `verifier` is any function `(result, *, nli=None) -> result`. Without it, it uses
  `ledgerlens.verify.verify_result`, imported only on the first question so that building the integrator does not
  load the verification model, bound to the tools' `db_path`: the deadline and free text the model's SQL left out
  are read again from the same ledger.
- **Saving the case**: `CaseMemory.write_case` refuses anything that does not have every verdict supported. A disk
  or index failure while saving is logged and does not bring down the answer already verified.
- **Trace**: with `on_event`, `investigate` emits the investigation's run tree span by span
  (`ledgerlens/observability/trace.py`): the root `investigate`, triage and the agent through LangChain callbacks,
  and spans of its own for the single follow-up (`plan_followup`), verification (one child per claim), escalation
  and saving the case. Without `on_event` no callback is added and the result is the same.

Numbers: nothing here computes money. What the result claims comes from the tools.
"""

from __future__ import annotations

import json
import logging
import time
import typing
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any
from uuid import UUID

from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallRequest, ToolErrorMiddleware
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphRecursionError

from ledgerlens.agents.budget import (
    GRAPH_STEPS,
    NO_FALLBACK,
    PLANNED_OUTPUT_TOKENS,
    BudgetReservationMiddleware,
    TurnBudget,
    cap_sentence,
    caps_of,
    derived_recursion_limit,
    model_id_of,
    recursion_limit_for,
    shipped_turn_budget,
    usage_of,
)
from ledgerlens.agents.fallback import (
    ACTION_STOP,
    FallbackMiddleware,
    FallbackRunner,
    FallbackStopped,
    planned_input_of,
    strategy_of,
)
from ledgerlens.agents.modern import DEFAULT_SYSTEM_PROMPT, build_investigation_tools
from ledgerlens.agents.routing import SLOT_TRIAGE
from ledgerlens.byok.budget import BudgetExceededError
from ledgerlens.chains.parsers import TriageError
from ledgerlens.chains.triage import build_triage_declarative, triage_input_of
from ledgerlens.config import get_chat_model, get_settings, model_cascade
from ledgerlens.memory.long_term import CaseMemory
from ledgerlens.observability.trace import OnEvent, Tracer, langsmith_url, review_reasons, summary_line
from ledgerlens.run_context import SHIPPED_RUN_BUDGET, RunBudget, RunContext
from ledgerlens.schemas import Coherence, Evidence, InvestigationResult, PlanStep, ToolCallRecord, Triage, VerdictLabel
from ledgerlens.tools.envelope import error
from ledgerlens.tools.fx import FxClient
from ledgerlens.tools.policies import build_search_policies_tool

log = logging.getLogger(__name__)

Verifier = Callable[..., InvestigationResult]

# The verifier only links a claim to evidence when the SAME sentence cites the id in brackets. With no citation the
# claim has no support and the case goes to human review, so the model must be told to cite. A real
# model gathered all citations at the end of the paragraph, and the earlier sentences were left unsupported.
CITATION_RULE = (
    " Cite the evidence for each claim with the id in brackets at the end of the sentence, for example [sql:1] or "
    "[policy:refund-policy#refund-window, calc:1]. Each sentence carries its own citation: do not gather the "
    "citations at the end of the paragraph. Wrong: 'The deadline is 2026-11-09. Evidence is due by the 8th. [sql:1] "
    "[policy:x#y]'. "
    "Right: 'The deadline is 2026-11-09 [sql:1]. Evidence is due by the 8th [policy:x#y].' A claim with no citation "
    "is not verified."
)
# A real model asked for the FX rate of a date nobody gave it. The date of a payment or a refund is in the
# ledger, and that is the one that goes to the FX tool.
DATE_RULE = (
    " In a tool's arguments use only values that came from the question or from another tool. Before "
    "asking for an FX rate, read the payment or refund date in the ledger and use that date: do not assume dates. "
    "`refund_reference_rate` is the reference rate on the refund date, read in the ledger; never the one of the "
    "charge nor today's."
)
INTEGRATOR_SYSTEM_PROMPT = DEFAULT_SYSTEM_PROMPT + CITATION_RULE + DATE_RULE

# The evidence id prefix says where it came from (`docs/contracts/tools.md`).
_SOURCE_BY_PREFIX = {
    "sql": "sql",
    "api": "ledger_api",
    "policy": "policy",
    "fx": "fx",
    "calc": "calc",
    "case": "case",
}
# Field that identifies an item inside `data["results"]`, per tool (policy search and case search).
_ITEM_KEY = {"search_policies": "chunk_id", "recall_cases": "case_id"}

# The code of an exception that escaped a tool. The tools of the contract return the error envelope themselves,
# so this is the last wall: the run ends with a result for a human, not with a stack trace.
TOOL_FAILED = "TOOL_FAILED"


def _tool_failure_content(exc: Exception, request: ToolCallRequest) -> str:
    """The error envelope of an exception that escaped a tool, as the text the model reads.

    The model gets the failure as the result of the call, so it can report what is missing instead of
    making something up, and the assembled result names the code in `missing_information`.
    """
    name = str(request.tool_call.get("name", "the tool"))
    return json.dumps(error(TOOL_FAILED, f"{name} failed: {type(exc).__name__}: {exc}", False), ensure_ascii=False)


def _default_verifier(
    result: InvestigationResult, *, nli: Any = None, ledger_db: Path | str | None = None
) -> InvestigationResult:
    """The project's verifier, imported at use time (the import may load the NLI model).

    `ledger_db` is the ledger from which it reads again what the model's query left out (deadline and free text).
    """
    from ledgerlens.verify import verify_result

    return verify_result(result, nli=nli, ledger_db=ledger_db)


def default_verifier_for(db_path: Path | str | None) -> Verifier:
    """The project's verifier bound to the ledger the integrator's tools read."""
    return partial(_default_verifier, ledger_db=db_path)


def _caps_of_turn(context: Any) -> RunBudget:
    """The caps of the turn that a call carries: the caps of its ceiling, or the caps of the shipped paths.

    The ceiling of the turn travels with the call as its context, because that is where the caps live
    (ADR-054). A call that carries no ceiling gets the caps of the shipped paths.
    """
    return context.caps if isinstance(context, TurnBudget) else SHIPPED_RUN_BUDGET


def _with_step_limit(config: Any, caps: RunBudget) -> Any:
    """The configuration of a call with the ceiling of the steps of the graph.

    The limit never goes above the one the caps derive and never loosens a limit that the configuration
    already carries: a caller that brought a smaller limit keeps it (ADR-054).
    """
    limit = recursion_limit_for(caps)
    if config is None:
        return {"recursion_limit": limit}
    if not isinstance(config, Mapping):
        return config
    brought = config.get("recursion_limit")
    if isinstance(brought, int) and not isinstance(brought, bool) and brought <= limit:
        return config
    return {**config, "recursion_limit": limit}


@dataclass
class Integrator:
    """The assembled agent: the `create_agent` graph plus the verifier and the case memory.

    `invoke` passes through to the graph and adds the ceiling of the steps of the graph to the configuration
    of the call, so every path that reaches the graph is limited (ADR-054).

    `counts_calls` says whether this integrator reserves the calls of the turn against its own coordinator
    (ADR-054). It is True for the integrator that `build_integrator` builds, whose graph carries the
    reservation. It is False for an integrator whose graph was built elsewhere, because then the side that
    holds the provider is the one that counts.
    """

    graph: Any
    tools: list[BaseTool]
    verifier: Verifier = _default_verifier
    case_memory: CaseMemory | None = None
    triage: Runnable | None = None
    system_prompt: str = INTEGRATOR_SYSTEM_PROMPT
    run_context: RunContext | None = None
    counts_calls: bool = False
    # The retry of a failed model, when the deployment consented to it (ADR-084). The runner of the graph and the
    # runner of the triage are two, because the model of a retry is built differently in each of them.
    fallback: FallbackRunner | None = None
    triage_fallback: FallbackRunner | None = None
    # The name of the model of the triage, as the deployment named it. The name is what the cascade of the
    # deployment holds, and it is the name that says which model of the cascade a failed triage may retry with.
    triage_model: str | None = None
    _metadata: dict[str, Any] = field(default_factory=dict, repr=False)

    def invoke(self, payload: Any, config: Any = None, **kwargs: Any) -> Any:
        """Runs the graph, with the ceiling of the turn when the caller did not bring one.

        Every path that reaches the graph carries a limit of the steps: the one the caps of the turn derive
        (the caps of the shipped paths when the caller brought none), so no way of reaching the graph is
        unbounded (ADR-054).

        The limit never goes above the derived one and never loosens a limit the configuration already
        carries: a caller that brought a smaller limit keeps it.
        """
        if "context" not in kwargs:
            kwargs["context"] = shipped_turn_budget(owner="integrator" if self.counts_calls else "none")
        config = _with_step_limit(config, _caps_of_turn(kwargs.get("context")))
        return self.graph.invoke(payload, config, **kwargs)

    def identity(self) -> dict[str, str]:
        """The identity of the execution this agent belongs to, empty when there is no context.

        The identity is kept on the agent so that the trace, the result and the replay bundle can all say whose
        execution it was, without the caller having to carry it around.
        """
        return self.run_context.identity() if self.run_context is not None else {}


def build_integrator(
    model: BaseChatModel | None = None,
    *,
    db_path: Path | str | None = None,
    verifier: Verifier | None = None,
    checkpointer: Any | None = None,
    query_model: BaseChatModel | None = None,
    fx_client: FxClient | None = None,
    index_root: Path | str | None = None,
    embeddings: Embeddings | None = None,
    case_memory: CaseMemory | None = None,
    policy_model: BaseChatModel | None = None,
    triage_model: BaseChatModel | None = None,
    model_names: Mapping[str, str] | None = None,
    fallback_factory: Callable[[str], Any] | None = None,
    system_prompt: str = INTEGRATOR_SYSTEM_PROMPT,
    run_context: RunContext | None = None,
) -> Integrator:
    """Builds the integrator. With no arguments, everything follows the configuration (offline mode, `data/`).

    `model` talks and picks tools; `query_model` generates the `query_ledger` SQL (without it, the tool
    uses the configured model). `case_memory` is the long-term memory, read by `recall_cases` and written
    at the end of a fully supported investigation. `policy_model` rewrites the `search_policies` question (without
    it, the tool uses the configured model), which lets the temperature be fixed and the rewrite be scripted.
    `triage_model` reads the question and writes the plan that goes to the agent (without it, the configured model).
    `run_context` is the identity and the scope of the execution; with it, the case memory lives in the session
    folder instead of the global folder of the configuration.
    `model_names` names the model of each slot the way the deployment named it, and it is what the retry of a
    failed model reads to find the neighbour of the retry in the cascade of the deployment (ADR-084).
    `fallback_factory` builds the model of a retry, and the caller that holds the provider is the one that
    passes it: a deployment that consented to no retry, or a caller that does not pass it, has no runner and no
    middleware, and the behaviour of the run does not move (ADR-084).
    """
    # Without a context the memory stays in the global folder of the configuration, as it always was. With a context it
    # lives in the session folder: one visitor does not see the memory of another.
    memory = case_memory or CaseMemory(
        run_context.resolve_memory_dir() if run_context is not None else get_settings().runtime_dir,
        embeddings=embeddings,
    )
    tools = build_investigation_tools(
        query_model=query_model,
        db_path=db_path,
        fx_client=fx_client,
        index_root=index_root,
        embeddings=embeddings,
        case_memory=memory,
    )
    if policy_model is not None:
        policies = build_search_policies_tool(index_root=index_root, embeddings=embeddings, llm=policy_model)
        tools = [policies if tool.name == "search_policies" else tool for tool in tools]
    # The retry of a failed model, when the deployment consented to it and the caller holds the provider
    # (ADR-084). Without a consent, or without a factory, there is no runner and no middleware at all.
    strategy = strategy_of()
    graph_fallback: FallbackRunner | None = None
    triage_fallback: FallbackRunner | None = None
    if strategy is not None and fallback_factory is not None:
        cascade = model_cascade()
        graph_fallback = FallbackRunner(cascade=cascade, strategy=strategy, factory=fallback_factory)
        triage_fallback = FallbackRunner(
            cascade=cascade,
            strategy=strategy,
            factory=lambda name: build_triage_declarative(fallback_factory(name)),
        )

    middleware: list[Any] = []
    if graph_fallback is not None:
        # The retry of the fallback is outside the reservation: the reservation books the usage of a call under
        # the model of that call, and a retry that ran inside it would book the tokens of the model of the retry
        # under the model that failed (ADR-084).
        middleware.append(FallbackMiddleware(graph_fallback))
    # The reservation comes before the wall behind the tools: a cap that is reached stops the turn instead of
    # becoming the error of a tool that the model would read and work around (ADR-054).
    middleware.append(BudgetReservationMiddleware())
    middleware.append(ToolErrorMiddleware(_tool_failure_content))

    # The model of the triage, resolved once: the retry of the triage reads its name, and a caller that named no
    # triage model still runs one (ADR-085).
    triage = triage_model or get_chat_model()
    graph = create_agent(
        model or get_chat_model(),
        tools=tools,
        system_prompt=system_prompt,
        middleware=middleware,
        checkpointer=checkpointer if checkpointer is not None else InMemorySaver(),
    )
    return Integrator(
        graph=graph,
        tools=tools,
        verifier=verifier or default_verifier_for(db_path),
        case_memory=memory,
        triage=build_triage_declarative(triage),
        system_prompt=system_prompt,
        run_context=run_context,
        counts_calls=True,
        fallback=graph_fallback,
        triage_fallback=triage_fallback,
        triage_model=_triage_model_name(triage, model_names),
    )


def _triage_model_name(triage_model: BaseChatModel | None, model_names: Mapping[str, str] | None) -> str | None:
    """The name of the model of the triage, as the deployment named it.

    Why the name of the deployment first: the cascade holds the names with the provider on top of them, and a
    name without it could be the name of another provider's model. Why the name of the model object is the
    fallback: a caller that routed nothing still names a model, and the retry of the triage has to know which
    model of the cascade it may retry with (ADR-084).
    """
    named = (model_names or {}).get(SLOT_TRIAGE)
    if named:
        return named
    return model_id_of(triage_model) if triage_model is not None else None


def investigate(
    agent: Integrator,
    question: str,
    *,
    thread_id: str,
    context: str | None = None,
    on_event: OnEvent | None = None,
    budget: TurnBudget | None = None,
) -> InvestigationResult:
    """Asks the integrator a question and returns the verified result.

    The `thread_id` is the session: the same id continues the conversation, another id starts from scratch. The
    trace and evidence of the result are only those of this turn. `context` is a system message that goes to the
    agent right before the question (the demo page says there who is signed in and which statement line was
    picked); triage still reads only the question. `on_event`, when given, receives the investigation's trace span
    by span while it happens (`ledgerlens.observability.trace`): the root `investigate`, triage, the agent with each
    model and tool call, the single follow-up, verification and escalation. It may be called from a thread of the
    tools' executor. Without it, nothing changes.

    `budget` is the ceiling of the turn (ADR-054). Without it the turn carries the ceiling of the shipped paths
    (12 calls of a model, 16 calls of a tool, 120 seconds) and the integrator counts them. A caller that brings
    its own coordinator is the one that counts, because the side that holds the provider is the one that
    reserves.
    """
    trace = Tracer(on_event)
    root = trace.begin("investigate", "chain", {"question": question, "thread_id": thread_id, "context": context})
    turn = budget or turn_budget_for(agent)
    try:
        result = _investigate(agent, question, thread_id, context, trace, turn)
    except Exception as exc:
        trace.finish(root, error=f"{type(exc).__name__}: {exc}")
        raise
    usage = _usage_of_turn(turn)
    close_trace(trace, root, result, usage=usage, caps=caps_of(turn.caps))
    return result


def turn_budget_for(agent: Integrator) -> TurnBudget:
    """The ceiling of a turn that nobody bounded: the caps of the shipped paths.

    An integrator whose graph was built elsewhere (the live path builds its own graph over the wrapped tools)
    counts nothing, because the side that holds the provider is the one that counts there (ADR-054).
    """
    return shipped_turn_budget(owner="integrator" if agent.counts_calls else "none")


def _usage_of_turn(turn: TurnBudget) -> dict[str, Any]:
    """What the turn spent against what it was allowed, in the shape the trace carries.

    Nothing is recorded when nobody counted: the numbers of a turn that no coordinator saw would be a lie.

    Why the decisions of the fallback come with the usage: a reader of the trace of a run that retried has to see
    the model of the retry and the reason of it, and the decision is the only thing that carries both (ADR-084).
    """
    if turn.owner == "none":
        return {}
    usage = usage_of(turn.coordinator)
    if turn.state.fallbacks:
        usage["fallbacks"] = list(turn.state.fallbacks)
    return usage


def _investigate(
    agent: Integrator, question: str, thread_id: str, context: str | None, trace: Tracer, turn: TurnBudget
) -> InvestigationResult:
    # The limit of the steps of the graph comes from the cap of the calls of the models, so the graph and the
    # budget stop a turn that loops at the same place (ADR-054). A turn that was given no cap of the calls
    # gets the backstop of the product, which is a ceiling of the graph and not a cap of the run.
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": recursion_limit_for(turn.caps),
    }
    # The retries of a call are counted by the call: the consent of the deployment says how many retries a task
    # may get, and a task is a call of a model, so the triage is a task and each call of the graph is a task of
    # its own (ADR-084).
    first_turn = not agent.graph.get_state(config).values.get("messages")
    before_triage = len(turn.state.fallbacks)
    triage = run_triage(
        agent.triage,
        question,
        config=traced("triage", trace),
        turn=turn,
        runner=agent.triage_fallback,
        model=agent.triage_model,
    )
    # The reason of a triage whose retry did not happen: the run answers without a plan and the reader of the
    # result has to know why the plan is missing (ADR-085).
    triage_stop = _stop_reason_of(turn.state.fallbacks[before_triage:])
    if (asked := clarification_to_ask(triage, first_turn)) is not None:
        agent.graph.update_state(config, {"messages": [HumanMessage(question), AIMessage(asked)]})
        return clarification_result(question, thread_id, triage, asked)
    plan = plan_to_follow(triage)

    timer = _ToolTimer()
    run_config = {**config, **traced("agent", trace, timer)}
    messages: list[BaseMessage] = [SystemMessage(plan_message(plan))] if plan else []
    if context:
        messages.append(SystemMessage(context))
    try:
        state = agent.invoke({"messages": [*messages, HumanMessage(question)]}, run_config, context=turn)
    except BudgetExceededError as exc:
        if turn.owner != "integrator":
            # The ceiling is the caller's, so the refusal is the caller's to handle: the live path fails the run
            # with the cap named (ADR-054, section 7).
            raise
        return _cut_turn(agent, question, thread_id, config, turn, exc.cap, timer, plan, trace)
    except FallbackStopped as stopped:
        # A model failed and the retry did not happen: the run stops with the reason of the decision (ADR-084).
        # The cap that the coordinator recorded is the cap the result names, and the reason of the decision says
        # why the retry did not happen.
        if turn.owner != "integrator":
            raise
        return _cut_turn(
            agent,
            question,
            thread_id,
            config,
            turn,
            turn.cut_by() or NO_FALLBACK,
            timer,
            plan,
            trace,
            reason=stopped.decision.reason,
        )
    except GraphRecursionError:
        # The graph ran out of steps: the cut is the cap of the calls of the models when the caller gave
        # one, and the ceiling of the graph when it gave none (ADR-054).
        return _cut_turn(agent, question, thread_id, config, turn, _graph_cut(turn.caps), timer, plan, trace)
    turn_messages = _this_turn(state["messages"])
    result = _assemble(question, thread_id, turn_messages, timer.durations_ms, triage=plan, reason=triage_stop)

    asked = uncalled_steps(plan, result.tool_trace)
    days = fx_days_to_redo(question, result.evidence, result.tool_trace)
    if asked or days:
        text = followup_message(asked, days=days)
        span = trace.begin("plan_followup", "chain", {"asked": asked, "fx_days": days, "message": text})
        cut_by = turn.cut_by()
        reason: str | None = None
        extra: list[BaseMessage] | None = None
        if cut_by is not None:
            # The ceiling of the turn is spent: the follow-up does not run, and the answer that already exists
            # stands (ADR-054).
            log.info("the cap '%s' stopped the turn, the follow-up does not run", cut_by)
        else:
            try:
                extra = _ask_for_missing_tools(agent, text, len(state["messages"]), run_config, turn)
            except BudgetExceededError as exc:
                # The follow-up spends what the turn has left; a turn whose ceiling is gone does not get a
                # fresh allowance (ADR-054).
                cut_by = exc.cap
            except FallbackStopped as stopped:
                # A model of the follow-up failed and the retry did not happen: the answer that already exists
                # stands and the reason of the stop goes into the result (ADR-084).
                cut_by = turn.cut_by() or NO_FALLBACK
                reason = stopped.decision.reason
        result = _assemble(
            question,
            thread_id,
            turn_messages + (extra or []),
            timer.durations_ms,
            triage=plan,
            asked=asked,
            fx_asked=days,
            ask_failed=extra is None,
            cut_by=cut_by,
            caps=turn.caps,
            reason=reason or triage_stop,
        )
        trace.finish(
            span,
            outputs={"failed": extra is None, "cut_by": cut_by, "plan_deviations": result.plan_deviations},
        )
    return finish(agent, result, trace=trace)


def _graph_cut(caps: RunBudget) -> str:
    """The name of the cut when the graph ran out of steps.

    A cap that the caller gave names the cut, because the limit of the graph came from it. When the caller
    gave no cap of the calls of the models, the cut is the ceiling of the graph and not a cap of the run:
    naming a cap that nobody gave would be a lie (ADR-054).
    """
    return "max_model_calls" if derived_recursion_limit(caps) is not None else GRAPH_STEPS


def _stop_reason_of(decisions: list[dict[str, Any]]) -> str | None:
    """The reason of a stop of the fallback, when the decisions of the turn carry one.

    Why the decisions of the turn: a decision that stopped the retry is a value, and the value carries the reason
    that the reader of the result needs (ADR-085).
    """
    for decision in decisions:
        if decision.get("action") == ACTION_STOP:
            reason = str(decision.get("reason", "")).strip()
            if reason:
                return reason
    return None


def _cut_turn(
    agent: Integrator,
    question: str,
    thread_id: str,
    config: dict[str, Any],
    turn: TurnBudget,
    cap: str,
    timer: _ToolTimer,
    plan: Triage | None,
    trace: Tracer,
    reason: str | None = None,
) -> InvestigationResult:
    """The result of a turn that a cap cut: the answer that exists, the tools that ran and the cap that stopped it.

    A cap is not a crash: the turn comes back as a result that goes to a human, and the cap that stopped it is
    named in the missing information (ADR-054).

    Why the reason comes with it: the cut of a fallback is not a cap, and the reader of the result has to know
    why the retry did not happen (ADR-084).
    """
    if cap == NO_FALLBACK:
        log.warning("the turn of the session %s stopped: %s", thread_id, reason or "the retry did not happen")
    else:
        log.warning("the cap '%s' stopped the turn of the session %s", cap, thread_id)
    result = _assemble(
        question,
        thread_id,
        _messages_of(agent, config),
        timer.durations_ms,
        triage=plan,
        cut_by=cap,
        caps=turn.caps,
        reason=reason,
    )
    return finish(agent, result, trace=trace)


def _messages_of(agent: Integrator, config: dict[str, Any]) -> list[BaseMessage]:
    """The messages the turn has so far, read from the checkpointer after a cut.

    A turn that a cap cut did not end with a state, so the messages come from the checkpoint of the thread:
    what ran is what the trace says and what the answer that exists says.
    """
    try:
        state = agent.graph.get_state(config)
    except Exception as exc:  # the checkpoint is a courtesy: the result without it is still a result
        log.warning("could not read the state of the thread after the cut: %s: %s", type(exc).__name__, exc)
        return []
    return _this_turn(list(state.values.get("messages") or []))


def traced(run_name: str, trace: Tracer, *handlers: BaseCallbackHandler) -> dict[str, Any]:
    """The config of a LangChain call with the run name and the trace callbacks."""
    return {"run_name": run_name, "callbacks": [*handlers, *trace.handlers()]}


def close_trace(
    trace: Tracer,
    root: str,
    result: InvestigationResult,
    *,
    usage: dict[str, Any] | None = None,
    caps: dict[str, Any] | None = None,
) -> None:
    """Closes the trace root with the summary and, with LangSmith on, the URLs of the runs sent to it.

    `usage` is what the turn spent and `caps` is what it was allowed, so a reader of the trace sees the two
    together (ADR-054).
    """
    if not trace.enabled:
        return
    tokens = trace.tokens()
    urls = [{"name": trace.spans[r].name, "url": u} for r in trace.roots if (u := langsmith_url(r))]
    outputs = {
        "answer": result.answer,
        "recommended_action": result.recommended_action,
        "requires_human_review": result.requires_human_review,
        "plan_deviations": result.plan_deviations,
        "tool_calls": len(result.tool_trace),
        "tokens": tokens,
        "summary": summary_line(result, trace.elapsed_ms(root), tokens),
    }
    if usage:
        outputs["usage"] = usage
    if caps:
        outputs["budget"] = caps
    trace.finish(root, outputs=outputs, **({"langsmith": urls} if urls else {}))


def _ask_for_missing_tools(
    agent: Integrator, text: str, seen: int, run_config: dict[str, Any], turn: TurnBudget
) -> list[BaseMessage] | None:
    """The messages the follow-up `text` produced (from the follow-up on), or `None` if the call failed.

    A network or quota failure here cannot erase the answer the turn already had, so it only goes to the log.
    A cap that is reached is not a failure of the follow-up: it goes up, so the result says which cap stopped
    the turn (ADR-054).
    """
    try:
        state = agent.invoke({"messages": [HumanMessage(text)]}, run_config, context=turn)
    except BudgetExceededError:
        if turn.owner != "integrator":
            # The ceiling is the caller's: the follow-up fails like any other failure of the follow-up and the
            # answer that already existed stands.
            log.warning("the plan follow-up failed, the first answer stands: the budget of the run is exhausted")
            return None
        raise
    except FallbackStopped:
        # A model of the follow-up failed and the retry did not happen: the reason of the stop goes up, because a
        # follow-up that swallowed it would hide the only thing that says why the turn ended (ADR-084).
        raise
    except Exception as exc:  # the follow-up is an extra: the earlier answer still stands
        log.warning("the plan follow-up failed, the first answer stands: %s: %s", type(exc).__name__, exc)
        return None
    return list(state["messages"][seen:])


def finish(agent: Any, result: InvestigationResult, *, trace: Tracer | None = None) -> InvestigationResult:
    """Verifies the assembled result and saves the case if every verdict was supported.

    `agent` is the integrator of either version: only `verifier` and `case_memory` are used. `trace` receives the
    `verify` span (with one child per claim), the `escalation` span and the case write.
    """
    trace = trace or Tracer()
    span = trace.begin("verify", "verifier", {"answer": result.answer, "evidence_ids": [e.id for e in result.evidence]})
    try:
        verified = agent.verifier(result)
    except Exception as exc:
        trace.finish(span, error=f"{type(exc).__name__}: {exc}")
        raise
    verdicts = {v.claim_id: v for v in verified.verdicts}
    for claim in verified.claims:
        verdict = verdicts.get(claim.id)
        trace.point(
            claim.id,
            "verifier",
            {"text": claim.text, "kind": claim.kind, "evidence_ids": claim.evidence_ids, "numeric": claim.numeric},
            verdict,
            check=verdict.method if verdict else None,
            label=verdict.label if verdict else None,
        )
    counts = {label: sum(v.label == label for v in verified.verdicts) for label in typing.get_args(VerdictLabel)}
    trace.finish(span, outputs={"verdicts": counts, "coherence": verified.coherence})
    trace.point(
        "escalation",
        "verifier",
        {"missing_information": result.missing_information, "evidence_ids": [e.id for e in result.evidence]},
        {
            "requires_human_review": verified.requires_human_review,
            "reasons": review_reasons(verified),
            "recommended_action": verified.recommended_action,
        },
    )
    outcome = _remember(agent.case_memory, verified)
    if outcome is not None:
        trace.point("CaseMemory.write_case", "chain", {"session_id": verified.session_id}, outcome)
    return verified


# --- triage -------------------------------------------------------------------------------------


def run_triage(
    triage: Runnable | None,
    question: str,
    *,
    config: dict[str, Any] | None = None,
    turn: TurnBudget | None = None,
    runner: FallbackRunner | None = None,
    model: str | None = None,
) -> Triage | None:
    """The question's `Triage`, or `None` if there is no triage or it failed. A failure does not stop the question.

    `config` goes to the triage call (the run name and the trace callbacks). `turn` is the ceiling of the turn:
    the triage is a call of a model, so it is reserved like any other one (ADR-054). `runner` is the retry of a
    failed triage, when the deployment consented to it (ADR-084), and `model` is the name the router gave to the
    model of the triage, which is the name that says which model of the cascade the retry may use."""
    if triage is None:
        return None
    try:
        if turn is not None:
            turn.reserve_model_call("triage")
        out = triage.invoke({"complaint": question}, config)
    except BudgetExceededError:
        raise
    except Exception as exc:  # network, quota or exhausted script: the agent answers with no plan, as before triage
        retried = _triage_with_fallback(
            runner, question, config=config, turn=turn, model=model, failure=exc
        )
        if retried is not None:
            return retried
        log.warning("triage failed, the agent runs without a plan: %s: %s", type(exc).__name__, exc)
        return None
    if isinstance(out, TriageError):
        log.warning("triage unreadable (%s), the agent runs without a plan", out.code)
        return None
    return out


def _triage_with_fallback(
    runner: FallbackRunner | None,
    question: str,
    *,
    config: dict[str, Any] | None,
    turn: TurnBudget | None,
    model: str | None,
    failure: Exception,
) -> Triage | None:
    """The triage of the model of the retry, when the deployment consented to it and the budget covers it.

    Why the triage and not the agent: the triage is the lightest task of the run and the one that fails first,
    and a run without a plan is a run that answers less than it could.

    Why the model that failed is not called again: the call that failed already happened and the money of it is
    already spent, and a retry that answers the same model would spend the budget of the run twice for the same
    failure (ADR-084).

    Why the retry carries the plan of the complaint: the reservation of the retry checks the caps before the
    call, and a cap of the tokens and a cap of the money are caps of a planned call (FR-009).
    """
    if runner is None or model is None:
        return None

    def attempt(chain: Any) -> Any:
        return chain.invoke({"complaint": question}, config)

    try:
        out, _ = runner.retry(
            attempt,
            failed_model=model,
            turn=turn,
            planned_input_tokens=planned_input_of(triage_input_of(question)),
            planned_output_tokens=PLANNED_OUTPUT_TOKENS,
            failure=failure,
        )
    except FallbackStopped as stopped:
        log.warning(
            "the triage failed and the retry did not happen: %s",
            stopped.decision.reason,
        )
        return None
    if isinstance(out, TriageError):
        log.warning("triage unreadable (%s), the agent runs without a plan", out.code)
        return None
    return out


def clarification_to_ask(triage: Triage | None, first_turn: bool) -> str | None:
    """The question back, when triage cannot plan and the conversation is at its start.

    Triage reads only the current question. On a later turn "and the refund?" looks vague to it and the agent, which
    sees the history, understands, so there triage does not ask back.
    """
    if triage is not None and triage.needs_clarification and first_turn:
        return triage.clarification_question or None
    return None


def plan_to_follow(triage: Triage | None) -> Triage | None:
    """The triage that counts as a plan: one that knows what to investigate, not one that asked for clarification."""
    return triage if triage is not None and not triage.needs_clarification else None


def plan_message(triage: Triage) -> str:
    """The plan as a system message for the agent, with the notice that it may be revised."""
    steps = []
    for step in triage.plan:
        tool = f"-> {step.tool}" if step.tool else "-> no tool"
        after = f" (after {', '.join(step.depends_on)})" if step.depends_on else ""
        steps.append(f"{step.id}: {step.goal} {tool}{after}")
    return (
        f"Triage plan (intent: {triage.intent}). It is a plan, not a proof: run the steps that have a "
        "tool, in dependency order, without skipping a step for no reason. If an observation invalidates it "
        "(record does not exist, tool error), revise the plan and say in the answer which step changed and why.\n"
        + "\n".join(steps)
    )


def plan_deviations(triage: Triage | None, trace: list[ToolCallRecord]) -> list[str]:
    """Where the trace strayed from the plan: a step with a tool that did not run and a tool the plan did not expect."""
    if triage is None:
        return []
    called = [record.tool for record in trace]
    planned = {step.tool for step in triage.plan if step.tool}
    out = [
        f"{step.id}: {step.tool} was in the plan and was not called ({step.goal})"
        for step in triage.plan
        if step.tool and step.tool not in called
    ]
    out += [f"{tool}: called outside the plan" for tool in dict.fromkeys(called) if tool not in planned]
    return out


def uncalled_steps(triage: Triage | None, trace: list[ToolCallRecord]) -> list[PlanStep]:
    """The plan steps that have a tool whose tool was not called in this turn."""
    if triage is None:
        return []
    called = {record.tool for record in trace}
    return [step for step in triage.plan if step.tool and step.tool not in called]


def fx_days_to_redo(question: str, evidence: list[Evidence], trace: list[ToolCallRecord]) -> list[str]:
    """The `get_reference_fx` days with no origin in the ledger or the question, when no ledger date was asked for.

    Without ledger evidence there is nothing to compare with. If any call used a ledger day (even one the source
    refused), a call for a day with no origin is an extra query and nothing is asked. The verifier later checks the
    FX rate the answer uses.
    """
    from ledgerlens.verify.claims import ledger_days  # lazy: the verification package is imported only to verify

    known = ledger_days(evidence, question)
    if known is None:
        return []
    asked = [str(call.input.get("date")) for call in trace if call.tool == "get_reference_fx"]
    return [] if any(day in known for day in asked) else list(dict.fromkeys(asked))


def followup_message(steps: list[PlanStep], *, days: list[str] | None = None) -> str:
    """The single follow-up to the agent: what was missing (a plan tool, FX for a ledger date) and the final answer."""
    parts = []
    if steps:
        listed = ", ".join(f"{step.id} ({step.tool})" for step in steps)
        parts.append(
            f"Plan check: in these steps the tool was not called: {listed}. Call each one now or "
            "say, in one sentence, why it is not needed."
        )
    if days:
        parts.append(
            f"Date check: the FX rate was asked for {', '.join(days)}, and that date does not appear in the ledger "
            "you queried nor in the question. Read the payment or refund date in the ledger (query it again if "
            "it is missing), ask for the FX rate on that date and redo the calculation with the new rate."
        )
    parts.append("Then give the final answer to the original question, with the citations.")
    return " ".join(parts)


def followup_notes(steps: list[PlanStep], trace: list[ToolCallRecord], *, failed: bool) -> list[str]:
    """The follow-up record in `plan_deviations`: the step, the tool and what the agent did after."""
    called = {record.tool for record in trace}
    if failed:
        return [f"{step.id}: {step.tool}: the follow-up failed, the earlier answer stands" for step in steps]
    return [
        f"{step.id}: {step.tool}: asked of the agent once, and it "
        + ("called it" if step.tool in called else "did not call it")
        for step in steps
    ]


def fx_followup_notes(days: list[str], remaining: list[str], *, failed: bool) -> list[str]:
    """The FX date follow-up record: the day with no origin and whether the agent swapped it for a ledger date."""
    if failed:
        return [
            f"get_reference_fx: FX for {day} with no ledger origin: the follow-up failed, the earlier answer stands"
            for day in days
        ]
    return [
        f"get_reference_fx: FX for {day} with no origin in the ledger: asked of the agent once, and it "
        + ("kept the date" if day in remaining else "redid it with a ledger date")
        for day in days
    ]


def clarification_result(question: str, thread_id: str, triage: Triage | None, asked: str) -> InvestigationResult:
    """The result of a question sent back: no tools, evidence or claims, so nothing to verify."""
    return InvestigationResult(
        session_id=thread_id,
        question=question,
        triage=triage,
        answer=asked,
        claims=[],
        evidence=[],
        verdicts=[],
        coherence=Coherence(passed=True),
        recommended_action="ask_for_clarification",
        requires_human_review=False,
    )


# --- result assembly ---------------------------------------------------------------------------


class _ToolTimer(BaseCallbackHandler):
    """Times each tool call. Messages carry no duration, so it comes from the callbacks."""

    def __init__(self) -> None:
        self._started: dict[UUID, float] = {}
        self.durations_ms: list[int] = []  # in the order the calls started
        self._slot: dict[UUID, int] = {}

    def on_tool_start(self, serialized: Any, input_str: str, *, run_id: UUID, **kwargs: Any) -> None:
        self._started[run_id] = time.perf_counter()
        self._slot[run_id] = len(self.durations_ms)
        self.durations_ms.append(0)

    def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        self._finish(run_id)

    def on_tool_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._finish(run_id)

    def _finish(self, run_id: UUID) -> None:
        started = self._started.pop(run_id, None)
        if started is not None:
            self.durations_ms[self._slot[run_id]] = max(0, round((time.perf_counter() - started) * 1000))


def _this_turn(messages: list[BaseMessage]) -> list[BaseMessage]:
    """The messages of the current turn: from the user's last question on."""
    for index in range(len(messages) - 1, -1, -1):
        if isinstance(messages[index], HumanMessage):
            return messages[index:]
    return messages


def _text_of(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    parts = [part for part in content if isinstance(part, (str, dict))]
    return "".join(part if isinstance(part, str) else str(part.get("text", "")) for part in parts)


def _envelope(message: ToolMessage) -> dict[str, Any]:
    """The tool's response envelope. Text that is not JSON becomes an error, so it does not vanish from the trace."""
    try:
        parsed = json.loads(_text_of(message))
    except ValueError:
        parsed = None
    if isinstance(parsed, dict) and "ok" in parsed:
        return parsed
    return {"ok": False, "error": {"code": "UNPARSEABLE_TOOL_RESULT", "message": _text_of(message)[:200]}}


def _ref(tool: str, evidence_id: str, data: dict[str, Any], tool_input: dict[str, Any]) -> str:
    """Where the evidence came from, in one line: the query, the excerpt, the record or the formula."""
    if tool == "query_ledger":
        return str(data.get("sql") or evidence_id)
    if tool == "calculate":
        return str(data.get("formula") or evidence_id)
    if tool == "get_ledger_record":
        return str(tool_input.get("id") or evidence_id)
    return evidence_id.split(":", 1)[1]


def _content(tool: str, evidence_id: str, data: dict[str, Any]) -> str:
    """The evidence text: the item that has the id, when the call returned several, else the whole data."""
    key = _ITEM_KEY.get(tool)
    if key is not None:
        for item in data.get("results", []):
            if isinstance(item, dict) and evidence_id.split(":", 1)[1] == str(item.get(key)):
                return json.dumps(item, ensure_ascii=False)
    return json.dumps(data, ensure_ascii=False)


def _assemble(
    question: str,
    thread_id: str,
    turn: list[BaseMessage],
    durations_ms: list[int],
    *,
    triage: Triage | None = None,
    asked: list[PlanStep] | None = None,
    fx_asked: list[str] | None = None,
    ask_failed: bool = False,
    cut_by: str | None = None,
    caps: RunBudget | None = None,
    reason: str | None = None,
) -> InvestigationResult:
    """Builds the turn's result: trace, evidence and what was missing, without judging the answer.

    `asked` are the steps whose tool the code asked the agent for after the first answer; the follow-up
    goes into `plan_deviations`, and `ask_failed` says the follow-up call did not complete. `fx_asked` are the FX
    days with no origin in the ledger that the follow-up pointed out.

    `cut_by` names the cap that stopped the turn (ADR-054). The cap goes into the missing information with its
    value and the result goes to a human, because a turn that ran out of ceiling is not an answer. `reason` is
    the reason of a cut that is not a cap, which is the case of a fallback that did not happen (ADR-084).
    """
    results = {m.tool_call_id: m for m in turn if isinstance(m, ToolMessage)}
    calls = [call for m in turn if isinstance(m, AIMessage) for call in m.tool_calls]
    now = datetime.now(UTC)

    trace: list[ToolCallRecord] = []
    evidence: list[Evidence] = []
    seen_ids: set[str] = set()
    failures: dict[str, str] = {}  # tool -> error still with no recovery
    for step, call in enumerate(calls, start=1):
        message = results.get(call["id"])
        if message is None:  # the call never ran (step limit, for example)
            continue
        envelope = _envelope(message)
        tool, args = call["name"], dict(call["args"])
        succeeded = bool(envelope.get("ok"))
        failure = envelope.get("error") or {}
        ids = list(envelope.get("evidence_ids") or []) if succeeded else []
        trace.append(
            ToolCallRecord(
                step=step,
                tool=tool,
                input=args,
                ok=succeeded,
                evidence_ids=ids,
                error_code=None if succeeded else str(failure.get("code", "UNKNOWN")),
                duration_ms=durations_ms[step - 1] if step - 1 < len(durations_ms) else 0,
            )
        )
        if succeeded:
            failures.pop(tool, None)
            data = envelope.get("data") or {}
            for evidence_id in ids:
                if evidence_id in seen_ids:
                    continue
                seen_ids.add(evidence_id)
                evidence.append(
                    Evidence(
                        id=evidence_id,
                        source_type=_SOURCE_BY_PREFIX[evidence_id.split(":", 1)[0]],  # type: ignore[arg-type]
                        tool=tool,  # type: ignore[arg-type]
                        content=_content(tool, evidence_id, data),
                        ref=_ref(tool, evidence_id, data, args),
                        retrieved_at=now,
                    )
                )
        else:
            failures[tool] = f"{tool} ({failure.get('code', 'UNKNOWN')}): {failure.get('message', '')}".strip()

    answers = [m for m in turn if isinstance(m, AIMessage) and not m.tool_calls]
    missing = list(failures.values())
    if cut_by is not None:
        missing.append(cap_sentence(cut_by, caps))
    if reason:
        missing.append(reason)
    return InvestigationResult(
        session_id=thread_id,
        question=question,
        triage=triage,
        answer=_text_of(answers[-1]) if answers else "",
        claims=[],
        evidence=evidence,
        verdicts=[],
        coherence=Coherence(passed=True),
        missing_information=missing,
        recommended_action="escalate_to_human" if cut_by is not None else "none",
        requires_human_review=bool(failures) or not evidence or cut_by is not None,
        tool_trace=trace,
        plan_deviations=plan_deviations(triage, trace)
        + (followup_notes(asked, trace, failed=ask_failed) if asked else [])
        + (
            fx_followup_notes(fx_asked, fx_days_to_redo(question, evidence, trace), failed=ask_failed)
            if fx_asked
            else []
        ),
    )


def _remember(memory: CaseMemory | None, result: InvestigationResult) -> dict[str, Any] | None:
    """Saves the case when the investigation was fully supported and returns what `write_case` said (`None` with no
    memory).

    A failure while saving does not stop the answer: it goes to the log and comes back as a case not written."""
    if memory is None:
        return None
    try:
        outcome = memory.write_case(result)
    except Exception as exc:
        log.exception("could not write the case for session %s", result.session_id)
        return {"written": False, "reason": f"write failed ({type(exc).__name__})"}
    log.info("case memory for session %s: %s", result.session_id, outcome)
    return outcome
