"""The accessibility of the artifact: every media has a transcript, and the transcript survives the budget.

What they guarantee, and why: every media of the artifact carries a transcript, and an artifact over the
budget of the site keeps the transcript and drops the media, because the media is optional and the text is
not, and a reader on a slow connection reads the same words as a reader on a fast one.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from ledgerlens.proof.media import attach_media

TRANSCRIPT = "the run of the scenario S01 of the repository, with the verdicts of the deterministic verifier."


def test_every_media_of_the_artifact_carries_a_transcript(bundle_replay) -> None:
    """The media of the artifact is the events of the bundle, and the transcript is always there."""
    media = attach_media(bundle_replay, TRANSCRIPT)

    assert media.transcript == TRANSCRIPT
    assert media.media is not None
    assert not media.dropped


def test_an_artifact_over_the_budget_keeps_the_transcript_and_drops_the_media(bundle_replay) -> None:
    """Over the budget of the site, the media goes and the text stays."""
    media = attach_media(bundle_replay, TRANSCRIPT, budget_bytes=1)

    assert media.media is None
    assert media.dropped
    assert media.transcript == TRANSCRIPT
