"""The manifest of a run of the twin: which world the run measured and under which assumptions.

Why the manifest is canonical: the bytes of the manifest do not depend on the machine that wrote them, so two
runs of the same configuration produce the same bytes on two machines. The manifest has no clock and no path
of the machine, because a manifest that carried them would be a manifest that a reader could not reproduce.

Why the manifest carries the digest of the truth and the digest of the stream: the reader of a run knows
which world the run measured and which stream of arrivals it read, and a run that named neither would be a
run that the reader cannot place.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

__all__ = ["TwinManifest", "canonical_bytes", "digest_of"]


@dataclass(frozen=True)
class TwinManifest:
    """The manifest of a run of the twin: the truth, the provenance, the assumptions, the stream and the label.

    Why the label is a field of the manifest: a run whose condition was not determined is not published, and
    the label of the run is the condition of it, so the reader of the manifest knows whether the numbers of
    the run are numbers of a steady state or of a queue that never drains.
    """

    truth_sha256: str
    provenance: str
    assumptions: tuple[str, ...]
    stream_sha256: str
    commit: str
    label: str  # "steady_state" or "queue_never_drains"
    config: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """The manifest as a dictionary, for the canonical bytes."""
        return {
            "truth_sha256": self.truth_sha256,
            "provenance": self.provenance,
            "assumptions": list(self.assumptions),
            "stream_sha256": self.stream_sha256,
            "commit": self.commit,
            "label": self.label,
            "config": self.config,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TwinManifest:
        """The manifest back, from the dictionary read from the file."""
        return cls(
            truth_sha256=str(data["truth_sha256"]),
            provenance=str(data["provenance"]),
            assumptions=tuple(str(item) for item in data["assumptions"]),
            stream_sha256=str(data["stream_sha256"]),
            commit=str(data["commit"]),
            label=str(data["label"]),
            config=dict(data["config"]),
        )


def canonical_bytes(manifest: TwinManifest) -> bytes:
    """The canonical form of the manifest: sorted keys, no clock and no path of the machine."""
    return json.dumps(manifest.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest_of(manifest: TwinManifest) -> str:
    """The digest of the manifest: the sha256 of the canonical bytes of it."""
    return hashlib.sha256(canonical_bytes(manifest)).hexdigest()
