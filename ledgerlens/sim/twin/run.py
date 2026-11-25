"""The run of the twin: the stream, the queue and the manifest of a run, deterministic in the seed.

Why the run is deterministic in the seed: two runs of the same configuration with the same seed produce a
byte for byte equal manifest, and so does a third run with another hash seed of the interpreter, because the
bytes of the manifest do not depend on the machine that wrote them.

Why the run reads the truth and the stream and writes the manifest: the reader of a run knows which world the
run measured and which stream of arrivals it read, and a run that named neither would be a run that the
reader cannot place.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from ledgerlens.sim.twin.arrivals import ArrivalStream, generate_stream
from ledgerlens.sim.twin.arrivals import digest_of as stream_digest
from ledgerlens.sim.twin.config import TwinConfig, validate
from ledgerlens.sim.twin.manifest import TwinManifest
from ledgerlens.sim.twin.queue import QueueOutcome, serve

__all__ = ["TwinRun", "rebuild_projection", "run_twin", "sha256_of"]


@dataclass(frozen=True)
class TwinRun:
    """The run of the twin: the manifest of the run, the outcome of the queue and the stream it read."""

    manifest: TwinManifest
    queue: QueueOutcome
    stream: ArrivalStream


def sha256_of(path: Path) -> str:
    """The sha256 of the file, for the digest of the truth of the manifest."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rebuild_projection(db_path: Path) -> str:
    """The digest of the projected tables after a rebuild of the projector of the ledger.

    Why the digest survives a restart: the projection of the ledger is a pure function of the event log, so a
    rebuild of the projector gives the same digest as the projection it rebuilt, and the order of the ids of
    the events is the same. A rebuild that changed the digest would be a rebuild of another world.
    """
    import sqlite3

    from ledgerlens.sim.projector import canonical_hash, rebuild_database

    source = sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True)
    try:
        rebuilt = rebuild_database(source)
        try:
            return canonical_hash(rebuilt)
        finally:
            rebuilt.close()
    finally:
        source.close()


def run_twin(
    config: TwinConfig,
    *,
    truth_path: Path,
    commit: str,
    known_merchants: frozenset[str] | None = None,
    stream: ArrivalStream | None = None,
) -> TwinRun:
    """The run of the twin over the configuration: the stream, the queue and the manifest.

    Why the stream may be given and not generated: the second run of a paired comparison reads the stored
    stream of the first run, and a run that generated a second stream would be a run of another comparison.
    """
    validate(config, known_merchants=known_merchants)
    arrivals = stream if stream is not None else generate_stream(config)
    queue = serve(config, arrivals)
    manifest = TwinManifest(
        truth_sha256=sha256_of(truth_path),
        provenance="the versioned sample of the repository",
        assumptions=(
            arrivals.distribution,
            f"the capacity of {config.slots} slot(s) with the service time of {config.service_time_minutes} minutes",
            f"the review policy {config.review_policy}",
        ),
        stream_sha256=stream_digest(arrivals),
        commit=commit,
        label=queue.label,
        config={
            "seed": config.seed,
            "horizon_minutes": config.horizon_minutes,
            "arrival_rate_per_hour": str(config.arrival_rate_per_hour),
            "slots": config.slots,
            "service_time_minutes": str(config.service_time_minutes),
            "review_policy": config.review_policy,
        },
    )
    return TwinRun(manifest=manifest, queue=queue, stream=arrivals)
