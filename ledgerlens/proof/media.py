"""The media of the artifact and its transcript: the media is optional and the text is not.

Why the transcript survives the budget: the artifact can be read without the media, because the transcript of
every media is part of the artifact and the media is a convenience. When the artifact over the budget of the
site keeps the transcript and drops the media, a reader on a slow connection reads the same words as a reader
on a fast one, and a screen reader reads the same artifact as a sighted reader.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = ["MediaAttachment", "attach_media"]

# The budget of the site per scenario, from SC-004 of specs/001-r1-public-replay/spec.md, the same budget the
# measure of the replay site uses.
BUDGET_BYTES = 409600


@dataclass(frozen=True)
class MediaAttachment:
    """The media of the artifact and its transcript: the media may be dropped, the transcript never is."""

    media: str | None
    transcript: str
    dropped: bool


def attach_media(bundle_dir: Path, transcript: str, *, budget_bytes: int = BUDGET_BYTES) -> MediaAttachment:
    """The media of the artifact over the budget of the site: the transcript stays, the media may go.

    The media of the artifact is the events of the bundle, the full recording of the run. When the events are
    over the budget, the artifact drops the media and keeps the transcript, because the media is optional and
    the text is not.
    """
    events = bundle_dir / "events.jsonl"
    if events.stat().st_size > budget_bytes:
        return MediaAttachment(media=None, transcript=transcript, dropped=True)
    return MediaAttachment(media=str(events), transcript=transcript, dropped=False)
