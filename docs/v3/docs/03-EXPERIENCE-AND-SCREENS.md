# Experience architecture: every public screen and state

## Product shell / IA

- **Landing `/`** - portfolio entry, result in 10 seconds, two primary CTAs: "Try a case" and "See the engineering". A static illustration of evidence-backed reasoning, honest metrics, GitHub and repository license/source links. No generic SaaS pricing/signup.
- **Guided Demo `/demo`** - curated scenarios with clear labels, story, expected lesson, scenario duration and difficulty. No API key. Interactive step-through of recorded real runs.
- **Ledger `/lab/ledger`** - payments portal with account switch, activity/refunds/disputes/payouts, sortable/filterable dense table, detail panel and linked evidence.
- **Scenario Lab `/lab/scenarios`** - scenario gallery, branch editor, allowed mutations, validation, preview, reset and compare before/after.
- **Agent Inspector `/lab/runs/:id`** - plan/tree, timeline, tools, SQL, model calls, evidence, claims/verdicts and escalation; live updates in BYOK mode, replay controls in recorded mode.
- **Model Arena `/lab/arena`** - run comparison using identical snapshot+question+prompt variant, architecture/model selectors, outcomes, cost/latency/quality, provenance. Only displayed when comparable data exist.
- **Evaluation Lab `/research/evals`** - benchmark metadata, sample size, runs, uncertainty, per-case breakdown, known failures, held-out set policies, reproducible run command.
- **Architecture Tour `/engineering`** - clickable high-level diagram, ADRs, threat model, source links, data provenance and key trade-offs.
- **About `/about`** - portfolio narrative, repository, method, limitations, demo disclosure, contact link (only if supplied by owner; do not invent personal addresses).

## Universal navigation

Desktop: compact header (LedgerLens mark, Demo, Scenario Lab, Evaluation, Engineering, GitHub); contextual secondary navigation inside Lab. Right-side drawer for provenance on larger screens. Mobile: single-column with accessible tabs/segmented switch; no permanently tiny trace columns. A clear mode indicator remains visible: **Recorded Replay**, **Deterministic Sandbox** or **Live AI - Your Key**.

Persist only safe view preferences (e.g. last tab, theme) as URL query/state; never put BYOK, account secrets or whole prompts in URLs. Prefer deep links to *public sanitized* run artifacts, not session-bound private traces.

## Page-level UX contracts

### S01 Landing

Hero: "AI investigating payments - with evidence, not guesses." Subhead clearly says all money is simulated. Primary CTA launches curated FX discrepancy; secondary CTA opens architecture. Above fold: tiny evidence chain showing ledger + policy + calculator → verified answer. Social proof = actual GitHub tests and published evaluation data; no invented logos, customer counts or production uptime.

Below fold: 3 demo modes, high-level stack (Python/LangGraph/React), a result metric with sample size, limitations and open-source link. Technical screen captures should use *real implemented UI* after deployment, not conceptual screens represented as screenshots.

### S02 Scenario Gallery

Cards for at least: FX refund, duplicate charge, dispute deadline, settlement arithmetic, injected instruction in refund note, unavailable FX source, ambiguous purchase, no transaction. Each card displays a question, concepts demonstrated (RAG, SQL guard, memory, human review etc.), data origin (`public-derived`, `simulated`), and status (`Recorded`, `Editable`, `Live-compatible`).

Open card → scene overview, expected evidence, "Start guided replay", "Create editable branch", "Open ledger". Accessible search and filters. Avoid showing the exact answer/ground truth up front if visitor wants to investigate.

### S03 Payments Portal

At top: account persona badge (demo customer/merchant), currency, simulated balance/statistics; account switch. Main area: DataTable of transactions with amount, date, type, status, counterparty, provider and meaningful IDs. Selection opens contextual side panel: recorded business events, refund/FX fields, policy triggers and CTA "Investigate this". Different states for duplicate, disputed and refunded transactions. Mark which rows the selected agent run actually read, plus source links to tool responses. On mobile, list cards with full-detail drawer.

Required status design: authorized/captured/failed/partially_refunded/refunded/disputed/charged_back; display localized currency with explicit currency code, never ambiguous sign or locale. Sorting/filtering/pagination must be server-managed or bounded based on small public dataset; no table of thousands eagerly mounted.

### S04 Scenario Editor

Left: event timeline from immutable base. Center: form with *allowed operations*, e.g. change a refund FX rate via a sandbox business event, add a duplicate payment, shorten a chargeback deadline, simulate an FX outage as tool fault, inject untrusted text in a merchant note, toggle policy version. Right: preview of affected rows, expected invariants and invalidation warnings. Primary actions **Preview**, **Apply to sandbox**, **Run checks**, **Run agent (BYOK)**, **Reset**.

After mutation: show before/after values, event IDs, changed projection rows, changed expected facts, and whether the prior recorded trace still applies. **It does not**: a trace tied to a different snapshot is stale and must be visibly invalidated. "Run checks" is deterministic; no fake LLM response. If no BYOK, offer replay of the original case and a clear invitation for live analysis on the modified case.

### S05 Agent Inspector

Use 3 conceptual panes (can be tabs on mobile): **Execution** (tree/timeline), **Evidence** (citations/source payloads), **Decision** (claims/verdicts/action). Collapsible spans with time, token usage, model, arguments and output envelope. SQL is syntax-highlighted with sanitized literals; show AST allowlist and query guard result. High-level timeline: triage → plan → tool calls → verify → escalation → answer. Show delta between planned and actual tool calls.

For every claim show text, cited evidence IDs, verification method (`rule`, `numeric`, `nli`, `none`), verdict, score (when meaningful), warning that NLI is imperfect, and why human review was triggered. Export trace JSON scrubbed of secrets. Never render a model's hidden chain of thought or claim it is available; show observable plan, tool choices and outputs only.

### S06 Live Model Workspace

Opt-in modal with provider, model (only supported + testable), key entry via password field, provider request/billing disclosure, session lifetime, model capabilities and cost limits. Modes: `Replay`, `Sandbox deterministic`, `Live`. Live shows connection status, budget used, current step and abort. On cancellation display stopped/incomplete, not successful. Immediate "Forget key" revocation.

Model selection always carries actual `provider_model_id`, `capabilities`, `model_release/version when known`, `rate_card_timestamp`, and tested status. Unknown price shown as unknown; no fabricated cost. Model capabilities checked with safe metadata/probe, not model name heuristics alone.

### S07 Model Arena

Compare the same snapshot and query with architecture variants A/B/C; optionally provider/model choices. Table: correctness evaluation criteria, supported-claim ratio, critical mistakes, tool trajectory, escalation accuracy, latency, tokens and estimated/provider-reported cost. Different sample sizes/datasets must not be plotted as directly comparable without warning. Drill into one failing case and inspect divergent tool paths and evidence.

One-click comparison of **recorded reference** variants without key; live A/B/C comparison only with explicit cost preview and budget guard. No long, uncontrolled loops.

### S08 Evaluation Lab

Baseline metrics with date, dataset checksum, model config, number of cases, trials, scoring definitions, limitations. Failure gallery: cases B and C missed, where retrieval fails, where NLI says unknown, where tool paths differ. Include separate verifier calibration sets (`verification_set` versus `verification_live`) and caution about selection bias. Export CSV/JSON results and exact command to reproduce offline.

### S09 Architecture Tour

Clickable subsystem diagram; callouts for `query_ledger` AST guard, scoped ledger copy, decimal calculator, deterministic simulator, read-only APIs, NLI verifier, memory, observability. Each diagram node links to exact GitHub module and design ADR. Add a 60-second narrated *text* tour and downloadable high-level architecture; no needless 3D animation.

## Interaction states (global)

| State | UI behavior |
|---|---|
| Idle | Clear next action, sample case suggestion |
| Loading / replay | Non-blocking skeleton, cancel/stop, progress semantics |
| Offline | Explicit banner; static artifacts remain usable |
| Live streaming | Expandable spans append; text answer withheld until verifier completes |
| Verification unavailable | Label `Not verified`, no green badge |
| Unsupported model | Incompatible capability explanation, disabled run |
| Wrong key | Redacted error, keep field available to retry, no echo in trace |
| Branch mutation invalid | Transaction rejected atomically, show invariant and no partial changes |
| Stale baseline | Comparison requires same snapshot or clearly highlights mismatch |
| Session expired | Clear reset state; BYOK forgotten; replay available |
| Tool timeout | Partial trace + error classification; no fabricated conclusion |
| Unauthorized access | Generic forbidden message; no data existence leakage |

## Progressive disclosure

Default visitor view has a narrative and result. "Show engineering" reveals trace/tool arguments. "Show raw" exposes sanitized JSON. An expert can inspect everything while a recruiter is not confronted with implementation details immediately. Provide keyboard shortcuts for trace navigation, not mandatory to complete work.

## User education

Each scenario has: **Question → Evidence consulted → Agent actions → Verified answer → Why this design? → What fails?**. In guided mode, explanatory labels differentiate an LLM-produced conclusion from deterministic arithmetic/rules. This is not a textbook with long static walls of text; explanations accompany actual observable events.
