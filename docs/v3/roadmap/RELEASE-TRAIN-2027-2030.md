# LedgerLens - Open Release Train, 2027-2030+

**Version:** v3 vision extension, 2026-11-11. No artificial feature ceiling. Original R0 - R7 remain documented under `roadmap/RELEASE-TRAIN.md` and are not replaced. Dates are indicative, not commitments. Every release can be subdivided into independently reviewable slices.

## Dependency overview

| Release | Objective | Required predecessor(s) | Main strategic lens |
|---|---|---|---|
| **R0** | Baseline integrity | Current repo main | Quality/Proof |
| **R1** | Public Guided Experience | R0 | Distribution/Proof |
| **R2** | Editable Scenario Lab | R0,R1 | Bottlenecks/Reversibility |
| **R3** | Live BYOK and Provider Registry | R0,R2 | Optionality/Security |
| **R4** | Evaluation and Model Arena | R0,R1,R3 | Proof/Probabilistic |
| **R5** | Reliability and Portfolio Delivery | R1-R4 | Distribution |
| **R6** | Bounded Specialist Experiment | R4 | Asymmetric Bets |
| **R7** | Failure and Robustness Studio | R2,R4 | Inversion |
| **R8** | Evidence and Temporal Knowledge | R2,R4 | Compounding |
| **R9** | Operations Economics Lab | R4,R8 | Follow the Money |
| **R10** | Human Attention & Review OS | R8,R9 | Follow the Bottleneck |
| **R11** | Multiagent Orchestration Studio | R6,R8,R10 | Incentives/Orchestration |
| **R12** | Retrieval and Memory Research | R8,R11 | Compounding |
| **R13** | Agent Security and Red Team Lab | R7,R11,R12 | Inversion |
| **R14** | Protocols and External Specialists | R11,R13 | Distribution/Network |
| **R15** | Inference Routing & FinOps | R3,R4,R9 | Value Capture |
| **R16** | Durable Agent Operations | R11,R15 | Theory of Constraints |
| **R17** | Simulation Digital Twin | R2,R9,R10 | Second-Order |
| **R18** | Multimodal Document Intelligence | R8,R13,R17 | Comparative Advantage |
| **R19** | Causal & Counterfactual Studio | R9,R17,R18 | Second-Order |
| **R20** | Continuous Evals & Learning Science | R4,R12,R13 | Compounding |
| **R21** | Developer Platform & Tool SDK | R13,R16,R20 | Proof of Work |
| **R22** | Distribution & Career Signal Engine | R1,R4,R5,R9,R21 | Distribution/Bargaining |
| **R23+** | Open Research Horizons | Dependent on each research track | Optionality/Asymmetric Bets |

## Detailed release contracts

### R0 - Baseline integrity
- **Outcome:** Read existing Python source, freeze tests and hashes.
- **Depends on:** Current repo main.
- **Public proof:** Reproducible offline gate and redacted actual replay.
- **Guardrail:** No frontend rewrite until baseline is anchored.
- **Exit gate:** check offline gate and exact source SHA.
- **Strategic thesis:** Quality/Proof.
- **Acceptance principle:** no promotion on documentation alone; provide code links, repeatable tests, run bundle or benchmark, error cases and measured results.

### R1 - Public Guided Experience
- **Outcome:** Next.js keyless home, five real recorded case walkthroughs.
- **Depends on:** R0.
- **Public proof:** Visitor understands verified case in three minutes.
- **Guardrail:** No falsely animated live model.
- **Exit gate:** trace references source IDs and accessibility E2E passes.
- **Strategic thesis:** Distribution/Proof.
- **Acceptance principle:** no promotion on documentation alone; provide code links, repeatable tests, run bundle or benchmark, error cases and measured results.

### R2 - Editable Scenario Lab
- **Outcome:** Isolated event-sourced branches, mutation preview, deterministic projector.
- **Depends on:** R0,R1.
- **Public proof:** Visitor changes one scenario and sees evidence-consistent diff.
- **Guardrail:** No direct writes to base data.
- **Exit gate:** isolation/reset and money invariants pass.
- **Strategic thesis:** Bottlenecks/Reversibility.
- **Acceptance principle:** no promotion on documentation alone; provide code links, repeatable tests, run bundle or benchmark, error cases and measured results.

### R3 - Live BYOK and Provider Registry
- **Outcome:** Ephemeral provider credentials, tested tool models and bounded runs.
- **Depends on:** R0,R2.
- **Public proof:** Visitor safely runs real agent and inspects costs.
- **Guardrail:** No keys in persistence/traces.
- **Exit gate:** secret redaction and provider E2E passes.
- **Strategic thesis:** Optionality/Security.
- **Acceptance principle:** no promotion on documentation alone; provide code links, repeatable tests, run bundle or benchmark, error cases and measured results.

### R4 - Evaluation and Model Arena
- **Outcome:** Paired A/B/C evals, verifier lab, real error cohorts and costs.
- **Depends on:** R0,R1,R3.
- **Public proof:** Public benchmark exposes failures and limitations.
- **Guardrail:** No unverified benchmark superiority.
- **Exit gate:** run manifest and evaluation repeatability.
- **Strategic thesis:** Proof/Probabilistic.
- **Acceptance principle:** no promotion on documentation alone; provide code links, repeatable tests, run bundle or benchmark, error cases and measured results.

### R5 - Reliability and Portfolio Delivery
- **Outcome:** Static fallback, accessibility, performance, documentation, video.
- **Depends on:** R1-R4.
- **Public proof:** Public demo reliably serves job/interview audience.
- **Guardrail:** No always-on spend without limits.
- **Exit gate:** deployment/rollback E2E and incident simulation.
- **Strategic thesis:** Distribution.
- **Acceptance principle:** no promotion on documentation alone; provide code links, repeatable tests, run bundle or benchmark, error cases and measured results.

### R6 - Bounded Specialist Experiment
- **Outcome:** Add optional multiagent D topology with deliberate budget.
- **Depends on:** R4.
- **Public proof:** Demonstrate actual D vs C comparison.
- **Guardrail:** Not a mandatory default.
- **Exit gate:** cost/risk/quality comparisons prove or disprove benefit.
- **Strategic thesis:** Asymmetric Bets.
- **Acceptance principle:** no promotion on documentation alone; provide code links, repeatable tests, run bundle or benchmark, error cases and measured results.

### R7 - Failure and Robustness Studio
- **Outcome:** Tool errors, injected data, provider outages and self-test library.
- **Depends on:** R2,R4.
- **Public proof:** Visitor safely reproduces failure and defensive response.
- **Guardrail:** No unrestricted attack execution.
- **Exit gate:** attack tests and policy isolation pass.
- **Strategic thesis:** Inversion.
- **Acceptance principle:** no promotion on documentation alone; provide code links, repeatable tests, run bundle or benchmark, error cases and measured results.

### R8 - Evidence and Temporal Knowledge
- **Outcome:** Evidence graph, strict citations and policy versions.
- **Depends on:** R2,R4.
- **Public proof:** Every claim backtracks to exact versioned origin.
- **Guardrail:** Do not infer causal truth from link graph.
- **Exit gate:** citation and time-travel consistency.
- **Strategic thesis:** Compounding.
- **Acceptance principle:** no promotion on documentation alone; provide code links, repeatable tests, run bundle or benchmark, error cases and measured results.

### R9 - Operations Economics Lab
- **Outcome:** Cost-per-correct, review cost and risk-weighted utility simulations.
- **Depends on:** R4,R8.
- **Public proof:** Compare policies under explicit assumptions.
- **Guardrail:** No alleged real savings.
- **Exit gate:** unit/invariant tests and provenance tags.
- **Strategic thesis:** Follow the Money.
- **Acceptance principle:** no promotion on documentation alone; provide code links, repeatable tests, run bundle or benchmark, error cases and measured results.

### R10 - Human Attention & Review OS
- **Outcome:** Review state machine, abstention, queue simulator and workload UX.
- **Depends on:** R8,R9.
- **Public proof:** Review burden and decision quality compared.
- **Guardrail:** No live approvals or real customer operations.
- **Exit gate:** case queue and human decision audit.
- **Strategic thesis:** Follow the Bottleneck.
- **Acceptance principle:** no promotion on documentation alone; provide code links, repeatable tests, run bundle or benchmark, error cases and measured results.

### R11 - Multiagent Orchestration Studio
- **Outcome:** Supervisor, parallel graph, handoffs, critic, checkpoint visual editor.
- **Depends on:** R6,R8,R10.
- **Public proof:** Visitor builds a bounded graph and sees measured effects.
- **Guardrail:** No unbounded agent swarm.
- **Exit gate:** budget, scope and restart tests.
- **Strategic thesis:** Incentives/Orchestration.
- **Acceptance principle:** no promotion on documentation alone; provide code links, repeatable tests, run bundle or benchmark, error cases and measured results.

### R12 - Retrieval and Memory Research
- **Outcome:** Dense/BM25/hybrid, rerankers, temporal memory and poisoning lab.
- **Depends on:** R8,R11.
- **Public proof:** Visitor compares retrieval correctness on same dataset.
- **Guardrail:** No PII or unsupervised memory self-training.
- **Exit gate:** relevance and cross-account evals.
- **Strategic thesis:** Compounding.
- **Acceptance principle:** no promotion on documentation alone; provide code links, repeatable tests, run bundle or benchmark, error cases and measured results.

### R13 - Agent Security and Red Team Lab
- **Outcome:** OWASP-aligned canned attacks, MCP safety and identity checks.
- **Depends on:** R7,R11,R12.
- **Public proof:** Demonstrate bounded tool and memory trust.
- **Guardrail:** No real external exploitation.
- **Exit gate:** unsafe actions denied, failed attacks documented.
- **Strategic thesis:** Inversion.
- **Acceptance principle:** no promotion on documentation alone; provide code links, repeatable tests, run bundle or benchmark, error cases and measured results.

### R14 - Protocols and External Specialists
- **Outcome:** MCP resources/tools, A2A simulated partner, signed evidence contracts.
- **Depends on:** R11,R13.
- **Public proof:** Interoperable scoped external-agent mock.
- **Guardrail:** No secrets/prod financial actions exposed.
- **Exit gate:** conformance and identity tests.
- **Strategic thesis:** Distribution/Network.
- **Acceptance principle:** no promotion on documentation alone; provide code links, repeatable tests, run bundle or benchmark, error cases and measured results.

### R15 - Inference Routing & FinOps
- **Outcome:** Multi-provider adapters, routing decisions, quality/cost frontier.
- **Depends on:** R3,R4,R9.
- **Public proof:** Find model strategy minimizing cost per correct at target quality.
- **Guardrail:** No invented prices/models.
- **Exit gate:** paired vendor conformance and pricing timestamps.
- **Strategic thesis:** Value Capture.
- **Acceptance principle:** no promotion on documentation alone; provide code links, repeatable tests, run bundle or benchmark, error cases and measured results.

### R16 - Durable Agent Operations
- **Outcome:** Long-running workloads, health, tracing, cancellation, recovery, runbooks.
- **Depends on:** R11,R15.
- **Public proof:** Interrupt and resume a complex run reliably.
- **Guardrail:** No task duplication or state corruption.
- **Exit gate:** chaos/recovery tests, p95 and SLO results.
- **Strategic thesis:** Theory of Constraints.
- **Acceptance principle:** no promotion on documentation alone; provide code links, repeatable tests, run bundle or benchmark, error cases and measured results.

### R17 - Simulation Digital Twin
- **Outcome:** Scale simulated payment operations, faults, workload, multi-actor incentives.
- **Depends on:** R2,R9,R10.
- **Public proof:** Explore realistic pressure scenarios with declared assumptions.
- **Guardrail:** Never call simulation a real bank.
- **Exit gate:** seeded oracle and load tests.
- **Strategic thesis:** Second-Order.
- **Acceptance principle:** no promotion on documentation alone; provide code links, repeatable tests, run bundle or benchmark, error cases and measured results.

### R18 - Multimodal Document Intelligence
- **Outcome:** Synthetic statements, PDFs, images, voice, OCR source-grounded extraction.
- **Depends on:** R8,R13,R17.
- **Public proof:** Inspect extraction/grounding failures via screenshots.
- **Guardrail:** No user sensitive doc retention.
- **Exit gate:** extraction benchmark + file security tests.
- **Strategic thesis:** Comparative Advantage.
- **Acceptance principle:** no promotion on documentation alone; provide code links, repeatable tests, run bundle or benchmark, error cases and measured results.

### R19 - Causal & Counterfactual Studio
- **Outcome:** Structural assumptions, interventions, policy/FX alternate worlds.
- **Depends on:** R9,R17,R18.
- **Public proof:** Separate correlation from counterfactual mechanisms.
- **Guardrail:** No causal claim without identification.
- **Exit gate:** counterfactual oracle and sensitivity checks.
- **Strategic thesis:** Second-Order.
- **Acceptance principle:** no promotion on documentation alone; provide code links, repeatable tests, run bundle or benchmark, error cases and measured results.

### R20 - Continuous Evals & Learning Science
- **Outcome:** Review feedback, active learning, calibration and small models.
- **Depends on:** R4,R12,R13.
- **Public proof:** Failure-to-regression compounding loop.
- **Guardrail:** No automatically trusted labels.
- **Exit gate:** holdout gains + leakage/rollback tests.
- **Strategic thesis:** Compounding.
- **Acceptance principle:** no promotion on documentation alone; provide code links, repeatable tests, run bundle or benchmark, error cases and measured results.

### R21 - Developer Platform & Tool SDK
- **Outcome:** Python CLI, typed TS clients, API/MCP and reproducible case packs.
- **Depends on:** R13,R16,R20.
- **Public proof:** Any developer can rerun and inspect via headless tools.
- **Guardrail:** No public mutation of finance systems.
- **Exit gate:** SDK conformance/CLI offline gate.
- **Strategic thesis:** Proof of Work.
- **Acceptance principle:** no promotion on documentation alone; provide code links, repeatable tests, run bundle or benchmark, error cases and measured results.

### R22 - Distribution & Career Signal Engine
- **Outcome:** Public case-study exports, demos, essays, sources, contributor UX.
- **Depends on:** R1,R4,R5,R9,R21.
- **Public proof:** Independent engineers can verify and share work.
- **Guardrail:** No vanity claims or fake endorsements.
- **Exit gate:** proof-source links, analytics privacy, feedback.
- **Strategic thesis:** Distribution/Bargaining.
- **Acceptance principle:** no promotion on documentation alone; provide code links, repeatable tests, run bundle or benchmark, error cases and measured results.

### R23+ - Open Research Horizons
- **Outcome:** Neuro-symbolic, causal, local models, formal methods, federation and new agent paradigms.
- **Depends on:** Dependent on each research track.
- **Public proof:** New research streams added continuously with gates.
- **Guardrail:** No promise of exhaustive future tech coverage.
- **Exit gate:** per-topic reproducible result and safety review.
- **Strategic thesis:** Optionality/Asymmetric Bets.
- **Acceptance principle:** no promotion on documentation alone; provide code links, repeatable tests, run bundle or benchmark, error cases and measured results.

## Scope policy

Nothing is deleted merely because it is technically difficult. `R23+` is a living discovery space. Candidate capabilities can appear in multiple experiments and move across releases after recording an ADR. The implementable backlog selects an order with dependency and risk control, but is **not** a boundary around the vision. Research output may be a rigorous negative result and still count as completion of an experiment.

## Three separate clocks

1. **Portfolio publishing clock:** ship the minimal honest demo quickly and keep extending.
2. **Engineering learning clock:** work on hard system-level proofs and benchmark quality.
3. **Research horizon clock:** explore ambitious ideas without letting them block a visitor’s first case.

No roadmap item is a prediction of career income, model vendor development or market adoption.
