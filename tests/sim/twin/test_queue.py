"""The queue of the twin: a queue that never drains is a label and not a number.

What they guarantee, and why: (a) a capacity of one slot and an arrival rate above the service rate carries
the label `queue_never_drains` and publishes no throughput, because the throughput of a run that never drained
is a property of the horizon and not of the system; (b) a capacity that is large enough publishes a
throughput, because a queue that drains has a throughput that is a property of the system; (c) a capacity of
zero is refused, because a capacity of zero is not a capacity.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ledgerlens.sim.twin.arrivals import generate_stream
from ledgerlens.sim.twin.config import TwinConfig
from ledgerlens.sim.twin.queue import QUEUE_NEVER_DRAINS, STEADY_STATE, QueueRefused, serve


def _stream(config: TwinConfig):
    """The stream of the arrivals of the configuration."""
    return generate_stream(config)


def test_a_queue_that_never_drains_carries_the_label_and_publishes_no_throughput() -> None:
    """One slot and an arrival rate above the service rate: the label and no number."""
    config = TwinConfig(slots=1, arrival_rate_per_hour=Decimal("30"), service_time_minutes=Decimal("15"))
    outcome = serve(config, _stream(config))

    assert outcome.label == QUEUE_NEVER_DRAINS
    assert outcome.throughput_per_hour is None


def test_a_capacity_that_is_large_enough_publishes_a_throughput() -> None:
    """A queue that drains has a throughput that is a property of the system."""
    config = TwinConfig(slots=4, arrival_rate_per_hour=Decimal("6"), service_time_minutes=Decimal("15"))
    outcome = serve(config, _stream(config))

    assert outcome.label == STEADY_STATE
    assert outcome.throughput_per_hour is not None
    assert outcome.throughput_per_hour > 0


def test_a_capacity_of_zero_is_refused() -> None:
    """A capacity of zero is not a capacity."""
    config = TwinConfig(slots=0)
    with pytest.raises(QueueRefused, match="at least 1"):
        serve(config, _stream(config))
