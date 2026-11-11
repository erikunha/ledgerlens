"""Legacy integrator: the same agent as `integrator.py`, built with `AgentExecutor` and `RunnableWithMessageHistory`.

Why it exists: it shows the single agent, with the RAG, SQL and API tools under one executor, built with
`create_openai_tools_agent` and `AgentExecutor`, with the history wired by `RunnableWithMessageHistory`, so
that memory lasts the whole session. `integrator.py` delivers the same result with the current API (`create_agent`
and a checkpointer, ADR-010); this module is the twin on the legacy API. Both versions share the six tools
(`build_investigation_tools`), the prompt (`INTEGRATOR_SYSTEM_PROMPT`), the result assembly, the verifier and the
rule for saving the case. Flow of one question::

    question -> triage (intent, entities, plan)
             -> RunnableWithMessageHistory (loads the session history from SQLite)
             -> AgentExecutor (model + six tools, a loop of calling a tool and reading the observation)
             -> intermediate_steps turned into messages -> `_assemble` (trace, evidence, gaps)
             -> verifier -> if every verdict was supported, saves the case -> final result

What changes compared with `create_agent`:

- **History**: lives in the project's SQLite file (`ledgerlens/memory/history.py`), per `session_id`, and so
  survives a new process. `create_agent` keeps the state in the checkpointer, inside the process.
- **What the history keeps**: only the question and the final answer of each turn. The tool rounds of a
  turn do not come back to the next turn's prompt, because `AgentExecutor` keeps them in `agent_scratchpad`, which
  lasts one call. The checkpointer also keeps the tool messages. Facts from old turns stay
  in the answer and, when proven, in the case memory (`recall_cases`).
- **Trace and evidence**: `AgentExecutor` returns `intermediate_steps`, a list of (action, observation). Each
  pair becomes an `AIMessage` with the call and a `ToolMessage` with the observation, and the final answer becomes
  the last `AIMessage`. The observation arrives as the envelope dictionary and is serialized as JSON, as `create_agent`
  does. With these messages, the modern integrator's `_assemble` builds the result unchanged.
- **Triage**: the same as with `create_agent`. The plan reaches the prompt as a system message between the history
  and the question (`triage_context`), repeated on every loop round and outside the saved history, which keeps
  only the question and the answer. A question returned by triage is saved in the session history without calling
  the executor.
- **Single follow-up**: the same as in the modern integrator. If a step with a tool did not run, or FX was asked
  for a date with no origin in the ledger, the executor is called once more in the same session, with the plan (if
  any) as context and the follow-up as input; that round's actions and answer go into the turn. The follow-up and
  the new answer stay in the session history like any exchange.
- **Duration**: comes from the same callbacks (`_ToolTimer`), passed in the call configuration.
- **Step limit**: when `max_iterations` runs out, the executor returns a fixed text as the answer and the trace
  keeps only the calls that ran.
- **No `policy_model`**: the `search_policies` question rewrite uses the configured model; swapping that
  model for a scripted one is the job of `build_integrator`.

Numbers: nothing here computes money. What the result claims comes from the tools.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_classic.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.tools import BaseTool

from ledgerlens.agents.integrator import (
    INTEGRATOR_SYSTEM_PROMPT,
    Verifier,
    _assemble,
    _default_verifier,
    _ToolTimer,
    clarification_result,
    clarification_to_ask,
    close_trace,
    default_verifier_for,
    finish,
    followup_message,
    fx_days_to_redo,
    plan_message,
    plan_to_follow,
    run_triage,
    traced,
    uncalled_steps,
)
from ledgerlens.agents.modern import build_investigation_tools
from ledgerlens.chains.triage import build_triage_declarative
from ledgerlens.config import get_chat_model, get_settings
from ledgerlens.memory.history import DEFAULT_MAX_TOKENS, get_session_history
from ledgerlens.memory.long_term import CaseMemory
from ledgerlens.observability.trace import OnEvent, Tracer
from ledgerlens.run_context import RunContext
from ledgerlens.schemas import InvestigationResult
from ledgerlens.tools.fx import FxClient

log = logging.getLogger(__name__)


@dataclass
class ExecutorIntegrator:
    """The assembled agent: the executor, the history around it, the verifier and the case memory.

    `invoke` passes through to the runnable with history, so this object works where a LangChain chain is expected.
    """

    executor: AgentExecutor
    runnable: RunnableWithMessageHistory
    tools: list[BaseTool]
    verifier: Verifier = _default_verifier
    case_memory: CaseMemory | None = None
    triage: Runnable | None = None
    system_prompt: str = INTEGRATOR_SYSTEM_PROMPT
    run_context: RunContext | None = None

    def invoke(self, payload: Any, config: Any = None, **kwargs: Any) -> Any:
        return self.runnable.invoke(payload, config, **kwargs)

    def identity(self) -> dict[str, str]:
        """The identity of the execution this agent belongs to, empty when there is no context.

        The legacy path carries the context too, so that the two integrators answer the same question about whose
        execution it was.
        """
        return self.run_context.identity() if self.run_context is not None else {}


def build_executor_integrator(
    model: BaseChatModel | None = None,
    *,
    db_path: Path | str | None = None,
    history_db_path: Path | str | None = None,
    verifier: Verifier | None = None,
    query_model: BaseChatModel | None = None,
    fx_client: FxClient | None = None,
    index_root: Path | str | None = None,
    embeddings: Embeddings | None = None,
    case_memory: CaseMemory | None = None,
    triage_model: BaseChatModel | None = None,
    system_prompt: str = INTEGRATOR_SYSTEM_PROMPT,
    max_iterations: int = 8,
    max_history_tokens: int = DEFAULT_MAX_TOKENS,
    run_context: RunContext | None = None,
) -> ExecutorIntegrator:
    """Builds the legacy integrator. The tool arguments are those of `build_integrator`.

    `db_path` is the ledger the tools read; `history_db_path` is the history SQLite file (without it, the
    `history.db` in the configured runtime folder). A new object over the same `history_db_path` recovers
    the sessions already saved. `triage_model` reads the question and writes the agent's plan (without it, the
    configured model). `run_context` is the identity and the scope of the execution; with it, the case memory lives in
    the session folder instead of the global folder of the configuration.
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

    # The system prompt goes in as a ready message, not a template, so braces in the text do not break it.
    prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessage(content=system_prompt),
            MessagesPlaceholder("chat_history", optional=True),
            MessagesPlaceholder("triage_context", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )
    llm = model or get_chat_model()
    executor = AgentExecutor(
        agent=create_openai_tools_agent(llm, tools, prompt),
        tools=tools,
        max_iterations=max_iterations,
        return_intermediate_steps=True,  # without the steps there is no trace and no evidence
    )
    runnable = RunnableWithMessageHistory(
        executor,
        lambda session_id: get_session_history(session_id, db_path=history_db_path, max_tokens=max_history_tokens),
        input_messages_key="input",
        history_messages_key="chat_history",
        output_messages_key="output",
    )
    return ExecutorIntegrator(
        executor=executor,
        runnable=runnable,
        tools=tools,
        verifier=verifier or default_verifier_for(db_path),
        case_memory=memory,
        triage=build_triage_declarative(triage_model or get_chat_model()),
        system_prompt=system_prompt,
        run_context=run_context,
    )


def investigate_with_executor(
    agent: ExecutorIntegrator, question: str, *, session_id: str, on_event: OnEvent | None = None
) -> InvestigationResult:
    """Asks the legacy integrator a question and returns the verified result.

    The `session_id` is the session: the same id continues the conversation, another starts from scratch. The trace
    and evidence of the result are only those of this turn. `on_event` receives the same trace `investigate` emits.
    """
    trace = Tracer(on_event)
    root = trace.begin("investigate", "chain", {"question": question, "session_id": session_id})
    try:
        result = _investigate(agent, question, session_id, trace)
    except Exception as exc:
        trace.finish(root, error=f"{type(exc).__name__}: {exc}")
        raise
    close_trace(trace, root, result)
    return result


def _investigate(agent: ExecutorIntegrator, question: str, session_id: str, trace: Tracer) -> InvestigationResult:
    history = agent.runnable.get_session_history(session_id)
    first_turn = not history.messages
    triage = run_triage(agent.triage, question, config=traced("triage", trace))
    if (asked := clarification_to_ask(triage, first_turn)) is not None:
        history.add_messages([HumanMessage(question), AIMessage(asked)])
        return clarification_result(question, session_id, triage, asked)
    plan = plan_to_follow(triage)

    timer = _ToolTimer()
    payload: dict[str, Any] = {"input": question}
    if plan is not None:
        payload["triage_context"] = [SystemMessage(plan_message(plan))]
    run_config = {"configurable": {"session_id": session_id}, **traced("agent", trace, timer)}
    output = agent.invoke(payload, run_config)
    turn = _turn_messages(question, output)
    result = _assemble(question, session_id, turn, timer.durations_ms, triage=plan)

    asked = uncalled_steps(plan, result.tool_trace)
    days = fx_days_to_redo(question, result.evidence, result.tool_trace)
    if asked or days:
        text = followup_message(asked, days=days)
        span = trace.begin("plan_followup", "chain", {"asked": asked, "fx_days": days, "message": text})
        extra = _ask_for_missing_tools(agent, text, plan, run_config)
        result = _assemble(
            question,
            session_id,
            turn + (extra or []),
            timer.durations_ms,
            triage=plan,
            asked=asked,
            fx_asked=days,
            ask_failed=extra is None,
        )
        trace.finish(span, outputs={"failed": extra is None, "plan_deviations": result.plan_deviations})
    return finish(agent, result, trace=trace)


def _ask_for_missing_tools(
    agent: ExecutorIntegrator, text: str, plan: Any, run_config: dict[str, Any]
) -> list[BaseMessage] | None:
    """The messages of the follow-up turn `text` (actions, observations, new answer), or `None` if the call failed.

    The follow-up is a second input in the same session, with the plan (if any) repeated as context. A failure here
    does not erase the answer the turn already had: it goes to the log.
    """
    payload: dict[str, Any] = {"input": text}
    if plan is not None:
        payload["triage_context"] = [SystemMessage(plan_message(plan))]
    try:
        output = agent.invoke(payload, run_config)
    except Exception as exc:  # the follow-up is an extra: the earlier answer still stands
        log.warning("the plan follow-up failed, the first answer stands: %s: %s", type(exc).__name__, exc)
        return None
    return _turn_messages(text, output)


def _turn_messages(question: str, output: dict[str, Any]) -> list[BaseMessage]:
    """Rewrites the executor's turn as the messages `create_agent` would produce.

    Each (action, observation) of `intermediate_steps` becomes the call (`AIMessage` with `tool_calls`) and its return
    (`ToolMessage`). The `tool_call_id` links the two; `create_openai_tools_agent` always carries it in the action.
    """
    messages: list[BaseMessage] = [HumanMessage(question)]
    for action, observation in output["intermediate_steps"]:
        call = {"name": action.tool, "args": action.tool_input, "id": action.tool_call_id}
        messages.append(AIMessage(content="", tool_calls=[call]))
        messages.append(ToolMessage(content=_observation_text(observation), tool_call_id=action.tool_call_id))
    messages.append(AIMessage(content=str(output["output"])))
    return messages


def _observation_text(observation: Any) -> str:
    """The observation as JSON text, the same content `create_agent` puts in the tool message.

    The tools return the envelope as a dictionary and the executor passes it on like that; `_assemble` reads JSON.
    Text (the input error handler returns text) goes on as it came.
    """
    if isinstance(observation, str):
        return observation
    return json.dumps(observation, ensure_ascii=False, default=str)
