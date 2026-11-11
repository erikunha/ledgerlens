# LedgerLens v3 - Open Implementation Backlog

This file extends, **does not supersede**, the original `roadmap/IMPLEMENTATION-BACKLOG.md`. Its IDs have `LL-V3-` prefix to avoid collision. A line is a concrete candidate work unit, not yet an implementation-ready feature spec. See `advanced-specs/` for detailed contracts.

| ID | Release | Task | Evidence required |
|---|---|---|---|
| `LL-V3-R0-01` | R0 | Freeze baseline commit, lockfile and scenario hashes | reproducible test + trace/fixture + source link |
| `LL-V3-R0-02` | R0 | Run offline tests and record exact output | reproducible test + trace/fixture + source link |
| `LL-V3-R0-03` | R0 | Normalize existing Span to public TraceEvent schema | reproducible test + trace/fixture + source link |
| `LL-V3-R0-04` | R0 | Capture and redact canonical replay bundle | reproducible test + trace/fixture + source link |
| `LL-V3-R0-05` | R0 | Reconcile reported 30-vs-43 case verifier claims | reproducible test + trace/fixture + source link |
| `LL-V3-R0-06` | R0 | Add migration-safe Python RunContext | reproducible test + trace/fixture + source link |
| `LL-V3-R0-07` | R0 | Document current SQL guard and account isolation | reproducible test + trace/fixture + source link |
| `LL-V3-R1-01` | R1 | Implement Next.js shell and responsive design tokens | reproducible test + trace/fixture + source link |
| `LL-V3-R1-02` | R1 | Ship zero-auth scenario gallery with provenance | reproducible test + trace/fixture + source link |
| `LL-V3-R1-03` | R1 | Render true recorded trace stepping | reproducible test + trace/fixture + source link |
| `LL-V3-R1-04` | R1 | Implement payment record explorer | reproducible test + trace/fixture + source link |
| `LL-V3-R1-05` | R1 | Show claim/verdict/evidence linked inspector | reproducible test + trace/fixture + source link |
| `LL-V3-R1-06` | R1 | Add architecture explorer with source anchors | reproducible test + trace/fixture + source link |
| `LL-V3-R1-07` | R1 | Automate accessibility and mobile Playwright tests | reproducible test + trace/fixture + source link |
| `LL-V3-R2-01` | R2 | Design typed sandbox event/mutation commands | reproducible test + trace/fixture + source link |
| `LL-V3-R2-02` | R2 | Fork immutable base snapshot per session | reproducible test + trace/fixture + source link |
| `LL-V3-R2-03` | R2 | Implement idempotent append/projection | reproducible test + trace/fixture + source link |
| `LL-V3-R2-04` | R2 | Preview and diff sandbox mutations | reproducible test + trace/fixture + source link |
| `LL-V3-R2-05` | R2 | Recompute scenario oracle after mutation | reproducible test + trace/fixture + source link |
| `LL-V3-R2-06` | R2 | Implement reset/hash consistency and TTL | reproducible test + trace/fixture + source link |
| `LL-V3-R2-07` | R2 | Run two-visitor isolation and conflict E2E | reproducible test + trace/fixture + source link |
| `LL-V3-R3-01` | R3 | Build tested model/provider registry | reproducible test + trace/fixture + source link |
| `LL-V3-R3-02` | R3 | Implement ephemeral BYOK secret handle and delete | reproducible test + trace/fixture + source link |
| `LL-V3-R3-03` | R3 | Create Python run coordinator and strict budget | reproducible test + trace/fixture + source link |
| `LL-V3-R3-04` | R3 | Stream typed SSE and cancellation | reproducible test + trace/fixture + source link |
| `LL-V3-R3-05` | R3 | Wire model selector and transparent consent | reproducible test + trace/fixture + source link |
| `LL-V3-R3-06` | R3 | Conformance-test tool-calling on selected provider | reproducible test + trace/fixture + source link |
| `LL-V3-R3-07` | R3 | Exercise key/trace redaction under failure | reproducible test + trace/fixture + source link |
| `LL-V3-R4-01` | R4 | Freeze comparable A/B/C eval manifests | reproducible test + trace/fixture + source link |
| `LL-V3-R4-02` | R4 | Reproduce old benchmark and report deviations | reproducible test + trace/fixture + source link |
| `LL-V3-R4-03` | R4 | Build dataset slice/relevance metadata | reproducible test + trace/fixture + source link |
| `LL-V3-R4-04` | R4 | Implement paired quality/latency/cost chart | reproducible test + trace/fixture + source link |
| `LL-V3-R4-05` | R4 | Expose NLI and numeric verifier disagreements | reproducible test + trace/fixture + source link |
| `LL-V3-R4-06` | R4 | Run heldout regression and uncertainty estimates | reproducible test + trace/fixture + source link |
| `LL-V3-R4-07` | R4 | Publish failure gallery and test limitations | reproducible test + trace/fixture + source link |
| `LL-V3-R5-01` | R5 | Deploy static replay fallback separate from runtime | reproducible test + trace/fixture + source link |
| `LL-V3-R5-02` | R5 | Implement safe degradation and status dashboard | reproducible test + trace/fixture + source link |
| `LL-V3-R5-03` | R5 | Publish code-linked architecture case study | reproducible test + trace/fixture + source link |
| `LL-V3-R5-04` | R5 | Verify keyboard and screenreader task completion | reproducible test + trace/fixture + source link |
| `LL-V3-R5-05` | R5 | Perform dependency/security and threat review | reproducible test + trace/fixture + source link |
| `LL-V3-R5-06` | R5 | Measure hosting, rate limit and p95 under sample load | reproducible test + trace/fixture + source link |
| `LL-V3-R6-01` | R6 | Implement narrow specialist dispatcher behind flag | reproducible test + trace/fixture + source link |
| `LL-V3-R6-02` | R6 | Define strict specialist output/evidence schema | reproducible test + trace/fixture + source link |
| `LL-V3-R6-03` | R6 | Benchmark specialist against baseline C on paired set | reproducible test + trace/fixture + source link |
| `LL-V3-R6-04` | R6 | Compare parallel and sequential critical path | reproducible test + trace/fixture + source link |
| `LL-V3-R6-05` | R6 | Publish negative results if no benefit | reproducible test + trace/fixture + source link |
| `LL-V3-R6-06` | R6 | Enforce call/recursion/cost ceilings | reproducible test + trace/fixture + source link |
| `LL-V3-R7-01` | R7 | Collect safe canned adversarial prompts | reproducible test + trace/fixture + source link |
| `LL-V3-R7-02` | R7 | Simulate tool timeout and provider 429 | reproducible test + trace/fixture + source link |
| `LL-V3-R7-03` | R7 | Show error source and safe recovery trace | reproducible test + trace/fixture + source link |
| `LL-V3-R7-04` | R7 | Build fault injector with no network side effects | reproducible test + trace/fixture + source link |
| `LL-V3-R7-05` | R7 | Regression-test missing policy/FX scenarios | reproducible test + trace/fixture + source link |
| `LL-V3-R7-06` | R7 | Create reproducible incident tour | reproducible test + trace/fixture + source link |
| `LL-V3-R8-01` | R8 | Design immutable EvidenceRef + SourceVersion schema | reproducible test + trace/fixture + source link |
| `LL-V3-R8-02` | R8 | Build relational evidence link traversal | reproducible test + trace/fixture + source link |
| `LL-V3-R8-03` | R8 | Implement temporal policy selectors | reproducible test + trace/fixture + source link |
| `LL-V3-R8-04` | R8 | Render claim-to-record provenance graph | reproducible test + trace/fixture + source link |
| `LL-V3-R8-05` | R8 | Reject forged or stale citation references | reproducible test + trace/fixture + source link |
| `LL-V3-R8-06` | R8 | Provide trace-linked export and source hashes | reproducible test + trace/fixture + source link |
| `LL-V3-R9-01` | R9 | Implement Decimal-based per-case economic ledger | economic/functional oracle + paired test + assumptions |
| `LL-V3-R9-02` | R9 | Capture provider token cost with date/version | economic/functional oracle + paired test + assumptions |
| `LL-V3-R9-03` | R9 | Build cost-per-correct and provenance UI | economic/functional oracle + paired test + assumptions |
| `LL-V3-R9-04` | R9 | Add review and error-risk assumptions panel | economic/functional oracle + paired test + assumptions |
| `LL-V3-R9-05` | R9 | Compute paired economic frontiers | economic/functional oracle + paired test + assumptions |
| `LL-V3-R9-06` | R9 | Test no-double-count and undefined denominators | economic/functional oracle + paired test + assumptions |
| `LL-V3-R9-07` | R9 | Publish hypothetical vs observed labels | economic/functional oracle + paired test + assumptions |
| `LL-V3-R10-01` | R10 | Implement review task/decision state machine | economic/functional oracle + paired test + assumptions |
| `LL-V3-R10-02` | R10 | Add reviewer role simulation and audit | economic/functional oracle + paired test + assumptions |
| `LL-V3-R10-03` | R10 | Build queue simulation and capacity slider | economic/functional oracle + paired test + assumptions |
| `LL-V3-R10-04` | R10 | Compare review thresholds to false errors | economic/functional oracle + paired test + assumptions |
| `LL-V3-R10-05` | R10 | Introduce selective prediction/abstention view | economic/functional oracle + paired test + assumptions |
| `LL-V3-R10-06` | R10 | Verify pause/resume after human decision | economic/functional oracle + paired test + assumptions |
| `LL-V3-R10-07` | R10 | Test overloaded queue display | economic/functional oracle + paired test + assumptions |
| `LL-V3-R11-01` | R11 | Define DAG/supervisor/agent-tool schema | reproducible test + trace/fixture + source link |
| `LL-V3-R11-02` | R11 | Implement bounded parallel dispatch | reproducible test + trace/fixture + source link |
| `LL-V3-R11-03` | R11 | Build agent topology editor with simulation | reproducible test + trace/fixture + source link |
| `LL-V3-R11-04` | R11 | Add handoff and context filtering tests | reproducible test + trace/fixture + source link |
| `LL-V3-R11-05` | R11 | Checkpoint and resume after interruption | reproducible test + trace/fixture + source link |
| `LL-V3-R11-06` | R11 | Compare multiagent and singleagent outcome/cost | reproducible test + trace/fixture + source link |
| `LL-V3-R11-07` | R11 | Visualize plan-vs-actual dependencies | reproducible test + trace/fixture + source link |
| `LL-V3-R12-01` | R12 | Create temporal memory and source provenance schema | reproducible test + trace/fixture + source link |
| `LL-V3-R12-02` | R12 | Implement BM25/hybrid/re-rank lab | reproducible test + trace/fixture + source link |
| `LL-V3-R12-03` | R12 | Evaluate dense vs hybrid on same relevance labels | reproducible test + trace/fixture + source link |
| `LL-V3-R12-04` | R12 | Add memory inspect/edit/delete flow | reproducible test + trace/fixture + source link |
| `LL-V3-R12-05` | R12 | Quarantine untrusted memory injection | reproducible test + trace/fixture + source link |
| `LL-V3-R12-06` | R12 | Test cross-account retrieval boundary | reproducible test + trace/fixture + source link |
| `LL-V3-R12-07` | R12 | Benchmark evidence/tokens trade-off | reproducible test + trace/fixture + source link |
| `LL-V3-R13-01` | R13 | Map OWASP agentic threats to safe fixtures | reproducible test + trace/fixture + source link |
| `LL-V3-R13-02` | R13 | Build prompt and tool poisoning labs | reproducible test + trace/fixture + source link |
| `LL-V3-R13-03` | R13 | Implement privilege intersections at dispatcher | reproducible test + trace/fixture + source link |
| `LL-V3-R13-04` | R13 | Create malicious citation detector | reproducible test + trace/fixture + source link |
| `LL-V3-R13-05` | R13 | Stress-test BYOK data egress prevention | reproducible test + trace/fixture + source link |
| `LL-V3-R13-06` | R13 | Publish threat matrix and limits | reproducible test + trace/fixture + source link |
| `LL-V3-R13-07` | R13 | Verify kill/revoke on incident | reproducible test + trace/fixture + source link |
| `LL-V3-R14-01` | R14 | Expose read-only case/replay resources via MCP | schema conformance + auth/isolation test + example |
| `LL-V3-R14-02` | R14 | Add typed tool registry and permission spec | schema conformance + auth/isolation test + example |
| `LL-V3-R14-03` | R14 | Build A2A mock external-review protocol | schema conformance + auth/isolation test + example |
| `LL-V3-R14-04` | R14 | Sign/verify delegated case identity in simulation | schema conformance + auth/isolation test + example |
| `LL-V3-R14-05` | R14 | Reject malformed or elevated tool manifests | schema conformance + auth/isolation test + example |
| `LL-V3-R14-06` | R14 | Conformance-test timeouts/retries | schema conformance + auth/isolation test + example |
| `LL-V3-R15-01` | R15 | Add provider adapters behind shared typed gateway | economic/functional oracle + paired test + assumptions |
| `LL-V3-R15-02` | R15 | Implement per-intent routing table and fallback | economic/functional oracle + paired test + assumptions |
| `LL-V3-R15-03` | R15 | Log and present routing decision rationale | economic/functional oracle + paired test + assumptions |
| `LL-V3-R15-04` | R15 | Calibrate price snapshots and cost estimates | economic/functional oracle + paired test + assumptions |
| `LL-V3-R15-05` | R15 | Test small-vs-large model cost per correct | economic/functional oracle + paired test + assumptions |
| `LL-V3-R15-06` | R15 | Apply circuit breaker and hard spend cap | economic/functional oracle + paired test + assumptions |
| `LL-V3-R15-07` | R15 | Validate provider schema drift reporting | economic/functional oracle + paired test + assumptions |
| `LL-V3-R16-01` | R16 | Persist durable graph checkpoints and job journals | reproducible test + trace/fixture + source link |
| `LL-V3-R16-02` | R16 | Implement idempotent restart recovery | reproducible test + trace/fixture + source link |
| `LL-V3-R16-03` | R16 | Instrument OpenTelemetry GenAI spans safely | reproducible test + trace/fixture + source link |
| `LL-V3-R16-04` | R16 | Build health/incident SLO dashboard | reproducible test + trace/fixture + source link |
| `LL-V3-R16-05` | R16 | Load test concurrent visit branches | reproducible test + trace/fixture + source link |
| `LL-V3-R16-06` | R16 | Run chaos drills for cancellation/duplicate events | reproducible test + trace/fixture + source link |
| `LL-V3-R16-07` | R16 | Document deployment and rollback | reproducible test + trace/fixture + source link |
| `LL-V3-R17-01` | R17 | Expand seeded operational event generator | reproducible test + trace/fixture + source link |
| `LL-V3-R17-02` | R17 | Add arrival/service review queue events | reproducible test + trace/fixture + source link |
| `LL-V3-R17-03` | R17 | Model divergent stakeholder incentives | reproducible test + trace/fixture + source link |
| `LL-V3-R17-04` | R17 | Implement workload pressure simulation UI | reproducible test + trace/fixture + source link |
| `LL-V3-R17-05` | R17 | Bound and expose simulation assumptions | reproducible test + trace/fixture + source link |
| `LL-V3-R17-06` | R17 | Validate projector with property tests | reproducible test + trace/fixture + source link |
| `LL-V3-R17-07` | R17 | Build synthetic data quality report | reproducible test + trace/fixture + source link |
| `LL-V3-R18-01` | R18 | Build synthetic PDF/receipt/document fixture set | reproducible test + trace/fixture + source link |
| `LL-V3-R18-02` | R18 | Extract OCR fields with source coordinates | reproducible test + trace/fixture + source link |
| `LL-V3-R18-03` | R18 | Create document-to-ledger matching experiment | reproducible test + trace/fixture + source link |
| `LL-V3-R18-04` | R18 | Evaluate multilingual policy passage retrieval | reproducible test + trace/fixture + source link |
| `LL-V3-R18-05` | R18 | Implement safe upload/size/retention controls | reproducible test + trace/fixture + source link |
| `LL-V3-R18-06` | R18 | Compare OCR and vision models vs ground truth | reproducible test + trace/fixture + source link |
| `LL-V3-R18-07` | R18 | Publish extraction failure examples | reproducible test + trace/fixture + source link |
| `LL-V3-R19-01` | R19 | Define structural causal assumptions and interventions | reproducible test + trace/fixture + source link |
| `LL-V3-R19-02` | R19 | Implement FX/policy counterfactual branch tool | reproducible test + trace/fixture + source link |
| `LL-V3-R19-03` | R19 | Show direct and downstream consequences | reproducible test + trace/fixture + source link |
| `LL-V3-R19-04` | R19 | Build causal-vs-correlational explanation test | reproducible test + trace/fixture + source link |
| `LL-V3-R19-05` | R19 | Validate with synthetic structural oracle | reproducible test + trace/fixture + source link |
| `LL-V3-R19-06` | R19 | Include confounder and identifiability caveats | reproducible test + trace/fixture + source link |
| `LL-V3-R20-01` | R20 | Implement feedback-to-gold-label review pipeline | reproducible test + trace/fixture + source link |
| `LL-V3-R20-02` | R20 | Add dataset versioning and holdout isolation | reproducible test + trace/fixture + source link |
| `LL-V3-R20-03` | R20 | Calibrate NLI/abstention thresholds | reproducible test + trace/fixture + source link |
| `LL-V3-R20-04` | R20 | Train optional small intent model with license review | reproducible test + trace/fixture + source link |
| `LL-V3-R20-05` | R20 | Ablate prompt/retrieval/fine-tune alternatives | reproducible test + trace/fixture + source link |
| `LL-V3-R20-06` | R20 | Publish measured drift and rollback report | reproducible test + trace/fixture + source link |
| `LL-V3-R20-07` | R20 | Maintain failure-to-regression ledger | reproducible test + trace/fixture + source link |
| `LL-V3-R21-01` | R21 | Generate TS client from OpenAPI schema | schema conformance + auth/isolation test + example |
| `LL-V3-R21-02` | R21 | Publish Python CLI and SDK for replay/evals | schema conformance + auth/isolation test + example |
| `LL-V3-R21-03` | R21 | Support MCP read-only tool delivery | schema conformance + auth/isolation test + example |
| `LL-V3-R21-04` | R21 | Add typed example conformance suites | schema conformance + auth/isolation test + example |
| `LL-V3-R21-05` | R21 | Create local docker/uv quickstart offline | schema conformance + auth/isolation test + example |
| `LL-V3-R21-06` | R21 | Package portable benchmark bundles | schema conformance + auth/isolation test + example |
| `LL-V3-R21-07` | R21 | Version tool contracts and semver guarantees | schema conformance + auth/isolation test + example |
| `LL-V3-R22-01` | R22 | Generate source-linked shareable case study artifacts | accessible artifact + verified public proof |
| `LL-V3-R22-02` | R22 | Create accessible short demos and captions | accessible artifact + verified public proof |
| `LL-V3-R22-03` | R22 | Define privacy-safe portfolio visitor analytics | accessible artifact + verified public proof |
| `LL-V3-R22-04` | R22 | Run five-person comprehension usability audit | accessible artifact + verified public proof |
| `LL-V3-R22-05` | R22 | Publish reproducibility and attribution checklist | accessible artifact + verified public proof |
| `LL-V3-R22-06` | R22 | Collect external engineering reviews | accessible artifact + verified public proof |
| `LL-V3-R22-07` | R22 | Review conversion/feedback not vanity metrics | accessible artifact + verified public proof |
| `LL-V3-R23+-01` | R23+ | Define next research candidate with hypothesis and evidence | reproducible test + trace/fixture + source link |
| `LL-V3-R23+-02` | R23+ | Select independent research baseline and oracle | reproducible test + trace/fixture + source link |
| `LL-V3-R23+-03` | R23+ | Build smallest safe synthetic demonstrator | reproducible test + trace/fixture + source link |
| `LL-V3-R23+-04` | R23+ | Publish positive or negative result with limitations | reproducible test + trace/fixture + source link |
| `LL-V3-R23+-05` | R23+ | Review cost/ownership/scope before public claim | reproducible test + trace/fixture + source link |
| `LL-V3-R23+-06` | R23+ | Append capability without renumbering existing IDs | reproducible test + trace/fixture + source link |

## Per-task definition of done

Task moves to `verified` only after: exact source SHA recorded; affected schemas and data versions specified; authorized scopes enforced; deterministic and failure-path tests executed; frontend interaction tested when applicable; a meaningful proof artifact captured; known non-goals and rollback noted. New work must not bypass the original offline CI gate.

## Promotion from broad vision to engineering spec

For any chosen task, create a `advanced-specs/LL-V3-Rx-nn-...md` with user outcome, domain constraints, system contracts, component owner, persistence/migration, security, failure semantics, BDD cases, performance/cost budget, verification commands and source links. Avoid generating hundreds of near-identical boilerplate spec files before actual design decisions are needed.
