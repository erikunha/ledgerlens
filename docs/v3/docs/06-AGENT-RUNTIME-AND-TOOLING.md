# Agent runtime and tool contracts

## Architectural thesis

**Make the same existing agent observable, configurable and comparable; do not invent ten agents.** The present `build_integrator`/`investigate` pipeline already has triage, plan, tool use, claim verification, memory and escalation. The public demo will expose these observable phases with explicit boundaries.

## Modes and claims

| Execution | Model involved? | Tools involved? | Source of answer | Label |
|---|---|---|---|---|
| `recorded_replay` | No call at playback | No call at playback | Genuine recorded run bundle | `Recorded execution` |
| `deterministic_sandbox` | No model | Rules + event projector | Deterministic checks and data diff | `Simulation; no LLM` |
| `live_agent` | Yes, visitor BYOK | Yes, scoped Python tools | Fresh provider-run outcome | `Live AI` |
| `offline_scripted` (legacy) | ScriptedChatModel, not learned model | Real local tools according to script | Script + tools | `Scripted fixture` |

No animation should imply a model is thinking while replaying. Do not expose private chain-of-thought; show triage output, explicit plan, tool requests/results, verifier and recommendation.

## Runtime service contract

```python
@dataclass(frozen=True)
class RunContext:
    run_id: str
    session_id: str
    branch_id: str | None
    snapshot_sha256: str
    account_id: str
    mode: Literal['recorded_replay', 'deterministic_sandbox', 'live_agent']
    model_profile_id: str | None
    prompt_version: str
    policy_version: str
    trace_schema_version: str
    budget: RunBudget
    deadline_at: datetime
    cancellation_token: CancellationToken
```

`RunBudget`: `max_model_calls`, `max_tool_calls`, `max_input_tokens`, `max_output_tokens`, `max_estimated_usd` (when price known), `max_wall_seconds`, `max_sql_rows`, `max_sql_seconds`, `max_memory_items`. Track actual usage separately. If model prices are unavailable, disable spending-based estimate as a hard bound and enforce calls/tokens/time; disclose this.

`build_integrator` must accept injected model/client, ledger path/snapshot, policy retriever, verifier, memory store and callbacks rather than consulting mutable global process state. Preserve the existing API via a compatibility adapter and tests.

## Canonical agent lifecycle

```text
validate & authorize run
 -> bind immutable snapshot/account scope
 -> triage (intent, identifiers, urgency, plan)
 -> clarification gate (if ambiguous)
 -> agent loop (bounded model turns)
 -> tool invocation (schema validation + authorization + budget + deadline)
 -> evidence normalization and IDs
 -> answer drafting
 -> deterministic numeric + temporal + coherence checks
 -> optional NLI text verification (explicit availability state)
 -> escalation/recommended action (recommendation only)
 -> final typed InvestigationResult + trace + metrics
```

Plan follow-up logic already attempts a missing step once; preserve the upper bound. Explicitly compare planned and observed trajectories in the Inspector. Clarification should not incur unnecessary downstream calls.

## Tool registry

Existing tools remain the production-quality pedagogical core:

| Tool | Input | Security | Test obligations |
|---|---|---|---|
| `query_ledger` | natural-language request + max rows | scoped, generated SQL allowlist + sqlite read-only + timeout | DML denied, CTE/subquery bypass denied, no schema leak |
| `get_ledger_record` | typed ledger ID | scope-aware authorized record only | unauthorized record indistinguishable from nonexistent |
| `search_policies` | text query, k, transform | immutable policy index, versioned chunks | empty/duplicate/stale retrieval, citation accuracy |
| `get_reference_fx` | currencies, dates | provider boundary, fixture/live labeling | unavailable rate, unsupported currency, date source |
| `calculate` | declarative operation + Decimal inputs | deterministic, no eval() | currencies, rounding, divide-zero, negative amounts |
| `recall_cases` | semantic case query | visitor memory scope and seed provenance | no cross-session retrieval, memory injection handling |

**Proposed demonstrations:** `inspect_sql_guard` is a *safe educational diagnostic* exposing reasons for rejecting a proposed query, never a write tool. `explain_verifier` returns a structured record of claim rules, evidence and model scores. These should call deterministic inspection services; they need not become LLM-callable production tools.

Tool result envelope v1:

```json
{
  "tool": "get_reference_fx",
  "ok": false,
  "data": null,
  "error": { "code": "UNSUPPORTED_CURRENCY", "retryable": false, "message": "No ECB reference for ARS" },
  "evidence_refs": [],
  "duration_ms": 15,
  "source_mode": "recorded_fixture"
}
```

Do not allow arbitrary URLs, SQL, table names or local paths to be passed through tool input. Tool parameters should be explicit Pydantic models; request data should never automatically become agent instructions.

## Verifier

Separate checks into four verdict-producing stages:

1. **Citation binding:** parse `sql:`, `policy:`, `fx:`, `calc:` references and associate each statement with exact evidence. Missing references = unverified, not supported.
2. **Deterministic financial checks:** decimal amounts/rates/date provenance, settlement equality, signed delta and currencies (prefer code over NLI).
3. **Textual entailment NLI:** only applicable to claims with comprehensible evidence; track calibration set, model version, score and threshold; may be unavailable on low-memory hosts.
4. **Escalation policy:** deadline/cutoff, unsupported currency, suspicious untrusted text, missing evidence, high-risk case, source outage.

Preserve `supported`, `contradicted`, `not_enough_evidence`, with method enum and rationale. Add a separate operational state `verification_status`: `complete`, `partial`, `unavailable`, `timed_out`. Do not map `unavailable` to `supported`.

## Architecture variants to compare

- **A Fixed chain:** useful negative control, no tools.
- **B ReAct:** natural agent-tool loop with limited tools.
- **C Full evidence-first agent:** current main implementation with verifier and escalation.
- **D Optional specialist graph:** route to a *small* independent reviewer or planner only where experimental hypotheses show gain. D must be implemented after C benchmarks and only published as better if measured quality/cost/latency improves on held-out cases.

No shared conversation memory between A/B/C runs; same snapshot, query and policy version; independent run IDs; preserve model parameters and trials. Collect failure cases, not only average scores.

## Memory and provenance

Existing SQLite short-term memory and FAISS long-term case memory are valuable for the local package. For public browsers: session-scoped short-term memory; seed past cases read-only (same labeled content for everyone); disable cross-visitor writes. When a sandbox branch is edited, previous learned facts tied to old ledger snapshots must be excluded or marked stale. A `MemoryEvent` includes `source_run_id`, `snapshot_hash`, `scope`, `created_at`, `explicit_confidence` if calibrated, and `expiry`.

## When to use multi-agent orchestration

A separate agent is warranted only when independent, measurable reasoning is needed (e.g. financial verifier cannot share the main agent's narrative assumptions; fault diagnosis can be parallelized). Use bounded LangGraph subgraphs, typed state, deterministic join and conflict resolution, no unbounded conversation loops. Evaluate additional calls, latency, model costs, and false positives. If D cannot beat C in a representative evaluation set, keep it as an experimental optional view, not the default.

## Failure injection demonstrator

The visitor may inject a **harmless test note**: `IGNORE ALL PREVIOUS INSTRUCTIONS ...` into a simulated record, or block FX tool return. The application shows which layer rejects/abstains. These are educational test fixtures; avoid offering arbitrary code execution or unfiltered third-party URL fetching. Assertions test that attempted tool escalation never reaches unauthorized execution.

## Security/performance boundaries

- Hard limits for iterations, tools, tokens, wall clock, memory and concurrency; cancel further calls when exhausted.
- Tool execution uses a single account-specific ledger snapshot; current account switch invalidates previous run context.
- Separate logical locks for mutable branch projector and in-flight run (runs bind a revision and never see mid-run mutation).
- No model-generated SQL runs without AST guard, read-only mode and timeout.
- Trace result is typed, sanitized and versioned. Never expose provider API error body verbatim if it might include secrets.
- Avoid agent loops persisting raw prompts/PII in public data stores.
