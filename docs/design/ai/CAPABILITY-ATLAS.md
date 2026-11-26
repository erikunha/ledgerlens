# Open-Ended Capability Atlas - LedgerLens v3

This is a **candidate roadmap**, not a list of implemented capabilities. No arbitrary ceiling: new ideas can be appended with stable IDs. `phase` denotes a plausible discovery/implementation window, not a delivery guarantee. Capabilities must pass security and reproducibility gates before they are marked shipped. Every entry names a falsifiable verification condition.

## Data integrity - R0-R2
Strategic lens: **Proof of Work**.

| ID | Candidate capability | Required verification |
|---|---|---|
| CAP-001 | Immutable scenario manifest | A replay hash resolves to same canonical input |
| CAP-002 | Event-sourced financial ledger | Replay gives identical ledger projection |
| CAP-003 | Sandbox branch isolation | Two visitors cannot read/write each others branch |
| CAP-004 | Snapshot hash & version | Mismatched revision returns 409 |
| CAP-005 | Typed mutation commands | Invalid money/currency rejected before event append |
| CAP-006 | Reset to base | Reset produces identical canonical hash |
| CAP-007 | Temporal policy versioning | Old case evaluates against policy valid at event time |
| CAP-008 | Deterministic currencies | Minor-unit and rounding tests for currency |
| CAP-009 | Simulated business calendars | Holiday and timezone boundaries verified |
| CAP-010 | Data lineage explorer | Every row maps to source fixture and transformation |
| CAP-011 | Controlled synthetic generator | Same seed and version reproduce case |
| CAP-012 | Replay stale detection | Mutated branch invalidates recorded answer |
| CAP-013 | Data license manifest | Every external dataset has attribution |
| CAP-014 | Cross-account projection | Scoped copies exclude other account rows |

## Frontend experience - R1-R5
Strategic lens: **Distribution Advantage**.

| ID | Candidate capability | Required verification |
|---|---|---|
| CAP-015 | Guided 60s demo | First-time visitor reaches a resolved case keyless |
| CAP-016 | Payment portal modern UX | Customer and merchant records filter correctly |
| CAP-017 | Case gallery and difficulty | Each scenario links to truth and reproduction |
| CAP-018 | Recorded trace scrubber | Pause/seek never triggers provider request |
| CAP-019 | Agent execution timeline | Critical steps and data inputs visible |
| CAP-020 | Claim to source clickthrough | Each claim resolves original evidence |
| CAP-021 | Accessible data tables | Keyboard/screen-reader tests pass |
| CAP-022 | Mobile responsive trace | No clipped controls on 360px viewport |
| CAP-023 | Clear mode labels | Replay/sandbox/live labels always shown |
| CAP-024 | Shareable sanitized permalink | Shared artifact has no secrets or branch access |
| CAP-025 | Theme and contrast | WCAG checks and system theme adaptation |
| CAP-026 | Failure-first onboarding | Visitor can start with injection/outage example |
| CAP-027 | Interactive architecture map | Every node links to existing source or planned spec |
| CAP-028 | Public methodology page | Research claims carry samples and limitations |

## Financial reasoning - R2-R9
Strategic lens: **Follow the Money**.

| ID | Candidate capability | Required verification |
|---|---|---|
| CAP-029 | Decimal arithmetic engine | Exact cents for refund and fee arithmetic |
| CAP-030 | Applied vs reference FX | Different rate sources never conflated |
| CAP-031 | Refund difference decomposition | Rate vs markup components sum correctly |
| CAP-032 | Merchant payout reconciliation | Gross minus adjustments equals net |
| CAP-033 | Duplicate charge heuristic | False positive cases represented |
| CAP-034 | Chargeback deadline calculator | Business-day and timezone cutoffs correct |
| CAP-035 | Refund window evaluator | Policy versions and capture dates enforced |
| CAP-036 | Currency precision adapters | JPY/zero-decimal and 3-decimal round-trip |
| CAP-037 | Multi-currency accounting view | Money provenance and conversion dated |
| CAP-038 | Policy-to-executable rule projection | Generated suggestion validated by code |
| CAP-039 | Financial invariant monitor | Perturbation violating conservation flagged |
| CAP-040 | Cross-source reconciliation | Conflicting ledger/API statuses escalated |
| CAP-041 | Negative/partial adjustment simulation | Signed money behavior exact |
| CAP-042 | Business-case risk scoring | Assumptions explicit and not called actual loss |

## Agent runtime - R3-R11
Strategic lens: **Follow the Bottleneck**.

| ID | Candidate capability | Required verification |
|---|---|---|
| CAP-043 | Bounded ReAct loop | Cannot exceed configured tool/model iterations |
| CAP-044 | Structured triage | Pydantic entities and plan validated |
| CAP-045 | Triage clarification control | Ambiguous id never invents transaction |
| CAP-046 | Supervisor-specialist graph | Least-privilege delegation demonstrated |
| CAP-047 | Parallel evidence fan-out | Independent nodes run concurrently with cost tracked |
| CAP-048 | Specialist as tool | Supervisor retains final output and citations |
| CAP-049 | Handoff routing | Specialist assumes only scoped conversation |
| CAP-050 | Independent critic | Contradictions caught without self-confirmation |
| CAP-051 | Graph pause and resume | Checkpoint survives simulated restart |
| CAP-052 | Durable run journal | Duplicate event does not duplicate effect |
| CAP-053 | Graph cancellation | Stops work and exposes partial trace |
| CAP-054 | Idempotent retry | Tool retry bounded and traceable |
| CAP-055 | Budget exhaustion | Fails safely with no extra provider calls |
| CAP-056 | Plan vs execution diff | Tool trajectory compared with approved plan |
| CAP-057 | Agent-to-agent spoof test | Invalid delegate identity is rejected |
| CAP-058 | Cross-agent context filter | No widened data scope in subagent |

## Model provider & FinOps - R3-R15
Strategic lens: **Opportunity Cost**.

| ID | Candidate capability | Required verification |
|---|---|---|
| CAP-059 | User-supplied ephemeral key | No key persisted or exported |
| CAP-060 | Provider capability probe | Tool-calling models enabled only when tested |
| CAP-061 | OpenAI model adapter | Schema and tool tests pass |
| CAP-062 | Anthropic model adapter | Tool results normalized with tested conformance |
| CAP-063 | Google model adapter | Rate/capability tests recorded |
| CAP-064 | Local OpenAI-compatible mode | User-run environment without SSRF |
| CAP-065 | Multi-model policy router | Routing decision and eval recorded |
| CAP-066 | Cheap-first cascade | Fallback only under budget/policy constraints |
| CAP-067 | Latency-aware routing | p95 regression visible |
| CAP-068 | Cost-aware routing | Cost per correct reported, not tokens alone |
| CAP-069 | Fallback/circuit breaker | Provider outage yields bounded retry |
| CAP-070 | Price snapshot versioning | USD estimate tied to published date |
| CAP-071 | Prompt and version registry | Diff any experiment prompt by version |
| CAP-072 | Tool-call schema conformance | Malformed calls rejected safely |
| CAP-073 | Token/cache accounting | Provider usage marked observed vs estimated |
| CAP-074 | Spend kill switch | Run stops at hard budget |
| CAP-075 | Model drift monitoring | Regression compared on frozen dataset |

## Retrieval, memory & knowledge - R8-R12
Strategic lens: **Compounding**.

| ID | Candidate capability | Required verification |
|---|---|---|
| CAP-076 | Dense semantic policy retrieval | Recall@k tested against labels |
| CAP-077 | BM25/lexical retrieval | Exact identifiers retrieved correctly |
| CAP-078 | Hybrid retriever | Improvement evaluated on paired cases |
| CAP-079 | Cross encoder reranking | Latency vs precision measured |
| CAP-080 | Query rewriting ablation | Loss of original terms detectable |
| CAP-081 | Temporal policy retrieval | Correct revision selected for case date |
| CAP-082 | Evidence source hashing | Citations resolve immutable digest |
| CAP-083 | Structured query routing | SQL preferred to vector for exact fields |
| CAP-084 | Evidence relational graph | Trace references and causal caveats represented |
| CAP-085 | Session memory lifecycle | Thread reset and TTL enforced |
| CAP-086 | Case episodic memory | Cross-account recall forbidden |
| CAP-087 | Memory provenance tags | Origin and approval status visible |
| CAP-088 | Memory poisoning quarantine | Malicious case cannot become instruction |
| CAP-089 | Memory edit/forget | Deletion verified in retriever |
| CAP-090 | Graph RAG experiment | Benchmarks vs relational evidence baseline |
| CAP-091 | Context budgeting | Token/coverage tradeoff reported |

## Verification & evaluation - R4-R20
Strategic lens: **Proof of Work**.

| ID | Candidate capability | Required verification |
|---|---|---|
| CAP-092 | Claim-level numeric verifier | Amount/currency/date mismatches caught |
| CAP-093 | Textual NLI verifier | Labeled 43-case set versioned |
| CAP-094 | Citation existence check | Missing ids marked unsupported |
| CAP-095 | Verbal and numeric coherence | Claim conflict flagged by rules |
| CAP-096 | Strict and equivalent trajectories | Both scoring definitions retained |
| CAP-097 | Paired A/B/C benchmark | Same snapshot used for variants |
| CAP-098 | Multi-agent D experiment | Gain compared to C including cost |
| CAP-099 | Thread-level evaluation | Follow-up case outcome checked |
| CAP-100 | Cost per correct evaluation | Undefined denominator reported explicitly |
| CAP-101 | Calibrated risk-coverage | ECE/Brier only if valid probability inputs |
| CAP-102 | Review threshold ablation | False escalation and misses reported |
| CAP-103 | Negative-case gallery | Failures are visible with reproduction |
| CAP-104 | Frozen holdout suite | No prompt optimization on holdout |
| CAP-105 | Judge agreement study | LLM grader checked against humans |
| CAP-106 | Statistical uncertainty interval | Sample and method declared |
| CAP-107 | CI regression detection | Fail gates for critical factual regressions |
| CAP-108 | Architecture ablation suite | Remove component to measure marginal effect |
| CAP-109 | Benchmark artifact export | Version, hashes and run IDs included |

## Security & permissions - R3-R13
Strategic lens: **Inversion**.

| ID | Candidate capability | Required verification |
|---|---|---|
| CAP-110 | SQL AST allowlist | Only bounded SELECT supported |
| CAP-111 | Readonly SQLite defense | Database connection cannot mutate |
| CAP-112 | Account scoped data | Cross-account access attempt denied |
| CAP-113 | Prompt injection in ledger note | System instructions from row ignored |
| CAP-114 | Policy text injection | Retrieved passage cannot grant rights |
| CAP-115 | MCP tool poisoning detector | Manifest expansion rejected by server policy |
| CAP-116 | Inter-agent identity verification | Spoofed sender rejected |
| CAP-117 | Memory poisoning prevention | Unapproved content quarantined |
| CAP-118 | BYOK leakage scanner | Keys absent from logs/spans/exports |
| CAP-119 | Run concurrency limiter | Excess requests safely throttled |
| CAP-120 | No arbitrary remote URLs | Server rejects SSRF-style model endpoint |
| CAP-121 | Permission downgrade test | Parent tool scope cannot widen |
| CAP-122 | Sandbox resource quotas | Time/memory/network bounded |
| CAP-123 | Trace privacy filter | PII and secrets redacted |
| CAP-124 | Supply chain and SBOM checks | Dependency vulnerabilities documented |
| CAP-125 | Incident stop controls | Revoke key and terminate outstanding run |
| CAP-126 | Attack replay corpus | Safe fixtures reproducible |
| CAP-127 | Audit chain integrity | Event provenance tampering detected |

## Human review & workflow - R10
Strategic lens: **Follow the Incentives**.

| ID | Candidate capability | Required verification |
|---|---|---|
| CAP-128 | Typed review tasks | Evidence and reason mandatory |
| CAP-129 | Review decision state machine | Invalid transition rejected |
| CAP-130 | Reviewer role simulation | Approvals sandbox-only and attributed |
| CAP-131 | Escalation policy editor | Threshold change visibly affects queue |
| CAP-132 | Review queue metrics | Wait/service/rework distinguished |
| CAP-133 | Human attention budget | Workload simulated separately from model latency |
| CAP-134 | Risk-based triage | False approve/reject tradeoff displayed |
| CAP-135 | Second-opinion experiment | Human vs model decisions compared |
| CAP-136 | Disagreement review | Conflicting verifier results preserve context |
| CAP-137 | Selective prediction | Agent can abstain explicitly |
| CAP-138 | Reviewer feedback to eval | Verified corrections become cases |
| CAP-139 | Review history and audit | Decisions immutable and versioned |
| CAP-140 | Override rationale | Reason recorded without altering raw truth |
| CAP-141 | Human verification drill | Visitor confirms groundedness manually |

## Ops economics - R9
Strategic lens: **Value Capture**.

| ID | Candidate capability | Required verification |
|---|---|---|
| CAP-142 | Observed vs assumed spend | Money metric cannot hide provenance |
| CAP-143 | Model token cost ledger | Provider per-run costs reconciled |
| CAP-144 | Compute overhead cost | Show non-token cost if measured |
| CAP-145 | Labor cost assumption slider | Rate visible and not represented as market average |
| CAP-146 | Review burden simulator | Manual minutes tied to method |
| CAP-147 | Cost per correct case | Explicit numerator denominator and cohorts |
| CAP-148 | Risk-weighted expected loss | Probability and impact separately labeled |
| CAP-149 | Quality/cost Pareto chart | Dominated strategies visible |
| CAP-150 | Break-even analysis | Only for stated hypothetical economics |
| CAP-151 | Queue utilization | Overload shown at >= 1 |
| CAP-152 | Critical-path analysis | Latency vs total-work difference shown |
| CAP-153 | Performance budget dashboard | p95/throughput visible |
| CAP-154 | Policy change economics | Wrong-policy impact bounded by assumptions |
| CAP-155 | No-double-count validator | Repeated benefits not summed twice |
| CAP-156 | Economic experiment export | Assumptions included in JSON |

## Simulation & data science - R2-R19
Strategic lens: **Second-Order Thinking**.

| ID | Candidate capability | Required verification |
|---|---|---|
| CAP-157 | Seeded scenario generator | Same config reproduces dataset |
| CAP-158 | Event fork and projector | Branches do not change root data |
| CAP-159 | Mutation preview/apply/reset | Preview and apply exact diff |
| CAP-160 | Fault injection FX outage | Unavailable state and escalation correct |
| CAP-161 | Fault injection tool timeout | Partial trace and bounded retry |
| CAP-162 | Mutation chain/undo | Reversible branch events implemented |
| CAP-163 | Scenario versioning | Existing case oracle not silently changed |
| CAP-164 | Snapshot-to-run provenance | All runs reference matching branch hash |
| CAP-165 | Counterfactual FX analysis | Intervention vs correlation caveat shown |
| CAP-166 | Policy sensitivity analysis | Old vs new rule interpretation clear |
| CAP-167 | Queue discrete-event simulation | Deterministic arrival/service results |
| CAP-168 | Graph state simulator | Agent topology supports finite capped runs |
| CAP-169 | Provider response mocking | Test outputs labeled simulated |
| CAP-170 | Synthetic label generation | Model-generated labels separated from oracle |
| CAP-171 | Dataset contamination check | Train/holdout overlap flagged |
| CAP-172 | Simulation validity note | Limitations visible in UI |

## Infrastructure & SRE - R5-R16
Strategic lens: **Theory of Constraints**.

| ID | Candidate capability | Required verification |
|---|---|---|
| CAP-173 | API typed contract | OpenAPI schema integration tests |
| CAP-174 | SSE event stream | Reconnect sequence no event loss |
| CAP-175 | Run state checkpoint | Recovery after restart idempotent |
| CAP-176 | Partial trace after error | Root cause details retained |
| CAP-177 | OpenTelemetry span mapping | GenAI attributes and redaction align |
| CAP-178 | Provider error taxonomy | 429/5xx/timeouts classified |
| CAP-179 | Resilient worker queue | No duplicate task in restart |
| CAP-180 | Static replay fallback | Landing works when backend down |
| CAP-181 | Multi-session load test | No data mixing under concurrency |
| CAP-182 | Observability dashboard | Critical path and error cohort reported |
| CAP-183 | CI contract validation | Schemas/examples checked on PR |
| CAP-184 | Deployment and rollback runbook | Rollback test documented |
| CAP-185 | Dependency health and costs | Degraded mode shows accurate state |
| CAP-186 | Performance and a11y budgets | Core E2E thresholds enforced |

## Interoperability & dev tools - R14-R21
Strategic lens: **Distribution Advantage**.

| ID | Candidate capability | Required verification |
|---|---|---|
| CAP-187 | Python SDK for investigations | CLI and API use same core |
| CAP-188 | Typed TypeScript client | OpenAPI generated contract conformance |
| CAP-189 | CLI scenario replay | No web UI required |
| CAP-190 | Read-only MCP resource server | No external payment mutation tools |
| CAP-191 | MCP tool adapter | Tool registry and rights preserved |
| CAP-192 | A2A mock partner simulation | Cross-agent identity and scope verified |
| CAP-193 | Event export JSONL | Versioned sanitized event bundle |
| CAP-194 | Trace format export | Portable evidence/tracing metadata |
| CAP-195 | Plugin capability registry | Unknown tool disabled by default |
| CAP-196 | Developer tool playground | Safe fixture inputs only |
| CAP-197 | Public reproducibility recipes | Cloned repo can run offline |
| CAP-198 | Evaluation harness CLI | Run manifest and output hashes |
| CAP-199 | Local-only container quickstart | BYOK not required for baseline |
| CAP-200 | Source code deep links | Line-level anchors match SHA |

## Learning & distribution - R1-R22
Strategic lens: **Proof of Work**.

| ID | Candidate capability | Required verification |
|---|---|---|
| CAP-201 | Interactive predict/reveal | Visitor makes prediction before answer |
| CAP-202 | Why tool was chosen | Tool action mapped to case evidence |
| CAP-203 | Mistake diagnosis tour | A failure can be reproduced |
| CAP-204 | No-key shareable scenarios | First run under three minutes |
| CAP-205 | Short accessible demo video | Captions and transcript |
| CAP-206 | Portfolio proof cards | Each claim links source/version |
| CAP-207 | LinkedIn case study templates | Numbers must be proven by artifact |
| CAP-208 | Progressive expert mode | Less novice clutter, same facts |
| CAP-209 | Architecture ADR explorer | Decision alternatives readable |
| CAP-210 | Quiz by specialization | Agent security/evals/frontend choices |
| CAP-211 | Learning path from cases | Optional next challenge recommendation |
| CAP-212 | Public feedback collection | No sensitive data collected |
| CAP-213 | Release notes grounded in tests | Shipped vs planned explicit |
| CAP-214 | Contribution starter tasks | Clear verified reproduction cases |

## Frontier research - R23+
Strategic lens: **Asymmetric Bets**.

| ID | Candidate capability | Required verification |
|---|---|---|
| CAP-215 | Neuro-symbolic policy engine | Compared to deterministically encoded rules |
| CAP-216 | Bayesian decision layer | Calibration and prior sensitivity reported |
| CAP-217 | Causal graphs | Identification assumptions written |
| CAP-218 | Counterfactual explanation agent | Interventions tested on synthetic oracle |
| CAP-219 | Adaptive multi-armed model router | Out-of-sample regret evaluated |
| CAP-220 | Distilled verifier | Better latency with tested quality |
| CAP-221 | Fine-tuned intent classifier | Holdout uplift and license verified |
| CAP-222 | Small local tool agent | Hardware-cost and result benchmark |
| CAP-223 | Multimodal screenshot extraction | OCR truth and confidence validated |
| CAP-224 | Voice assistant for case exploration | Accessibility and transcript accuracy tested |
| CAP-225 | Graph RAG over financial evidence | Better groundedness than baseline |
| CAP-226 | Federated eval benchmark | No cross-tenant leakage in mock protocol |
| CAP-227 | Privacy-preserving analytics | Computation vs disclosure tradeoffs measured |
| CAP-228 | Formal state-machine verification | Safety properties checked exhaustively where finite |
| CAP-229 | Autonomous sandbox planner | No unsafe external side effects |
| CAP-230 | Model drift forecaster | Forecast evaluated on held-out time windows |
| CAP-231 | Synthetic curriculum learning | Scenario novelty and correctness rated |
| CAP-232 | Multi-role collaboration simulator | Incentive conflicts modeled explicitly |
| CAP-233 | Agent incident detective | Diagnoses repeated failures on traces |
| CAP-234 | Research plugin marketplace | Tools signed, scoped and tested |

## Capability state machine

`proposed → discovery → spec_ready → implementing → verified → shipped`, or `paused/rejected` with reason. Only tests, live traces, actual CI or observed behavior can promote a status to verified; producing a design document cannot.

## Evidence required for promotion

Each capability record shall include baseline commit hash, module owner, implementation spec, schema diffs, deterministic tests, failure-path tests, screenshots/trace where applicable, benchmark cohort, privacy/data scope, deployment decision and `verification_ref`. Related capabilities share infrastructure but never skip individual feature acceptance.

## Strategic admission test

For each idea ask: who benefits? who decides? what economic/review bottleneck? first- and second-order effects? what evidence makes this distinctive? how do visitors experience it? what can fail? cheapest reversible test? whether to publish as a research finding rather than production feature.
