---
type: adr
status: accepted
date: 2026-11-07
---

# ADR-008: Evaluation design in LangSmith

Status: accepted. Date: 2026-11-07.

## Context

The project needs an evaluation of quality and tool trajectory in LangSmith, with conclusions drawn from the metrics. Measuring with a few good cases does not show whether the agent works. The evaluation must also run offline, so anyone can reproduce it.

## Decision

- **Set.** About 30 cases: 12 derived from the planted scenarios (with ground truth from the `data/scenarios.json` manifest) and about 18 natural cases taken from the generated database (status, policy, settlement), with ground truth computed from the tables.
- **Variants.** A (chain with no tools), B (ReAct agent with tools), C (full agent with verification). This makes it possible to say what each layer adds.
- **Evaluators.** Correctness (key fields by code, plus an LLM judge for the explanation), groundedness (the share of `supported` claims) and trajectory with the `openevals` 0.2.2 evaluators (`strict`, `unordered`, `subset`, `superset`). Verified: it runs without a key, and tool calls inside a single message compare as a group, so the converter writes one message per call.
- **Execution.** `langsmith.evaluate` online; offline, `upload_results=False` with `Example` objects (verified without a key; plain dictionaries fail).
- **Targets.** The full agent beats variant A on correctness and has a trajectory score of at least 80 percent.
- **Records.** The links and the export of the experiments stay outside the repository. The conclusions cite the metrics and the cases that failed.

## Alternatives considered

- **Manual spot checks.** They show no trend and no regression.
- **Third-party evaluation platforms.** LangSmith already covers traces and experiments.
- **`agentevals`.** It exists on PyPI, but `openevals` covers the four required modes.

## Consequences

- Online results depend on a LangSmith key and quota (plan limits not verified). The offline report is plan B and uses the same format.
- The LLM judge can be wrong. Numeric fields never go through it.
- Thirty cases give a trend, not statistical significance, and the analysis says so.
- A run varies (the trajectory of B moved by 0.07 with no code change), so `--repeats N` runs each variant N times and the report carries the mean, minimum and maximum per metric. If LangSmith refuses the upload of traces, the runs go on without storage and the report says so and why.
