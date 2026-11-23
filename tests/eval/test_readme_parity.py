"""The two READMEs of the repository carry the same structure.

Why it exists: ADR-016 makes the parity between `README.md` and `README.pt-BR.md` part of the definition of done,
and a translation that lags behind its source is a defect, the same way a stale document is. The two files are the
same document in two languages and not a sentence by sentence translation, so what the two of them can be held on is
the shape of the document: the same headings, in the same order, with the same count, and the same number of bullets
under the limitations.

What it guarantees: a heading that exists in one language and not in the other, a heading that moved, and a
limitations list that grew on one side only, all fail here with a sentence that names the file and the fix.

What it does not do: it writes nothing and it reads nothing but the two files, so it can run offline and in the
first seconds of a checkout.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
README_PT = ROOT / "README.pt-BR.md"

# A heading of the two documents. Only the levels two and three are compared, because the title of the document is
# the name of the product in the two languages and it says nothing about the shape of the document.
_HEADING = re.compile(r"^(#{2,3})\s+(\S.*?)\s*$")

# The section of the limitations, in the two languages. The prefix is spelled the same way in both, so the section is
# found without writing the text of the Portuguese heading in this file.
_LIMITATIONS_PREFIX = "limita"


def _logical_lines(text: str) -> list[str]:
    """The lines of a document that are not inside a fenced block of code.

    Why the fences are dropped: a line of a code block that starts with a hash is code and not a heading, and a
    heading counted from a code block would be a defect of the reader and not a defect of the document.
    """
    lines: list[str] = []
    inside = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            inside = not inside
            continue
        if not inside:
            lines.append(line)
    return lines


def _headings(text: str) -> list[tuple[int, str]]:
    """The headings of a document, as (level, title), in the order they appear."""
    found: list[tuple[int, str]] = []
    for line in _logical_lines(text):
        match = _HEADING.match(line)
        if match:
            found.append((len(match.group(1)), match.group(2)))
    return found


def _bullets_of_the_limitations(text: str) -> int:
    """The bullets of the limitations section of a document.

    The section is the one whose heading starts with the prefix of the limitations in the two languages, and it ends
    at the next heading of the same level. A bullet is a line that starts with a dash and a space.
    """
    lines = _logical_lines(text)
    start = None
    level = 0
    for index, line in enumerate(lines):
        match = _HEADING.match(line)
        if match and match.group(2).lower().startswith(_LIMITATIONS_PREFIX):
            start = index
            level = len(match.group(1))
            break
    if start is None:
        raise AssertionError("the document has no limitations section")
    count = 0
    for line in lines[start + 1 :]:
        match = _HEADING.match(line)
        if match and len(match.group(1)) <= level:
            break
        if line.startswith("- "):
            count += 1
    return count


@pytest.fixture(scope="module")
def readme() -> str:
    """The English README, the source of the truth."""
    return README.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def readme_pt() -> str:
    """The Brazilian Portuguese README, the translation of the English one."""
    return README_PT.read_text(encoding="utf-8")


def test_the_two_readmes_carry_the_same_number_of_headings(readme: str, readme_pt: str) -> None:
    """The two documents carry the same count of headings, and the same count of each level.

    A heading that exists in one language and not in the other is a defect of this repository: the translation has to
    arrive in the same commit, so the missing heading goes into the file that does not have it.
    """
    english = _headings(readme)
    portuguese = _headings(readme_pt)
    assert len(english) == len(portuguese), (
        f"README.md carries {len(english)} headings and README.pt-BR.md carries {len(portuguese)}: "
        "the two documents must carry the same count, and a heading that exists in one language only is a defect "
        "of the translation layer (ADR-016)"
    )
    for level in (2, 3):
        one = sum(1 for found, _ in english if found == level)
        other = sum(1 for found, _ in portuguese if found == level)
        assert one == other, (
            f"README.md carries {one} headings of level {level} and README.pt-BR.md carries {other}: "
            "the two documents must carry the same number of headings of each level"
        )


def test_the_two_readmes_carry_the_same_headings_in_the_same_order(readme: str, readme_pt: str) -> None:
    """The two documents carry the same headings, in the same order.

    The text of a heading is written in the language of its document, so what the two files are held on is the level
    of the heading and its place in the sequence. A section that was added on one side only, or a section that moved,
    breaks the sequence and fails here with the position of the break.
    """
    english = _headings(readme)
    portuguese = _headings(readme_pt)
    levels = [found for found, _ in english]
    others = [found for found, _ in portuguese]
    for index in range(min(len(levels), len(others))):
        if levels[index] != others[index]:
            raise AssertionError(
                f"the heading {index + 1} of the two documents is not the same level: README.md carries a level "
                f"{levels[index]} heading ({english[index][1]!r}) and README.pt-BR.md carries a level {others[index]} "
                f"heading ({portuguese[index][1]!r}): the two documents must carry the same headings, in the same "
                "order, and a heading that exists in one language only is a defect of the translation layer (ADR-016)"
            )


def test_the_two_readmes_carry_the_same_number_of_bullets_under_the_limitations(
    readme: str, readme_pt: str
) -> None:
    """The limitations of the two documents carry the same number of bullets.

    The limitations are the part of the README that a reader trusts most, so a bullet that was added to one language
    only is a claim that one of the two readers does not see. The fix is to translate the bullet, not to delete it.
    """
    english = _bullets_of_the_limitations(readme)
    portuguese = _bullets_of_the_limitations(readme_pt)
    assert english == portuguese, (
        f"the limitations of README.md carry {english} bullets and the limitations of README.pt-BR.md carry "
        f"{portuguese}: the two lists must carry the same number of bullets, because a limitation that one of the two "
        "readers does not see is a limitation that is not published"
    )
