# Feature Specification: Human review queue and approval state machine

**Feature Branch**: `feature/v3`

**Created**: 2026-11-23

**Status**: Draft

**Input**: Design documents: [ADR-019](../../docs/decisions/ADR-019-sandbox-facade-contract.md),
[ADR-021](../../docs/decisions/ADR-021-typed-mutation-and-atomic-commit.md),
[ADR-022](../../docs/decisions/ADR-022-reset-and-staleness.md),
[ADR-030](../../docs/decisions/ADR-030-case-memory-scoped-to-the-session.md),
[ADR-047](../../docs/decisions/ADR-047-the-lifecycle-and-the-limits-of-the-branch.md),
[ADR-073](../../docs/decisions/ADR-073-the-published-bundle-carries-the-evidence-its-verdict-was-computed-on-and-it-is-reproducible.md),
[ADR-074](../../docs/decisions/ADR-074-a-case-ends-in-a-decision-and-the-decision-belongs-to-the-code.md),
[ADR-P007](../../docs/design/adrs/ADR-P007-no-multiagent-by-default.md) and the design packages
[LL-V3-R10-03, human review queue simulator](../../docs/design/advanced-specs/R10-03-human-review-queue-simulator.md) and
[LL-V3-R10-06, human approval state machine](../../docs/design/advanced-specs/R10-06-human-approval-state-machine.md).
The milestone that builds the cost of the review is
[specs/011](../011-r9-cost-per-case-and-decision-utility/spec.md).

The package was written for a greenfield plan. The repository has since built the rule that sends a case to a person,
the policy that describes the review and the branch that an approval may apply to. The review itself does not exist:
there is no queue, no task, no decision and no state. This specification builds the queue simulator and the state
machine, and it keeps the agent out of the decision.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A reviewer takes a case, reads it and decides (Priority: P1)

A case is sent to a person. The reviewer opens the task and sees the question, the answer, the evidence the answer
cited, the verdict the code gave, the limits of what the case decided and what is missing. The reviewer approves the
change, rejects it, asks for more evidence or escalates it, and writes the reason. The decision is recorded and the
case leaves the queue.

**Why this priority**: the repository decides that a case goes to a person and stops there. The decision is the part
that a person takes, and it is the part that a case cannot close without.

**Independent test**: take a task from the queue, read it and decide it. The task carries the evidence, the verdict,
the limits and the missing pieces, the decision is recorded with its reason, the task leaves the queue and the
decision is visible in the history of the case.

### User Story 2 - An approval applies to a branch and never to a payment (Priority: P1)

The reviewer approves a change to the data of a branch. The approval is bound to the branch event it approves and to
the hash of the evidence the reviewer read. It never moves money, it never calls a payment processor and it never
touches a live run. The reviewer sees that on the screen before the decision.

**Why this priority**: the red line of the repository is that no real money moves, and the sandbox is the only place
where a change happens. An approval that reached a live payment would break the promise that the demo is a
laboratory.

**Independent test**: approve a task and read what happened. The event of the branch carries the approval, the
canonical hash of the branch moves by the rules of the branch, and no code path of a payment processor is called,
which a test proves by reading the modules of `ledgerlens/` and refusing an import of a payment client.

### User Story 3 - A decision written inside a tool cannot move the state (Priority: P1)

The text of a tool, or of a record of the ledger, contains a sentence that says the case is approved. The reviewer
reads it as data. The state of the task does not move, and the reason of the decision is never read from the text of
a tool.

**Why this priority**: the repository already treats the text of a record as data and never as an instruction, and the
same rule has to hold for the text of a tool. A state machine that reads an approval out of a tool output is a state
machine that anybody can advance.

**Independent test**: build a task whose evidence carries a sentence that claims an approval, decide the task with
the ordinary route, and assert that the state moved only because of the decision and that the sentence of the tool
appears nowhere in the decision.

### User Story 4 - Two decisions on the same revision, one of them applies (Priority: P1)

Two reviewers open the same task. The first one decides it. The second one tries to decide it afterwards and is
refused with a conflict, because the revision it read is no longer the current one. The state moved once.

**Why this priority**: a decision that applied twice would apply an approval to a state that the first decision
already changed, and the history of the case would lie.

**Independent test**: read the revision of a task, decide it, and decide it again with the same revision. The
first decision applies, the second is refused with a conflict, and the count of the decisions of the task is one.

### User Story 5 - A case without its evidence can only be requested or rejected (Priority: P2)

A task arrives with a piece of evidence missing. The reviewer cannot approve it. The reviewer may ask for the missing
piece or reject the case, and the reason of the decision says which one and why.

**Why this priority**: an approval of a case whose evidence was never read is an approval of nothing, and the
package says the same.

**Independent test**: build a task with a missing piece of evidence and try to approve it. The approval is refused
with a reason that names the missing piece, the two other decisions are accepted, and each of them carries its
reason.

### User Story 6 - A cancelled run cannot be approved (Priority: P2)

The run of the case was cancelled. The task cannot be approved. The state of the task says that the case is closed
and why.

**Why this priority**: the repository already has the rule that a run that was cut by a cap is a case that was cut
and not a wrong answer, and a cancelled run is the same kind of fact.

**Independent test**: cancel the run of a task and try to decide it. The decision is refused with the reason that
the run was cancelled, and the task is closed.

### User Story 7 - The engineer reads the capacity of the review queue (Priority: P1)

An engineer asks what happens when the volume of the cases that need a person grows. The simulation answers with
the utilization of the reviewers, the throughput, the backlog over the time and the distribution of the waiting time,
and it warns that the system is overloaded when the utilization reaches one. The numbers come from a simulation and
not from a model.

**Why this priority**: the theory of constraints is one of the lenses of the design package, and the queue of the
review is the constraint of a system that escalates. The waiting time must never be a sentence that a model wrote.

**Independent test**: run the simulation of a queue with a known arrival and a known number of reviewers and read
the result. The utilization, the throughput, the backlog and the waiting time are computed by the simulator, and the
same seed gives the same schedule.

### User Story 8 - Two policies of the review are compared over the same arrivals (Priority: P2)

The engineer wants to know whether raising the threshold of the escalation helps. The simulation runs the two
policies over the same arrivals, with the same seed and the same reviewers, and compares the backlog, the waiting
time and the number of the cases that were escalated.

**Why this priority**: a comparison over two different arrivals is not a comparison, and this is the same rule that
the paired evaluation of [specs/009](../009-r4-paired-evaluation-arena/spec.md) follows.

**Independent test**: run two policies over the same arrival distribution with the same seed and read the two
results. The arrivals are identical, the backlog and the waiting time differ, and the difference is named.

### User Story 9 - The queue does not starve the critical cases (Priority: P3)

The engineer worries that a policy that serves the easy cases first will leave the critical ones waiting for ever.
The simulation measures the fairness of the priority and reports the waiting time of the critical class next to the
waiting time of the others.

**Why this priority**: the package asks for the fairness to be tracked, and a priority that starves a class of cases
is a defect of the policy and not a fact of the world.

**Independent test**: run a simulation with a priority that favours the easy cases and assert that the report names
the waiting time of the critical class separately and that a class that waits for ever is reported as starved.

### Edge Cases

- A queue with no reviewer: the cases wait, the utilization is not a division by zero, and the report says that no
  one is serving.
- An overloaded queue: the report says that the system is overloaded and publishes no finite steady state wait,
  because there is none.
- A decision of a task of a session of another person: refused, and the refusal says nothing about the task.
- A reviewer identity that came from the model: refused, and the state does not move.
- A replay of a recorded run: it is not an authorization, and it never advances a state.
- A decision with an evidence hash that no longer matches: refused with a conflict, because the reviewer read
  something else.
- A decision that arrives after the expiry of the branch: refused, and the branch is gone.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A review task is a typed domain object with the case it reviews, the evidence the reviewer read, the
  hash of that evidence, the state, the revision and the history of the decisions.
  - Test: `tests/review/test_review_task.py` fails while a task carries no hash of its evidence.
- **FR-002**: The states of a task are `queued`, `in_review`, `approved_for_sandbox`, `rejected`,
  `request_more_evidence` and `escalated`, and no other transition is possible.
  - Test: `tests/review/test_review_state_machine.py` fails while a transition that is not in the table is applied.
- **FR-003**: Every transition appends an event, and the history of the task is append only.
  - Test: `tests/review/test_review_state_machine.py` fails while a transition appends no event.
- **FR-004**: The permission of the reviewer is checked before the transition, and the identity of the reviewer comes
  from the session and never from the text of a tool, of a record or of a model.
  - Test: `tests/review/test_review_state_machine.py` fails while a decision that carries an identity of the model
  applies.
- **FR-005**: A decision whose expected revision is stale is refused with a conflict and moves nothing.
  - Test: `tests/review/test_review_state_machine.py` fails while a stale decision applies.
- **FR-006**: The evidence hash and the snapshot of the case must match the ones the reviewer read, and a mismatch
  is refused with a conflict.
  - Test: `tests/review/test_review_state_machine.py` fails while a decision with a moved snapshot applies.
- **FR-007**: A task whose evidence is incomplete cannot be approved, and the refusal names what is missing.
  - Test: `tests/review/test_review_state_machine.py` fails while a task with a missing evidence is approved.
- **FR-008**: The task of a run that was cancelled cannot be approved and is closed.
  - Test: `tests/review/test_review_state_machine.py` fails while the task of a cancelled run is approved.
- **FR-009**: An approval applies to an event of a branch and never to a live payment, and the module of the
  review never imports a payment client and never reaches a live run.
  - Test: `tests/review/test_review_task.py` reads the modules of `ledgerlens/review/` with `ast` and fails while
    a module imports a live run or a payment client.
- **FR-010**: A replay of a recorded run is not an authorization and never advances the state of a task.
  - Test: `tests/review/test_review_state_machine.py` fails while a replay advances a state.
- **FR-011**: The queue simulator is a discrete event simulator with a stable priority queue of the events
  `(at, sequence, type)`, and the same seed gives the same schedule.
  - Test: `tests/reconomics/test_queue.py` fails while two runs with the same seed differ.
- **FR-012**: A queue with no reviewer publishes no utilization and no division by zero, and the report says that no
  one is serving.
  - Test: `tests/economics/test_queue.py` fails while a queue with no reviewer raises or publishes a utilization.
- **FR-013**: A queue whose utilization reaches one is reported as overloaded, and no finite steady state waiting
  time is published for it.
  - Test: `tests/economics/test_queue.py` fails while an overloaded queue publishes a finite steady state wait.
- **FR-014**: The simulation of two policies over the same arrivals uses the same arrival distribution, and the
  result says so.
  - Test: `tests/economics/test_queue.py` fails while two policies are compared over different arrivals.
- **FR-015**: The waiting time of the critical class is published apart from the waiting time of the others, and a
  class that waits for ever is reported as starved.
  - Test: `tests/economics/test_queue.py` fails while the critical class is not named.
- **FR-016**: The simulator holds no identity of a visitor, and the report never presents the capacity of the queue
  as a staffing plan and never presents the latency of the interface as the work time of a reviewer.
  - Test: `tests/economics/test_queue.py` fails while the queue holds an identifier of a visitor.
- **FR-017**: The domain of the review never imports the API.
  - Test: `tests/review/test_review_task.py` reads the modules of `ledgerlens/review/` with `ast` and fails while a
    module imports `ledgerlens.api`.

### Key Entities

- **Review task**: a case that waits for a person, with its evidence, its hash, its state and its revision.
- **Decision**: the choice of a reviewer, with its reason and the moment it was made.
- **Event**: the append only record of a transition.
- **Queue experiment**: the arrivals, the case mix, the reviewers, the distribution of the review time, the
  threshold, the seed and the horizon.
- **Utilization**: the share of the time of the horizon that the reviewers spent working.
- **Overload**: the state of a queue whose utilization reached one.
- **Starvation**: the state of a class of cases that never reaches a reviewer.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The number of the transitions that were applied without the permission of the reviewer is zero, over
  the whole suite.
- **SC-002**: Every transition of a task appends an event, and no transition that is not in the table of the states
  is possible.
- **SC-003**: A decision with a stale revision, with a moved snapshot or with the identity of the model is refused
  and moves nothing.
- **SC-004**: A task with a missing evidence cannot be approved, and a task of a cancelled run cannot be approved.
- **SC-005**: An approval changes a branch and nothing else, and no module of `ledgerlens/review/` reaches a live
  run or a payment client.
- **SC-006**: The same seed gives the same schedule of the reviewers, and the report of the simulation names the
  utilization, the throughput, the backlog and the waiting time.
- **SC-007**: A queue with no reviewer and an overloaded queue are both reported without a division by zero and
  without a finite steady state wait that does not exist.
- **SC-008**: The waiting time of the critical class is published apart, and a starved class is reported as
  starved.

## Assumptions

- The queue is a simulation and not a measurement. The repository has no queue of reviews today, so there is no
  arrival distribution to fit. The simulation answers the question of the package with the assumptions it declares.
- The reviewer is a person. The agent prepares the candidate evidence and never decides, under ADR-P007 and the red
  line of the design package. A variant that dispatches a specialist reviewer is a different piece of work, it stays
  behind a flag, and it is published only after a paired comparison measures a gain.
- The decision never changes the model of a run. One run has one model and the four slots of the agent are four
  views of that model, under ADR-037 and the FR-013 it carries. A review never re-runs a case with another model.
- The review applies to a branch of a sandbox. The public interface simulates the role of the reviewer and has no
  execution effect beyond the branch, as the package says.
- The review time of a person is an assumption of the simulation, not a measurement, and it belongs with the
  assumptions of [specs/011](../011-r9-cost-per-case-and-decision-utility/spec.md).
- The queue simulator lives in `ledgerlens/economics/queue.py`, as the package says, inside the package that
  [specs/011](../011-r9-cost-per-case-and-decision-utility/spec.md) creates.

## Out of scope

- The rule that sends a case to a person, which is `ledgerlens/verify/escalation.py` and is not changed here.
- The policy of the review, which is `data/policies/escalation-and-review.md` and is not changed here.
- The cost of the review and the utility of a decision, which belong to
  [specs/011](../011-r9-cost-per-case-and-decision-utility/spec.md).
- The interface of the review queue and of the reviewer role. The first milestone builds the domain, the route and
  the simulator; the interface is a later milestone.
- The live mode. A review never reads a live run and never approves one.
- Any multi agent dispatch of the review, which stays behind a flag under ADR-P007.
- The staffing of a real operation. The simulation is a laboratory and it never presents itself as a plan of
  staffing.

## Design documents

| Document | What it decides for this specification |
|---|---|
| [ADR-019](../../docs/decisions/ADR-019-sandbox-facade-contract.md) | The facade follows the versioned contract and the session is a cookie, so the identity of the reviewer is the session. |
| [ADR-021](../../docs/decisions/ADR-021-typed-mutation-and-atomic-commit.md) | A mutation is a typed command and the commit is atomic, so an approval is a typed command on a branch. |
| [ADR-022](../../docs/decisions/ADR-022-reset-and-staleness.md) | The reset returns the base and a generation marks the answers that went stale, so an approval is marked stale by a reset. |
| [ADR-030](../../docs/decisions/ADR-030-case-memory-scoped-to-the-session.md) | The case memory lives in the folder of the session, so the work of a reviewer never leaks between the sessions. |
| [ADR-047](../../docs/decisions/ADR-047-the-lifecycle-and-the-limits-of-the-branch.md) | The lifecycle of the branch travels as a stream and the limits answer with a code, so the task of a review follows the same shape. |
| [ADR-073](../../docs/decisions/ADR-073-the-published-bundle-carries-the-evidence-its-verdict-was-computed-on-and-it-is-reproducible.md) | The bundle carries the evidence the verdict was computed on, so the reviewer reads the evidence of the bundle. |
| [ADR-074](../../docs/decisions/ADR-074-a-case-ends-in-a-decision-and-the-decision-belongs-to-the-code.md) | The decision belongs to the code, so the rules of the escalation stay in the code and the person decides among the options the code offers. |
| [ADR-P007](../../docs/design/adrs/ADR-P007-no-multiagent-by-default.md) | The runtime stays a single agent with a deterministic verifier, so the agent prepares the evidence and never approves, and any specialist variant stays behind a flag until a comparison measures a gain. |
| [LL-V3-R10-03](../../docs/design/advanced-specs/R10-03-human-review-queue-simulator.md) | The design package of the queue simulator. |
| [LL-V3-R10-06](../../docs/design/advanced-specs/R10-06-human-approval-state-machine.md) | The design package of the state machine. |
| [specs/011](../011-r9-cost-per-case-and-decision-utility/spec.md) | The milestone that creates the economics package and the assumptions of the review. |

## Status

| Part | State in the repository on 2026-11-23 |
|---|---|
| The rule that sends a case to a person | Built. `ledgerlens/verify/escalation.py` decides the escalation and the recommended action in code, and the reasons name the policy section that decided. |
| The numbers of the policy | Built. `ledgerlens/policy_limits.py` holds the limits of the plan of the merchant and the source of each. |
| The policy of the review | Written. `data/policies/escalation-and-review.md` states when to escalate, the urgency levels, the response times, the human review flag and what goes with the case. |
| The domain of the review | Not built. There is no `ledgerlens/review/` and no `ReviewTask`. |
| The state machine and the events of the decisions | Not built. |
| The route that takes a decision | Not built. The facade of the sandbox and of the live run exist, and no route serves a review. |
| The interface of the reviewer | Not built. |
| The queue simulator | Not built. There is no queue, no arrival distribution and no measurement of a reviewer. |
| The economics package that holds the simulator | Not built. It is created by [specs/011](../011-r9-cost-per-case-and-decision-utility/spec.md). |
| The link from the escalation to a task | Not built. The escalation says `escalate_to_human` and the case stops there. |

The package says the review queue lives in `ledgerlens/economics/queue.py` and the state machine in a new typed
domain. The repository has no `ledgerlens/economics/` today, so the queue lives in the package that
[specs/011](../011-r9-cost-per-case-and-decision-utility/spec.md) creates, and the state machine lives in
`ledgerlens/review/`. This specification follows the repository and does not move the cost of the review out of the
package it belongs to.
