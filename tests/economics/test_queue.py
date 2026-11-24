"""The simulator of the queue of the review.

What they guarantee, and why: (a) two runs of the same experiment with the same seed give the same schedule, because
a schedule that moved between two runs would make every number of the report unreadable; (b) a queue with no reviewer
publishes no utilization and does not divide by zero; (c) an overloaded queue publishes no finite steady state wait,
because there is none; (d) two policies are compared only over the same arrivals; (e) the waiting time of the
critical class is published apart from the others and a class that waits for ever is reported as starved; (f) the
report never reads as a plan of a team and never as a measurement of the interface.

The fixture of the schedule holds two reviewers, four arrivals and a review time of five minutes, so the schedule
below can be worked out by hand and written in the test.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ledgerlens.economics.queue import (
    CLASS_CRITICAL,
    CLASS_ORDINARY,
    EVENT_ARRIVAL,
    EVENT_FINISH,
    EVENT_START,
    NOT_A_STAFFING_PLAN,
    ORDER_EASIEST_FIRST,
    ORDER_FIFO,
    Arrival,
    QueueExperiment,
    QueuePolicy,
    ReviewTime,
    compare_policies,
    simulate,
)

# The review time of the fixture: five minutes for every case, so the schedule can be worked out by hand.
FIXED = ReviewTime(minimum=5, mode=5, maximum=5)


def _experiment(
    *,
    arrivals: tuple[Arrival, ...],
    reviewers: int = 2,
    threshold: int = 5,
    order: str = ORDER_FIFO,
    horizon: int = 12,
    review_time: ReviewTime = FIXED,
    seed: int = 7,
) -> QueueExperiment:
    """An experiment over the arrivals that the test hands over."""
    return QueueExperiment(
        arrivals=arrivals,
        reviewers=reviewers,
        policy=QueuePolicy(name="the policy of the test", threshold=threshold, order=order),
        review_time=review_time,
        seed=seed,
        horizon_minutes=horizon,
    )


# The four arrivals of the fixture: they arrive at the minutes 0, 2, 4 and 6 and every one of them asks for a person.
THE_FOUR = (
    Arrival(at_minute=0, score=5),
    Arrival(at_minute=2, score=5),
    Arrival(at_minute=4, score=5),
    Arrival(at_minute=6, score=5),
)


def test_the_schedule_of_the_fixture_is_the_one_a_reader_can_work_out() -> None:
    """Two reviewers, four arrivals and five minutes of review give a schedule that the test writes down.

    Why it matters: a simulator of a queue is only trustworthy when a reader can check one of its schedules by hand.
    """
    report = simulate(_experiment(arrivals=THE_FOUR))

    starts = [(event.case_index, event.at_minute) for event in report.events if event.type == EVENT_START]
    assert starts == [(0, 0), (1, 2), (2, 5), (3, 7)]
    # The case that arrived at the minute 4 waited one minute and the case that arrived at the minute 6 waited one.
    assert report.mean_wait_minutes is not None
    assert report.mean_wait_minutes == pytest.approx(0.5)
    assert report.completed == 4
    assert report.backlog_at_horizon == 0


def test_two_runs_of_the_same_experiment_with_the_same_seed_are_the_same() -> None:
    """The seed decides the schedule, and the schedule of two runs does not move."""
    first = simulate(_experiment(arrivals=THE_FOUR))
    second = simulate(_experiment(arrivals=THE_FOUR))

    assert first.to_dict() == second.to_dict()


def test_two_runs_with_a_different_seed_can_differ() -> None:
    """The seed is what decides the draw, and a different seed draws a different review time.

    Why it matters: a simulator whose seed changed nothing would be hiding the assumption it rests on.
    """
    spread = ReviewTime(minimum=2, mode=5, maximum=10)
    first = simulate(_experiment(arrivals=THE_FOUR, review_time=spread, seed=1))
    second = simulate(_experiment(arrivals=THE_FOUR, review_time=spread, seed=2))

    assert first.review_minutes != second.review_minutes


def test_a_queue_with_no_reviewer_publishes_no_utilization_and_does_not_divide() -> None:
    """A queue that nobody serves has no utilization and no mean wait, and it does not raise."""
    report = simulate(_experiment(arrivals=THE_FOUR, reviewers=0, horizon=30))

    assert report.utilization is None
    assert report.mean_wait_minutes is None
    assert report.completed == 0
    assert report.backlog_at_horizon == 4
    assert report.steady_state_wait_minutes is None
    assert "no reviewer" in report.steady_state_reason


def test_an_overloaded_queue_publishes_no_finite_steady_state_wait() -> None:
    """A queue whose utilization reached one has no steady state, and the report says so."""
    # One reviewer, a case every two minutes and six minutes of review: the reviewer never catches up.
    arrivals = tuple(Arrival(at_minute=minute, score=5) for minute in range(0, 24, 2))
    report = simulate(_experiment(arrivals=arrivals, reviewers=1, horizon=24, review_time=ReviewTime(6, 6, 6)))

    assert report.utilization is not None
    assert report.utilization == 1
    assert report.overloaded is True
    assert report.steady_state_wait_minutes is None
    assert "overloaded" in report.steady_state_reason


def test_a_queue_that_is_not_overloaded_publishes_a_steady_state_wait() -> None:
    """A queue with room to breathe publishes the mean time in the system of the window."""
    report = simulate(_experiment(arrivals=THE_FOUR))

    assert report.overloaded is False
    assert report.steady_state_wait_minutes is not None
    assert report.steady_state_wait_minutes > 0


def test_two_policies_are_compared_over_the_same_arrivals() -> None:
    """The comparison refuses two policies that did not see the same arrivals."""
    first = simulate(_experiment(arrivals=THE_FOUR))
    other = simulate(_experiment(arrivals=THE_FOUR + (Arrival(at_minute=8, score=5),)))
    second = simulate(_experiment(arrivals=THE_FOUR))

    with pytest.raises(ValueError, match="the same arrivals"):
        compare_policies(first, other)
    comparison = compare_policies(first, second)
    assert comparison.to_dict()["same_arrivals"] is True


def test_a_threshold_that_rises_sends_fewer_cases_to_a_person() -> None:
    """The policy with the higher threshold escalates less, over the same arrivals."""
    low = simulate(_experiment(arrivals=THE_FOUR, threshold=5))
    high = simulate(_experiment(arrivals=THE_FOUR, threshold=9))

    assert low.arrived == 4
    assert high.arrived == 0
    assert low.arrivals_digest == high.arrivals_digest


def test_the_waiting_time_of_the_critical_class_is_published_apart() -> None:
    """The critical class has its own line in the report and not only a part of the mean."""
    arrivals = (
        Arrival(at_minute=0, score=5, case_class=CLASS_CRITICAL),
        Arrival(at_minute=0, score=5, case_class=CLASS_ORDINARY),
    )
    report = simulate(_experiment(arrivals=arrivals, reviewers=1, horizon=20))

    critical = report.critical_class
    assert critical is not None
    assert critical.name == CLASS_CRITICAL
    assert critical.arrived == 1
    assert critical.served == 1
    assert critical.starved is False
    assert critical.p50_minutes == 0
    # The ordinary case of the same minute waited, and the report says so apart from the critical one.
    ordinary = [class_wait for class_wait in report.classes if class_wait.name == CLASS_ORDINARY]
    assert ordinary and ordinary[0].p50_minutes == 5
    published = report.to_dict()
    assert published["critical_class"]["name"] == CLASS_CRITICAL


def test_a_class_that_waits_for_ever_is_reported_as_starved() -> None:
    """A priority that serves the easy cases first starves the critical ones, and the report names it."""
    # One reviewer, the easy cases arrive first and the critical case is the slowest one of all.
    arrivals = (
        Arrival(at_minute=0, score=5, case_class=CLASS_ORDINARY, review_minutes=2),
        Arrival(at_minute=1, score=5, case_class=CLASS_ORDINARY, review_minutes=2),
        Arrival(at_minute=2, score=5, case_class=CLASS_ORDINARY, review_minutes=2),
        Arrival(at_minute=3, score=5, case_class=CLASS_CRITICAL, review_minutes=20),
    )
    report = simulate(
        _experiment(arrivals=arrivals, reviewers=1, horizon=5, order=ORDER_EASIEST_FIRST)
    )

    critical = report.critical_class
    assert critical is not None
    assert critical.starved is True
    assert critical.served == 0
    assert critical.arrived == 1
    assert report.starved_classes == (CLASS_CRITICAL,)
    assert report.backlog_at_horizon == 1


def test_the_same_arrivals_with_the_order_of_the_arrival_serve_the_critical_case() -> None:
    """The order of the arrival does not starve the critical class, and the report says that it did not."""
    arrivals = (
        Arrival(at_minute=0, score=5, case_class=CLASS_ORDINARY, review_minutes=2),
        Arrival(at_minute=1, score=5, case_class=CLASS_ORDINARY, review_minutes=2),
        Arrival(at_minute=2, score=5, case_class=CLASS_ORDINARY, review_minutes=2),
        Arrival(at_minute=3, score=5, case_class=CLASS_CRITICAL, review_minutes=20),
    )
    report = simulate(_experiment(arrivals=arrivals, reviewers=1, horizon=30, order=ORDER_FIFO))

    critical = report.critical_class
    assert critical is not None
    assert critical.starved is False
    assert critical.served == 1
    assert report.starved_classes == ()


def test_the_report_never_reads_as_a_plan_of_a_team() -> None:
    """The capacity of the queue is a number of a simulation and not an advice about a team."""
    report = simulate(_experiment(arrivals=THE_FOUR))

    published = report.to_dict()
    assert published["disclaimer"] == NOT_A_STAFFING_PLAN
    for key in published:
        for word in ("staff", "headcount", "hire", "employee", "fte"):
            assert word not in key.lower(), key


def test_the_report_never_reads_the_latency_of_the_interface_as_the_work_of_a_reviewer() -> None:
    """The work time of a reviewer is the assumption of the experiment and never a measured latency."""
    report = simulate(_experiment(arrivals=THE_FOUR))

    published = report.to_dict()
    assert "latency" not in published
    assert published["review_time"] == {"minimum": 5, "mode": 5, "maximum": 5}
    assert published["review_minutes"] == [5, 5, 5, 5]


def test_the_simulator_holds_no_identity_of_a_visitor() -> None:
    """The arrival of a case carries the moment, the strength and the class, and nothing about a person."""
    fields = set(Arrival.__dataclass_fields__)
    assert fields == {"at_minute", "score", "case_class", "review_minutes"}

    report = simulate(_experiment(arrivals=THE_FOUR))
    for event in report.events:
        assert event.case_index is not None
        assert isinstance(event.case_index, int)
        assert event.reviewer is None or isinstance(event.reviewer, int)


def test_the_simulator_never_imports_the_api_and_never_calls_a_model() -> None:
    """The queue is a leaf of the domain, like the rest of the economics."""
    package = Path(__file__).resolve().parents[2] / "ledgerlens" / "economics"
    forbidden_prefixes = ("ledgerlens.api", "ledgerlens.offline", "ledgerlens.config", "ledgerlens.agents")

    for module in sorted(package.glob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert not name.startswith(forbidden_prefixes), f"{module.name} imports {name}"


def test_the_events_of_the_queue_carry_the_three_kinds_and_a_stable_order() -> None:
    """The trace of the queue holds the arrival, the start and the finish, and the order never moves."""
    report = simulate(_experiment(arrivals=THE_FOUR))

    kinds = {event.type for event in report.events}
    assert kinds == {EVENT_ARRIVAL, EVENT_START, EVENT_FINISH}
    keys = [(event.at_minute, event.sequence) for event in report.events]
    assert keys == sorted(keys)
    assert len({event.sequence for event in report.events}) == len(report.events)
