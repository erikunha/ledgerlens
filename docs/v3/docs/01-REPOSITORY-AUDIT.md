# Repository audit - evidence-based baseline

**Inspected:** `README.md`, `pyproject.toml`, `docs/architecture.md`, `docs/contracts/ledger_schema.sql`, the simulator, agent integrators, schemas, settings, account scoping, SQL guards, Streamlit UI, tracer, verifier, eval report, test suite and Git tree. Main branch inspected at commit `d9f5b06cc71dc6a3ad1f57a579e734ce11f15f73` (2026-11-09). This is **static inspection**; no repository tests have been executed as part of this spec.

## Baseline inventory

| Module/file | Observed implementation | Portfolio implication |
|---|---|---|
| `ledgerlens/agents/integrator.py` | Modern `create_agent` integrator, triage, follow-up, trace assembly, verifier | Core to retain; surface its states rather than rewrite |
| `ledgerlens/agents/executor_integrator.py` and `legacy_react.py` | Legacy comparison path | Retain for experiment A/B/C, isolate from public defaults |
| `ledgerlens/chains/` | Fixed and LCEL chains, routers, parser repair | Useful as baseline and educational architecture variants |
| `ledgerlens/tools/sql_guard.py` | sqlglot parser AST validation; allowed tables/functions; single SELECT; LIMIT wrap | Excellent demonstration of least privilege; still combine with read-only connection and timeouts |
| `ledgerlens/tools/sql.py` | Read-only SQLite connection, query length/row/time controls | Keep, adversarial tests for input/CPU limits |
| `ledgerlens/tools/` | SQL, ledger record, FX, calculator, policies, case retrieval | Must remain independently typed, testable and observable |
| `ledgerlens/verify/` | Claim extraction, numeric/coherence checks, NLI, escalation | Key differentiator; expose decisions and limitations |
| `ledgerlens/observability/trace.py` | Span start/end, metadata, tokens, compact/redaction; live callback | Extend to transport-safe, versioned event envelopes, replay bundles |
| `ledgerlens/memory/` | SQLite session history, FAISS case memory, summarization | Make visitor isolation explicit; no cross-session shared memory |
| `ledgerlens/sim/` | Deterministic event-sourced simulation, seeded scenarios, projector and canonical hash | Reuse for sandbox branching; avoid writing projections directly |
| `ledgerlens/api/accounts.py` | `scoped_ledger` copies only one account's relevant entities | Useful base; must add per-visitor branch isolation |
| `ledgerlens/api/ledger_service.py` | Read-only FastAPI endpoints for transactions, settlements and replay | Not yet a full public demo application API; protect or replace as needed |
| `app/streamlit_app.py` | 660-line presentation plus live thread/queue handling, 7:4 layout | Replace presentation with Next.js; run Streamlit as legacy demo until parity |
| `ledgerlens/config.py` | Offline scripted, `init_chat_model`, environment-sourced model/key | Must add per-run provider config; avoid process-wide key/env mutation |
| `data/scenarios.json` | 12 planted scenarios including FX, duplicate, dispute, unknown, injection, outage, memory | Design the guided journey from these real fixtures |
| `data/eval/report_online.md` | 30 cases, A/B/C, three trials, costs, trajectory and groundedness | Make reproducible reference, not universal benchmark |
| `tests/` | Extensive pytest suite including Streamlit AppTest and verifier checks | Preserve; extend with API/e2e/security/tenant-isolation tests |
| `docs/decisions/` | Ten ADRs, documented trade-offs | Add ADRs for public demo, BYOK, sandbox and UI |

The Git tree showed 221 tracked blobs at the audit point. That is a repository inventory count, not an indication of code quality or test coverage.

## Audited benchmark nuances

- A (no tools) mean correctness **0.17**; B (ReAct) **0.55**; C (full verifier) **0.82** on the 30-case test. The means aggregate three trial runs.
- Groundedness C **0.74**; trajectory *equivalent unordered* C **0.73**, below its **0.80** stated goal.
- A/B have groundedness **0.00** in the evaluator because those variants do not emit cited evidence in that experimental setup. It does **not** prove all of their answers lack factual basis.
- Some trace uploads to LangSmith were refused by quota (`HTTP 429`) according to the report; model/tool execution continued locally.
- The NLI thresholds manifest reports combined accuracy **0.786** across calibration sets, with live set **0.625** vs verification_set **1.0**. Do not collapse these into a claim of universally perfect verification.
- **Metadata drift verified:** `verification_set.jsonl` contains **43** nonblank records, `verification_live.jsonl` **40**, and `report_online.json` says 43 verifier cases. However, `verify/thresholds.json` calibration metadata records `verification_set: 30`. The versions/protocols must be reconciled before citing the combined 0.786 number as if it used the current 43-case set.
- Verification benchmarks and agent benchmarks measure different tasks. Distinguish all datasets, sizes, metrics, variants, models, prices and dates.

## Critical gaps / prioritized technical debt

**P0 - hosting blocker**: Streamlit's `@st.cache_resource` creates process-cached source and per-account file resources. Never give public visitors write access to them. Introduce a session-owned sandbox filesystem/DB, an immutable source, and scoped data retrieval derived from the same branch; invalidate all state when a branch changes.

**P0 - security and BYOK**: Current settings are sourced from `.env`/process environment, not visitor-specific. Do not change `os.environ` to select a model/key in a web request. Introduce per-run `ModelRuntimeConfig`, ephemeral secrets, capability checks and a scoped client factory. Prevent trace/log leakage.

**P0 - evaluation semantics**: The replay must identify static fixtures vs recorded live runs, and include hashes of dataset, prompts, code and model. Replayed footage and timings cannot be misrepresented as live generation.

**P1 - frontend split**: Move presentation out of the monolithic Streamlit script into UI components calling versioned API. Keep domain authority in Python. Do not re-implement claims/FX policies in TypeScript.

**P1 - editable scenarios**: Original domain tables include strong SQL constraints; changes to `status`, amount, refund or deadline may require correlated business events and re-projecting. A direct table patch risks violating invariants and defeating provenance.

**P1 - verifier performance**: CPU NLI may be slow on low-cost hosts. Provide recorded results for anonymous replay; in Live, bound timeout/memory and expose clear verification availability/status. Never silently replace NLI with hard-coded green checks.

**P2 - tests / deployment**: No Playwright suite for a React app exists yet; add contracts, isolation, chaos and accessibility tests before a public launch.

## Explicit keep / refactor / add

- **Keep:** simulator and event log, all tools and SQL defenses, agent integrators, verifier, report generator, test fixtures, ADRs, license and dataset attribution.
- **Refactor:** runtime/configuration injection, session identity, tracing transport, agent API, deterministic demo representation, test harness abstraction.
- **Add:** Next.js UI, FastAPI public facade, scenario branch engine, recorded run bundles, model capability registry, evaluation UI, BYOK safeguards, deployment runbooks.
- **Do not add without proof:** multi-agent swarm, Kubernetes, external vector DB, full production payment write API, user accounts or financial transaction processing.

## Existing test baseline to run before first PR

```bash
uv sync --extra dev --extra app --extra api --extra verify
LEDGERLENS_OFFLINE=1 bash scripts/gate.sh
uv run pytest -q tests/agents tests/tools tests/verify tests/sim tests/app
```

These commands are **instructions for future implementation**. They are not recorded as executed results in this deliverable.
