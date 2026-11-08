---
type: adr
status: accepted
date: 2026-11-08
---

# ADR-010: Modern integrator, legacy methods only as a demonstration

## Context

`initialize_agent`, `ConversationBufferMemory`, `RouterChain`, `create_openai_tools_agent`, `AgentExecutor` and `RunnableWithMessageHistory` are outdated. The current base is `create_agent` from `langchain.agents`. ADR-003 treated the legacy APIs as part of the core.

## Decision

The integrator agent is built with `create_agent` (LangChain 1.x), with per-session history in the agent state. The legacy methods appear only as a short demonstration, with a sentence giving the current equivalent and why the project uses the current one. The evaluation combines answer quality and tool trajectory in LangSmith, with its own trajectory log as the offline alternative.

The same agent also exists in the legacy API, in `ledgerlens/agents/executor_integrator.py`: `create_openai_tools_agent` with `AgentExecutor`, wrapped in `RunnableWithMessageHistory` over the project's SQLite history. Both integrators use the same six tools, the same system prompt, the same result assembly, the same verifier and the same case-writing rule (only with every verdict supported). The difference is in short-term memory: `create_agent` keeps the state, with the tool messages, in the checkpointer, inside the process; the legacy executor stores the question and the final answer of each turn in the SQLite file, so the session survives a new process. The executor's trail and evidence come from `intermediate_steps`, converted into the messages that `create_agent` would produce.

## Alternatives considered

- Only the legacy methods: they are outdated, and the project would keep an old API in its core.
- Only the new API, with no legacy at all: loses the chance to show how the APIs evolved and leaves unanswered what changed.

## Consequences

- The core uses the current API; the legacy modules sit next to their current equivalent for comparison.
- ADR-003 remains valid for the other legacy modules, with the integrator governed by this ADR.
