---
type: adr
status: accepted
date: 2026-11-07
---

# ADR-004: Offline mode

Status: accepted. Date: 2026-11-07.

## Context

The project needs an alternative that works without keys or credentials, so anyone can reproduce everything. For that reason tests, the offline evaluation and the demo run with `LEDGERLENS_OFFLINE=1`.

The test with `GenericFakeChatModel` showed a limit: with `create_openai_tools_agent` and `AgentExecutor`, a message with `tool_calls` and empty content fails (`No generation chunks were returned`), and with non-empty content the tool call is silently dropped. The executor uses the streaming path, and that model rebuilds the chunks from the text only.

## Decision

With `LEDGERLENS_OFFLINE=1`:

- **Model.** `ScriptedChatModel`, a subclass of `BaseChatModel` that implements only `_generate` and replays a list of `AIMessage` (text and tool calls). Tested: it runs `create_openai_tools_agent` with `AgentExecutor` and records the steps. `GenericFakeChatModel` is still valid for text-only chains.
- **Embeddings and index.** `fastembed` (ONNX, no `torch`) and a pregenerated, versioned FAISS index.
- **Exchange rates.** Recorded responses from Frankfurter (v1, ECB only) and from the Brazilian central bank (BCB).
- **Data.** A sample derived from the public data, versioned (ADR-009), or the generator with a fixed seed.
- **Evaluation.** `langsmith.evaluate(..., upload_results=False)` with `Example` objects, which runs without a key (tested) and produces the report in the same format.

Online mode only swaps the providers. Nothing in the domain code knows which mode it is in.

## Alternatives considered

- **Require keys.** Breaks reproduction.
- **Local model through Ollama.** Slow and nondeterministic in tests, with an extra install.
- **Mock the agent.** Does not exercise the real executor.

## Consequences

- Tests check the exact order of the tools, because the model's script is known.
- A scripted model does not prove answer quality. Quality is measured online (ADR-008).
- The scenario scripts live in `tests/` next to the ground truth in `data/scenarios.json`.
