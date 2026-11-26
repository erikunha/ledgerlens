---
type: adr
status: accepted
date: 2026-11-24
---

# ADR-087: The review is a typed task, the identity of the reviewer is the session, and the agent never decides

Status: accepted. Date: 2026-11-24.

## Context

The repository decides that a case goes to a person and stops there. The rule that escalates is in
`ledgerlens/verify/escalation.py`, the numbers of the policy are in `ledgerlens/policy_limits.py`, and the branch that
an approval may apply to is in `ledgerlens/sandbox/branch.py`. What did not exist was the review itself: there was no
task, no queue, no decision and no state.

The design packages
[LL-V3-R10-06, human approval state machine](../design/advanced-specs/R10-06-human-approval-state-machine.md) and
[LL-V3-R10-03, human review queue simulator](../design/advanced-specs/R10-03-human-review-queue-simulator.md) say
what the review has to be, and the two rules that matter most came from them. The agent prepares the evidence and
never decides, and the review responsibility has to be inspectable and impossible to bypass by an instruction that
somebody wrote into the content of a case.

The repository already had the two rules that this decision generalises. It treats the text of a record of the ledger
as data and never as an instruction, and it never moves real money: the sandbox is the only place where a change
happens (ADR-019, ADR-021, ADR-047).

## Decision

**A review is a typed task, the identity of the reviewer is the session of the request, and the agent prepares the
evidence and never decides.**

1. **The task carries the hash of the evidence.** A task holds the case it reviews, the evidence the reviewer read,
   the hash of that evidence, the state, the revision and the history. A decision binds to what was read and not to
   what is on the screen now, and a decision over evidence that is not the evidence of the task is refused.
2. **The table of the transitions is explicit.** A task is in one of six states, and every transition names the state
   it comes from, the state it goes to and the decision that causes it. A transition outside the table is refused,
   because a state machine with a state outside its table is a machine whose history nobody can read.
3. **The identity of the reviewer is the session.** It never arrives with the content of the case. A decision that
   carries an identity of a model is refused, and so is a decision that carries no session at all.
4. **The checks run before the transition and not after.** The permission of the reviewer comes first, because a
   decision of nobody is not a decision. The revision comes next, because a stale revision is a conflict and not a
   broken case. The evidence and the snapshot come after, because a decision over something that moved is a decision
   about something else. A decision that was refused leaves no trace, because a task that moved and then said it did
   not move is a task whose history lies.
5. **The history is append only.** Every transition appends an event and nothing rewrites one, and the history of a
   case is the proof of what happened to it.
6. **A replay is not an authorisation.** The events of a run can be replayed, and a replay changes nothing. A replay
   that carries no event of the history authorises nothing, because a flag on its own would let a caller skip the
   checks by asking for a replay.
7. **The text of a tool cannot move the state.** A sentence in the evidence that claims an approval is data. The
   state moves because a person decided it, and the reason of the decision comes from the reviewer and never from the
   text of the evidence.
8. **The route reads the domain and the domain never reads the route.** A decision of a session of another person is
   refused, and the refusal carries the code and nothing else: no case, no evidence and no state, because a task that
   a person may not see must not leak through the answer of a refusal. A decision over a stale revision is answered
   with the code of a conflict, because the caller of the route is a page of a person.
9. **The package never reaches a live run.** It imports no API, no payment client and no model, so an approval of a
   review can never move real money. The approval binds to the event of a branch that the task carries.
10. **The review never changes the model of a run.** One run has one model under ADR-037, and a review reads the
    result of a run and never re-runs it.

## Alternatives considered

- **To let the model write the reason of the decision.** Refused. The reason of a decision is what a person wrote,
  and a reason that came out of the content of the case is the content of the case.
- **To read the reviewer out of the text of the evidence.** Refused. It would be a decision that anybody could write
  into a tool.
- **To let a rejected decision move the task to a state outside the table.** Refused. The states of a task are the
  six the table names, and a state outside it is a state that no reader can interpret.
- **To keep the count of the retries of a decision in the session.** Refused. A task has a revision, and the
  revision is what says that a decision is late.
- **To let the route of the review call the branch of the sandbox directly.** Refused for now. The route reads the
  domain and the domain never reads the route, and the binding of an approval to an event of a branch is a piece of
  work of its own.

## Consequences

- **The repository has the domain of the review**, in `ledgerlens/review/` (`task.py`, `state_machine.py` and
  `routes.py`), with the tests in `tests/review/`: the hash of the evidence travels with the task, the table of the
  transitions is explicit, the identity of the reviewer is the session, every transition appends an event, a stale
  revision is a conflict, a decision over other evidence is refused, a task with no evidence and the task of a
  cancelled run cannot be approved, a replay changes nothing, and a refusal discloses nothing about the task.
- **The queue of the review does not exist yet.** The domain of the task and the state machine are there, and the
  service that opens a task when the escalation flags a case is the piece of work of the next milestone, together with
  the simulator of the queue.
- **The approval does not reach the sandbox yet.** The task carries the event of a branch that the approval binds to,
  and the binding itself is the piece of work of the next milestone.
- **The review never changes the model of a run.** The package imports no model and no registry that calls one, and
  the test reads the modules with `ast` and proves it.

## Links

- [ADR-019, the contract of the facade of the sandbox](ADR-019-sandbox-facade-contract.md)
- [ADR-021, the typed mutation and the atomic commit](ADR-021-typed-mutation-and-atomic-commit.md)
- [ADR-037, the case of the demo runs on a bridge over the caller](ADR-037-the-case-of-the-demo-runs-on-a-bridge-over-the-caller.md)
- [ADR-047, the lifecycle and the limits of the branch](ADR-047-the-lifecycle-and-the-limits-of-the-branch.md)
- [ADR-074, a case ends in a decision and the decision belongs to the code](ADR-074-a-case-ends-in-a-decision-and-the-decision-belongs-to-the-code.md)
- [ADR-P007, no multi-agent by default](../design/adrs/ADR-P007-no-multiagent-by-default.md)
- [the package of the review](../../ledgerlens/review/)
- [the test of the domain](../../tests/review/test_review_task.py)
- [the test of the route](../../tests/review/test_review_routes.py)
