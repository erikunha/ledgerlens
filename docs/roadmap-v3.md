# Roadmap v3: the LedgerLens as a public laboratory of applied AI engineering

This document is the work plan from 2026-11-11 onwards. The decision that anchors it is the
[ADR-011](decisions/ADR-011-v3-roadmap-in-verifiable-slices.md). The detailed specification of each release lives in
[`specs/`](specs/), written with the specification toolkit, and the design package that drives the whole cycle is
versioned in [`docs/v3/`](v3/ORIGEM.md).

## The decision

The LedgerLens is a **public laboratory of applied AI engineering** that uses payment operations as a domain rich in
constraints. It is not a fintech, not a banking product, not a SaaS, and it will never move real money. Whoever visits
the repository or the site finds an engineering machine that can be inspected, not a promise.

Three outcomes to optimise, in this order:

1. **Engineering**: real depth in frontend, Python, agents, tools, data, security, tests, evals, observability and cost.
2. **Demonstration**: one person can experiment without a key and without a login, and understand the result with
   evidence.
3. **Career**: verifiable material to show to engineers, interviewers, managers and founders. No promise of financial
   return.

## The red lines

1. Never fake a live execution, a retrieved value, a benchmark result or a certificate.
2. Never make real money movement available. Every change is a sandbox event.
3. Never leak the key of a visitor who brings their own, not in a log, not in a trace, not in a replay.
4. Never claim that multiple agents are better without a paired comparative test.
5. Never simplify a financial problem to the point of hiding its difficulty.
6. Never call "live" what is a replay or a simulation.

## The loop

One task per commit. The repository gate green before each commit. Each slice delivers evidence a third party can
rerun: a hash of origin, a test, a fixture or a trace, and the exact command.

What counts as evidence comes from the design package itself: for the engineering tasks, "reproducible test +
trace/fixture + source link"; for the economic ones, "economic/functional oracle + paired test + assumptions".

## R0: freeze the truth

Without this, nothing after it is comparable. No behaviour change enters this phase.

| ID | Task | Evidence | State |
|---|---|---|---|
| LL-V3-R0-01 | Freeze the commit, the lockfile and the hash of the scenarios | [`verification/baseline.md`](../verification/baseline.md) | done |
| LL-V3-R0-02 | Run the offline tests and record the exact output | [`verification/baseline.md`](../verification/baseline.md) | done |
| LL-V3-R0-03 | Normalise the current `Span` into the public `TraceEvent` schema | [`ledgerlens/observability/trace_event.py`](../ledgerlens/observability/trace_event.py) and [`tests/observability/test_trace_event.py`](../tests/observability/test_trace_event.py) | done |
| LL-V3-R0-04 | Capture and redact the canonical replay bundle | [`data/eval/replay/s01`](../data/eval/replay/s01) and [`tests/replay/test_bundle.py`](../tests/replay/test_bundle.py) | done |
| LL-V3-R0-05 | Reconcile the divergence between the 30 and the 43 cases of the verifier | [`docs/verification_sets.md`](verification_sets.md) and [`tests/verify/test_verification_sets.py`](../tests/verify/test_verification_sets.py) | done |
| LL-V3-R0-06 | `RunContext` in Python, without global state per visitor | [`ledgerlens/run_context.py`](../ledgerlens/run_context.py) and [`tests/agents/test_run_context.py`](../tests/agents/test_run_context.py) | done |
| LL-V3-R0-07 | Document the SQL guard and the account isolation | [`docs/tools.md`](tools.md) and [`docs/architecture.md`](architecture.md) | done |

The public `TraceEvent` is the contract of `contracts/schemas/trace-event.schema.json` of the package, implemented in
[`ledgerlens/observability/trace_event.py`](../ledgerlens/observability/trace_event.py) with the decision in the
[ADR-013](decisions/ADR-013-public-trace-as-a-versioned-contract.md): `schema_version`, `run_id`, `seq`, `at`,
`event_type`, `span_id`, `parent_span_id`, `payload`, `snapshot_sha256` and `mode`, with `mode` in `recorded_replay`,
`deterministic_sandbox` or `live_agent`.

## R1: the visitor without a key

The specification is in [`specs/001-r1-public-replay/`](specs/001-r1-public-replay/).

| ID | Task | State |
|---|---|---|
| LL-V3-R1-01 | Next.js shell and responsive design tokens | pending |
| LL-V3-R1-02 | Zero-auth scenario gallery, with provenance | pending |
| LL-V3-R1-03 | Render the recorded trace, step by step | pending |
| LL-V3-R1-04 | Payment record explorer | pending |
| LL-V3-R1-05 | Linked claim, verdict and evidence inspector | pending |
| LL-V3-R1-06 | Architecture explorer with source anchors | pending |
| LL-V3-R1-07 | Automated accessibility and mobile tests | pending |

The frontend consumes versioned API schemas and never reimplements a domain rule. Python stays the authority.

## R2: the sandbox

The specification is in [`specs/002-r2-visitor-sandbox/`](specs/002-r2-visitor-sandbox/).

| ID | Task | State |
|---|---|---|
| LL-V3-R2-01 | Typed mutation commands for the sandbox | pending |
| LL-V3-R2-02 | Fork the immutable base snapshot per session | pending |
| LL-V3-R2-03 | Idempotent append and projection | pending |
| LL-V3-R2-04 | Preview and diff of the mutations | pending |
| LL-V3-R2-05 | Recompute the scenario oracle after the mutation | pending |
| LL-V3-R2-06 | Reset, hash consistency and time to live | pending |
| LL-V3-R2-07 | End to end isolation between two visitors, and the conflict case | pending |

The public base is immutable: each visitor gets an isolated branch and can reset deterministically. Nothing writes
directly to the domain table; an event is written and the projector recomputes.

## R3: bring your own key, last

The specification is in [`specs/003-r3-bring-your-own-key/`](specs/003-r3-bring-your-own-key/).

| ID | Task | State |
|---|---|---|
| LL-V3-R3-01 | Provider registry and the list of tested capabilities | pending |
| LL-V3-R3-02 | Ephemeral secret handle, with the delete path | pending |
| LL-V3-R3-03 | Run coordinator with a strict budget | pending |
| LL-V3-R3-04 | Typed server-sent events and cancellation | pending |
| LL-V3-R3-05 | Model picker and a transparent consent | pending |
| LL-V3-R3-06 | Tool calling conformance test for the provider | pending |
| LL-V3-R3-07 | Redaction of the key and of the trace under failure | pending |

BYOK only comes after the per-session isolation tests and the redaction tests are green. The key stays on the server,
in the session, and disappears at the exit.

## After R3

R4 brings the comparable experiments and the reconciliation of the verifier with the right denominators; R5 brings the
deployment with a static fallback, the security hardening and the real measurement of latency and cost. R6 onwards are
research tracks: multiagent, versioned memory, durable execution, digital twin, multimodal and causality, each one with
the proof gate the package defines.

## Where the design package is

The package with the atlas of 234 capabilities, the 161 new ids, the 34 screens, the 19 component specs and the 7
schemas is versioned in [`docs/v3/`](v3/ORIGEM.md), imported by `scripts/import_v3_pack.py`. It is 125 files, sha256
`4bf1cb2402ac7b31d85244e9ec7e4970c1db5ab63f17361d43471e102a2cbad1` over the relative path and the bytes, the same
digest as the ADR-011.

The import is mechanical: the em dash becomes a hyphen, the word the context guard forbids becomes the English
synonym, the cedilla of "facade" is dropped, and the two documents that exist only in Brazilian Portuguese are
translated into English. No claim of the package was rewritten. The package is third party material and it is in
English; the plan that drives the work is this document, in the voice of the project. The provenance is in the
[ADR-012](decisions/ADR-012-v3-package-versioned-in-docs-v3.md).

## How the plan is specified

Each release has a specification folder under [`specs/`](specs/), written with the specification toolkit and following
the same structure:

- `spec.md`: the user stories with priorities, the functional requirements, the entities and the success criteria
- `plan.md`: the technical context, the constitution check and the file structure
- `tasks.md`: the ordered task list, mapped to the user stories, with the checkpoints

The constitution lives in the `memory` folder of the specification toolkit, and holds the principles that every slice
obeys. The tooling that generates the folders is in the `scripts` folder of the same toolkit.

## What has not been measured

The central economic number of the project, the cost per correctly resolved case, **has no measurement**. Every value
in the package is a premise, a simulated profile, or labelled as such. Before any cost or economy number is published,
there has to be a measurement with the right denominator and a declared premise.

The quality numbers the repository publishes come from real runs. The reconciliation of the denominators is the
LL-V3-R0-05 and it is done: the combined NLI accuracy of 0.786 is measured over 70 NLI cases, the 30 text cases of the
verification set plus the 40 live ones, and not over the 43 records of the verification set. Each number says what it
counts in [`docs/verification_sets.md`](verification_sets.md).
