# LedgerLens v3 - Read me first

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
