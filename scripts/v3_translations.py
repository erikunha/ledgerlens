"""The English translations of the two package documents that exist only in Brazilian Portuguese.

They live here, in a module of their own, so that the import script stays readable and the translation is versioned
with the code that applies it. The content is a translation, not a rewrite: no claim was added or dropped.
"""

from __future__ import annotations

READ_ME_FIRST = """# LedgerLens v3 - Read me first

**Status:** product, engineering and research documentation. The original code on GitHub was not changed in this
delivery. Content does not equal implemented functionality.

## Central decision

The LedgerLens will be a **public laboratory of applied AI engineering**, using the domain of payment operations as a
scenario rich in constraints. It is not a fintech, a banking product or a SaaS. The goal is to let visitors experience
AI, systems engineering, quality, security and cost concepts in a verifiable way.

Now we connect the strategic lenses discussed (Follow the Money, Follow the Bottleneck, Incentives, Value Capture, Proof
of Work, Distribution, Optionality, Compounding, Theory of Constraints, Second-Order Thinking and others) to the
engineering experience itself.

### Three outcomes to optimise

1. **Engineering:** real depth in the systems (frontend, Python, agents, tools, data, security, tests, evals,
   multimodal, models, orchestration).
2. **Demonstration:** one person can experiment without a key and without a login and understand the results with
   evidence; whoever wants depth can run BYOK in a controlled way.
3. **Career:** create verifiable material to show to engineers, interviewers, managers and founders, without promising
   automatic financial return.

## What the package preserves

The previous v2 master blueprint, the architecture documentation, the existing API contracts, nine ADRs, the roadmap
and the original backlog were copied without changing the Python modules on GitHub. The v3 extension uses new ids so as
not to overwrite earlier tasks.

## What v3 adds

- 234 **candidate** capabilities, spread over 15 areas; each one has a form of proof.
- 24 release stages, from R0 to R23+, without limiting the research horizon.
- 161 new candidate tasks, with priorities based on dependencies and checks, not on an artificial ceiling.
- 34 screens and experience surfaces with routes and UX states.
- 19 technical specs of relevant components, including sandbox, evals, multiagents, cost control, human review,
  security, models and research.
- Seven new JSON Schemas and seven consistent examples for the v3 contracts.
- Documents about economics, incentives, bottlenecks, portfolio, studies, evaluation, security, agent network and
  trends.

**Attention:** these are not 234 ready features and the 161 tasks are not all implementation-ready. The critical
contracts are detailed; the rest is an open atlas and backlog that can be refined progressively before each pull
request.

## What already really exists in the original repository

LangChain/LangGraph, SQL tools with a guard, FAISS policies, FX, Decimal, memory, NLI and deterministic checks, trace
logs, payment simulation by events, Streamlit, pytest/Ruff tests and an experiment report with 30 cases. The numeric
results in the repository were not re-run in this delivery.

## Minimum path to show value

1. Preserve the baseline and the S01-S12 cases.
2. Create a true, auditable and key-free replay.
3. Show the payment row, the tool tree, the evidence and the verified claims.
4. Add a per-visitor sandbox with fictional data changes and deterministic result.
5. Show how much quality, cost and review need change in comparable experiments.
6. Publish a case study with links to commits, tests and reproduction.

In parallel, keep the vision for R8-R23+: temporal evidence, economics and review, multiagents, memory, tools, security,
external agents, routing, durable execution, digital twin, multimodal, causality and ML.

## Recommended reading order

`README.md` -> `strategy/00-STRATEGIC-INTELLIGENCE-STACK.md` -> `product/01-SCREEN-REGISTRY.md` ->
`ai/CAPABILITY-ATLAS.md` -> `roadmap/RELEASE-TRAIN-2027-2030.md` -> `advanced-specs/` -> `contracts/`.

## Red lines

Never fake a live execution, retrieved values, benchmark results or certificates. Never make real money movement
available. Never leak BYOK. Never assume that multiple agents are better without a comparative test. Never simplify a
financial problem to the point of hiding its difficulty. The value is demonstrable depth and the ability to judge
trade-offs.
"""

EXECUTIVE_SUMMARY = """# LedgerLens 2027+ - Executive summary and decision

## Goal

Turn the LedgerLens into a public demonstration that lets a recruiter or a technical lead understand four
competences in 90 seconds: (1) architecture of applied AI systems, (2) agentic execution and tool use under control,
(3) empirical evaluation and data integrity, and (4) production full-stack engineering. **Do not build a fintech, a
payments product or a paid SaaS.**

## The portfolio hypothesis

A more demonstrable project, with reproducible comparison between agents, scenarios the visitor can change and an
excellent visual experience, can signal more professional capacity than adding invisible complexity to the
implementation. The success metric is not MRR: it is a technical evaluator understanding, testing and believing in the
engineering decisions.

## What already deserves to be preserved

The project implements a triage pipeline, an agent with tools, read-only SQL guarded by AST, simulated data in
reproducible events, memory, claim verification, NLI, rule-based escalation, tracing and A/B/C evaluations. The CLI and
the offline mode exist. The current Streamlit app implements a payment portal and live traces. None of this should be
replaced by a fake demo.

## Limitations verified while reading the code

- The offline mode uses `ScriptedChatModel` and accepts a defined subset of questions; it is not a free model.
- `app/streamlit_app.py` holds UI, session management, Thread/Queue and rendering in about 660 lines. That makes complex
  screens hard to evolve.
- `@st.cache_resource` keeps scoped sources and ledgers in a process-wide cache; a mutable public demo will need new
  isolation, and must never write into those resources.
- Model selection is done by environment variable today; the front end has no BYOK UI and no model catalogue.
- The main online evaluation set is small (30 cases with 3 repetitions). The report itself says the trajectory of
  variant C did not reach the 0.80 target (unordered equivalent: 0.73).
- The calibration in `verify/thresholds.json` records 0.786 combined accuracy, with 0.625 on the live set and 1.00 on
  the verification set used for the tuning. Those results measure different subsets and protocols and have to be
  presented honestly, without claiming the verifier is perfect.
- The current UI draws the trace and the answer in the help panel. A technical audience does not see a complete
  laboratory of scenarios, models and evals.

## Recommended product

Three modes: **Replay**, **Sandbox** and **Live (BYOK)**. Replay is free, immediate and deterministic; Sandbox allows
`fork` of a snapshot with valid mutations and recomputation; Live runs the Python agent with a chosen real model and
explicit limits. A Next.js UI shows Ledger, Scenario Lab, Agent Inspector, Evidence Graph, Eval Lab, Model Arena and
Architecture Tour. The authenticity of the results is labelled in the interface.

## Stack decision

Keep Python/Pydantic/LangChain/LangGraph/SQLite/EventStore/FAISS/Decimal as the core; add FastAPI for controlled public
exposure and SSE for traces; Next.js with TypeScript and TanStack Query/Table for the experience. Do not introduce
Postgres/Kubernetes/Temporal/Redis by default. Initially, deploy a small backend with a single process, session
expiry, resource limits and the possibility of serving a static replay when the backend is unavailable.

## Fundamental trade-off

The biggest career delivery is letting someone see **the difference between a convincing answer and a proven answer**.
So invest first in the Evidence Inspector and in the editable scenario with an execution A/B. Multiagents only come in
as an experimental comparison, if there is an objective gain.

## Delivery trail

R0: baseline and executable audit -> R1: public visual replay -> R2: isolated scenario editor -> R3: live BYOK -> R4:
Evaluation/Model Arena -> R5: security and reliability and polish -> R6 optional: multiagent and new failures. No
arbitrary dates; the gates are in the roadmap.

## What not to build

KYC, a real bank account, real payments, a multi-tenant SaaS, charging visitors, a complete bank backoffice panel, a
production distributed architecture, ten agents having artificial conversations, or a trained model without an
experimental hypothesis.
"""

_TRANSLATIONS = {
    "00-LEIA-PRIMEIRO-PT-BR.md": READ_ME_FIRST,
    "docs/00-RESUMO-EXECUTIVO-PT.md": EXECUTIVE_SUMMARY,
}
