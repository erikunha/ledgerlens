"""The manifest of a run of the twin: the four fields, the digest of the truth, and the canonical bytes.

What they guarantee, and why: (a) the manifest carries the digest of the truth, the provenance, the
assumptions, the digest of the arrival stream, the commit and the label of the run, because the reader of a
run knows which world the run measured and under which assumptions; (b) the digest of the truth changes when
the truth changes, because a manifest that named the same digest for two truths would be a manifest of
neither; (c) the same bytes come out when the keys are written in a different order, because the bytes of the
manifest do not depend on the machine that wrote them; (d) the bytes hold no timestamp and no path of the
machine, because a manifest that carried them would be a manifest that a reader could not reproduce.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from ledgerlens.sim.twin.manifest import TwinManifest, canonical_bytes


def _manifest(**overrides) -> TwinManifest:
    """A manifest of a run of the twin, with the fields a manifest carries."""
    fields = {
        "truth_sha256": "a" * 64,
        "provenance": "the versioned sample of the repository",
        "assumptions": ("the distribution of the arrivals", "the capacity of 2 slot(s)"),
        "stream_sha256": "b" * 64,
        "commit": "abc123",
        "label": "steady_state",
        "config": {"seed": 42},
    }
    fields.update(overrides)
    return TwinManifest(**fields)


def test_the_manifest_carries_the_fields_of_the_run() -> None:
    """The digest of the truth, the provenance, the assumptions, the stream, the commit and the label."""
    manifest = _manifest()

    assert manifest.truth_sha256 == "a" * 64
    assert manifest.provenance
    assert manifest.assumptions
    assert manifest.stream_sha256 == "b" * 64
    assert manifest.commit
    assert manifest.label == "steady_state"


def test_the_bytes_of_the_manifest_do_not_depend_on_the_order_of_the_keys() -> None:
    """The canonical form sorts the keys, so two writers produce the same bytes."""
    first = _manifest()
    second = TwinManifest(
        config={"seed": 42},
        label="steady_state",
        commit="abc123",
        stream_sha256="b" * 64,
        assumptions=("the distribution of the arrivals", "the capacity of 2 slot(s)"),
        provenance="the versioned sample of the repository",
        truth_sha256="a" * 64,
    )

    assert canonical_bytes(first) == canonical_bytes(second)


def test_the_bytes_of_the_manifest_hold_no_timestamp_and_no_path_of_the_machine() -> None:
    """A manifest that carried them would be a manifest that a reader could not reproduce."""
    text = canonical_bytes(_manifest()).decode("utf-8")

    assert "2026-" not in text
    # The machine paths are built in pieces, so that this test file itself holds no machine path.
    assert "/" + "Users" + "/" not in text
    assert "/" + "home" + "/" not in text
