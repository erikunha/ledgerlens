# LedgerLens Lab - Screen Registry (full-scope vision)

All screens are planned until individually verified as implemented. Routes, screens and capabilities are **proposals**, not assertions about the current Streamlit UI. Every route supports keyboard navigation, focus management, semantic labelling, descriptive empty/loading/error/cancelled states, reduced motion and mobile adaptation. Money calculations and tool permissions remain server-side.

| # | Screen | Route | Primary value | Target |
|---:|---|---|---|---|
| 1 | Home / Start | `/` | Understand what is live vs replay, start scenario with no account | R1 |
| 2 | Guided Tour | `/tour` | Follow a scripted path through ledger, tool, verification | R1 |
| 3 | Payment Portal | `/pay` | Inspect account activity and ask why a transaction differs | R1 |
| 4 | Case Gallery | `/cases` | Choose an investigation by difficulty/risk/skill | R1 |
| 5 | Case Detail | `/cases/[id]` | Read ground truth, constraints, expected tool chain and outcome | R1 |
| 6 | Scenario Editor | `/lab/scenario/[id]` | Modify simulated data under domain invariants | R2 |
| 7 | Branch Diff | `/lab/diff/[branch]` | Inspect exact before/after of events, ledger and conclusions | R2 |
| 8 | Agent Flight Recorder | `/runs/[id]` | Inspect real or recorded timeline of model/tools | R1 |
| 9 | Agent Graph | `/runs/[id]/graph` | Understand orchestration, dependencies, critical path | R11 |
| 10 | Evidence Graph | `/runs/[id]/evidence` | Trace each answer claim to primary data and version | R8 |
| 11 | Verifier Studio | `/lab/verifier` | See why NLI and arithmetic verifiers disagree | R4 |
| 12 | Live Model Settings | `/live/settings` | Choose tested model and optional BYOK with clear budgets | R3 |
| 13 | Model Arena | `/lab/models` | Compare A/B/C/D/E across paired cases | R4 |
| 14 | Economics Lab | `/lab/economics` | Measure cost per correctly resolved case with assumptions | R9 |
| 15 | Review Queue Simulator | `/lab/review` | Find bottleneck caused by review policies | R10 |
| 16 | Incident Explorer | `/incidents` | Explore failures, degraded state and recovery | R16 |
| 17 | Attack Lab | `/lab/security` | Test prompt injection and permission boundaries safely | R13 |
| 18 | Memory Explorer | `/lab/memory` | Inspect session vs episodic memory and provenance | R12 |
| 19 | Retrieval Studio | `/lab/retrieval` | Compare RAG techniques against relevance ground truth | R12 |
| 20 | Tool Contract Lab | `/lab/tools` | See typed tool boundaries and failure behavior | R21 |
| 21 | Agent Studio | `/lab/agents` | Create a bounded workflow composition from allowed roles | R11 |
| 22 | Routing Lab | `/lab/routing` | Find model-cost/quality trade-off by intent | R15 |
| 23 | Evaluation Workbench | `/lab/evals` | Run dataset slices and inspect methodology | R4 |
| 24 | Dataset Workbench | `/lab/datasets` | Understand origin and simulation provenance | R17 |
| 25 | Architecture Explorer | `/architecture` | Explore frontend, domain Python, agent tools, trust boundary | R1 |
| 26 | Learning Studio | `/learn` | Predict behavior, reveal actual outcomes and why | R20 |
| 27 | Proof-of-Work Studio | `/share` | Generate correct and reproducible technical case study | R22 |
| 28 | Runtime Status | `/status` | See live vs static availability and known incident status | R5 |
| 29 | Privacy Controls | `/privacy` | Understand data retention, keys and reset controls | R3 |
| 30 | Research Horizon | `/research` | Browse proposed ideas and negative results | R23 |
| 31 | API & MCP Playground | `/developer` | Test typed sandbox-only developer tools | R21 |
| 32 | Multimodal Document Lab | `/lab/documents` | Analyze synthetic receipts/contracts with source-grounded extraction | R18 |
| 33 | Causal What-if Lab | `/lab/counterfactual` | Compare counterfactual policy/FX changes with assumptions | R19 |
| 34 | Performance & Cost Observatory | `/lab/performance` | Inspect end-to-end costs, traces, resources and p95 | R16 |

## Detailed interaction contracts

### UX-001 - Home / Start
- **Route / phase:** `/` · R1; **target user:** All.
- **User job:** Understand what is live vs replay, start scenario with no account.
- **Primary interactions:** Click starter S01, expand engineering proof, jump to GitHub.
- **Inputs and APIs:** Replay catalog, status manifest.
- **Success metric:** first-case start rate.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-002 - Guided Tour
- **Route / phase:** `/tour` · R1; **target user:** Visitor.
- **User job:** Follow a scripted path through ledger, tool, verification.
- **Primary interactions:** Pause, step, seek, inspect source, replay.
- **Inputs and APIs:** Immutable trace bundle.
- **Success metric:** time-to-understand / 3-min completion.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-003 - Payment Portal
- **Route / phase:** `/pay` · R1; **target user:** Customer/merchant.
- **User job:** Inspect account activity and ask why a transaction differs.
- **Primary interactions:** Switch fictional account, filter, pick a record.
- **Inputs and APIs:** Scoped ledger snapshot + statements.
- **Success metric:** account isolation + record discovery.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-004 - Case Gallery
- **Route / phase:** `/cases` · R1; **target user:** All.
- **User job:** Choose an investigation by difficulty/risk/skill.
- **Primary interactions:** Search intents, filter evidence types, open case.
- **Inputs and APIs:** Scenario manifest; expected results.
- **Success metric:** case launched per exposure.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-005 - Case Detail
- **Route / phase:** `/cases/[id]` · R1; **target user:** Analyst.
- **User job:** Read ground truth, constraints, expected tool chain and outcome.
- **Primary interactions:** Replay, fork case, compare, inspect code.
- **Inputs and APIs:** Scenario manifest + evidence refs.
- **Success metric:** understands result and limitations.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-006 - Scenario Editor
- **Route / phase:** `/lab/scenario/[id]` · R2; **target user:** Engineer/analyst.
- **User job:** Modify simulated data under domain invariants.
- **Primary interactions:** Change FX, refund, policy version, deadlines; preview/apply.
- **Inputs and APIs:** Sandbox events + projector + snapshot hash.
- **Success metric:** valid branch mutations / consistency.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-007 - Branch Diff
- **Route / phase:** `/lab/diff/[branch]` · R2; **target user:** Engineer.
- **User job:** Inspect exact before/after of events, ledger and conclusions.
- **Primary interactions:** Reset, export sanitized patch, compare runs.
- **Inputs and APIs:** Versioned branch and two snapshots.
- **Success metric:** no base mutation + diff accuracy.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-008 - Agent Flight Recorder
- **Route / phase:** `/runs/[id]` · R1; **target user:** Engineer.
- **User job:** Inspect real or recorded timeline of model/tools.
- **Primary interactions:** Search spans, inspect SQL, view raw sanitized payload.
- **Inputs and APIs:** TraceEvent stream + model usage.
- **Success metric:** span completeness / debugging success.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-009 - Agent Graph
- **Route / phase:** `/runs/[id]/graph` · R11; **target user:** Senior engineer.
- **User job:** Understand orchestration, dependencies, critical path.
- **Primary interactions:** Expand nodes, compare plan vs actual, select critical path.
- **Inputs and APIs:** Run DAG + trace refs.
- **Success metric:** graph causality clarity.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-010 - Evidence Graph
- **Route / phase:** `/runs/[id]/evidence` · R8; **target user:** Engineer/reviewer.
- **User job:** Trace each answer claim to primary data and version.
- **Primary interactions:** Select claim, inspect evidence, verify source hash.
- **Inputs and APIs:** Claim/Veredict/Evidence/SourceGraph.
- **Success metric:** citation validity and user comprehension.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-011 - Verifier Studio
- **Route / phase:** `/lab/verifier` · R4; **target user:** Researcher.
- **User job:** See why NLI and arithmetic verifiers disagree.
- **Primary interactions:** Alter non-financial assertion text; compare thresholds.
- **Inputs and APIs:** Verifier result + oracle + fixture.
- **Success metric:** false/unsupported verdict detection.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-012 - Live Model Settings
- **Route / phase:** `/live/settings` · R3; **target user:** Technical visitor.
- **User job:** Choose tested model and optional BYOK with clear budgets.
- **Primary interactions:** Provider/model select, consent, test/forget key.
- **Inputs and APIs:** Provider capability registry and ephemeral key handle.
- **Success metric:** no leakage + tested calls.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-013 - Model Arena
- **Route / phase:** `/lab/models` · R4; **target user:** Researcher.
- **User job:** Compare A/B/C/D/E across paired cases.
- **Primary interactions:** Change cohort, select runs, view plots and failure diffs.
- **Inputs and APIs:** Eval manifests + paired run artifacts.
- **Success metric:** comparison integrity.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-014 - Economics Lab
- **Route / phase:** `/lab/economics` · R9; **target user:** Engineering leader.
- **User job:** Measure cost per correctly resolved case with assumptions.
- **Primary interactions:** Change labor rate, review share, error loss, compare strategies.
- **Inputs and APIs:** Case evaluation + economic assumptions.
- **Success metric:** provenance + no false savings claim.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-015 - Review Queue Simulator
- **Route / phase:** `/lab/review` · R10; **target user:** Ops lead.
- **User job:** Find bottleneck caused by review policies.
- **Primary interactions:** Adjust rate, reviewers, thresholds; run simulation.
- **Inputs and APIs:** Case mix + deterministic queue model.
- **Success metric:** detect overload and false escalations.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-016 - Incident Explorer
- **Route / phase:** `/incidents` · R16; **target user:** SRE/security.
- **User job:** Explore failures, degraded state and recovery.
- **Primary interactions:** Inspect 429, tool failure, timeouts, resume/replay.
- **Inputs and APIs:** Fault manifest + trace + runbook.
- **Success metric:** safe failure classification.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-017 - Attack Lab
- **Route / phase:** `/lab/security` · R13; **target user:** Security engineer.
- **User job:** Test prompt injection and permission boundaries safely.
- **Primary interactions:** Choose canned attack, run dry-run, inspect deny event.
- **Inputs and APIs:** Synthetic attack corpus + policy engine.
- **Success metric:** blocked unauthorized cases.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-018 - Memory Explorer
- **Route / phase:** `/lab/memory` · R12; **target user:** AI engineer.
- **User job:** Inspect session vs episodic memory and provenance.
- **Primary interactions:** Reset, compare, poison synthetic memory, quarantine.
- **Inputs and APIs:** Scoped memory snapshots + refs.
- **Success metric:** correct forget + no cross-account.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-019 - Retrieval Studio
- **Route / phase:** `/lab/retrieval` · R12; **target user:** AI engineer.
- **User job:** Compare RAG techniques against relevance ground truth.
- **Primary interactions:** Dense/BM25/hybrid rerank; show matched policy chunks.
- **Inputs and APIs:** Policy docs + relevance labels.
- **Success metric:** Recall@k and answer uplift.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-020 - Tool Contract Lab
- **Route / phase:** `/lab/tools` · R21; **target user:** Platform engineer.
- **User job:** See typed tool boundaries and failure behavior.
- **Primary interactions:** Inspect schema, run safe fixtures, invalid inputs.
- **Inputs and APIs:** ToolSpec catalog + examples.
- **Success metric:** guarded malformed calls.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-021 - Agent Studio
- **Route / phase:** `/lab/agents` · R11; **target user:** Staff engineer.
- **User job:** Create a bounded workflow composition from allowed roles.
- **Primary interactions:** Choose supervisor/specialists, budgets, topology; execute sandbox.
- **Inputs and APIs:** Versioned graphs + capability ACL.
- **Success metric:** bounded calls and reproducibility.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-022 - Routing Lab
- **Route / phase:** `/lab/routing` · R15; **target user:** AI platform engineer.
- **User job:** Find model-cost/quality trade-off by intent.
- **Primary interactions:** Change routing rules, compare repeated cases.
- **Inputs and APIs:** Model profiles + eval matrices.
- **Success metric:** cost per correct vs baseline.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-023 - Evaluation Workbench
- **Route / phase:** `/lab/evals` · R4; **target user:** Researcher.
- **User job:** Run dataset slices and inspect methodology.
- **Primary interactions:** Filters, holdout, compare CI, download metrics.
- **Inputs and APIs:** Dataset/version/run manifests.
- **Success metric:** no test leakage + reproducibility.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-024 - Dataset Workbench
- **Route / phase:** `/lab/datasets` · R17; **target user:** Data engineer.
- **User job:** Understand origin and simulation provenance.
- **Primary interactions:** Explore seed, scenario data, generate synthetic fork.
- **Inputs and APIs:** Dataset lineage + attributions.
- **Success metric:** license/source traceability.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-025 - Architecture Explorer
- **Route / phase:** `/architecture` · R1; **target user:** Hiring manager/engineer.
- **User job:** Explore frontend, domain Python, agent tools, trust boundary.
- **Primary interactions:** Click system nodes for source path + ADR.
- **Inputs and APIs:** Architecture manifests + code links.
- **Success metric:** explain architecture without author.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-026 - Learning Studio
- **Route / phase:** `/learn` · R20; **target user:** Engineer learner.
- **User job:** Predict behavior, reveal actual outcomes and why.
- **Primary interactions:** Choose hypothesis, replay, reflect, short quizzes.
- **Inputs and APIs:** Case and run proof + evaluation criteria.
- **Success metric:** learning completion.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-027 - Proof-of-Work Studio
- **Route / phase:** `/share` · R22; **target user:** Portfolio reviewer.
- **User job:** Generate correct and reproducible technical case study.
- **Primary interactions:** Select run, redact, export card/report with sources.
- **Inputs and APIs:** Experiment manifests + git SHA.
- **Success metric:** clickthrough and integrity.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-028 - Runtime Status
- **Route / phase:** `/status` · R5; **target user:** All.
- **User job:** See live vs static availability and known incident status.
- **Primary interactions:** Inspect version, provider availability, mode.
- **Inputs and APIs:** Sanitized system status + runbooks.
- **Success metric:** honest degradation.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-029 - Privacy Controls
- **Route / phase:** `/privacy` · R3; **target user:** All.
- **User job:** Understand data retention, keys and reset controls.
- **Primary interactions:** Delete session, revoke key, disable analytics.
- **Inputs and APIs:** Session manifest + deletion confirmation.
- **Success metric:** secret and branch lifecycle.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-030 - Research Horizon
- **Route / phase:** `/research` · R23; **target user:** Researcher.
- **User job:** Browse proposed ideas and negative results.
- **Primary interactions:** Sort by evidence maturity, inspect open issues.
- **Inputs and APIs:** Capability atlas + evidence maturity.
- **Success metric:** clarity of planned vs shipped.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-031 - API & MCP Playground
- **Route / phase:** `/developer` · R21; **target user:** Developer.
- **User job:** Test typed sandbox-only developer tools.
- **Primary interactions:** Inspect REST/SSE schemas, run safe requests.
- **Inputs and APIs:** OpenAPI + tool spec.
- **Success metric:** schema conformance.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-032 - Multimodal Document Lab
- **Route / phase:** `/lab/documents` · R18; **target user:** ML engineer.
- **User job:** Analyze synthetic receipts/contracts with source-grounded extraction.
- **Primary interactions:** Upload allowed sample, inspect OCR fields and errors.
- **Inputs and APIs:** Synthetic PDF/images, extractor versions.
- **Success metric:** extractor field precision.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-033 - Causal What-if Lab
- **Route / phase:** `/lab/counterfactual` · R19; **target user:** Researcher.
- **User job:** Compare counterfactual policy/FX changes with assumptions.
- **Primary interactions:** Intervene on simulated causes, see affected derived facts.
- **Inputs and APIs:** Event rules + causal model documentation.
- **Success metric:** invariants and causal caveats.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.

### UX-034 - Performance & Cost Observatory
- **Route / phase:** `/lab/performance` · R16; **target user:** Platform engineer.
- **User job:** Inspect end-to-end costs, traces, resources and p95.
- **Primary interactions:** Compare single vs parallel and caching effects.
- **Inputs and APIs:** OpenTelemetry metrics + cost ledger.
- **Success metric:** comparable p95 and costs.
- **UI states:** empty with suggested next action; ready; waiting/replaying; partial result; invalid input; denied access; upstream failure; stale snapshot; interrupted/cancelled; keyboard and screen-reader alternative.
- **Evidence/acceptance:** actions are captured by accessible E2E; link to source/eval/assumptions visible; replay/simulated/live modes unambiguous; no untrusted data crosses session boundaries; errors must preserve user context and offer safe recovery.
