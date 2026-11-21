# LedgerLens v3 - Open-Ended Applied AI & Strategic Intelligence Blueprint

> **Date: 2026-11-11. Design-only expansion; no production implementation or GitHub modification in this deliverable.** Baseline: [`erikunha/ledgerlens`](https://github.com/erikunha/ledgerlens), static code inspection, latest observed commit `d9f5b06cc71dc6a3ad1f57a579e734ce11f15f73`.

This pack **preserves all v2 portfolio master specs, contracts, ADRs and architecture documents**, and adds an extensive, open-ended strategy, AI and implementation roadmap based on Follow the Money, Follow the Bottleneck, Incentives, Value Capture, Proof of Work, Distribution, Optionality, Asymmetric Bets, Compounding and 10+ other mental models.

## What was added in v3

- **234 candidate capabilities in 15 domains:** [`ai/CAPABILITY-ATLAS.md`](ai/CAPABILITY-ATLAS.md) and structured [`ai/capability-atlas.json`](ai/capability-atlas.json). These are not shipped features.
- **24 release stages (R0 - R23+)**, including long-term research: [`roadmap/RELEASE-TRAIN-2027-2030.md`](roadmap/RELEASE-TRAIN-2027-2030.md).
- **161 new proposed engineering tasks:** [`roadmap/IMPLEMENTATION-BACKLOG-V3.md`](roadmap/IMPLEMENTATION-BACKLOG-V3.md).
- **34 screen/interaction specs:** [`product/01-SCREEN-REGISTRY.md`](product/01-SCREEN-REGISTRY.md).
- **19 high-detail engineering specs:** [`advanced-specs/`](advanced-specs/) covering economics, human review, multiagent, data isolation, security, model routing, evidence, durability, evals and proof exports.
- **7 proposed v3 JSON Schemas + 7 matching examples:** [`contracts/schemas/`](contracts/schemas/) and [`contracts/examples/`](contracts/examples/). All example IDs and hashes are **illustrative**, not from live runs.
- **6 strategic documents:** [`strategy/`](strategy/).
- **9 agentic technical/research documents:** [`ai/`](ai/).
- **Product/UI specs:** [`product/`](product/).
- **Primary-source trend research and competitive patterns:** [`research/`](research/).

## Start reading

1. [Strategy translated to concrete implementation](strategy/00-STRATEGIC-INTELLIGENCE-STACK.md)
2. [Follow the money in payments operations](strategy/01-MARKET-AND-VALUE-FLOW.md)
3. [Economic cost/quality/review model](strategy/05-ECONOMIC-MODELS.md)
4. [Full screen registry](product/01-SCREEN-REGISTRY.md)
5. [Multiagent design](ai/01-MULTIAGENT-ORCHESTRATION.md)
6. [Open feature atlas](ai/CAPABILITY-ATLAS.md)
7. [Release train and dependencies](roadmap/RELEASE-TRAIN-2027-2030.md)
8. [Implementation backlog](roadmap/IMPLEMENTATION-BACKLOG-V3.md)
9. [Research references](research/01-WHAT-CHANGED-IN-2026.md)
10. [Existing v2 master architecture](docs/05-SYSTEM-ARCHITECTURE.md)

### Honesty and scope

- LedgerLens remains a **public portfolio and research demo**, not a fintech/SaaS or actual payment/decision tool.
- **Unlimited vision does not require simultaneous implementation.** No planned feature is cut from the atlas solely due to complexity; public release gates still enforce quality, safety and real evidence.
- Historic A/B/C evaluations are repo-reported, not re-run here. All hypothetical economics and provider examples are explicitly labeled.
- Existing v2 documentation, 9 ADRs and baseline contracts are retained unchanged; v3 additions are separate and versioned.

---

## Preserved v2 master specification

# LedgerLens - Applied AI Engineering Portfolio Master Specification

**Status:** proposed architecture and implementation specifications; **not an implemented product**.  
**Date:** 2026-11-11 · **Baseline:** [`erikunha/ledgerlens`](https://github.com/erikunha/ledgerlens), `main`, commit `d9f5b06cc71dc6a3ad1f57a579e734ce11f15f73` observed in the audit.  
**Purpose:** convert an existing, technically substantive payments-investigation agent into a public, interactive, honest, high-signal engineering demonstration for senior/staff-level and applied AI roles. **Not a fintech or commercial SaaS.**

## Product decision

Ship **LedgerLens Lab** as three progressively deeper experiences sharing the *same* existing Python investigation engine:

1. **Guided Replay** - free, fast, no credentials; recorded real runs and exact reproducible traces, visibly labeled replay.
2. **Scenario Sandbox** - isolated simulated financial events, editable through constrained business actions; deterministic recalculation and comparison; optional model re-run.
3. **Live Agent** - BYOK, user-selected supported model, strict execution budgets, real tool use, claim verification, observable traces; no real money and no actual payments.

A professional Next.js front end presents an analyst's payment workspace, a scenario editor, an agent trace inspector, an evidence graph, a comparison/evaluation lab, and an architecture tour. Prefer **clarity, provenance, and measured engineering** over features added for show.

## Read in order

| Document | Main content |
|---|---|
| [00 - Executive decision, PT-BR](docs/00-RESUMO-EXECUTIVO-PT.md) | Direction, prioritization, career/portfolio logic |
| [01 - Repo audit](docs/01-REPOSITORY-AUDIT.md) | What exists, exact files, debt, preserve/change |
| [02 - PRD](docs/02-PRD-AND-DEFINITION-OF-DONE.md) | Personas, success metrics, constraints, detailed stories |
| [03 - UX and screens](docs/03-EXPERIENCE-AND-SCREENS.md) | Information architecture, screens, navigation, states |
| [04 - Scenario sandbox](docs/04-SCENARIO-AND-SIMULATION-ENGINE.md) | Event branching, editable data, controlled mutations |
| [05 - System architecture](docs/05-SYSTEM-ARCHITECTURE.md) | Runtime, API, frontend, hosting, component boundaries |
| [06 - Agent runtime](docs/06-AGENT-RUNTIME-AND-TOOLING.md) | Agents, tools, graph, verifier, constraints |
| [07 - BYOK](docs/07-BYOK-MODEL-REGISTRY.md) | Provider selection, ephemeral secrets, model capability checks |
| [08 - Evidence/observability](docs/08-EVIDENCE-TRACING-AND-PROVENANCE.md) | Live traces, replay bundles, explainable decisions |
| [09 - Evals](docs/09-EVALUATION-AND-EXPERIMENTS.md) | Measured quality, model comparison, guardrails |
| [10 - Security](docs/10-SECURITY-AND-THREAT-MODEL.md) | Threat model, isolation, SQL restrictions, safe deployment |
| [11 - APIs](docs/11-API-AND-INTERFACE-CONTRACTS.md) | REST, SSE, request/response contracts and errors |
| [12 - Design system](docs/12-FRONTEND-ENGINEERING-AND-DESIGN-SYSTEM.md) | Component architecture, a11y, performance, implementation |
| [13 - Release/operations](docs/13-CI-CD-DEPLOYMENT-AND-RUNBOOKS.md) | Reproducibility, CI gates, incident playbooks |
| [14 - LinkedIn presentation](docs/14-PORTFOLIO-PRESENTATION.md) | 90-second narrative, demo routes, recruiter UX |
| [15 - Risks](docs/15-RISKS-AND-OPEN-DECISIONS.md) | Reversible decisions, residual risks, explicit non-goals |
| [Release train](roadmap/RELEASE-TRAIN.md) | Milestones, dependencies, quality gates and sequencing |
| [Implementation handoff](docs/17-IMPLEMENTATION-HANDOFF.md) | First PRs, engineering-agent rules and technical acceptance |
| [Implementation backlog](roadmap/IMPLEMENTATION-BACKLOG.md) | ID-based tasks and acceptance criteria |
| [High-detail implementation specs](specs/) | Runnable contracts/test scenarios for P0-P1 critical components |
| [ADRs](adrs/README.md) | Technical decisions with alternatives |
| [Contracts](contracts/) | OpenAPI, JSON Schemas, examples, policies |
| [Evals](eval/) | Seed evaluation protocol and test matrix |
| [Wireframes](design/SCREEN-WIREFRAMES.md) | Layout descriptions and usability rules |
| [Sources](docs/16-SOURCES.md) | Public docs used for implementation choices |
| [Validation](verification/VALIDATION.md) | What was actually machine-checked; what remains unverified |

## Non-negotiable invariants

1. **No real payment mutations.** Every editable action is a sandbox event and cannot reach live financial services.
2. **Public baseline is immutable.** Every visitor receives an isolated branch; they can reset it deterministically.
3. **No misleading live demo.** Replay, deterministic simulation, and provider-backed live execution are distinctly labeled.
4. **Claims are traceable.** A claim's evidence, verifier result, derivation, and limitations can be inspected.
5. **No secrets in storage/traces.** BYOK is opt-in, ephemeral, consented, metered, and revoked on exit/expiry.
6. **The existing Python core remains authoritative.** Next.js does not reimplement business rules.
7. **Full fidelity requires proof.** No performance, eval, security, or market claim is marked complete without execution evidence.
8. **Multiaagent only after a measured win.** The main story is trustworthy applied AI, not an artificial swarm.

## Definition of done (public portfolio release)

A first-time visitor can open a URL, run a guided case without a key, change a permitted synthetic transaction attribute, see both the changed ledger and grounded consequences, inspect a trace and verifier, compare recorded architectures and metrics, understand offline vs live status, use accessible keyboard navigation, and reach the source repository - all without logging in or paying. Real model BYOK is additional, not required for evaluating the project.

## Scope of this deliverable

**Design-only:** specs, reference contracts, test plans, examples, ADRs and execution backlog. No code in the original repository was changed and no live deployment was performed. The contracts are proposed v1 interfaces and are *not* a substitute for implementation and runtime testing.
