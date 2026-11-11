# Research and technical sources

## Project primary evidence (verified by connected GitHub read, 2026-11-11)

- [LedgerLens repository](https://github.com/erikunha/ledgerlens)
- [README](https://github.com/erikunha/ledgerlens/blob/main/README.md)
- [Architecture](https://github.com/erikunha/ledgerlens/blob/main/docs/architecture.md)
- [Simulator manifest](https://github.com/erikunha/ledgerlens/blob/main/data/scenarios.json)
- [Event/ledger SQL schema](https://github.com/erikunha/ledgerlens/blob/main/docs/contracts/ledger_schema.sql)
- [Streamlit demo](https://github.com/erikunha/ledgerlens/blob/main/app/streamlit_app.py)
- [Agent integrator](https://github.com/erikunha/ledgerlens/blob/main/ledgerlens/agents/integrator.py)
- [SQL guard](https://github.com/erikunha/ledgerlens/blob/main/ledgerlens/tools/sql_guard.py)
- [Tracing](https://github.com/erikunha/ledgerlens/blob/main/ledgerlens/observability/trace.py)
- [Verification thresholds](https://github.com/erikunha/ledgerlens/blob/main/ledgerlens/verify/thresholds.json)
- [Online evaluation report](https://github.com/erikunha/ledgerlens/blob/main/data/eval/report_online.md)
- [Simulator audit ADR](https://github.com/erikunha/ledgerlens/blob/main/docs/decisions/ADR-009-public-data-first-simulation-for-gaps.md)

## External references

- [Next.js App Router documentation](https://nextjs.org/docs/app) - frontend routing and rendering architecture.
- [LangGraph persistence documentation](https://github.com/langchain-ai/docs/blob/main/src/oss/langgraph/persistence.mdx) - thread checkpointers vs cross-thread store distinctions.
- [OpenTelemetry Semantic Conventions for GenAI agent spans](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md) - trace attribute mapping; development status, pin mapping version.
- [LangSmith Evaluation](https://www.langchain.com/langsmith/evaluation) and [evaluation types](https://docs.langchain.com/langsmith/evaluation-types) - dataset/target/evaluator benchmarking patterns.
- [OWASP Top 10 for Agentic Applications](https://genai.owasp.org/2025/12/09/owasp-top-10-for-agentic-applications-the-benchmark-for-agentic-security-in-the-age-of-autonomous-ai/) - agent risks.
- [OWASP Prompt Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html) - least privilege, tool-level checks and untrusted context.
- [Playwright accessibility testing](https://playwright.dev/docs/accessibility-testing) - automated + manual accessibility coverage.
- [FastAPI documentation](https://fastapi.tiangolo.com/) - API and streaming response primitives.
- [UCI Online Retail II dataset](https://archive.ics.uci.edu/dataset/502/online+retail+ii) - publicly derived order/cancellation source. Confirm license and NOTICE in codebase before changing sample.

## Epistemic status

- Project observations came from reading source files and GitHub repository metadata. No runtime execution of repository or hosted UI occurred during this spec.
- External docs informed patterns/standards; compatibility between specific versions must be tested as part of implementation.
- Targets, rates, time budgets, UI screens and architecture extensions are decisions **proposed**, not empirical findings.
