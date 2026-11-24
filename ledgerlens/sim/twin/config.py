"""The configuration of a run of the twin: what the run simulates, and the refusal of what cannot be simulated.

Why the refusal happens before any write: a configuration that cannot be simulated is refused before anything
is written, because a run that wrote a manifest for a configuration that is not valid is a run that published
a number about nothing.

Why the configuration is typed: the fields of a run of the twin are the fields of the model, and a field that
is not typed is a field that a caller can write anything into, and the model would read it as a number.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

__all__ = ["TwinConfig", "TwinConfigRefused", "validate"]


class TwinConfigRefused(Exception):
    """The configuration of the twin is refused, and the message names the field that is wrong."""


@dataclass(frozen=True)
class TwinConfig:
    """The configuration of a run of the twin: the seed, the horizon, the arrivals, the capacity and the policy.

    Why the arrival distribution is a parameter and not a fit: the repository has no arrival data, so the
    distribution of the arrivals is a model of the repository, and it is written in the manifest of the run as
    an assumption, never presented as a measurement.

    Why the capacity is a number of slots and never a number of people: the repository has no people in it,
    and a number of people would be a claim the twin cannot support.
    """

    seed: int = 42
    horizon_minutes: int = 480
    arrival_rate_per_hour: Decimal = Decimal("6")
    slots: int = 2
    service_time_minutes: Decimal = Decimal("15")
    review_policy: str = "shipped"
    merchants: tuple[str, ...] = ()
    extra: dict = field(default_factory=dict, compare=False)


def validate(config: TwinConfig, *, known_merchants: frozenset[str] | None = None) -> TwinConfig:
    """The configuration, validated, and the refusal of what cannot be simulated.

    Why the refusal names the field: a refusal that does not name the field that is wrong is a refusal that
    the caller cannot act on, and the message of the refusal names the field and the value.
    """
    if config.horizon_minutes <= 0:
        raise TwinConfigRefused(
            f"the horizon of the run is {config.horizon_minutes} and it must be at least 1 minute"
        )
    if config.slots < 1:
        raise TwinConfigRefused(f"the capacity of the run is {config.slots} slot(s) and it must be at least 1")
    if config.arrival_rate_per_hour < 0:
        raise TwinConfigRefused(
            f"the arrival rate of the run is {config.arrival_rate_per_hour} and it must not be negative"
        )
    if config.service_time_minutes <= 0:
        raise TwinConfigRefused(
            f"the service time of the run is {config.service_time_minutes} and it must be more than 0"
        )
    for name, value in config.extra.items():
        if not name.isidentifier():
            raise TwinConfigRefused(f"the field {name!r} of the configuration is not a field of the model")
        if value is None:
            raise TwinConfigRefused(f"the field {name!r} of the configuration has no value")
    if known_merchants is not None:
        unknown = set(config.merchants) - set(known_merchants)
        if unknown:
            raise TwinConfigRefused(
                f"the merchant(s) {sorted(unknown)} are not in the ledger, and the twin reads the ledger "
                "of the repository"
            )
    return config
