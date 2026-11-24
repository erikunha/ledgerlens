# The review of a case by a person

The repository decides that a case goes to a person and stops there. The rule that escalates is in
`ledgerlens/verify/escalation.py` and the numbers of the policy are in `ledgerlens/policy_limits.py`. This page says
what the review is, what it does and what it refuses to do.

## The task

A review task holds the case it reviews, the evidence the reviewer read, the hash of that evidence, the state, the
revision and the history. The hash travels with the task because a decision binds to what was read and not to what is
on the screen now: a reviewer who reads the evidence, waits and then decides has to be sure that the evidence did not
change under them.

The history is append only. Every decision appends an event and nothing rewrites one, because the history of a case
is the proof of what happened to it.

## The states

A task is in one of six states.

| The state | What it means |
| --- | --- |
| `queued` | the code sent the case to a person and nobody opened it yet |
| `in_review` | a reviewer has the task and is reading it |
| `approved_for_sandbox` | the reviewer approved the change for the branch of the sandbox |
| `rejected` | the reviewer refused the change |
| `request_more_evidence` | the reviewer asked for evidence that the case does not have |
| `escalated` | the reviewer sent the case further up |

The table of the transitions is explicit in `ledgerlens/review/state_machine.py`: every transition names the state it
comes from, the state it goes to and the decision that causes it. A transition outside the table is refused, because a
state machine with a state outside its table is a machine whose history nobody can read.

## The checks before a transition

The checks run before the transition and not after, and a decision that was refused leaves no trace. A task that moved
and then said it did not move is a task whose history lies.

1. **The permission of the reviewer.** The identity of the reviewer is the session of the request and never the
   content of the case. A decision that carries an identity of a model is refused, and so is a decision with no
   session.
2. **The revision.** A decision over a revision that moved is a conflict. Two reviewers open the same task, the
   first one decides it and the second one is told that the state moved, which is a different answer from the one
   that says the case cannot be decided.
3. **The evidence and the snapshot.** A decision over evidence that is not the evidence of the task is refused, and
   so is a decision over a snapshot of the case that moved.
4. **The task itself.** A task with no evidence cannot be approved, because nobody read anything, and the task of a
   cancelled run cannot be approved, because the run it reviews is gone.

## The route

`ledgerlens/review/routes.py` is a facade over the domain: it opens the task of the session that owns it and it
takes the decision of the session that owns it. It holds no rule of its own, and every refusal comes from the state
machine.

A refusal carries the code and nothing else. A task that a person may not see must not leak through the answer of a
refusal, so the refusal carries no case, no evidence and no state.

| The code | What it means |
| --- | --- |
| `ok` | the task was served or the decision applied |
| `forbidden` | the session is not the one that owns the task |
| `conflict` | the revision the decision was taken over is no longer the current one |
| `not_found` | there is no task for that case |

## What the review never does

- **It never decides.** The agent prepares the evidence and never decides. A sentence in the evidence that claims an
  approval is data: the state moves because a person decided it, and the reason of the decision comes from the
  reviewer and never from the text of the evidence.
- **It never moves real money.** The package imports no API, no payment client and no model, so an approval of a
  review can never reach a live payment. The approval binds to the event of a branch of the sandbox.
- **It never re-runs the case.** One run has one model ([ADR-037](decisions/ADR-037-the-case-of-the-demo-runs-on-a-bridge-over-the-caller.md)),
  and a review reads the result of a run and never changes the model of it.

## What does not exist yet

The queue of the review does not exist yet, and neither does the service that opens a task when the escalation flags
a case. The simulator of the queue is the piece of work of the next milestone of
[specs/012](../specs/012-r10-human-review-and-approval/spec.md), and the defaults of that simulator are fictional
and marked as such.

[ADR-087](decisions/ADR-087-the-review-is-a-typed-task-the-identity-of-the-reviewer-is-the-session-and-the-agent-never-decides.md)
is the decision that says what the review is and what it refuses to do.
