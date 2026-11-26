# Feature Specification: The multi-agent orchestration studio

**Feature Branch**: `feature/v3`

**Created**: 2026-11-23

**Status**: Draft

**Input**: Design documents: `docs/design/adrs/ADR-P007-no-multiagent-by-default.md`,
`docs/design/ai/01-MULTIAGENT-ORCHESTRATION.md`, `docs/design/ai/02-SPECIALIST-ROSTER.md`,
`docs/design/advanced-specs/R11-02-budgeted-specialist-dispatch.md`,
`docs/design/advanced-specs/R11-05-graph-checkpoint-and-resume.md`, and the decisions already in force:
`docs/decisions/ADR-037-the-case-of-the-demo-runs-on-a-bridge-over-the-caller.md`,
`docs/decisions/ADR-054-the-agent-loop-has-a-ceiling-in-every-path.md`,
`docs/decisions/ADR-034-the-registry-the-budget-and-the-endpoint.md`,
`docs/decisions/ADR-053-the-held-out-set-and-the-blind-labelling.md`,
`docs/decisions/ADR-013-public-trace-as-a-versioned-contract.md`. User description: "The design package
proposes a dispatcher that sends work to specialists, a graph that is checkpointed and resumed, and a paired
comparison that proves the gain. The repository ships a single agent with a deterministic verifier. This
specification ports the proposal, says plainly what the repository already has, and puts the whole thing behind
a flag until a measurement exists."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read that the shipped runtime is one agent and one deterministic verifier (Priority: P1)

A reader of the repository asks what runs today. The answer is the agent of `ledgerlens/agents/integrator.py`
with its six tools and the verifier of `ledgerlens/verify/`, which is code and a local cross-encoder, not a
model. The reader is told, in the same place, that the studio of this specification is experimental, that it
is behind a flag that is off in the shipped configuration, and that the flag only opens for an experiment that
is measured against the single agent over the same cases.

**Why this priority**: ADR-P007 is a red line. The main runtime stays a single agent with a deterministic
verifier until a paired comparison measures a gain, and a reader who believes the opposite will read every
number of the repository as the number of a multi-agent system.

**Independent test**: read `ledgerlens/agents/integrator.py` and `ledgerlens/verify/checks.py` and find one
agent and one verifier that is not a provider model, then read the configuration of the studio and find the
flag off by default.

### User Story 2 - Send a task to a specialist under a budget that the parallel work cannot exceed (Priority: P1)

The studio receives a plan of a case. It validates that the plan is acyclic, it schedules the independent
steps under a concurrency cap, and every step spends from the same budget of the run. A fan-out of three
steps that each would spend the whole cap of the run stops at the cap: the run ends with the reason, the
partial results that were produced and the trace that says what was spent. The spend of the run is money, so
it is a `Decimal` and never a float, and a price that was not verified is unknown and never zero.

**Why this priority**: the package makes the budget the contract of the dispatch, and the repository already
counts the calls of every model of a run in `ledgerlens/byok/budget.py`. A fan-out that spends more than the
single agent would spend is a fan-out that buys a worse answer for a bigger bill, and no measurement would
survive it.

**Independent test**: run the dispatcher over a plan with two independent read-only steps and a budget that
fits one of them, and expect the run to stop with the name of the cap that stopped it, a partial result and
no call outside the budget.

### User Story 3 - Refuse a specialist that widens the scope or asks for a tool it may not use (Priority: P1)

A specialist asks for a tool that is not in the allowlist of its own task, and it names an account that is not
the account of the run. The dispatcher refuses both: the permissions of a specialist are the intersection of
the permissions of its parent with the permissions of its own spec, never the union, and an unknown tool is
never called. The refusal is an event of the trace with the reason.

**Why this priority**: a subagent that widens its scope turns a research question into a data leak. The
repository already refuses an unknown tool in the live path, and the studio cannot be the place where that
rule is looser.

**Independent test**: call the dispatcher with a specialist spec whose tool list holds a tool outside the
allowlist and with an account outside the scope of the run, and expect two refusals, no tool call and no read
of the other account.

### User Story 4 - Let the arithmetic decide when two specialists disagree (Priority: P1)

Two specialists report a different net for the same settlement. The studio does not vote and does not average.
The deterministic calculator of the repository recomputes the amount, and its answer is the one that stands,
or the case abstains and says that the number is contested. Money is never decided by a model.

**Why this priority**: the package says it in its acceptance criteria, and the repository says it in
`AGENTS.md`: the numbers come out of a function with `Decimal` and never out of the model.

**Independent test**: build a join of two results with different amounts for the same row and expect the
result to carry the value of the calculator, or to carry no value and a named abstention, and never a
majority value.

### User Story 5 - Restart a suspended run without repeating an effect (Priority: P1)

A run is suspended between the read of the rate and the verification. It resumes from the journal of the run:
the steps that completed are not run again, the result of the rate is reused because the snapshot it was read
from is the snapshot of the branch, and a step whose inputs changed is not run at all: it needs a new run.
A resume never carries a key of a visitor across the restart, so a resume without a fresh authorization stops
with the reason.

**Why this priority**: ADR-037 and the vault of the live mode forbid the reuse of a secret outside its
session, and a resume that repeats an effect corrupts the branch of a visitor, which the sandbox of the
repository already protects with an idempotent commit.

**Independent test**: interrupt a run after the read of the rate, resume it, and expect the read of the rate
to happen once, the projection of the branch to carry no duplicated event, and a resume without a fresh
authorization to be refused.

### User Story 6 - Publish the comparison, including the comparison that fails (Priority: P2)

The studio is measured against the single agent over the same cases, with the same snapshot, with the
uncertainty of the measurement written next to the number. If the multi-agent run is not better once the
extra latency and the extra cost are counted, the result is published as a negative result and the flag
stays off. The page says which set the number was measured over and what the number is allowed to claim.

**Why this priority**: the package asks for a pre-registered comparison and for a published negative result.
The repository publishes the failures of its catalog on purpose
([ADR-068](../../docs/decisions/ADR-068-the-published-catalogue-holds-the-failures-and-not-only-the-cases-the-agent-resolves.md)),
and a study that hides its negative result is not a study.

**Independent test**: read the manifest of the experiment and find the pre-registration, the set the number
was measured over, the denominator and the rule of the comparison, and then find the decision that follows
the result, including the decision that keeps the flag off.

### Edge Cases

- A plan whose edges form a cycle: the dispatcher refuses it at the planning, before any step runs and
  before any money is spent.
- A specialist that times out: the run carries a partial status and names the scope that is missing. It
  never reports a success it did not have.
- A tool that fails twice: the retry happens only for a read-only tool, at most twice, and the run never
  loops on it.
- Two visitors at the same time: they never share a model, a cache, a memory or a branch.
- A run whose budget was spent by the baseline: the comparison reports the baseline and the studio over the
  same budget, and the studio is not credited with a case the budget did not buy.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** (ADR-P007): The shipped runtime stays a single agent with a deterministic verifier, the studio
  of this specification is behind a flag that is off in the shipped configuration, and the flag opens only for
  an experiment that is registered before it runs.
  - Test: `tests/orchestration/test_studio_flag.py` expects the flag off in the shipped configuration and
    expects a refusal when a run asks for the studio without a registered experiment.
- **FR-002** (ADR-P007 and the protocol of the package): The comparison of the studio against the single
  agent is pre-registered over a named set of cases, with the same snapshot for both arms, and the result is
  published with its denominator and its uncertainty, whether it is a gain or a loss.
  - Test: `tests/orchestration/test_paired_comparison.py` reads the manifest of the experiment and expects the
    pre-registration, the set, the shared snapshot and the decision that follows the result.
- **FR-003** (ADR-054 and the budget of the run): Every step of the studio spends from the budget of the run
  that the coordinator of `ledgerlens/byok/budget.py` enforces, the caps of the run are checked before a call
  and again after it, and a cap that stops the run names the cap that stopped it.
  - Test: `tests/orchestration/test_dispatch_budget.py` expects the run to stop at the cap, with the name of
    the cap and the partial result, and expects no call outside the budget.
- **FR-004** (the package and the scope of a run): The permissions of a specialist are the intersection of the
  permissions of its parent and the permissions of its own spec, the account scope of a run is never widened,
  and a tool that is not in the allowlist is refused and never called.
  - Test: `tests/orchestration/test_dispatch_scope.py` expects a refusal for a tool outside the allowlist and
    for an account outside the scope, and expects no tool call.
- **FR-005** (the package): A plan with a cycle is refused at the planning, before any step runs.
  - Test: `tests/orchestration/test_plan_validation.py` expects the refusal of a cyclic plan and expects no
    step to have run.
- **FR-006** (the package and the repository): A join of two results accepts only evidence identifiers that
  resolve to a record of the run and only a snapshot that matches the snapshot of the run, and a disagreement
  over an amount is settled by the deterministic calculator or becomes a named abstention, never by a vote.
  - Test: `tests/orchestration/test_join_and_conflict.py` expects the refusal of an invented evidence
    identifier and expects the value of the calculator, or a named abstention, over two conflicting amounts.
- **FR-007** (the package and ADR-021): A crash and a retry of a run do not duplicate the events of a branch,
  because the commands of the branch keep their idempotency key and the store is idempotent on the event
  identifier.
  - Test: `tests/orchestration/test_restart_idempotency.py` expects one event of the branch after a repeated
    commit with the same idempotency key, and expects the projection of the branch to be unchanged.
- **FR-008** (the package and ADR-037): A resume reads the journal of the run, reuses the output of a step
  that completed, runs again only a step that did not complete and that is idempotent and read-only, refuses
  a step whose snapshot or configuration version changed, and never rehydrates a credential of a visitor.
  - Test: `tests/orchestration/test_resume.py` expects the reuse of the completed step, the refusal of the
    invalidated step and the refusal of a resume without a fresh authorization.
- **FR-009** (the package and ADR-013): Every decision of the dispatcher is an event of the public trace with
  the plan it read, the step it ran, the budget it had and the reason it stopped, and the trace of a published
  recording says which specialist answered which part of the question.
  - Test: `tests/orchestration/test_trace_of_dispatch.py` reads the events of a run of the studio and expects
    one event per step with the budget it had and the reason it stopped.
- **FR-010** (ADR-053 and ADR-059): The set of the comparison is a set of the manifest of the datasets, it is
  not read by anything but the final scoring of the comparison, and a tuning script that reads it fails.
  - Test: `tests/orchestration/test_comparison_dataset_role.py` expects the role of the set of the comparison
    and expects the refusal of a script that reads it.

### Key Entities

- **Studio**: the experimental variant of the runtime that dispatches parts of a case to specialists. It is
  off in the shipped configuration and it never replaces the single agent of the shipped path.
- **Plan**: the directed acyclic graph of the steps of a case, validated before any step runs.
- **Specialist spec**: the versioned description of what a specialist may read, which tools it may call, what
  it may spend and what it must return.
- **Step result**: the typed result of a step: its status, the evidence it produced, what it spent and the
  error that stopped it.
- **Journal of a run**: the durable record of the steps of a run, their attempts, their inputs and their
  outputs, from which a run resumes.
- **Resume token**: the short-lived authorization that lets a suspended run continue.
- **Comparison manifest**: the pre-registered description of a paired comparison: the set, the snapshot, the
  arms and the rule that decides the result.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The shipped configuration runs the single agent with the deterministic verifier, and the flag of
  the studio is off.
- **SC-002**: The refusal to open the flag without a registered experiment names the experiment that is
  missing.
- **SC-003**: A fan-out of steps never spends more than the budget of the run, and the run that a cap stopped
  carries the name of the cap and its partial result.
- **SC-004**: No step of the studio ever calls a tool outside its allowlist and no step ever reads outside the
  scope of the run.
- **SC-005**: A cyclic plan is refused before any step runs.
- **SC-006**: Two results that disagree over an amount end with the value of the calculator or with a named
  abstention, and never with a value that came from a vote.
- **SC-007**: A crash and a retry leave the branch of the visitor exactly where the crash left it, with no
  duplicated event.
- **SC-008**: A resume reuses the output of a completed step, refuses a step whose snapshot changed and never
  rehydrates a credential.
- **SC-009**: The trace of a run of the studio says which specialist answered which part of the question,
  and the trace of a published recording says the same.
- **SC-010**: The comparison is published with its denominator and its uncertainty, and the result that follows
  it is published too, including the result that keeps the flag off.

## Design documents

- [ADR-P007: Prefer one evidence-first agent; multiagent requires a measured win](../../docs/design/adrs/ADR-P007-no-multiagent-by-default.md)
- [Multi-Agent Orchestration and Durable Runtime](../../docs/design/ai/01-MULTIAGENT-ORCHESTRATION.md)
- [Agent Roles and Boundaries](../../docs/design/ai/02-SPECIALIST-ROSTER.md)
- [R11-02 Budgeted specialist dispatch](../../docs/design/advanced-specs/R11-02-budgeted-specialist-dispatch.md)
- [R11-05 Graph checkpoint and resume](../../docs/design/advanced-specs/R11-05-graph-checkpoint-and-resume.md)
- [ADR-037: The case of the demo runs on a bridge over the caller](../../docs/decisions/ADR-037-the-case-of-the-demo-runs-on-a-bridge-over-the-caller.md)
- [ADR-034: The registry of tested models, the two costs of a run and the endpoint](../../docs/decisions/ADR-034-the-registry-the-budget-and-the-endpoint.md)
- [ADR-054: The agent loop has a ceiling in every path](../../docs/decisions/ADR-054-the-agent-loop-has-a-ceiling-in-every-path.md)
- [ADR-053: The held out set and the blind labelling](../../docs/decisions/ADR-053-the-held-out-set-and-the-blind-labelling.md)
- [ADR-013: The public trace is a versioned contract](../../docs/decisions/ADR-013-public-trace-as-a-versioned-contract.md)

## Status

**What exists in the repository today.** The shipped runtime is one agent (`ledgerlens/agents/integrator.py`)
with six tools, one verifier that is code and a local cross-encoder (`ledgerlens/verify/`), a triage chain, a
case memory and a prompt. The budget of a run counts the calls of every model
(`ledgerlens/byok/budget.py`), the loop has a ceiling in every path (`ledgerlens/agents/budget.py`), the trace
is a public contract with a sequence that grows (`ledgerlens/observability/trace_event.py`), the sandbox
commits idempotently and projects its state as a pure function of the base and the log
(`ledgerlens/sandbox/mutation.py`, `ledgerlens/sandbox/projector.py`), and the held out set of the
comparison exists with its blind labelling. The variant `D` exists today only as a value of the field
`variant` of the request of a live run (`ledgerlens/api/byok.py`), with no dispatcher behind it.

**What the package proposes.** A dispatcher in Python that owns the policy and the registry of the tools, a
plan that is a directed acyclic graph with typed results, per-role and aggregate caps, a scheduler that
joins only on matching snapshots and known evidence identifiers, a deterministic verification before the
summary, a journal of the run and a resume of a suspended run, and a pre-registered paired comparison with a
published negative result.

**What this specification changes.** The dispatcher never replaces the verifier, and the verifier stays
deterministic. In the live path the four slots of the agent stay four views of the one model of the run
(ADR-037, FR-013): a specialist of the live path is a specialist of the same model, and the choice of the
model of a slot is the subject of ADR-078 (in preparation), not of this specification. The comparison is
written down before it is run, and the negative result is published with the positive one.

**What is still to be built.** Everything of this specification: the dispatcher, the plan and its validation,
the specialist registry, the journal of the run, the resume, the manifest of the comparison and the published
result. None of it exists.

## Assumptions

- The comparison of the studio against the single agent is a hypothesis and not a measurement. No number of
  this specification says that a multi-agent run is better, and the measurement is the paired comparison of
  FR-002.
- The single agent of the shipped path is the baseline of the comparison. It is the same code, the same
  tools, the same verifier and the same snapshot of the branch.
- The journal of a run may live in the file backed store of the sandbox for a first version. The decision of
  a durable store is the decision of another milestone and is not taken here.
- The provider is a fake in the tests of this specification. No test of the studio opens a socket, and the
  whole suite runs offline with `LEDGERLENS_OFFLINE=1`.

## Out of scope

- The debate, the council and the other families of the table of the package. Only the dispatch and the
  resume are in scope.
- Any external agent, any remote MCP call and any protocol of an external specialist. The tools of the
  repository are local and the studio never calls anything that is not in the allowlist of the run.
- A durable workflow engine such as Temporal. The package itself says the backend may remain the checkpointer
  of LangGraph for a first version.
- The choice of the model of each slot. That is ADR-078 (in preparation) and it is written before the code
  of the routing.
- The frontend of `apps/web/`. The interface of the studio is the trace and the published recording.
