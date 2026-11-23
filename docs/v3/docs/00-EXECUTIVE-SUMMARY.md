# LedgerLens 2027+ - Executive summary and decision

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

- The offline mode uses `ScriptedChatModel` and accepts a defined subset of questions; it is not a free local language
  model.
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
