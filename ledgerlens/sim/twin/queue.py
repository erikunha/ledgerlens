"""The queue of the twin: the capacity of the slots, the service time and the condition of the run.

Why the condition of the queue is a label and not a number: a run is either in a steady state or it is
labelled `queue_never_drains`, and there is no third state and no number for a run that never drained, because
the throughput of such a run is a property of the horizon and not of the system.

Why the capacity is a number of slots and never a number of people: the repository has no people in it, and a
number of people would be a claim the twin cannot support. The slots are a capacity, and the report says
"slots" and never "analysts".
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ledgerlens.sim.twin.arrivals import ArrivalStream
from ledgerlens.sim.twin.config import TwinConfig

__all__ = ["QueueOutcome", "QueueRefused", "serve"]

# The label of a run whose queue never drains: the queue grows without bound over the horizon, and the
# throughput of such a run is a property of the horizon and not of the system.
QUEUE_NEVER_DRAINS = "queue_never_drains"
STEADY_STATE = "steady_state"


class QueueRefused(Exception):
    """The queue is refused, and the message says why."""


@dataclass(frozen=True)
class QueueOutcome:
    """The outcome of the queue of a run: the condition of the run, and the figures of the service.

    Why the throughput is None when the queue never drains: the throughput of a run that never drained is a
    property of the horizon and not of the system, and a number that does not exist is never published as a
    number.
    """

    label: str
    served: int
    waiting_at_the_end: int
    throughput_per_hour: Decimal | None
    busiest_wait_minutes: int


def serve(config: TwinConfig, stream: ArrivalStream) -> QueueOutcome:
    """The queue of a run over the stream of the arrivals: the condition of the run and the figures of the service.

    Why the service is computed and never written: the waiting time of a case is the time it waited for a
    slot, and the number of a wait that a model wrote would carry the authority of a measurement without
    having the evidence of one. The queue is a discrete event simulation over the stream.
    """
    if config.slots < 1:
        raise QueueRefused(f"the capacity of the run is {config.slots} slot(s) and it must be at least 1")
    # The slots are the servers of the queue: each one serves a case for the service time, and a case that
    # arrives with no free slot waits. The queue is simulated minute by minute over the horizon.
    free_at = [0] * config.slots  # the minute each slot is free again
    served = 0
    waiting_at_the_end = 0
    busiest_wait = 0
    pending: list[tuple[int, str]] = []  # the cases that wait for a slot, in the order of the arrival
    arrivals = list(stream.arrivals)
    cursor = 0
    for minute in range(config.horizon_minutes + 1):
        while cursor < len(arrivals) and arrivals[cursor].minute <= minute:
            pending.append((arrivals[cursor].minute, arrivals[cursor].kind))
            cursor += 1
        # The slots that are free take the next case of the queue.
        for slot in range(config.slots):
            if free_at[slot] <= minute and pending:
                arrived, _kind = pending.pop(0)
                busiest_wait = max(busiest_wait, minute - arrived)
                free_at[slot] = minute + int(config.service_time_minutes)
                served += 1
    waiting_at_the_end = len(pending)
    if waiting_at_the_end and served == 0:
        label = QUEUE_NEVER_DRAINS
    elif waiting_at_the_end and _never_drains(config, stream):
        label = QUEUE_NEVER_DRAINS
    else:
        label = STEADY_STATE
    throughput = None
    if label == STEADY_STATE:
        hours = Decimal(config.horizon_minutes) / Decimal(60)
        throughput = (Decimal(served) / hours).quantize(Decimal("0.01"))
    return QueueOutcome(
        label=label,
        served=served,
        waiting_at_the_end=waiting_at_the_end,
        throughput_per_hour=throughput,
        busiest_wait_minutes=busiest_wait,
    )


def _never_drains(config: TwinConfig, stream: ArrivalStream) -> bool:
    """Whether the queue never drains: the arrivals outpace the service over the whole horizon.

    Why the condition is computed and not read from the end of the queue: a queue that ends with cases waiting
    is not always a queue that never drains, and the condition of the run is the condition of the system, and
    not the condition of one horizon.
    """
    service_per_hour = Decimal(config.slots) * (Decimal(60) / config.service_time_minutes)
    return config.arrival_rate_per_hour > service_per_hour
