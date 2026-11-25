"""The arrival stream of the twin: the count follows the declared distribution, and the digest is recorded.

What they guarantee, and why: (a) the count of the arrivals follows the declared distribution over a long
horizon, because the stream is generated from the seed with the declared distribution and a stream that did
not follow it would be a stream of another model; (b) the stream is the same for the same seed, because the
stream is generated once and read by every run of a comparison; (c) the digest of the stream is recorded in
the manifest, because the reader of a run knows which stream the run measured.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from ledgerlens.sim.twin.arrivals import digest_of, generate_stream
from ledgerlens.sim.twin.config import TwinConfig
from ledgerlens.sim.twin.run import run_twin


def test_the_count_of_the_arrivals_follows_the_declared_distribution() -> None:
    """Over a long horizon, the count of the arrivals is near the rate of the distribution."""
    config = TwinConfig(seed=42, horizon_minutes=60 * 100, arrival_rate_per_hour=Decimal("6"))
    stream = generate_stream(config)

    hours = 100
    expected = 6 * hours
    assert 0.7 * expected <= len(stream.arrivals) <= 1.3 * expected
    assert "exponential" in stream.distribution


def test_the_stream_is_the_same_for_the_same_seed() -> None:
    """Two generations of the same seed give the same stream, and the digest is the same."""
    config = TwinConfig(seed=42)
    first = generate_stream(config)
    second = generate_stream(config)

    assert first.arrivals == second.arrivals
    assert digest_of(first) == digest_of(second)


def test_the_digest_of_the_stream_is_recorded_in_the_manifest() -> None:
    """The reader of a run knows which stream the run measured."""
    config = TwinConfig(seed=42)
    run = run_twin(config, truth_path=Path("data/scenarios.json"), commit="abc123")

    assert run.manifest.stream_sha256 == digest_of(run.stream)
