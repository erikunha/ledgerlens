# Engineering-Reverse-Engineering: Public Agent Tools and Demos

**Method:** only official public documentation and GitHub descriptions were used. No login, private code, paywalled functionality, source extraction or inspection of authenticated dashboards. These are *adjacent engineering products*, not direct payment-ops competitors. The purpose is to identify patterns worth learning and avoid building a generic clone.

| Reference | Publicly documented capabilities | Do not compete on | LedgerLens-specific differentiation experiment |
|---|---|---|---|
| LangSmith Studio | live agent step visualization, prompts, tool outputs, debug | generic trace visualization | case-centered claim/evidence/economics overlay |
| Arize Phoenix | tracing, datasets, evals, prompt/playground, MCP | observability platform parity | seeded finance scenario mutations that change the financial truth |
| Langfuse | traces, cost, scores, prompt management, datasets | general LLM monitoring | no-key public teaching of agent correctness, groundedness and review burden |
| Braintrust | evaluation studies, experiments and model comparisons | general-purpose eval infrastructure | financial case-level utility with transparent uncertainty |
| OpenAI Agents SDK | handoffs, manager agents, guardrails, tracing | copying agent loop internals | compare execution patterns inside a consistent domain/eval harness |
| assistant-ui | React chat primitives and runtimes | generic chat UI | advanced visual agent inspector, ledger data editor, provenance graph |
| Craft Anything | study/build/check/refine, evidence ledger, tool registry | binary/web reverse engineering engine | apply evidence-backed iteration to own agent experiments |

## Study → Build → Check → Refine adaptation

- **Study:** inspect how existing LedgerLens S01 - S12 behave, public SDK docs and performance artifacts; document coverage/unknowns.
- **Build:** implement original frontend/engine seam, not copy vendor interface/branding/code.
- **Check:** compare result against recorded oracle, code checks, accessibility, security and paired agent evals.
- **Refine:** update failure corpus, ADR and release gate with proof. A significant failure becomes a regression test.

## What not to duplicate

Do not build a full-scale substitute for LangSmith, Langfuse or Phoenix; use them as optional export backends. LedgerLens owns the **domain learning loop**, versioned scenarios, independent proof, exact financial reasoning and the visitor experience. A generic tool like Phoenix may exceed it as observability software, which is expected and irrelevant to portfolio value.

## Sources

- https://github.com/erikunha/ledgerlens
- https://github.com/storytold/craft-anything
- https://github.com/Arize-ai/phoenix
- https://arize.com/docs/phoenix/
- https://github.com/langfuse/langfuse-docs/blob/main/content/docs/observability/overview.mdx
- https://www.braintrust.dev/evals
- https://github.com/langchain-ai/docs/blob/main/src/oss/langgraph/studio.mdx
- https://openai.github.io/openai-agents-python/
- https://www.assistant-ui.com/docs/
