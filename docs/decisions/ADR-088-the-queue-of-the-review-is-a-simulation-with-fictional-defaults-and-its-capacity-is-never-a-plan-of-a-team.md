---
type: adr
status: accepted
date: 2026-11-24
---

# ADR-088: The queue of the review is a simulation with fictional defaults, and its capacity is never a plan of a team

Status: accepted. Date: 2026-11-24.

## Context

[ADR-087](ADR-087-the-review-is-a-typed-task-the-identity-of-the-reviewer-is-the-session-and-the-agent-never-decides.md)
built the task of the review, the table of its states and the route that takes the decision. What the milestone of
[specs/012](../../specs/012-r10-human-review-and-approval/spec.md) still owed was the queue: the capacity of the
reviewers, the waiting time of a case and the comparison of two policies of the escalation.

The design package
[LL-V3-R10-03, human review queue simulator](../design/advanced-specs/R10-03-human-review-queue-simulator.md) says where
the simulator lives and what it has to answer. It says two things that this decision repeats because they are the ones
that decide whether the numbers can be trusted.

The first is that the waiting time is computed and never written. A model can describe a wait, and a description of a
wait is not a wait. The numbers of a queue that a model wrote would carry the authority of a measurement without
having the evidence of one.

The second is that the capacity of a queue is not a staffing plan. The repository has no queue of reviews today, so
there is no arrival distribution to fit, no review of this repository was ever timed and no team exists that the
number of the reviewers describes. A report that read as a plan of a team would be read as advice, and the simulator
has no authority to give advice about a team that does not exist.

## Decision

**The queue of the review is a discrete event simulator with fictional defaults that are marked as such, and its
capacity is never a plan of a team.**

1. **The waiting time is computed and never written.** The simulator works the schedule of the reviewers out of the
   arrivals, the number of the reviewers and the assumption of the review time, and it publishes the schedule so a
   reader can check it.
2. **The seed decides the schedule.** Two runs of the same experiment with the same seed give the same schedule, and
   the events of the queue are ordered by `(at, sequence, type)`, so two events of the same minute are never in an
   order that a reader has to guess.
3. **The defaults are fictional and the report says so.** The distribution of the review time, the number of the
   reviewers and the horizon are assumptions of the experiment, and every report carries them.
4. **The capacity is never a plan of a team.** Every report carries a line that says that it is a simulation with
   fictional defaults and not a staffing plan, and the number of the reviewers is never published under a name that
   reads as a headcount.
5. **The work time of a reviewer is not the latency of the interface.** The simulator reads no measurement of the
   interface, and the package of the economics is a leaf of the domain: it imports no API and calls no model.
6. **The simulator holds no identity of a visitor.** A case carries the minute it arrived, how strongly it asks, its
   class and its work time, and a field that names a person would be data about a person that the model has no use
   for.
7. **An overloaded queue publishes no finite steady state waiting time.** A queue whose utilization reached one has
   no steady state, and a number that does not exist is never published as a number.
8. **A queue with no reviewer publishes no utilization.** There is nobody serving, and a utilization of nothing is not
   a number.
9. **The waiting time of the critical class is published apart.** A priority that serves the easy cases first leaves
   the critical cases waiting, and a report that published only the mean of everything would hide it. A class that
   waits for ever is reported as starved.
10. **Two policies are compared only over the same arrivals.** The comparison refuses two reports whose arrivals have
    different digests, because a comparison over two different arrivals measures the difference between the arrivals.
11. **The review keeps the rules of ADR-087.** The agent prepares the evidence and never decides, the identity of the
    reviewer is the session of the request, the history of a task is append only and the approval binds to an event of
    a branch and never to a live payment.
12. **The review never changes the model of a run.** One run has one model under ADR-037, and a review reads the
    result of a run and never re-runs it.
13. **Any specialist dispatch of the review stays behind a flag.** It becomes the default only when a paired
    comparison over the same cases measures a gain, under ADR-P007, and no such measurement exists.

## Alternatives considered

- **To let a model write the waiting times of the queue.** Refused. A sentence that describes a wait is not a wait,
  and the repository publishes numbers that a reader can reproduce.
- **To fit the arrival distribution over the cases of the repository.** Refused. The cases of the repository were not
  escalated to a person, so a distribution fitted over them would be a distribution of nothing.
- **To publish the capacity of the queue as a number of people to hire.** Refused. The number of the reviewers is an
  assumption of an experiment, and a report that reads as advice is a report that will be read as a fact.
- **To publish the finite steady state wait of an overloaded queue.** Refused. There is none, and a number that does
  not exist is never published as a number.
- **To compare two policies over two different sets of arrivals.** Refused. That comparison measures the arrivals
  and not the policies.
- **To publish a file of the published results with the numbers of the simulator.** Refused for now. A simulation
  with fictional defaults written to a file of the published results would be read as a measurement, and the
  repository publishes only what it measured.

## Consequences

- **The repository has the simulator of the queue**, in `ledgerlens/economics/queue.py`, with the tests in
  `tests/economics/test_queue.py`: the same seed gives the same schedule, a queue with no reviewer publishes no
  utilization and does not divide by zero, an overloaded queue publishes no finite steady state wait, two policies are
  compared only over the same arrivals, the waiting time of the critical class is published apart and a class that
  waits for ever is reported as starved, and the report never reads as a plan of a team.
- **The simulator is a leaf of the economics.** The package imports no API, no registry that calls a model and no
  payment client, and the test reads the modules with `ast` and proves it.
- **The queue of the repository does not exist yet.** The simulator is a laboratory: there is no service that opens a
  task when the escalation flags a case, and the cases of the repository never reach a queue.
- **The approval does not reach the sandbox yet.** The task carries the event of the branch that the approval binds
  to, and the binding itself is a piece of work of its own.
- **No artifact of the queue is published.** The report is a value that a caller publishes when it has an experiment
  that is worth publishing, and the repository publishes only what it measured.

## Links

- [ADR-037, the case of the demo runs on a bridge over the caller](ADR-037-the-case-of-the-demo-runs-on-a-bridge-over-the-caller.md)
- [ADR-087, the review is a typed task and the agent never decides](ADR-087-the-review-is-a-typed-task-the-identity-of-the-reviewer-is-the-session-and-the-agent-never-decides.md)
- [ADR-P007, no multi-agent by default](../design/adrs/ADR-P007-no-multiagent-by-default.md)
- [the simulator of the queue](../../ledgerlens/economics/queue.py)
- [the test of the simulator](../../tests/economics/test_queue.py)
- [the page of the queue](../queue.md)
- [the page of the review](../review.md)
- [the specification of the milestone](../../specs/012-r10-human-review-and-approval/spec.md)
