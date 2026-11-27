"""Keep the editable investigation ahead of optional examples so the next action is visible."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_featured_draft_and_composer_precede_more_questions():
    app_path = Path(__file__).resolve().parents[2] / "app" / "streamlit_app.py"
    page = AppTest.from_file(str(app_path), default_timeout=60).run()
    featured = page.button(key="featured")
    assert featured.label == "Use this question"
    controls = list(page.main)
    assert controls.index(page.text_input(key="draft")) < controls.index(page.button(key="suggestion-0"))
    featured.click().run()
    assert page.text_input(key="draft").value
    assert not page.chat_message
