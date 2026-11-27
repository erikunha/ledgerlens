"""The case of the demo runs on a chat model that is a bridge over the caller of the run.

Why it exists: the agent of the demo only talks to a LangChain chat model, and the run only counts the calls that
go through its `ModelCaller`. A model instance that is anything else is invisible to the budget of the run: the
triage model, the model that writes the SQL, the policy model and the model of the agent would each spend the money
of the visitor outside the caps, and the report of the run would count calls that never happened (FR-012). The
bridge is the meeting point: a chat model whose every generation is one call of the caller of the run, and a tool
wrapper whose every execution reserves one call of the budget.

Why the bridge lives in the API layer: the `ModelCaller` lives there, and the domain must never import the API.
The domain carries the turn (the messages, the schemas of the tools and the calls of the tools), and the bridge is
the code that translates the turn of LangChain into that domain and the answer of the domain back into the turn of
LangChain (FR-012).

What the bridge does with a turn, in one line each:

- the messages of LangChain become the messages of the domain: a system message keeps its role, a human message
  becomes a message of the role user, an assistant message carries the calls it asked for, and a message of a tool
  carries the identifier of the call it answers;
- the schemas of the tools the model may call travel with the request, so the provider knows what it may ask for;
- the answer of the provider becomes the message of LangChain: the text of the provider is the content, and every
  call the provider asked for becomes a tool call with its identifier and its arguments read as a mapping, because
  the client of LangChain refuses a text;
- the model of the request is always the model of the run, never a model of the bridge (FR-013).

Why the arguments of a call travel as a text and not as a mapping: the providers send the arguments of a call as a
JSON text, and the domain keeps them as that text. A number the provider wrote with two decimals would come back as
a number with one, and a text that is not a JSON text would come back as an empty object, and neither is what the
provider said (FR-012). The bridge therefore keeps the raw text of the arguments next to the mapping the client of
LangChain needs, and the next request of the run carries the raw text, byte for byte.

The rule of the type of the arguments is the rule of the domain (`arguments_text` of `ledgerlens.byok`), and the
bridge uses it instead of a rule of its own: a number that arrives as a number is refused by the domain, because it
has already lost the exact text of the amount, and a bridge that wrote it as a text would invent a text the provider
never sent (FR-012).

What is NOT on the live path, and why: the wire converters of the domain (`request_to_wire` and
`response_from_wire` of `ledgerlens.byok.adapter`) are not on the path of a live run. The path is the bridge, the
caller of the run and the adapter of the provider, and the adapter hands the request of the domain to the client of
the provider as the messages of LangChain, which reads the arguments of a call as a mapping. The converters are the
shape a provider would receive over HTTP, and they are what the tests of the domain use; the promise of the text of
the arguments holds inside the domain, where the budget and the trace of the run read it, and not in the body of the
request of the provider.

Why every tool of the case is wrapped: a tool that the case runs is a call of the budget of the run, exactly like
a call of a model, and the run stops when the cap of the tools is reached (FR-009, FR-012). A tool that reaches the
provider outside the caller is a tool whose execution nobody counted.

Why the agent of the demo is not rewritten: `build_integrator` already takes a model for each of the four slots that
FR-012 names (the model of the agent, the model that writes the SQL, the policy model and the triage model), and the
live mode fills the four with the bridge. `build_integrator` does not take the tools, so the seam builds the agent
and then binds the graph of the agent over the wrapped tools. Nothing of the agent changes: the same six tools, the
same verifier, the same memory and the same prompt.

Why the case never falls back to the model of the configuration: `get_chat_model()` is the model of the server, and
online that is the key of the server in the `.env` of the machine, outside the budget and outside the trace of the
run (FR-007). Three places of the repository fall back to it: the model of the agent and the triage model in
`ledgerlens/agents/integrator.py`, the model that writes the SQL in `ledgerlens/tools/sql.py` and the model that
rewrites the question of the policy search in `ledgerlens/tools/policies.py`. The live mode fills the four slots of
the agent, so none of the three is ever taken, and a test proves it by making the fallback raise.

Policy retrieval and case memory use deterministic word-count embeddings by default. Verification compares
amounts against the branch ledger. OpenAI live runs classify cited text through a fifth metered bridge. Other runs
use deterministic text rules. Callers can supply both dependencies.

The cancellation of the run is not swallowed: the caller raises `RunCancelled` before the next call, and the case
turns any failure of a cancelled run back into the cancellation, so the run ends as cancelled and not as a mystery
(FR-019).

Why the live path has the wall behind the tools: the graph of the live path is built here and not by
`build_integrator`, so the middleware of the demo path is not on it. A tool that raises would take the run down with
it, and the visitor would read the error of a tool instead of an answer. The wall of the live path is the same wall of
the demo path (`ToolErrorMiddleware` over the envelope of the integrator): the exception becomes the `TOOL_FAILED`
envelope the model reads, the result names the code and goes to a human (the contract of the tools).

Why the wall of the live path lets a cap and a cancellation through: a cap that stops the run and a run the visitor
stopped are ends of runs and not failures of a tool, and the model must never read them as something it can work
around (ADR-054, FR-019).

Why the answer of a run without an answer says what stopped it: the case answers with a text and the text is what the
visitor reads, so a run that a ceiling cut cannot end with nothing at all. The ceiling that stopped the turn is named
in the missing information of the result, and the case repeats it in the words the visitor reads (ADR-054).
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallRequest, ToolErrorMiddleware
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import Field

from ledgerlens.agents.budget import TurnBudget
from ledgerlens.agents.integrator import Integrator, _tool_failure_content, build_integrator, investigate
from ledgerlens.api.live_run import LIVE_MODE, LiveRunError, LiveRunPlan, ModelCaller, RunCancelled
from ledgerlens.byok import arguments_text
from ledgerlens.byok.adapter import ProviderMessage, ProviderRequest, ProviderResponse, ToolCall, ToolSchema
from ledgerlens.byok.budget import BudgetExceededError
from ledgerlens.byok.errors import ByokError
from ledgerlens.config import offline
from ledgerlens.embeddings import OfflineEmbeddings
from ledgerlens.memory.long_term import CaseMemory
from ledgerlens.run_context import RunContext
from ledgerlens.schemas import ESCALATION_PREFIX, InvestigationResult, VerdictLabel
from ledgerlens.tools.fx import FxClient
from ledgerlens.verify import verify_result
from ledgerlens.verify.nli import StubNli
from ledgerlens.verify.openai_classifier import EvidenceClassifier

log = logging.getLogger(__name__)

__all__ = [
    "MAX_BRIDGE_REQUESTS",
    "SLOT_AGENT",
    "SLOT_POLICY",
    "SLOT_SQL",
    "SLOT_TRIAGE",
    "BridgeChatModel",
    "DemoAgent",
    "DemoCase",
    "LedgerMissing",
    "UnknownToolRequested",
    "build_demo_agent",
    "demo_executor",
    "wrap_tool",
]

# The four model slots of the agent of the demo. FR-012 names the triage model, the generator of the SQL and any
# judge model, and the model of the agent is the fourth one: it is the model that picks the tools and writes the
# answer, and its calls are the calls of the run all the same.
SLOT_AGENT = "agent"
SLOT_TRIAGE = "triage"
SLOT_SQL = "sql"
SLOT_POLICY = "policy"
SLOT_VERIFIER = "verifier"

_OPENAI_PROVIDER = "openai"
_VERIFICATION_UNAVAILABLE = "Verification could not be completed."
_UNAVAILABLE_CLASSIFIER_SCORES = {"entailment": 0.0, "contradiction": 0.0, "neutral": 1.0}
_VERDICT_NAMES: dict[VerdictLabel, str] = {
    "supported": "supported",
    "contradicted": "contradicted",
    "not_enough_evidence": "with insufficient evidence",
}

# How many requests a bridge keeps. The last requests are the evidence of what a slot spoke and asked for, and the
# bound keeps the memory of a long run from growing without end (FR-012).
MAX_BRIDGE_REQUESTS = 32

# The roles of the domain, the ones the providers use.
_ROLE_USER = "user"
_ROLE_ASSISTANT = "assistant"
_ROLE_TOOL = "tool"
_ROLE_SYSTEM = "system"

# What the visitor reads when the run ended without an answer. The limit that stopped the run, when the result
# names one, is added to it, because a visitor cannot tell a run that was cut from a run that never started.
_NO_ANSWER = "the run ended without an answer"

# The words the sentence of the result uses when a limit stopped the turn. The sentence names the limit ("the cap
# 'max_model_calls' stopped the turn" or the ceiling of the graph), and the case repeats the sentence of the result
# instead of writing a second wording of the same limit (ADR-054).
_CUT_SENTENCE = re.compile(r"stopped the turn")


class UnknownToolRequested(ByokError):
    """The provider asked for a tool the case of the demo does not have.

    Why it is a refusal of the family of the product and not the error of a library: a provider that asks for a tool
    that does not exist is a provider that broke, and the run has to end with a reason that a visitor and an
    operator can read, never with the validation error of the client of a library (FR-018).
    """

    reason = "the provider asked for a tool the case does not have"


class LedgerMissing(ByokError):
    """The run has no ledger of the visitor, so the case of the demo refuses to run (ADR-038).

    Why the refusal and not the fallback: the fallback of the configuration is the whole published ledger of the
    repository, with the rows of every account of it, and a model that writes SQL would read the rows of another
    customer. A run that answers about records the visitor does not own is a run that spends the money of the visitor
    to say something that is not true (ADR-038).

    Why it is a refusal of the family of the domain: the coordinator ends the run with the reason of the refusal and
    the report of what was not spent, and a visitor reads a reason instead of a stack of a library (FR-018).
    """

    reason = "the run has no ledger of the visitor"


class BridgeChatModel(BaseChatModel):
    """A chat model whose every generation is one call of the caller of the run.

    Why the class exists and not a function: the agent of the demo expects a chat model, and the run expects a
    caller. The bridge is the object that is both, and it is the only place where the turn of the agent and the turn
    of the domain meet (FR-012).

    Why the model of the request is the model of the run: a run that asked the provider for another model would
    compare two models under one identifier, and the trace of the run would lie about what ran (FR-013). The bridge
    asks the caller and never decides the model itself.

    Why the requests are kept: a reader of a run has to be able to see which slot spoke and what it asked for, and
    the list is the evidence of that (FR-012).

    Why the list is bounded: only the last `MAX_BRIDGE_REQUESTS` requests are the evidence, and a list that grows
    with every call of a long run is a memory that grows without end.
    """

    # The caller of the run. It is the only way this model reaches the provider.
    caller: Any
    # The model of the run, the mirror of the model of the caller.
    model_id: str = ""
    # The slot of the agent of the demo that speaks through this bridge.
    slot: str = SLOT_AGENT
    # The tools the model may call, bound by `bind_tools`.
    bound_tools: tuple[Any, ...] = ()
    # The last requests this bridge sent, one per generation.
    requests: list[Any] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        """The name of the model in the traces, so the bridge is never mistaken for a provider."""
        return "ledgerlens-bridge"

    def bind_tools(self, tools: Sequence[Any], *, tool_choice: Any = None, **kwargs: Any) -> Runnable:
        """The same bridge, with the tools the model may call.

        Why a copy and not the model itself: the agent binds its tools to the model, and a bridge that changed its
        own tools would change the tools of every other slot that shares it. The copy keeps the list of the requests
        of the bridge, so the calls of the bound copy are seen by the slot that owns it.
        """
        return self.model_copy(update={"bound_tools": tuple(tools)})

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        """One generation of the bridge: one call of the caller of the run."""
        request = self._request_of(messages)
        self._remember(request)
        response = self.caller.complete(request)
        _refuse_the_unknown_tools(response, self.bound_tools)
        return ChatResult(generations=[ChatGeneration(message=_answer_of(response))])

    def _remember(self, request: ProviderRequest) -> None:
        """Keeps the request of the run, and drops the oldest one when the list is full.

        Why the list is bounded: the last requests are the evidence of what the slot spoke and asked for, and a
        list that grows with every call of a long run is a memory that grows without end (FR-012).
        """
        self.requests.append(request)
        if len(self.requests) > MAX_BRIDGE_REQUESTS:
            del self.requests[: len(self.requests) - MAX_BRIDGE_REQUESTS]

    def _request_of(self, messages: Sequence[BaseMessage]) -> ProviderRequest:
        """The turn of LangChain as the request of the run.

        Why the model of the caller and not the model of the bridge: the request may not carry another model than the
        one of the run, and the caller is the one that knows it (FR-013).
        """
        model_id = getattr(self.caller, "model_id", "") or self.model_id
        return ProviderRequest(
            model_id=model_id,
            messages=tuple(_provider_message_of(message) for message in messages),
            tools=tuple(_schema_of(tool) for tool in self.bound_tools),
        )


def wrap_tool(caller: ModelCaller, tool: BaseTool) -> BaseTool:
    """The same tool, with every execution of it reserved by the caller of the run.

    Why the tool is wrapped and not replaced: the agent of the demo has to keep its six tools, with their names,
    their descriptions and their arguments, and only the accounting of the execution changes. The wrapper reserves
    one call of the budget before the tool runs, so a tool that breaks a cap never runs at all (FR-009, FR-012).

    Why the name of the tool is given to the caller: the trace of the run has to say which tool ran (FR-026).
    """
    name = tool.name
    function = getattr(tool, "func", None)
    if tool.args_schema is None:
        # A tool without a schema of its arguments cannot be wrapped: the wrapper is a tool with the same schema, so
        # the agent keeps calling it exactly as it did before.
        raise ValueError(f"the tool '{name}' has no schema of its arguments, so it cannot be wrapped")

    def reserved(*args: Any, **kwargs: Any) -> Any:
        """Runs the tool of the case through the caller of the run."""
        if callable(function):
            return caller.call_tool(name, function, *args, **kwargs)
        return caller.call_tool(name, lambda: tool.invoke(kwargs))

    reserved.__name__ = name
    reserved.__doc__ = tool.description
    return StructuredTool.from_function(
        func=reserved,
        name=name,
        description=tool.description,
        args_schema=tool.args_schema,
        return_direct=tool.return_direct,
        handle_validation_error=tool.handle_validation_error,
    )


@dataclass(frozen=True)
class DemoAgent:
    """The agent of the demo and the bridges it speaks through.

    Why the bridges are named: a reader of a run has to be able to see which slot of the agent spoke and how many
    times it spoke, and the budget counts them all the same (FR-012).
    """

    agent: Integrator
    bridges: Mapping[str, BridgeChatModel]


def _live_tool_failure_content(exc: Exception, request: ToolCallRequest) -> str | None:
    """The envelope of a tool that raised in the live path, or None when the failure is not the tool's.

    Why the envelope and not the traceback: the model has to read what it could not get and report it, and a stack
    trace is not something the model can use. The envelope is the one of the demo path, so the live path and the
    demo path name the failure the same way (the contract of the tools).

    Why a cap and a cancellation are not enveloped: a cap that stops the run and a run the visitor stopped are
    ends of runs and not failures of a tool. The model must never read them as something it can work around, and
    the run has to end with the reason that a person can read (ADR-054, FR-019).
    """
    if isinstance(exc, (BudgetExceededError, ByokError, LiveRunError)):
        return None
    return _tool_failure_content(exc, request)


@dataclass
class _LiveEvidenceClassifier:
    """Let the deterministic checks finish when the provider cannot classify a claim."""

    classifier: EvidenceClassifier
    failed: bool = False

    def predict(self, premise: str, hypothesis: str) -> dict[str, float]:
        if not self.failed:
            try:
                return self.classifier.predict(premise, hypothesis)
            except (BudgetExceededError, LiveRunError):
                raise
            except Exception as failure:
                # One failed call makes the verification incomplete. Avoid spending on further labels.
                log.warning("Live claim verification failed (%s)", type(failure).__name__)
                self.failed = True
        return _UNAVAILABLE_CLASSIFIER_SCORES.copy()


def _verify_openai_result(
    result: InvestigationResult, *, classifier: EvidenceClassifier, ledger_db: Path | str | None
) -> InvestigationResult:
    """Mark incomplete verification for review after the deterministic checks run."""
    live_classifier = _LiveEvidenceClassifier(classifier)
    verified = verify_result(result, nli=live_classifier, ledger_db=ledger_db)
    if not live_classifier.failed:
        return verified
    return verified.model_copy(
        update={
            "requires_human_review": True,
            "recommended_action": "escalate_to_human",
            "missing_information": [*verified.missing_information, _VERIFICATION_UNAVAILABLE],
        }
    )


def build_demo_agent(
    caller: ModelCaller,
    *,
    db_path: Any = None,
    verifier: Any = None,
    index_root: Any = None,
    fx_client: FxClient | None = None,
    embeddings: Embeddings | None = None,
    case_memory: CaseMemory | None = None,
    run_context: RunContext | None = None,
) -> DemoAgent:
    """The agent of the demo, with the bridge of the run in each of its four model slots.

    The four slots are the ones FR-012 names: the model of the agent, the model that writes the SQL, the policy
    model and the triage model. All four are the bridge over the caller of the run, so every call of the agent is
    reserved, counted, traced and capped by the budget of the run (FR-012).

    The default verifier checks the same ledger the investigation reads. OpenAI live runs use the visitor's
    selected model for cited text classification.

    Why the graph is built twice: `build_integrator` does not take the tools, so the tools it built are wrapped
    here and the graph of the agent is bound over the wrapped tools. The agent itself is not rewritten: the same
    six tools, the same verifier, the same memory, the same prompt and the same checkpointer.

    Why the graph of the live path carries the wall behind the tools: the graph of the demo path is built by
    `build_integrator`, which puts the wall on it, and the graph of the live path is built here. A tool that raises
    has to become the envelope the model reads on both paths, or the visitor of the live path reads the error of a
    tool where the visitor of the demo path reads an answer (the contract of the tools).
    """
    bridges = {
        slot: BridgeChatModel(caller=caller, model_id=caller.model_id, slot=slot)
        for slot in (SLOT_AGENT, SLOT_TRIAGE, SLOT_SQL, SLOT_POLICY)
    }
    if verifier is None:
        if caller.provider == _OPENAI_PROVIDER and not offline():
            judge = BridgeChatModel(caller=caller, model_id=caller.model_id, slot=SLOT_VERIFIER)
            bridges[SLOT_VERIFIER] = judge
            verifier = partial(_verify_openai_result, classifier=EvidenceClassifier(judge), ledger_db=db_path)
        else:
            verifier = partial(verify_result, nli=StubNli(), ledger_db=db_path)
    checkpointer = InMemorySaver()
    agent = build_integrator(
        bridges[SLOT_AGENT],
        db_path=db_path,
        verifier=verifier,
        checkpointer=checkpointer,
        query_model=bridges[SLOT_SQL],
        fx_client=fx_client,
        index_root=index_root,
        embeddings=embeddings if embeddings is not None else OfflineEmbeddings(),
        case_memory=case_memory,
        policy_model=bridges[SLOT_POLICY],
        triage_model=bridges[SLOT_TRIAGE],
        run_context=run_context,
    )
    tools = [wrap_tool(caller, tool) for tool in agent.tools]
    graph = create_agent(
        bridges[SLOT_AGENT],
        tools=tools,
        system_prompt=agent.system_prompt,
        # The wall behind the tools of the live path: a tool that raises becomes the envelope the model reads, so
        # the run ends with a result for a human and not with the error of the tool (the contract of the tools).
        middleware=[ToolErrorMiddleware(_live_tool_failure_content)],
        checkpointer=checkpointer,
    )
    live = Integrator(
        graph=graph,
        tools=tools,
        verifier=agent.verifier,
        case_memory=agent.case_memory,
        triage=agent.triage,
        system_prompt=agent.system_prompt,
        run_context=agent.run_context,
    )
    return DemoAgent(agent=live, bridges=bridges)


class DemoCase:
    """The case of the demo: the agent of the demo runs on the bridge over the caller of the run.

    Why the case is a class and not a function: a case of the run needs the ledger, the index and the verifier of
    the environment it runs in, and the coordinator builds the case without knowing anything about the agent (the
    seam of `CaseExecutor`).

    Why the case raises the cancellation of the run: the agent of the demo catches the failures of the triage and
    of the follow-up, because a triage that fails does not stop the question. A cancellation is not a failure of the
    triage: it is the end of the run, and the case has to say so instead of answering a run the visitor stopped
    (FR-019).

    Why the bridges belong to the run and not to the case: two runs of the same case are two runs, and a bridge
    that belongs to no run would let the reader of one run see the calls of the other (FR-012).

    Why the history of the session comes from the plan of the run: the plan carries the messages of the request, and
    the case of the demo has no memory of its own. A run whose plan carries the history of the session starts where
    the session left, and a run whose plan carries none starts from scratch (FR-012).

    Why the ledger of the run is the ledger of the plan: the branch of the visitor is the only truth of the visitor,
    and the tools of the agent read the file of that branch and never the ledger of the configuration (ADR-038).

    Why the case forgets a run that ended: the case holds a context and bridges for every run it ever served,
    and a case that lives in a long lived process would grow without end. The coordinator knows when a run ends and
    tells the case, and the case drops the run from its two maps (ADR-038).
    """

    def __init__(
        self,
        *,
        db_path: Any = None,
        verifier: Any = None,
        index_root: Any = None,
        fx_client: FxClient | None = None,
        embeddings: Embeddings | None = None,
        case_memory: CaseMemory | None = None,
        run_context: RunContext | None = None,
        runtime_dir: Path | str | None = None,
    ) -> None:
        """The case with the ledger, the index and the verifier of the environment it runs in."""
        self._options: dict[str, Any] = {
            "db_path": db_path,
            "verifier": verifier,
            "index_root": index_root,
            "fx_client": fx_client,
            "embeddings": embeddings,
            "case_memory": case_memory,
            "run_context": run_context,
        }
        # The folder of the runtime that holds the memory of the session of the visitor. It is the folder of the
        # facade when the facade gave one, and the folder of the configuration otherwise (ADR-038).
        self._runtime_dir = runtime_dir
        # The bridges of each run, by the identifier of the run. A run writes its own key and reads nobody else one.
        self._bridges: dict[str, Mapping[str, BridgeChatModel]] = {}
        # The context of each run, by the identifier of the run: the identity of the run and the folder of its memory.
        self._contexts: dict[str, RunContext] = {}

    def bridges_of(self, run_id: str) -> Mapping[str, BridgeChatModel]:
        """The bridges of the run with that identifier, empty when the run never happened.

        Why the bridges are asked by the identifier of the run: the bridges belong to the run, and a reader that
        wants the calls of a run has to name it (FR-012).

        Why a reader of a run that ended finds nothing: the case forgets the run when it ends, and the run is over
        (ADR-038).
        """
        return self._bridges.get(run_id, {})

    def context_of(self, run_id: str) -> RunContext | None:
        """The context of the run with that identifier, or None when the run never happened.

        Why the context is kept: the context carries the identity of the run and the folder of the memory of its
        session, and a reader that wants to know where the memory of a run went has to name the run (ADR-038).
        """
        return self._contexts.get(run_id)

    def forget(self, run_id: str) -> None:
        """The case forgets the run: the context and the bridges of the run go away (ADR-038).

        Why the case forgets and not the coordinator: the coordinator knows when a run ends, and the case owns the
        context and the bridges of the runs it served. A case that is not the case of the demo has nothing to
        forget, and the coordinator only asks the case that knows how to forget (ADR-038).

        Why the run is forgotten at its end and not later: a case that keeps every run it ever served grows without
        end in a long lived process, one context and its bridges for every run (ADR-038).
        """
        self._contexts.pop(run_id, None)
        self._bridges.pop(run_id, None)

    def __call__(self, caller: ModelCaller, plan: LiveRunPlan) -> str:
        """The answer of the agent of the demo, on the bridge over the caller of the run.

        Why the answer of a run without an answer is not empty: the text this method returns is what the visitor
        reads, and a run that a ceiling cut cannot end with nothing at all (ADR-054).
        """
        options = self._options_of_the_run(plan)
        demo = build_demo_agent(caller, **options)
        self._bridges[plan.run_id] = demo.bridges
        self._contexts[plan.run_id] = options["run_context"]
        thread = plan.session_id or plan.run_id
        _remember_the_history(demo.agent, thread, plan.messages)
        # The coordinator of the run is the budget of the agent: the caller counts every call of the provider,
        # and the agent counts nothing of its own, so no call is counted twice (ADR-054).
        turn = TurnBudget(caps=plan.budget, coordinator=caller.budget, owner="caller")
        try:
            result = investigate(demo.agent, plan.question, thread_id=thread, budget=turn)
        except RunCancelled:
            raise
        except BaseException as failure:  # noqa: BLE001 - the failure is re-raised below, or the run was cancelled
            if caller.cancelled:
                raise RunCancelled("the run was cancelled while the case was running") from failure
            raise
        if caller.cancelled:
            raise RunCancelled("the run was cancelled while the case was running")
        return _the_answer_of_the_result(result, show_verification=SLOT_VERIFIER in demo.bridges)

    def _options_of_the_run(self, plan: LiveRunPlan) -> dict[str, Any]:
        """The options of the agent of this run: the ledger of the plan and the memory of the session.

        Why the ledger of the plan wins over the ledger of the case: the ledger of the plan is the ledger of the run,
        and a case that answered with a ledger of its own would answer about records the visitor does not own
        (ADR-038).

        Why a run without a ledger is a refusal and not a fallback: the fallback of the configuration is the whole
        published ledger of the repository, with the rows of every account of it, and a model that writes SQL reads
        whatever it is given (ADR-038).

        Why the file of the ledger has to be there: the file is written before the run starts and removed when it
        ends, and a case that reads a file that is gone would answer with a database that cannot be opened (ADR-038).
        """
        ledger = plan.ledger
        path = ledger.path if ledger is not None else self._options.get("db_path")
        if path is None:
            raise LedgerMissing(
                "the run names no branch and the case has no ledger of its own, so there is nothing to read"
            )
        if ledger is not None and not Path(ledger.path).exists():
            raise LedgerMissing("the file of the ledger of the run is not there: the branch of the visitor is gone")
        options = dict(self._options)
        options["db_path"] = path
        options["run_context"] = self._options.get("run_context") or self._context_of_the_run(plan)
        return options

    def _context_of_the_run(self, plan: LiveRunPlan) -> RunContext:
        """The context of the run: the identity of the visitor and the folder of the memory of its session.

        Why the memory lives in the folder of the session: the case memory of one visitor must never show up in the
        answer of another one, and the folder of the configuration is shared by the whole machine (ADR-038).
        """
        context = RunContext(
            run_id=plan.run_id,
            session_id=plan.session_id,
            mode=LIVE_MODE,
            account_id=plan.account_id,
            branch_id=plan.sandbox_id,
            branch_revision=plan.expected_revision,
            model_profile_id=plan.model_profile_id,
        )
        return replace(context, memory_dir=context.resolve_memory_dir(self._runtime_dir))


def demo_executor(caller: ModelCaller, plan: LiveRunPlan) -> str:
    """The case of the demo with the configuration of the product.

    Why the case is built here and not somewhere else: the coordinator knows nothing about the agent, and the case is
    the code that decides what to ask the model (the seam of `CaseExecutor`). Every call it makes goes through the
    caller of the run, so the budget counts the triage model, the generator of the SQL, the policy model and the
    model of the agent all the same (FR-012).

    Why the case is built per run: the history of the conversation is the one the plan of the run carries, and the
    checkpointer of the case is built per run, so the history of one run never crosses into another one. The
    milestone has no memory of the visitor across runs.

    Why the configuration never brings the ledger: the ledger of a run is the ledger of the plan, and a plan without
    one is a refusal, because the fallback of the configuration would hand the model the rows of every account of the
    repository (ADR-038).
    """
    return DemoCase()(caller, plan)


def _remember_the_history(agent: Integrator, thread: str, messages: Sequence[Mapping[str, str]]) -> None:
    """The history of the session in the checkpointer of the case, before the question of the run.

    Why the history comes from the plan: the plan of the run carries the messages of the request, and they are the
    conversation of the session. The case of the demo has no memory of its own, so a run whose plan carries no
    history starts from scratch, and a run whose plan carries one starts where the session left (FR-012).
    """
    history = [_history_message(message) for message in messages]
    kept = [message for message in history if message is not None]
    if not kept:
        return
    agent.graph.update_state({"configurable": {"thread_id": thread}}, {"messages": kept})


def _history_message(message: Mapping[str, str]) -> BaseMessage | None:
    """One message of the history of the session as a message of LangChain, or None when the role is not one.

    Why a message of the role tool is not part of the history: a message of a tool answers a call of a tool, and the
    call it answers is not in the plan of the run, so the pair would be broken (FR-012).
    """
    role = str(message.get("role") or "")
    content = str(message.get("content") or "")
    if role == _ROLE_USER:
        return HumanMessage(content=content)
    if role == _ROLE_ASSISTANT:
        return AIMessage(content=content)
    if role == _ROLE_SYSTEM:
        return SystemMessage(content=content)
    return None


def _role_of(message: BaseMessage) -> str:
    """The role of the domain of a message of LangChain.

    Why the roles are the plain strings: the providers use them, and the domain carries them as they are (FR-012).
    """
    if isinstance(message, SystemMessage):
        return _ROLE_SYSTEM
    if isinstance(message, ToolMessage):
        return _ROLE_TOOL
    if isinstance(message, AIMessage):
        return _ROLE_ASSISTANT
    return _ROLE_USER


def _text_of(message: BaseMessage) -> str:
    """The text of a message of LangChain, whatever shape its content has."""
    content = message.content
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for part in content:
        if isinstance(part, str):
            parts.append(part)
        elif isinstance(part, Mapping):
            parts.append(str(part.get("text", "")))
    return "".join(parts)


def _arguments_mapping(arguments: str) -> dict[str, Any]:
    """The arguments of a call as the mapping the client of LangChain expects.

    Why the text is read here and not kept: the client refuses a tool call whose arguments are a text, and the
    provider is the one that sent the text (FR-012).
    """
    if not arguments:
        return {}
    try:
        parsed = json.loads(arguments)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _tool_call_of(call: Mapping[str, Any]) -> ToolCall:
    """The call of a tool of the domain, from a call of LangChain.

    Why the arguments are read with the rule of the domain: the domain keeps the arguments of a call as the
    text the provider sent, and a mapping here would be a number that lost its decimals on the way (FR-012).
    """
    arguments = call.get("args")
    if arguments is None:
        arguments = call.get("arguments")
    name = str(call.get("name") or "")
    return ToolCall(
        id=str(call.get("id") or ""),
        name=name,
        arguments=arguments_text(arguments, name=name),
    )


def _tool_calls_of(message: BaseMessage) -> tuple[ToolCall, ...]:
    """The calls of the tools of a message of LangChain, with the arguments as the text the provider sent.

    Why the raw text is preferred: the client of LangChain keeps the arguments of a call as the text the provider
    sent, and a text that was parsed and written back is not the same text. A number that the provider wrote with
    two decimals would come back with one, and a text that is not a JSON text would come back as an empty object
    (FR-012).

    Why the rule of the domain and not a rule of the bridge: the type of the arguments of a call is one rule of
    the domain, and a number that arrives as a number is refused by it, because it has already lost the exact
    text of the amount (FR-012).
    """
    raw = getattr(message, "additional_kwargs", None) or {}
    calls: list[ToolCall] = []
    for item in raw.get("tool_calls") or ():
        if not isinstance(item, Mapping):
            continue
        function = item.get("function")
        source = function if isinstance(function, Mapping) else item
        arguments = source.get("arguments")
        if arguments is None:
            arguments = item.get("args")
        name = str(source.get("name") or item.get("name") or "")
        calls.append(
            ToolCall(
                id=str(item.get("id") or ""),
                name=name,
                arguments=arguments_text(arguments, name=name),
            )
        )
    if calls:
        return tuple(calls)
    return tuple(_tool_call_of(call) for call in getattr(message, "tool_calls", ()) or ())


def _provider_message_of(message: BaseMessage) -> ProviderMessage:
    """The message of the domain, from a message of LangChain.

    Why the calls of the assistant travel with the message: a provider that needs the pair of a call and of its
    answer has to be able to build it (FR-012).

    Why the arguments of a call travel as the raw text: the domain keeps them as the text the provider sent, and the
    budget and the trace of the run read exactly that text (FR-012).
    """
    tool_call_id = getattr(message, "tool_call_id", None)
    return ProviderMessage(
        role=_role_of(message),
        content=_text_of(message),
        tool_call_id=None if tool_call_id is None else str(tool_call_id),
        tool_calls=_tool_calls_of(message),
    )


def _schema_of(tool: Any) -> ToolSchema:
    """The schema of the domain of a tool, whatever shape the tool has.

    Why the schema of a tool of LangChain becomes a schema of the domain: the request has to tell the provider what
    it may call, and the parameters of the schema of the tool are a JSON schema (FR-012).
    """
    if isinstance(tool, ToolSchema):
        return tool
    if isinstance(tool, BaseTool):
        parameters: Mapping[str, Any] = {}
        if tool.args_schema is not None:
            parameters = tool.args_schema.model_json_schema()
        return ToolSchema(name=tool.name, description=tool.description, parameters=parameters)
    return ToolSchema.from_any(tool)


def _name_of(tool: Any) -> str:
    """The name of a tool, whatever shape the tool has.

    Why the name is read here and not elsewhere: the refusal of an unknown tool has to name the tool the provider
    asked for, and the tools of the case come in more than one shape (FR-018).
    """
    name = getattr(tool, "name", None)
    if isinstance(name, str) and name:
        return name
    if isinstance(tool, Mapping):
        return str(tool.get("name") or "")
    return ""


def _refuse_the_unknown_tools(response: ProviderResponse, tools: Sequence[Any]) -> None:
    """Refuses a provider that asks for a tool the case does not have.

    Why the refusal is here and not in the client of LangChain: the client answers a call for a tool that does not
    exist with a message for the model, and the run goes on with a model that is answering about a tool that is not
    there. A provider that asks for a tool that does not exist is a provider that broke, and the run has to end with
    a reason that names the tool, never with the validation error of a library (FR-018).
    """
    known = {_name_of(tool) for tool in tools}
    for call in response.tool_calls:
        if call.name not in known:
            raise UnknownToolRequested(
                f"the provider asked for the tool '{call.name}', and the case of the demo has no tool with that name"
            )


def _answer_of(response: ProviderResponse) -> AIMessage:
    """The message of LangChain, from the answer of the provider.

    Why the calls of the provider become the tool calls of the message: the agent of the demo runs the tools the
    provider asked for, and the arguments of a call are read as a mapping because the client of LangChain refuses a
    text (FR-012).

    Why the raw text of the arguments travels in the additional kwargs: the client of LangChain parses the
    arguments of a call into a mapping, and the text the provider sent has to survive that parsing, byte for byte,
    so the next request of the run carries what the provider said (FR-012).
    """
    raw = [
        {
            "id": call.id,
            "type": "function",
            "function": {"name": call.name, "arguments": call.arguments},
        }
        for call in response.tool_calls
    ]
    calls = [
        {"name": call.name, "args": _arguments_mapping(call.arguments), "id": call.id} for call in response.tool_calls
    ]
    usage = None
    if response.input_tokens or response.output_tokens:
        usage = {
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "total_tokens": response.input_tokens + response.output_tokens,
        }
    return AIMessage(
        content=response.content,
        tool_calls=calls,
        additional_kwargs={"tool_calls": raw},
        usage_metadata=usage,
    )


def _verification_summary(result: InvestigationResult) -> str:
    """Report verifier outcomes without presenting categorical scores as confidence."""
    review = "Human review required. " if result.requires_human_review else ""
    if _VERIFICATION_UNAVAILABLE in result.missing_information:
        return review + _VERIFICATION_UNAVAILABLE
    if not result.verdicts:
        return review.strip()
    counts = Counter(verdict.label for verdict in result.verdicts)
    summary = ", ".join(f"{counts[label]} {name}" for label, name in _VERDICT_NAMES.items())
    return f"{review}Verification found {summary}."


def _the_answer_of_the_result(result: InvestigationResult, *, show_verification: bool = False) -> str:
    """The text the visitor reads: the answer of the agent, or what stopped the run when there is no answer.

    Why a run without an answer says so: an empty answer is a run that says nothing, and a visitor cannot tell a
    run that a ceiling cut from a run that never started (ADR-054).
    """
    if result.answer.strip():
        summary = _verification_summary(result) if show_verification else ""
        if summary:
            return f"{summary}\n\n{result.answer}"
        return result.answer
    limit = _the_limit_of_the_cut(result)
    if limit is None:
        return f"{_NO_ANSWER}, and a person has to take the case over"
    return f"{_NO_ANSWER}: {limit}"


def _the_limit_of_the_cut(result: InvestigationResult) -> str | None:
    """The sentence that names the limit that stopped the turn, when the result of the run carries one.

    Why the sentence of the result and not a limit of its own: the result of the turn already says which limit
    stopped it and with which value, and a second wording of the same limit would be a second truth about it
    (ADR-054).

    Why the reasons of the escalation are left out: they say why a person has to review the result, and they are
    not the limit that stopped the turn.
    """
    for entry in result.missing_information:
        if entry.startswith(ESCALATION_PREFIX):
            continue
        if _CUT_SENTENCE.search(entry):
            return entry
    return None
