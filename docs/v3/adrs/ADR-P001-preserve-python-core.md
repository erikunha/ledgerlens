# ADR-P001: Preserve Python core; Next.js as presentation, FastAPI as facade

**Status:** proposed. **Context:** LedgerLens already has extensive Python tools, event projector, agent orchestration, Pydantic schemas and tests. Rewriting finance/agent logic in TypeScript would duplicate behavior and impair evaluation comparability.

**Decision:** keep Python core authoritative; expose versioned HTTP/SSE services via FastAPI; use Next.js App Router UI for the portfolio. Prefer generated API TS types. Python core cannot import frontend modules.

**Alternatives:** keep Streamlit (lowest effort, less control over complex UX); rewrite to TS (high risk of semantic drift); all-in-one Next.js routes (would split Python execution). **Trade-offs:** two runtimes/deploys, but clear boundaries and stronger portfolio evidence. **Rollback:** Streamlit remains working while Next.js reaches parity.
