"""The sentence that says the answer comes from an AI agent is published on the surfaces that answer a person.

Why this file exists: Article 50 of the EU AI Act has applied since 2 August 2026, and a surface that answers a
person has to say that the answer comes from an AI agent and that a person reviews the cases that need a review.
The words live in one place, `ledgerlens/prompts/ai_disclosure.json`, next to the module that exposes them, and
every surface reads them from there, so the demo application and the public site cannot drift apart.

What it guarantees: (a) the module of the domain holds a sentence, and it is not empty; (b) the file of the words
and the module hold the same sentence; (c) the demo application shows that sentence on the page, in the Help panel
where the question is typed; (d) every page of the public site that shows an answer to a person reads the file
of the domain, and not a second copy of the sentence.

Why the pages of the site are proved by reading their source and not by rendering them: the public site is a
TypeScript application whose tests are component tests, and the rendered page of the live mode is proved there, in
`apps/web/tests/unit/features/ai-disclosure.test.tsx`. What this file proves about the pages of the site is that
the words they show come from the file of the domain and not from a copy of their own.

Why the sandbox of the site is not in the list: the sandbox lists cases and lets the visitor work on them, and it
shows no answer of the agent to the visitor. The rule of this file is about the surfaces that answer a person, and
a surface that lists or edits cases does not answer.

What it does not do: it reads no network and asks no model. The page of the demo is rendered with the sample data
of the repository, exactly as the demo renders it offline.
"""

from __future__ import annotations

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from ledgerlens.prompts.ai_disclosure import AI_DISCLOSURE

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app" / "streamlit_app.py"
WORDS_FILE = ROOT / "ledgerlens" / "prompts" / "ai_disclosure.json"

# The pages of the public site that show an answer of the agent to a person, and the file of each.
SURFACES_OF_THE_SITE = {
    "live": ROOT / "apps" / "web" / "app" / "(public)" / "live" / "page.tsx",
    "replay": ROOT / "apps" / "web" / "app" / "(public)" / "replay" / "scenario" / "[scenario]" / "page.tsx",
}


def test_the_module_of_the_domain_holds_a_sentence() -> None:
    """The sentence exists, it is not empty, and it says what the obligation asks for.

    Why the substance is checked and not only the emptiness: a sentence that says nothing about the agent and
    nothing about the review would pass an emptiness check, and a page that carries it would say nothing to the
    person who reads it.
    """
    assert AI_DISCLOSURE.strip(), "the sentence of the disclosure is empty"
    assert "AI agent" in AI_DISCLOSURE, "the sentence does not say that the answer comes from an AI agent"
    assert "person" in AI_DISCLOSURE, "the sentence does not say that a person reviews the cases"
    assert "review" in AI_DISCLOSURE, "the sentence does not say what the person reviews"


def test_the_words_of_the_domain_live_in_the_file_the_site_reads() -> None:
    """The sentence of the module and the file of the words are the same sentence.

    Why the file exists next to the module: the public site reads the words from the file, because the site is
    another stack and cannot import a module of Python. The file is the one place the words are written.
    """
    words = json.loads(WORDS_FILE.read_text(encoding="utf-8"))
    assert words["sentence"] == AI_DISCLOSURE


def test_the_demo_application_shows_the_sentence() -> None:
    """The page of the demo carries the sentence, in the Help panel where the question is typed.

    Why the page is rendered and not read: the point of the change is that a person sees the sentence, and a
    sentence in the source of a page is not a sentence on the page.
    """
    app = AppTest.from_file(str(APP), default_timeout=60).run()

    assert not app.exception, f"the page of the demo raised {app.exception}"
    assert any(AI_DISCLOSURE in caption.value for caption in app.caption), (
        "the sentence of the disclosure is not on the page of the demo: the Help panel has to say it"
    )


def test_every_surface_of_the_site_that_answers_reads_the_words_of_the_domain() -> None:
    """Each page of the site that shows an answer takes its words from the file of the domain.

    Why the check is over the source and not over the rendered page: the pages of the site are proved by the
    component tests of the frontend, and what this proves is the wiring, that the words reach the reader from
    the domain and not from a second copy that can drift.
    """
    for name, path in SURFACES_OF_THE_SITE.items():
        source = path.read_text(encoding="utf-8")
        assert "ledgerlens/prompts/ai_disclosure.json" in source, (
            f"the page {name} of the site does not read the words of the domain: a second copy of the sentence is "
            "a sentence that can drift"
        )
