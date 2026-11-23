"""The sentence that tells a person that the answer comes from an AI agent.

What it is for: Article 50 of the EU AI Act has applied since 2 August 2026, and a surface that answers a
person has to say two things: that the answer comes from an AI agent, and that a person reviews the cases
that need a review. The sentence lives here, in the domain, and both surfaces of the product read it from
here, so the demo application and the public site cannot drift apart.

Why the words live in a JSON file next to this module: the public site is a TypeScript application and
cannot import a module of Python. It reads the JSON file, and this module reads the same file, so there is
one place where the sentence is written and a test can hold the two surfaces to it.

Interface used by other modules: `AI_DISCLOSURE`, the sentence itself, ready to be shown.
"""

from __future__ import annotations

import json
from pathlib import Path

# The file of the words, next to this module. The public site reads it by this same relative path.
WORDS_FILE = Path(__file__).with_name("ai_disclosure.json")

__all__ = ["AI_DISCLOSURE", "WORDS_FILE"]


def _read_sentence() -> str:
    """The sentence of the disclosure, read from the file of the words.

    Why it is read and not written here: the site reads the same file, and a sentence written twice is two
    sentences that will drift. The file is the only place where the words are written.
    """
    words = json.loads(WORDS_FILE.read_text(encoding="utf-8"))
    sentence = words.get("sentence")
    if not isinstance(sentence, str) or not sentence.strip():
        raise ValueError(f"The file {WORDS_FILE} does not hold a sentence of the disclosure.")
    return sentence.strip()


AI_DISCLOSURE: str = _read_sentence()
