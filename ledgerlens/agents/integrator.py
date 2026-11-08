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

Numbers: nothing here computes money. What the result claims comes from the tools.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any
from uuid import UUID

from langchain.agents import create_agent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import InMemorySaver

from ledgerlens.agents.modern import DEFAULT_SYSTEM_PROMPT, build_investigation_tools
from ledgerlens.chains.parsers import TriageError
from ledgerlens.chains.triage import build_triage_declarative
from ledgerlens.config import get_chat_model, get_settings
from ledgerlens.memory.long_term import CaseMemory
from ledgerlens.schemas import Coherence, Evidence, InvestigationResult, PlanStep, ToolCallRecord, Triage
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


@dataclass
class Integrator:
    """The assembled agent: the `create_agent` graph plus the verifier and the case memory.

    `invoke` passes through to the graph, so this object works where a LangChain agent is expected.
    """

    graph: Any
    tools: list[BaseTool]
    verifier: Verifier = _default_verifier
    case_memory: CaseMemory | None = None
    triage: Runnable | None = None
    system_prompt: str = INTEGRATOR_SYSTEM_PROMPT
    _metadata: dict[str, Any] = field(default_factory=dict, repr=False)

    def invoke(self, payload: Any, config: Any = None, **kwargs: Any) -> Any:
        return self.graph.invoke(payload, config, **kwargs)


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
    system_prompt: str = INTEGRATOR_SYSTEM_PROMPT,
) -> Integrator:
    """Builds the integrator. With no arguments, everything follows the configuration (offline mode, `data/`).

    `model` talks and picks tools; `query_model` generates the `query_ledger` SQL (without it, the tool
    uses the configured model). `case_memory` is the long-term memory, read by `recall_cases` and written
    at the end of a fully supported investigation. `policy_model` rewrites the `search_policies` question (without
    it, the tool uses the configured model), which lets the temperature be fixed and the rewrite be scripted.
    `triage_model` reads the question and writes the plan that goes to the agent (without it, the configured model).
    """
    memory = case_memory or CaseMemory(get_settings().runtime_dir, embeddings=embeddings)
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
    graph = create_agent(
        model or get_chat_model(),
        tools=tools,
        system_prompt=system_prompt,
        checkpointer=checkpointer if checkpointer is not None else InMemorySaver(),
    )
    return Integrator(
        graph=graph,
        tools=tools,
        verifier=verifier or default_verifier_for(db_path),
        case_memory=memory,
        triage=build_triage_declarative(triage_model or get_chat_model()),
        system_prompt=system_prompt,
    )


def investigate(agent: Integrator, question: str, *, thread_id: str, context: str | None = None) -> InvestigationResult:
    """Asks the integrator a question and returns the verified result.

    The `thread_id` is the session: the same id continues the conversation, another id starts from scratch. The
    trace and evidence of the result are only those of this turn. `context` is a system message that goes to the
    agent right before the question (the demo page says there who is signed in and which statement line was
    picked); triage still reads only the question.
    """
    config = {"configurable": {"thread_id": thread_id}}
    first_turn = not agent.graph.get_state(config).values.get("messages")
    triage = run_triage(agent.triage, question)
    if (asked := clarification_to_ask(triage, first_turn)) is not None:
        agent.graph.update_state(config, {"messages": [HumanMessage(question), AIMessage(asked)]})
        return clarification_result(question, thread_id, triage, asked)
    plan = plan_to_follow(triage)

    timer = _ToolTimer()
    run_config = {**config, "callbacks": [timer]}
    messages: list[BaseMessage] = [SystemMessage(plan_message(plan))] if plan else []
    if context:
        messages.append(SystemMessage(context))
    state = agent.invoke({"messages": [*messages, HumanMessage(question)]}, run_config)
    turn = _this_turn(state["messages"])
    result = _assemble(question, thread_id, turn, timer.durations_ms, triage=plan)

    asked = uncalled_steps(plan, result.tool_trace)
    days = fx_days_to_redo(question, result.evidence, result.tool_trace)
    if asked or days:
        extra = _ask_for_missing_tools(agent, followup_message(asked, days=days), len(state["messages"]), run_config)
        result = _assemble(
            question,
            thread_id,
            turn + (extra or []),
            timer.durations_ms,
            triage=plan,
            asked=asked,
            fx_asked=days,
            ask_failed=extra is None,
        )
    return finish(agent, result)


def _ask_for_missing_tools(
    agent: Integrator, text: str, seen: int, run_config: dict[str, Any]
) -> list[BaseMessage] | None:
    """The messages the follow-up `text` produced (from the follow-up on), or `None` if the call failed.

    A network or quota failure here cannot erase the answer the turn already had, so it only goes to the log.
    """
    try:
        state = agent.invoke({"messages": [HumanMessage(text)]}, run_config)
    except Exception as exc:  # the follow-up is an extra: the earlier answer still stands
        log.warning("the plan follow-up failed, the first answer stands: %s: %s", type(exc).__name__, exc)
        return None
    return list(state["messages"][seen:])


def finish(agent: Any, result: InvestigationResult) -> InvestigationResult:
    """Verifies the assembled result and saves the case if every verdict was supported.

    `agent` is the integrator of either version: only `verifier` and `case_memory` are used.
    """
    verified = agent.verifier(result)
    _remember(agent.case_memory, verified)
    return verified


# --- triage -------------------------------------------------------------------------------------


def run_triage(triage: Runnable | None, question: str) -> Triage | None:
    """The question's `Triage`, or `None` if there is no triage or it failed. A failure does not stop the question."""
    if triage is None:
        return None
    try:
        out = triage.invoke({"complaint": question})
    except Exception as exc:  # network, quota or exhausted script: the agent answers with no plan, as before triage
        log.warning("triage failed, the agent runs without a plan: %s: %s", type(exc).__name__, exc)
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
) -> InvestigationResult:
    """Builds the turn's result: trace, evidence and what was missing, without judging the answer.

    `asked` are the steps whose tool the code asked the agent for after the first answer; the follow-up
    goes into `plan_deviations`, and `ask_failed` says the follow-up call did not complete. `fx_asked` are the FX
    days with no origin in the ledger that the follow-up pointed out.
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
    return InvestigationResult(
        session_id=thread_id,
        question=question,
        triage=triage,
        answer=_text_of(answers[-1]) if answers else "",
        claims=[],
        evidence=evidence,
        verdicts=[],
        coherence=Coherence(passed=True),
        missing_information=list(failures.values()),
        recommended_action="none",
        requires_human_review=bool(failures) or not evidence,
        tool_trace=trace,
        plan_deviations=plan_deviations(triage, trace)
        + (followup_notes(asked, trace, failed=ask_failed) if asked else [])
        + (
            fx_followup_notes(fx_asked, fx_days_to_redo(question, evidence, trace), failed=ask_failed)
            if fx_asked
            else []
        ),
    )


def _remember(memory: CaseMemory | None, result: InvestigationResult) -> None:
    """Saves the case when the investigation was fully supported. A failure while saving does not stop the answer."""
    if memory is None:
        return
    try:
        outcome = memory.write_case(result)
    except Exception:
        log.exception("could not write the case for session %s", result.session_id)
        return
    log.info("case memory for session %s: %s", result.session_id, outcome)
