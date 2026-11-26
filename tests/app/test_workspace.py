"""Check account isolation when navigating away from Payments and returning."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[2] / "app" / "streamlit_app.py"


def test_returning_to_payments_preserves_the_selected_account(monkeypatch):
    monkeypatch.setenv("LEDGERLENS_OFFLINE", "1")
    page = AppTest.from_file(str(APP), default_timeout=30).run()
    page.selectbox(key="account").set_value("M-03").run()
    for view in ("Replay", "Evaluation", "Proof", "Engineering", "Payments"):
        page.radio(key="view").set_value(view).run()
        assert not page.exception
    assert page.selectbox(key="account").value == "M-03"
