"""Verify the shared AI disclosure on each workspace that presents agent answers."""

from __future__ import annotations

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from ledgerlens.prompts.ai_disclosure import AI_DISCLOSURE

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app" / "streamlit_app.py"
WORDS_FILE = ROOT / "ledgerlens" / "prompts" / "ai_disclosure.json"


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


def test_recorded_and_live_answers_display_the_disclosure(monkeypatch) -> None:
    monkeypatch.setenv("LEDGERLENS_API_BASE_URL", "http://127.0.0.1:1")
    app = AppTest.from_file(str(APP), default_timeout=60).run()
    for workspace in ("recordings", "investigations"):
        app.button(key=f"nav-{workspace}").click().run()
        if workspace == "Payments":
            app.session_state["credential"] = {"handle": "test"}
            app.session_state["live_settings"] = {"model_profile_id": "test"}
            app.button(key="use-openai").click().run()
        assert not app.exception
        assert any(AI_DISCLOSURE in caption.value for caption in app.caption)
