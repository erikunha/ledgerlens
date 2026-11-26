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


def test_both_modes_share_the_editable_payment_question(monkeypatch):
    monkeypatch.setenv("LEDGERLENS_OFFLINE", "1")
    page = AppTest.from_file(str(APP), default_timeout=30).run()
    page.button(key="featured").click().run()
    page.text_input(key="draft").set_value("My edited refund question").run()
    page.button(key="use-openai").click().run()
    assert page.text_input(key="draft").value == "My edited refund question"
    assert page.session_state["investigation_mode"] == "Scripted demo"
    assert any("Scripted demo · No API charges" in item.value for item in page.markdown)
    assert not page.button(key="send").disabled
    assert page.session_state["turns"] == []


def test_legacy_live_link_opens_the_shared_payment_composer(monkeypatch):
    monkeypatch.setenv("LEDGERLENS_OFFLINE", "1")
    page = AppTest.from_file(str(APP), default_timeout=30)
    page.query_params["view"] = "Live"
    page.run()
    assert page.session_state["investigation_mode"] == "Scripted demo"
    assert page.selectbox(key="account").value == "C-0412"
    assert page.button(key="featured")
    assert not page.button(key="send").disabled
    assert "nav-Live" not in [button.key for button in page.button]


def test_paid_turns_keep_edited_questions_answers_and_account(monkeypatch):
    import streamlit as st

    from app import interactive_views

    submitted = []
    results = {}
    monkeypatch.setattr(interactive_views, "render_live_settings", lambda **_: True)

    def submit(scenario, account, question):
        submitted.append((scenario, account, question))
        run = str(len(submitted))
        st.session_state["live_run"] = run
        return run

    def status():
        if result := results.get(st.session_state.get("live_run")):
            st.write(result["answer"])
        return result

    monkeypatch.setattr(interactive_views, "submit_live_question", submit)
    monkeypatch.setattr(interactive_views, "render_live_status", status)
    page = AppTest.from_file(str(APP), default_timeout=30).run()
    page.button(key="featured").click().run()
    page.session_state["credential"] = {"handle": "test"}
    page.session_state["live_settings"] = {"model_profile_id": "test"}
    page.button(key="use-openai").click().run()
    page.text_input(key="draft").set_value("My edited question")
    assert page.button(key="send").label == "Send to OpenAI"
    page.button(key="send").click().run()
    assert submitted == [("S01", "C-0412", "My edited question")]
    assert page.selectbox(key="account").disabled
    assert next(button for button in page.button if button.label == "Switch to demo").disabled
    assert next(button for button in page.button if button.label == "Configure OpenAI").disabled
    assert page.button(key="send").disabled
    results["1"] = {"status": "completed", "answer": "First answer"}
    page.run()
    assert not page.selectbox(key="account").disabled
    page.text_input(key="draft").set_value("A follow-up")
    page.button(key="send").click().run()
    results["2"] = {"status": "completed", "answer": "Second answer"}
    page.run()
    assert [turn["live_result"]["answer"] for turn in page.session_state["turns"]] == ["First answer", "Second answer"]
    assert not page.exception
    page.selectbox(key="account").set_value("M-09").run()
    assert page.session_state["turns"] == []
    assert not any("First answer" in item.value or "Second answer" in item.value for item in page.markdown)


def test_rejected_paid_question_remains_in_the_composer(monkeypatch):
    from app import interactive_views

    monkeypatch.setattr(interactive_views, "render_live_settings", lambda **_: True)
    monkeypatch.setattr(interactive_views, "submit_live_question", lambda *_: None)
    page = AppTest.from_file(str(APP), default_timeout=30).run()
    page.session_state["credential"] = {"handle": "test"}
    page.session_state["live_settings"] = {"model_profile_id": "test"}
    page.button(key="use-openai").click().run()
    page.text_input(key="draft").set_value("Keep my words")
    page.button(key="send").click().run()
    assert page.text_input(key="draft").value == "Keep my words"
    assert page.session_state["turns"] == []


def test_paid_secondary_account_disables_send_for_featured_case(monkeypatch):
    from app import interactive_views

    monkeypatch.setattr(interactive_views, "render_live_settings", lambda **_: True)
    monkeypatch.setattr(interactive_views, "render_live_status", lambda: None)
    page = AppTest.from_file(str(APP), default_timeout=30).run()
    page.selectbox(key="account").set_value("M-09").run()
    page.button(key="featured").click().run()
    original = page.text_input(key="draft").value
    page.session_state["credential"] = {"handle": "test"}
    page.session_state["live_settings"] = {"model_profile_id": "test"}
    page.button(key="use-openai").click().run()
    assert any("OpenAI · Using your key" in item.value for item in page.markdown)
    assert page.button(key="send").disabled
    assert any("scripted answers for this account" in item.value for item in page.info)
    next(button for button in page.button if button.label == "Switch to demo").click().run()
    assert not page.button(key="send").disabled
    assert page.text_input(key="draft").value == original
    assert not page.session_state["turns"]
