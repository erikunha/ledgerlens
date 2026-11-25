"""The simulator of the queue of the review: the capacity of the reviewers, computed and never guessed.

Why it exists: the repository decides that a case goes to a person, and a system that escalates has a bottleneck that
is the person. The design package asks what happens when the volume of the cases that need a person grows, and the
answer has to be a number that anybody can reproduce and not a sentence that a model wrote (FR-011).

Why the waiting time is computed and never written: a model can describe a wait, and a description of a wait is not a
wait. The simulator works the schedule out of the arrivals, the number of the reviewers and the assumptions of the
review time, and it publishes the schedule so a reader can check it.

Why the defaults are fictional and marked as such: the repository has no queue of reviews today, so there is no arrival
distribution to fit and no review of this repository was ever timed. Every number of the report is an assumption of the
experiment, and the report says so.

Why the simulator holds no identity of a visitor: a queue models the capacity of the reviewers and not the people that
brought the cases. A session, a name or a key of a provider in a queue model would be data about a person that the
model has no use for (FR-016).

Why the capacity is never a plan of a team: the number of the reviewers is an assumption of the experiment and the work
time of a reviewer is not the latency of the interface. A report that read as a staffing plan would be read as advice,
and the simulator has no authority to give advice about a team that does not exist here (FR-016).

Why the events have a stable order: the queue of the events is ordered by `(at, sequence, type)` and the sequence is the
order in which the events were created. Two runs of the same experiment with the same seed give the same schedule, and a
schedule that changed between two runs would make every number of the report unreadable (FR-011).

Why the times are whole minutes: a schedule that a reader can work out by hand is a schedule that can be checked, and a
fraction of a minute in a queue of a person is a precision that nobody can measure.
"""

from __future__ import annotations

import hashlib
import heapq
import json
import random
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

__all__ = [
    "CLASS_CRITICAL",
    "CLASS_ORDINARY",
    "DEFAULT_HORIZON_MINUTES",
    "EVENT_ARRIVAL",
    "EVENT_FINISH",
    "EVENT_START",
    "NOT_A_STAFFING_PLAN",
    "ORDER_EASIEST_FIRST",
    "ORDER_FIFO",
    "ORDERS",
    "Arrival",
    "ClassWait",
    "PolicyComparison",
    "QueueEvent",
    "QueueExperiment",
    "QueuePolicy",
    "QueueReport",
    "ReviewTime",
    "compare_policies",
    "simulate",
]

# The class of the cases that a person has to see first, and the class of the ones that can wait.
CLASS_CRITICAL = "critical"
CLASS_ORDINARY = "ordinary"

# The order of the queue: the first in, the first out, and the easiest case first, which is the order that starves
# the long cases when the capacity is short.
ORDER_FIFO = "fifo"
ORDER_EASIEST_FIRST = "easiest_first"
ORDERS = (ORDER_FIFO, ORDER_EASIEST_FIRST)

# The three kinds of event of the queue: a case arrives, a reviewer takes it and a reviewer finishes it.
EVENT_ARRIVAL = "arrival"
EVENT_START = "start"
EVENT_FINISH = "finish"

# The length of the window of the observation when the experiment does not say. It is an assumption and not a fact.
DEFAULT_HORIZON_MINUTES = 60

# What the report says about what it is not. The capacity of a queue of a laboratory is not advice about a team, and
# the work time of a reviewer is not the latency of the interface.
NOT_A_STAFFING_PLAN = (
    "this is a simulation with fictional defaults and it is not a staffing plan: the number of the reviewers is an "
    "assumption of the experiment and the work time of a reviewer is not the latency of the interface"
)

# The percentiles of the waiting time that the report publishes.
_PERCENTILE_50 = 50
_PERCENTILE_95 = 95


@dataclass(frozen=True)
class Arrival:
    """A case that asks for a person, and when it asks.

    Why the fields are exactly these four: a case is a moment, a strength, a class and a work time, and a field that
    names a person would be data the model has no use for (FR-016).

    Why the work time can be stated by the case: a simulator that always drew it would hide the assumption that the
    slow cases are the critical ones, and a fixture that a reader can work out by hand needs a time it can name.
    """

    at_minute: int
    # How strongly the case asks for a person, compared with the threshold of the policy.
    score: int
    case_class: str = CLASS_ORDINARY
    # The minutes a review of this case takes, or None to draw it from the distribution of the experiment.
    review_minutes: int | None = None

    def __post_init__(self) -> None:
        if self.at_minute < 0:
            raise ValueError(f"an arrival at the minute {self.at_minute} is before the queue opened")
        if not self.case_class:
            raise ValueError("an arrival carries the class of its case, and an empty class is not a class")
        if self.review_minutes is not None and self.review_minutes < 0:
            raise ValueError("the review time of a case is not a negative number of minutes")


@dataclass(frozen=True)
class QueuePolicy:
    """The rule that decides which cases go to a person and in what order they are served.

    Why the threshold is a number and not a name: the comparison of two policies is a comparison of two numbers over
    the same arrivals, and a policy that could not be compared could not be compared (FR-014).
    """

    name: str
    threshold: int
    order: str = ORDER_FIFO

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("a policy names itself, and an empty name is not a name")
        if self.order not in ORDERS:
            raise ValueError(f"the order {self.order!r} is not one of the orders the simulator knows: {ORDERS}")


@dataclass(frozen=True)
class ReviewTime:
    """The distribution of the minutes a review takes, with the mode in the middle.

    Why a distribution and not a number: the time a person spends on a case is not the same for every case, and a
    simulator that assumed it was would publish a schedule that never happens.

    Why the three numbers are whole minutes: a schedule that a reader can work out by hand is a schedule that can be
    checked.
    """

    minimum: int
    mode: int
    maximum: int

    def __post_init__(self) -> None:
        if self.minimum < 0:
            raise ValueError("the minimum of the review time is not a negative number of minutes")
        if not self.minimum <= self.mode <= self.maximum:
            raise ValueError(
                f"the review time needs the minimum <= the mode <= the maximum, and it carries "
                f"{self.minimum}, {self.mode} and {self.maximum}"
            )


@dataclass(frozen=True)
class QueueExperiment:
    """One run of the simulator: the arrivals, the reviewers, the assumption of the review time and the seed.

    Why the seed is a field and not a default of the simulator: two runs of the same experiment with the same seed
    give the same schedule, and a comparison of two policies is only a comparison when the two runs share the seed
    (FR-011 and FR-014).
    """

    arrivals: tuple[Arrival, ...]
    reviewers: int
    policy: QueuePolicy
    review_time: ReviewTime
    seed: int = 0
    horizon_minutes: int = DEFAULT_HORIZON_MINUTES

    def __post_init__(self) -> None:
        if self.reviewers < 0:
            raise ValueError("the number of the reviewers is not a negative number")
        if self.horizon_minutes <= 0:
            raise ValueError("the horizon of the observation is not a number of minutes")
        for arrival in self.arrivals:
            if not isinstance(arrival, Arrival):
                raise ValueError("the arrivals of an experiment are arrivals and not something else")


@dataclass(frozen=True)
class QueueEvent:
    """One event of the queue: when it happened, in what order and what it was about.

    Why the case is a number and not a name: an event that named a visitor would be an event about a person, and the
    simulator has no business knowing people (FR-016).
    """

    at_minute: int
    sequence: int
    type: str
    case_index: int | None = None
    reviewer: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """The event as a dictionary, for the report of the simulation."""
        return {
            "at_minute": self.at_minute,
            "sequence": self.sequence,
            "type": self.type,
            "case_index": self.case_index,
            "reviewer": self.reviewer,
        }


@dataclass(frozen=True)
class ClassWait:
    """The waiting time of one class of cases, and whether the class starved.

    Why the class is published apart and not merged with the others: a priority that serves the easy cases first can
    leave the critical cases waiting for ever, and a report that only published the mean of everything would hide
    that (FR-015).
    """

    name: str
    arrived: int
    served: int
    starved: bool
    mean_wait_minutes: Decimal | None
    p50_minutes: int | None
    p95_minutes: int | None

    def to_dict(self) -> dict[str, Any]:
        """The class as a dictionary, for the report of the simulation."""
        return {
            "name": self.name,
            "arrived": self.arrived,
            "served": self.served,
            "starved": self.starved,
            "mean_wait_minutes": None if self.mean_wait_minutes is None else str(self.mean_wait_minutes),
            "p50_minutes": self.p50_minutes,
            "p95_minutes": self.p95_minutes,
        }


@dataclass(frozen=True)
class QueueReport:
    """What one simulation of the queue says: the schedule, the capacity and the waiting times.

    Why the report carries the assumption of the review time and the seed: a schedule that changed between two runs
    of the same experiment would make every number of the report unreadable, so the reader has to see what produced
    it (FR-011).
    """

    policy_name: str
    threshold: int
    order: str
    seed: int
    horizon_minutes: int
    reviewers: int
    arrivals_digest: str
    review_time: ReviewTime
    review_minutes: tuple[int, ...]
    events: tuple[QueueEvent, ...]
    backlog_over_time: tuple[tuple[int, int], ...]
    arrived: int
    completed: int
    backlog_at_horizon: int
    in_review_at_horizon: int
    utilization: Decimal | None
    throughput_per_hour: Decimal | None
    mean_wait_minutes: Decimal | None
    wait_p50_minutes: int | None
    wait_p95_minutes: int | None
    overloaded: bool
    steady_state_wait_minutes: Decimal | None
    steady_state_reason: str
    classes: tuple[ClassWait, ...]

    @property
    def critical_class(self) -> ClassWait | None:
        """The waiting time of the critical class, published apart from the others.

        Why it is None when there was no critical case: a class that never arrived has no waiting time, and a zero
        would say that the critical cases waited no time at all.
        """
        for class_wait in self.classes:
            if class_wait.name == CLASS_CRITICAL:
                return class_wait
        return None

    @property
    def starved_classes(self) -> tuple[str, ...]:
        """The names of the classes that never reached a reviewer."""
        return tuple(class_wait.name for class_wait in self.classes if class_wait.starved)

    def to_dict(self) -> dict[str, Any]:
        """The report as a dictionary, for the published result.

        Why the disclaimer travels with the numbers: a reader who sees the capacity of a queue without it can read it
        as a plan of a team, and the simulator has no authority to give one (FR-016).
        """
        steady_state = self.steady_state_wait_minutes
        return {
            "policy": {"name": self.policy_name, "threshold": self.threshold, "order": self.order},
            "seed": self.seed,
            "horizon_minutes": self.horizon_minutes,
            "reviewers": self.reviewers,
            "arrivals_digest": self.arrivals_digest,
            "review_time": {
                "minimum": self.review_time.minimum,
                "mode": self.review_time.mode,
                "maximum": self.review_time.maximum,
            },
            "review_minutes": list(self.review_minutes),
            "events": [event.to_dict() for event in self.events],
            "backlog_over_time": [list(point) for point in self.backlog_over_time],
            "arrived": self.arrived,
            "completed": self.completed,
            "backlog_at_horizon": self.backlog_at_horizon,
            "in_review_at_horizon": self.in_review_at_horizon,
            "utilization": None if self.utilization is None else str(self.utilization),
            "throughput_per_hour": None if self.throughput_per_hour is None else str(self.throughput_per_hour),
            "mean_wait_minutes": None if self.mean_wait_minutes is None else str(self.mean_wait_minutes),
            "wait_p50_minutes": self.wait_p50_minutes,
            "wait_p95_minutes": self.wait_p95_minutes,
            "overloaded": self.overloaded,
            "steady_state_wait_minutes": None if steady_state is None else str(steady_state),
            "steady_state_reason": self.steady_state_reason,
            "classes": [class_wait.to_dict() for class_wait in self.classes],
            "critical_class": None if self.critical_class is None else self.critical_class.to_dict(),
            "starved_classes": list(self.starved_classes),
            "disclaimer": NOT_A_STAFFING_PLAN,
        }


@dataclass(frozen=True)
class PolicyComparison:
    """The comparison of two policies of the queue over the same arrivals."""

    first: QueueReport
    second: QueueReport
    mean_wait_difference_minutes: Decimal | None
    p95_difference_minutes: int | None
    backlog_difference: int
    utilization_difference: Decimal | None

    def to_dict(self) -> dict[str, Any]:
        """The comparison as a dictionary, for the published result."""
        return {
            "arrivals_digest": self.first.arrivals_digest,
            "same_arrivals": True,
            "same_seed": self.first.seed == self.second.seed,
            "first": self.first.to_dict(),
            "second": self.second.to_dict(),
            "mean_wait_difference_minutes": (
                None
                if self.mean_wait_difference_minutes is None
                else str(self.mean_wait_difference_minutes)
            ),
            "p95_difference_minutes": self.p95_difference_minutes,
            "backlog_difference": self.backlog_difference,
            "utilization_difference": (
                None if self.utilization_difference is None else str(self.utilization_difference)
            ),
            "disclaimer": NOT_A_STAFFING_PLAN,
        }


def _digest_of(arrivals: Sequence[Arrival]) -> str:
    """The digest of the arrivals of an experiment.

    Why the arrivals and not the whole experiment: two policies are compared over the same arrivals, and the digest
    of the arrivals is what says that they were (FR-014).
    """
    body = json.dumps(
        [[arrival.at_minute, arrival.score, arrival.case_class] for arrival in arrivals],
        separators=(",", ":"),
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _draw_review_minutes(rng: random.Random, review_time: ReviewTime) -> int:
    """The minutes of one review, drawn from the distribution of the experiment.

    Why the draw is over whole minutes with a weight that grows up to the mode and falls after it: a distribution
    that a reader can reproduce with a pocket calculator is a distribution that can be checked, and the seed is the
    only thing that decides the draw.

    Why the draw uses integers and no float: the schedule of the reviewers is compared minute by minute, and a
    rounding of a float would move a case between two minutes without saying so.
    """
    low, mode, high = review_time.minimum, review_time.mode, review_time.maximum
    if high <= low:
        return low
    weights = [minute - low + 1 if minute <= mode else high - minute + 1 for minute in range(low, high + 1)]
    pick = rng.randrange(sum(weights))
    for minute, weight in zip(range(low, high + 1), weights, strict=True):
        if pick < weight:
            return minute
        pick -= weight
    return high


def _percentile(values: Sequence[int], percentile: int) -> int | None:
    """The percentile of the waiting times, by the nearest rank.

    Why the nearest rank and not an interpolation: the number of the waiting times is small and a percentile that
    lands between two waits is not a wait that anybody saw.
    """
    if not values:
        return None
    ordered = sorted(values)
    count = len(ordered)
    rank = (percentile * count + 99) // 100
    return ordered[min(max(rank, 1), count) - 1]


def _mean(values: Sequence[int]) -> Decimal | None:
    """The mean of the waiting times, or None when there is no wait at all."""
    if not values:
        return None
    return Decimal(sum(values)) / Decimal(len(values))


def simulate(experiment: QueueExperiment) -> QueueReport:
    """The simulation of the queue, and everything the report of it says.

    Why the arrivals are sorted and not taken as they come: the queue is ordered in the time, and an experiment whose
    arrivals were not ordered would make the schedule depend on the order the caller wrote them down.
    """
    ordered = tuple(sorted(experiment.arrivals, key=lambda arrival: arrival.at_minute))
    digest = _digest_of(ordered)
    rng = random.Random(experiment.seed)
    # The draw happens for every case, so that the seed of the experiment decides the same cases whatever they state.
    drawn = tuple(_draw_review_minutes(rng, experiment.review_time) for _ in ordered)
    durations = tuple(
        drawn[index] if arrival.review_minutes is None else arrival.review_minutes
        for index, arrival in enumerate(ordered)
    )

    horizon = experiment.horizon_minutes
    # The cases that the policy of the experiment sends to a person and that arrive inside the window.
    escalating = [
        (index, arrival)
        for index, arrival in enumerate(ordered)
        if arrival.score >= experiment.policy.threshold and arrival.at_minute <= horizon
    ]

    sequence = 0
    events: list[tuple[int, int, str, int, int]] = []
    trace: list[QueueEvent] = []
    backlog_over_time: list[tuple[int, int]] = []
    # The free minute of every reviewer, and the minutes it worked inside the window.
    free_at = [0] * experiment.reviewers
    busy_minutes = [0] * experiment.reviewers
    # The cases that arrived and wait for a reviewer, in the order they arrived.
    pending: list[tuple[int, int]] = []
    arrival_minute: dict[int, int] = {}
    start_minute: dict[int, int] = {}
    finish_minute: dict[int, int] = {}

    def _start(case_index: int, at: int, reviewer: int) -> None:
        """A reviewer takes a case, and the review ends later."""
        nonlocal sequence
        duration = durations[case_index]
        free_at[reviewer] = at + duration
        start_minute[case_index] = at
        busy_minutes[reviewer] += max(0, min(at + duration, horizon) - at)
        sequence += 1
        trace.append(QueueEvent(at, sequence, EVENT_START, case_index, reviewer))
        sequence += 1
        heapq.heappush(events, (at + duration, sequence, EVENT_FINISH, reviewer, case_index))

    def _next_case() -> int:
        """The case that a reviewer takes next, by the order of the policy.

        Why the order is read here and not in the loop: the order of the queue is a rule of the policy, and a rule
        that lives in two places is a rule that one of them will forget.
        """
        if experiment.policy.order == ORDER_EASIEST_FIRST:
            # The easiest case first, which is the order that starves the long cases when the capacity is short.
            return min(pending, key=lambda item: (durations[item[0]], item[1], item[0]))[0]
        # The queue is filled in the order of the arrival, so the first of the list is the one that waited the most.
        return pending[0][0]

    index = 0
    # The events of the queue: an arrival and a finish, in the order of the time and of the sequence.
    while index < len(escalating) or events:
        next_arrival = escalating[index][1].at_minute if index < len(escalating) else None
        next_finish = events[0][0] if events else None
        if next_finish is None or (next_arrival is not None and next_arrival <= next_finish):
            case_index, arrival = escalating[index]
            at = arrival.at_minute
            index += 1
            sequence += 1
            trace.append(QueueEvent(at, sequence, EVENT_ARRIVAL, case_index, None))
            arrival_minute[case_index] = at
            if pending:
                # The queue is not empty, so the case waits and it never jumps the line.
                pending.append((case_index, at))
            else:
                free = [slot for slot in range(experiment.reviewers) if free_at[slot] <= at]
                if free:
                    reviewer = min(free, key=lambda slot: (free_at[slot], slot))
                    _start(case_index, at, reviewer)
                else:
                    pending.append((case_index, at))
            backlog_over_time.append((at, len(pending)))
            continue

        at, sequence_finish, _, reviewer, case_index = heapq.heappop(events)
        trace.append(QueueEvent(at, sequence_finish, EVENT_FINISH, case_index, reviewer))
        finish_minute[case_index] = at
        if pending:
            chosen = _next_case()
            pending.remove((chosen, arrival_minute[chosen]))
            _start(chosen, at, reviewer)
        backlog_over_time.append((at, len(pending)))

    return _report_of(
        experiment,
        digest,
        durations,
        trace,
        backlog_over_time,
        ordered,
        arrival_minute,
        start_minute,
        finish_minute,
        busy_minutes,
    )


def _report_of(
    experiment: QueueExperiment,
    digest: str,
    durations: tuple[int, ...],
    trace: list[QueueEvent],
    backlog_over_time: list[tuple[int, int]],
    ordered: tuple[Arrival, ...],
    arrival_minute: dict[int, int],
    start_minute: dict[int, int],
    finish_minute: dict[int, int],
    busy_minutes: list[int],
) -> QueueReport:
    """The report of a simulation, read out of the schedule that the simulation worked out."""
    horizon = experiment.horizon_minutes
    reviewers = experiment.reviewers

    arrived = sorted(arrival_minute)
    started_in_window = [case for case, minute in start_minute.items() if minute <= horizon]
    completed = [case for case, minute in finish_minute.items() if minute <= horizon]
    backlog_at_horizon = len([case for case in arrived if start_minute.get(case, horizon + 1) > horizon])
    in_review_at_horizon = len(
        [
            case
            for case in started_in_window
            if finish_minute.get(case, horizon + 1) > horizon
        ]
    )

    total_busy = sum(busy_minutes)
    utilization = None
    if reviewers > 0:
        utilization = Decimal(total_busy) / Decimal(reviewers * horizon)
    overloaded = utilization is not None and utilization >= 1

    waits = [start_minute[case] - arrival_minute[case] for case in started_in_window]
    mean_wait = _mean(waits)
    p50 = _percentile(waits, _PERCENTILE_50)
    p95 = _percentile(waits, _PERCENTILE_95)

    throughput = None
    if horizon > 0:
        throughput = Decimal(len(completed)) * Decimal(60) / Decimal(horizon)

    # The area under the number of the cases that were in the system, which is what Little's Law needs.
    area = 0
    for case in arrived:
        end = min(finish_minute.get(case, horizon), horizon)
        area += max(0, end - arrival_minute[case])
    steady_state: Decimal | None = None
    steady_state_reason = ""
    if reviewers == 0:
        steady_state_reason = "no reviewer is serving, so the queue has no steady state to publish"
    elif overloaded:
        steady_state_reason = (
            "the utilization reached one, so the system is overloaded and there is no finite steady state waiting "
            "time to publish"
        )
    elif not completed:
        steady_state_reason = "no case was completed inside the window, so there is no steady state to publish"
    else:
        steady_state = Decimal(area) / Decimal(len(completed))
        steady_state_reason = (
            "the mean time in the system over the window, read with the law of Little and only while the system is "
            "not overloaded"
        )

    classes: list[ClassWait] = []
    names = {ordered[case].case_class for case in arrived} | {arrival.case_class for arrival in ordered}
    for name in sorted(names):
        of_class = [case for case in arrived if ordered[case].case_class == name]
        served = [case for case in of_class if start_minute.get(case, horizon + 1) <= horizon]
        class_waits = [start_minute[case] - arrival_minute[case] for case in served]
        classes.append(
            ClassWait(
                name=name,
                arrived=len(of_class),
                served=len(served),
                starved=bool(of_class) and len(served) < len(of_class),
                mean_wait_minutes=_mean(class_waits),
                p50_minutes=_percentile(class_waits, _PERCENTILE_50),
                p95_minutes=_percentile(class_waits, _PERCENTILE_95),
            )
        )

    return QueueReport(
        policy_name=experiment.policy.name,
        threshold=experiment.policy.threshold,
        order=experiment.policy.order,
        seed=experiment.seed,
        horizon_minutes=horizon,
        reviewers=reviewers,
        arrivals_digest=digest,
        review_time=experiment.review_time,
        review_minutes=durations,
        events=tuple(sorted(trace, key=lambda event: (event.at_minute, event.sequence))),
        backlog_over_time=tuple(point for point in backlog_over_time if point[0] <= horizon),
        arrived=len(arrived),
        completed=len(completed),
        backlog_at_horizon=backlog_at_horizon,
        in_review_at_horizon=in_review_at_horizon,
        utilization=utilization,
        throughput_per_hour=throughput,
        mean_wait_minutes=mean_wait,
        wait_p50_minutes=p50,
        wait_p95_minutes=p95,
        overloaded=overloaded,
        steady_state_wait_minutes=steady_state,
        steady_state_reason=steady_state_reason,
        classes=tuple(classes),
    )


def compare_policies(first: QueueReport, second: QueueReport) -> PolicyComparison:
    """The comparison of two policies over the same arrivals, or a refusal when the arrivals differ.

    Why the digest and not the name of the policy: the name is what a caller typed and the digest is what the
    arrivals are, and only the second one can tell that the two policies saw the same cases (FR-014).
    """
    if first.arrivals_digest != second.arrivals_digest:
        raise ValueError(
            "the two policies were not compared over the same arrivals, so the comparison is refused: the digest of "
            f"the first is {first.arrivals_digest!r} and the digest of the second is {second.arrivals_digest!r}"
        )
    mean_difference = None
    if first.mean_wait_minutes is not None and second.mean_wait_minutes is not None:
        mean_difference = second.mean_wait_minutes - first.mean_wait_minutes
    p95_difference = None
    if first.wait_p95_minutes is not None and second.wait_p95_minutes is not None:
        p95_difference = second.wait_p95_minutes - first.wait_p95_minutes
    utilization_difference = None
    if first.utilization is not None and second.utilization is not None:
        utilization_difference = second.utilization - first.utilization
    return PolicyComparison(
        first=first,
        second=second,
        mean_wait_difference_minutes=mean_difference,
        p95_difference_minutes=p95_difference,
        backlog_difference=second.backlog_at_horizon - first.backlog_at_horizon,
        utilization_difference=utilization_difference,
    )
