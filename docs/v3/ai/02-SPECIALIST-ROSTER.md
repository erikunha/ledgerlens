# Agent Roles and Boundaries

**Important:** these are *capabilities/roles*, not a requirement to instantiate 25 independent LLMs. Each can be a deterministic Python tool, narrow LLM process, subgraph or delegated agent. The experiment measures whether specialization pays off.

| Role | Input | Allowed function | Output and evidence | Primary failure/control |
|---|---|---|---|---|
| Intake/Triage | question + scoped metadata | intent, entities, clarification | typed `Triage` | disambiguation, no guessing |
| Ledger Investigator | scoped ledger read | SQL select/record read | relevant immutable rows | SQL guard + timeout |
| FX Specialist | dates/currencies | rate lookup, rate comparison | rate source/time + caveats | never equate benchmark to actual rate |
| Refund Specialist | refund + policy | policy scope checks | supported adjustment hypothesis | no refund execution |
| Dispute Specialist | dispute docs/dates | deadline computation | status, cutoff evidence | no legal conclusions |
| Settlement Specialist | period and entries | exact cash arithmetic | fee/refund/net breakdown | Decimal/integer minor units |
| Policy Analyst | policy search | passage + version comparison | citation + temporal validity | quote integrity |
| Retrieval Strategist | question | choose retrieval route | coverage report | prevent context expansion leakage |
| Memory Researcher | thread and cases | scoped case memory read | similar cases + uncertainty | memory poisoning / tenant isolation |
| Evidence Curator | raw refs | canonical evidence assembly | provenance graph | no invented citations |
| Narrative Composer | supported facts | plain-language explanation | answer with claim refs | unsupported inference |
| Claim Verifier | answer + evidence | NLI + numerical verifier | structured verdicts | threshold calibration |
| Coherence Auditor | computed results | invariant checks | contradictions and explanations | deterministic precedence |
| Escalation Controller | verdicts/risks | threshold policy | review recommendation | over/under-escalation |
| Case Reviewer | approved review context | human decision support | review record | server approval required |
| Model Router | intent/risk/budget | allowed provider selection | model choice + rationale | budget/compatibility check |
| Tool Sentinel | tool call and policy | validate args/permission | allow/deny audit event | prevent tool misuse |
| Red Team Generator | sandbox config | inject synthetic untrusted text | adversarial case package | isolated environment |
| Data Lineage Analyst | event refs | reconstruct source/projector | chain of transformations | stale snapshot handling |
| Scenario Designer | synthetic fixture spec | bounded event editing | diff + ground truth update | branch-only writes |
| Evaluation Judge | run + evaluation criteria | code or judge evaluation | grades and uncertainty | independent holdout |
| Cost Analyst | measured usage | compute cost model | normalized cost ledger | provenance required |
| Bottleneck Analyst | traces + queue model | simulate load/capacity | critical path, overload | no fabricated staff savings |
| Incident Investigator | partial runs/alerts | failure triage, replay | root-cause hypothesis | don't claim root cause from correlation |
| Technical Tutor | run + artifact | generate explanation/exercise | user-facing teaching | label model-generated teaching |
| Experiment Historian | experiment manifests | compare versions | immutable experiment narrative | prevent cherry-picking |

## Shared specialist contract

`run_specialist(spec: SpecialistSpec, context: RunContext, inputs: StrictTypedInputs) -> SpecialistResult`. `SpecialistSpec`: versioned ID, required inputs, allowed tool IDs, maximum data scope, budget, retry policy, timeout, output schema, expected evidence. `SpecialistResult`: output, status, refs, tokens/spend, trace ID, abstention reason. No specialist can write to source events or move funds.

## Role-to-screen mapping

- Agent Flow: Intake, Ledger, Policy, FX, Settlement, Composer, Verifier.
- Human Review: Escalation + Case Reviewer + review-economics context.
- Attack Lab: Tool Sentinel + Red Team + Evidence Curator.
- Cost/Quality Arena: Model Router + Evaluation Judge + Cost Analyst.
- Scenario Lab: Data Lineage Analyst + Scenario Designer + technical tutor.

Potential extension roles (research): multimodal document examiner, code-change evaluator, external agent gateway, causal hypothesis reviewer, anomaly detector, skill recommender, temporal RAG curator, forecast simulator. Their existence in the spec does **not** prove their usefulness or safety.
