"""Check account isolation when navigating away from Payments and returning."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[2] / "app" / "streamlit_app.py"


def test_returning_to_payments_preserves_the_selected_account(monkeypatch):
    monkeypatch.setenv("LEDGERLENS_OFFLINE", "1")
    page = AppTest.from_file(str(APP), default_timeout=30).run()
    page.selectbox(key="account").set_value("M-03").run()
    for view in ("Replay", "Evaluation", "Proof", "Engineering", "Payments"):
        page.button(key=f"nav-{view}").click().run()
        assert not page.exception
    assert page.selectbox(key="account").value == "M-03"


def test_featured_refund_opens_an_editable_draft_and_matching_recorded_proof(monkeypatch):
    monkeypatch.setenv("LEDGERLENS_OFFLINE", "1")
    page = AppTest.from_file(str(APP), default_timeout=30).run()
    page.button(key="featured").click().run()
    assert "TX-2048" in page.text_input(key="draft").value
    assert not page.session_state["turns"]
    page.button(key="recording-link").click().run()
    assert page.selectbox(key="recording_scenario").value == "S01"
    page.button(key="open_recording_proof").click().run()
    assert page.selectbox(key="proof_recording").value == ("replay", "S01")
    assert not page.exception



def test_dispute_links_to_a_recording_without_promising_a_calculation(monkeypatch):
    monkeypatch.setenv("LEDGERLENS_OFFLINE", "1")
    page = AppTest.from_file(str(APP), default_timeout=30).run()
    page.selectbox(key="account").set_value("M-09").run()
    link = page.button(key="recording-link")
    assert link.label == "See the recording"
    link.click().run()
    assert page.selectbox(key="recording_scenario").value == "S03"
