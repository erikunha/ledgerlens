# The queue of the review

The repository decides that a case goes to a person and stops there. The rule that escalates is in
`ledgerlens/verify/escalation.py`, the task of the review is in `ledgerlens/review/` and the page that says what the
review is and what it refuses to do is [`docs/review.md`](review.md). This page says what the queue of the review is,
what it computes and what it refuses to say.

## The simulator

The queue of the review is a **simulation**. The repository has no queue of reviews today: nobody timed a review of
this repository, and no arrival distribution was ever measured. The simulator therefore answers a question with the
assumptions it declares, and every number it publishes is an assumption and not a fact.

`ledgerlens/economics/queue.py` is a discrete event simulator. It works the schedule of the reviewers out of the
arrivals, the number of the reviewers and the assumption of the review time, and it publishes the schedule so a
reader can check it.

Why the waiting time is computed and never written: a model can describe a wait, and a description of a wait is not
a wait. The time a case spends in the queue is the difference between two minutes that the simulator worked out.

## The experiment

An experiment holds six things, and every one of them is a choice of the person who runs it.

| The field | What it is |
| --- | --- |
| `arrivals` | the cases that ask for a person, each with the minute it arrived, how strongly it asks, its class and the minutes its review takes |
| `reviewers` | the number of the people who serve the queue |
| `policy` | the threshold that decides which cases go to a person and the order the queue is served in |
| `review_time` | the distribution of the minutes a review takes, with the mode in the middle |
| `seed` | the seed that decides the draw of the review time |
| `horizon_minutes` | the length of the window of the observation |

The seed decides the schedule, and the same experiment with the same seed gives the same schedule. A schedule that
moved between two runs of the same experiment would make every number of the report unreadable.

The events of the queue are ordered by `(at, sequence, type)`. The sequence is the order in which the events were
created, so two events of the same minute are never in an order that a reader has to guess.

## The orders of the queue

Two orders are available.

- `fifo`: the case that arrived first is served first.
- `easiest_first`: the case whose review takes less time is served first.

The second order is the one that breaks. A queue that serves the easy cases first leaves the slow cases waiting, and
the slow cases are often the critical ones. The simulator publishes the waiting time of every class apart, so a
report of a queue that starves a class names the class that starved.

## What the report says

| The number | What it means |
| --- | --- |
| `utilization` | the share of the window the reviewers spent working, or nothing when nobody is serving |
| `throughput_per_hour` | the cases that were completed inside the window, per hour |
| `mean_wait_minutes` | the mean of the waiting times of the cases that reached a reviewer |
| `wait_p50_minutes` and `wait_p95_minutes` | the middle and the tail of the waiting times |
| `backlog_at_horizon` | the cases that were still waiting at the end of the window |
| `overloaded` | whether the utilization reached one |
| `steady_state_wait_minutes` | the mean time in the system of the window, and nothing when the system is overloaded |
| `classes` | the waiting time of every class of cases, and whether the class starved |

An overloaded queue has no finite steady state waiting time, and the report publishes none. A queue with no reviewer
has no utilization and no mean wait, and the report does not divide by zero.

## The policy and the threshold

The policy of an experiment carries the threshold that decides which cases go to a person. Raising the threshold
sends fewer cases to the queue, and the comparison of two policies is only a comparison when the two policies saw the
same arrivals.

`compare_policies` refuses two reports whose arrivals have different digests. The name of a policy is what a caller
typed and the digest is what the arrivals are, and only the second one can tell that the two policies saw the same
cases.

## What the queue never does

- **It never holds an identity of a visitor.** A case carries the minute, the strength, the class and the work time,
  and a field that names a person would be data about a person that the model has no use for.
- **It never reads as a plan of a team.** The number of the reviewers is an assumption of the experiment and the work
  time of a reviewer is not the latency of the interface. Every report carries a line that says so.
- **It never calls a model.** The package of the economics is a leaf of the domain, and a queue that asked a model
  for the waiting time would publish a sentence with the authority of a number.

## What does not exist yet

The simulator is a laboratory and the queue of the repository does not exist yet. There is no service that opens a
task when the escalation flags a case, and the approval of a review does not reach the branch of the sandbox yet: the
task carries the event of the branch that the approval binds to and the binding itself is a piece of work of its own.

No artifact of the queue is published either. A simulation with fictional defaults that was written to a file of the
published results would be read as a measurement, and the repository publishes only what it measured.

[ADR-088](decisions/ADR-088-the-queue-of-the-review-is-a-simulation-with-fictional-defaults-and-its-capacity-is-never-a-plan-of-a-team.md)
is the decision that says what the queue is and what it refuses to say.
