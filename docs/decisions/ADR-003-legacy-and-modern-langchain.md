---
type: adr
status: accepted
date: 2026-11-07
---

# ADR-003: Legacy and modern LangChain side by side

Status: accepted. Date: 2026-11-07.

## Context

The project demonstrates APIs that now live in the `langchain-classic` package: `initialize_agent` with `ZERO_SHOT_REACT_DESCRIPTION`, `ConversationBufferMemory`, `LLMRouterChain` with `MultiPromptChain`, `create_openai_tools_agent` and `AgentExecutor`. The current path is `langchain` 1.x with `create_agent`. On 2026-11-07, with `langchain` 1.4.9, `langchain-core` 1.7.6 and `langchain-classic` 1.0.8, the imports work, and the ReAct agent and the tools agent ran with a scripted model.

Three behaviors change the design, each with a test in `tests/agents/`:

1. `ZERO_SHOT_REACT_DESCRIPTION` rejects tools with more than one argument (`ZeroShotAgent does not support multi-input tool`).
2. The memory passed to `initialize_agent` does not appear in the default prompt. The prompt suffix must contain `{chat_history}`.
3. Importing `langchain_classic.chains` warns that `langchain-community` is being sunset (the repository is archived), and `initialize_agent` emits a deprecation warning.

## Decision

- The legacy APIs come from `langchain-classic`, each with a short note on its current equivalent.
- Shared blocks (prompts, parsers, tools, retrieval, verification) use LCEL and `langchain-core`, so they serve both paths.
- The ReAct agent gets single-input adapters (a string with JSON) over the structured tools, and the prompt suffix includes `{chat_history}`.
- `langchain-community` stays pinned at 0.4.2 and will not be updated.
- The model comes from `init_chat_model`; the online default is OpenAI, because `create_openai_tools_agent` uses OpenAI's tool format. Switching provider means changing an environment variable.
- A modern version with `create_agent` stays as the reference.

## Alternatives considered

- **Only the new API.** Loses the demonstrations of the legacy ReAct agent, the legacy router, the conversation buffer and `AgentExecutor`.
- **Only the legacy.** Teaches a design that the documentation itself already discourages.
- **Pin `langchain` 0.3.** An old line that conflicts with `langsmith` 0.14 and `langchain-core` 1.x.

## Consequences

- The deprecation warnings appear once and the documentation explains why.
- A smoke test (`tests/test_legacy_imports.py`) fails if any legacy API stops importing.
- Each tool exists in two forms: structured and adapted for text.
