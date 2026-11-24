"""The arrival stream of the twin: the cases that arrive, generated once from the seed and read by every run.

Why the distribution is a model and never a measurement: the repository has no arrival data, so the
distribution of the arrivals is a model of the repository. The stream is generated from the seed with the
declared distribution, and the distribution is written in the manifest of the run as an assumption, never
presented as a measurement of a real operation.

Why the stream is generated once and stored: a paired comparison of two policies reads the same stream, and a
comparison over two streams measures the difference between the streams and not the difference between the
policies. The second run of a comparison reads the stored stream and refuses to generate another one.

Why the stream has a digest: the digest of the stream is in the manifest of the run, so the reader of a run
knows which stream the run measured, and two runs over the same stream have the same digest.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from decimal import Decimal

from ledgerlens.sim.twin.config import TwinConfig

__all__ = ["Arrival", "ArrivalStream", "canonical_bytes", "digest_of", "generate_stream"]

# The mix of the kinds of the cases of the stream, with the share of each kind. The mix is part of the model,
# and it is written in the manifest of the run as an assumption.
CASE_MIX: tuple[tuple[str, Decimal], ...] = (
    ("refund", Decimal("0.5")),
    ("chargeback", Decimal("0.3")),
    ("fx", Decimal("0.2")),
)


@dataclass(frozen=True)
class Arrival:
    """One arrival of the stream: the minute it arrives and the kind of the case."""

    minute: int
    kind: str


@dataclass(frozen=True)
class ArrivalStream:
    """The stream of the arrivals of a run: the arrivals in the order they arrive, and the seed of them."""

    arrivals: tuple[Arrival, ...]
    seed: int
    distribution: str


def generate_stream(config: TwinConfig) -> ArrivalStream:
    """The stream of the arrivals of a run, generated once from the seed with the declared distribution.

    Why the inter-arrival times are exponential: the arrival of a case is the arrival of a customer, and the
    exponential inter-arrival time is the model of the arrivals that the repository declares. The model is
    written in the manifest, and it is not a measurement of a real operation.
    """
    rng = random.Random(f"{config.seed}:arrivals")
    rate_per_minute = float(config.arrival_rate_per_hour) / 60.0
    kinds = [kind for kind, _ in CASE_MIX]
    shares = [float(share) for _, share in CASE_MIX]
    arrivals: list[Arrival] = []
    minute = 0.0
    while True:
        minute += rng.expovariate(rate_per_minute) if rate_per_minute > 0 else config.horizon_minutes + 1
        if minute > config.horizon_minutes:
            break
        arrivals.append(Arrival(minute=int(minute), kind=rng.choices(kinds, weights=shares, k=1)[0]))
    distribution = (
        f"exponential inter-arrival times with the rate of {config.arrival_rate_per_hour} cases per hour, "
        f"over the horizon of {config.horizon_minutes} minutes, with the mix of the kinds "
        f"{[(kind, str(share)) for kind, share in CASE_MIX]}"
    )
    return ArrivalStream(arrivals=tuple(arrivals), seed=config.seed, distribution=distribution)


def canonical_bytes(stream: ArrivalStream) -> bytes:
    """The canonical form of the stream: the arrivals and the seed, with sorted keys and no clock."""
    return json.dumps(
        {
            "arrivals": [{"minute": arrival.minute, "kind": arrival.kind} for arrival in stream.arrivals],
            "seed": stream.seed,
            "distribution": stream.distribution,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def digest_of(stream: ArrivalStream) -> str:
    """The digest of the stream: the sha256 of the canonical bytes of it."""
    return hashlib.sha256(canonical_bytes(stream)).hexdigest()
