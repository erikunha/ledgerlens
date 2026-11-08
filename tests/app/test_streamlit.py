"""Streamlit page: shows the answer, the tool calls and the verdict on each claim, and keeps the conversation.

What they guarantee, and why: (a) a question typed in the chat becomes an answer, the list of tool calls and a
verdict per claim; (b) the second question of the same session continues the first (the history stays on screen
and the conversation uses the same `thread_id`); (c) the Help panel says whether the mode is offline or online;
(d) a suggestion only fills the field, and the edited or freely typed text is what goes to the agent; (e) the page
reads like a portal: the signed-in account's statement, an "Ask" per line that only fills the box, the account and
the line picked reaching the agent as context, and, after an answer, the tool calls, the verification badge and a
mark on the lines the agent read. The agent comes in through `session_state`, with the scripted model, so the test
depends on no model and no network.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from ledgerlens.agents import integrator as integrator_module
from ledgerlens.offline import text_message
from ledgerlens.schemas import InvestigationResult
from tests.agents.test_integrator import (  # noqa: F401  (reused fixtures)
    S01,
    cases,
    embeddings,
    index_root,
    integrator_for,
    ledger_db,
    s01_script,
    supporting_verifier,
)

APP = Path(__file__).resolve().parents[2] / "app" / "streamlit_app.py"
QUESTION = S01["questions"][0]


def send(app: AppTest, text: str) -> AppTest:
    """Types in the question box and presses Send."""
    app.text_input(key="draft").set_value(text)
    return app.button(key="send").click().run()


def draft(app: AppTest) -> str:
    return app.text_input(key="draft").value


def suggestion(app: AppTest, text: str):
    return next(b for b in app.button if b.label == text)


def page_text(at: AppTest) -> str:
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption] + [w.value for w in at.warning]
    return "\n".join(parts)


def verifier(result: InvestigationResult, *, nli=None) -> InvestigationResult:
    """Supports the turn with evidence; a turn with no tool (just conversation) has no claims."""
    return supporting_verifier([])(result) if result.evidence else result


@pytest.fixture
def at(ledger_db: Path, index_root: Path, cases) -> AppTest:  # noqa: F811
    script = s01_script() + [text_message("It was TX-2048.")]
    agent = integrator_for(ledger_db, index_root, cases, script, verifier=verifier)
    app = AppTest.from_file(str(APP), default_timeout=30)
    app.session_state["agent"] = agent
    app.session_state["observer"] = True  # "Show what the assistant checked": the demo viewer's details
    return app.run()


def test_the_page_starts_empty_with_the_mode_and_examples(at: AppTest) -> None:
    assert not at.exception
    text = page_text(at)
    assert "offline" in text.lower()
    assert any(QUESTION == b.label for b in at.button)
    assert len(at.chat_message) == 0


def test_a_question_shows_answer_tool_calls_and_verdicts(at: AppTest) -> None:
    send(at, QUESTION)
    assert not at.exception
    text = page_text(at)
    truth = S01["truth"]
    assert QUESTION in text
    assert truth["refund_brl"] in text  # the answer
    for tool in S01["expected_tools"]:  # the calls panel, in order
        assert tool in text
    assert text.index("query_ledger") < text.index("calculate")
    assert "Supported" in text  # the verdict, in words
    assert "CL1" in text


def test_the_second_turn_keeps_the_first_on_screen(at: AppTest) -> None:
    send(at, QUESTION)
    send(at, "And which transaction did I just ask about?")
    assert not at.exception
    text = page_text(at)
    assert QUESTION in text and "And which transaction" in text
    assert len(at.chat_message) == 4  # two questions and two answers
    assert len(at.session_state["turns"]) == 2
    first, second = (turn["result"].session_id for turn in at.session_state["turns"])
    assert first == second  # the same session


def test_a_suggestion_fills_the_input_and_does_not_investigate(at: AppTest, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(integrator_module, "investigate", lambda agent, question, **kw: calls.append(question))
    suggestion(at, QUESTION).click().run()
    assert not at.exception
    assert draft(at) == QUESTION
    assert calls == [] and at.session_state["turns"] == []
    assert len(at.chat_message) == 0


def test_an_edited_suggestion_is_sent_as_edited_and_the_input_clears(
    at: AppTest, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[str] = []
    investigate = integrator_module.investigate

    def spy(agent, question, **kw):
        sent.append(question)
        return investigate(agent, question, **kw)

    monkeypatch.setattr(integrator_module, "investigate", spy)
    suggestion(at, QUESTION).click().run()
    edited = QUESTION + " Detail the rate."
    send(at, edited)
    assert not at.exception
    assert sent == [edited]
    assert draft(at) == ""
    assert S01["truth"]["refund_brl"] in page_text(at)


def test_free_typed_text_is_sent_as_typed(at: AppTest, monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[str] = []
    investigate = integrator_module.investigate
    monkeypatch.setattr(
        integrator_module,
        "investigate",
        lambda agent, q, **kw: (sent.append(q), investigate(agent, q, **kw))[1],
    )
    send(at, "  And the deadline?  ")
    assert sent == ["And the deadline?"]
    assert draft(at) == ""


def test_an_empty_input_sends_nothing(at: AppTest) -> None:
    send(at, "   ")
    assert not at.exception
    assert at.session_state["turns"] == []


def test_suggested_ids_exist_in_the_sample_manifest(at: AppTest) -> None:
    import json
    import re

    manifest = json.loads((APP.parents[1] / "data" / "scenarios.json").read_text(encoding="utf-8"))
    known = {i for ids in manifest["reserved_ids"].values() for i in ids}
    labels = [b.label for b in at.button if b.key and b.key.startswith("suggestion-")]
    assert 2 <= len(labels) <= 4
    for label in labels:
        for ident in re.findall(r"\b(?:TX|CB|ST|C|M|R)-\d{2,4}\b", label):
            assert ident in known, (ident, label)


def test_online_mode_is_named_in_the_help_panel(at: AppTest, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEDGERLENS_OFFLINE", "0")
    at.run()
    text = page_text(at)
    assert "Online: model" in text and "offline" not in text.lower()


def test_without_an_injected_agent_the_offline_page_answers_the_example_and_refuses_the_rest() -> None:
    app = AppTest.from_file(str(APP), default_timeout=300)
    app.session_state["observer"] = True
    app.run()
    assert not app.exception
    send(app, QUESTION)
    assert not app.exception
    text = page_text(app)
    assert S01["truth"]["refund_brl"] in text and "Supported" in text and "`calculate`" in text
    send(app, "What is the weather today?")
    assert not app.exception
    assert "only answer the suggested questions" in page_text(app)


def test_the_question_is_on_screen_while_the_agent_investigates(at: AppTest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Online the investigation takes tens of seconds and the question only showed up when it finished."""
    shown: list[str] = []
    markdown = st.markdown

    def record(body, *args, **kwargs):
        shown.append(str(body))
        return markdown(body, *args, **kwargs)

    on_screen_when_called: list[list[str]] = []
    investigate = integrator_module.investigate

    def spy(agent, question, **kw):
        on_screen_when_called.append(list(shown))
        return investigate(agent, question, **kw)

    monkeypatch.setattr(st, "markdown", record)
    monkeypatch.setattr(integrator_module, "investigate", spy)

    send(at, QUESTION)

    assert not at.exception
    assert len(on_screen_when_called) == 1
    assert QUESTION in on_screen_when_called[0]  # already on screen when the agent starts


def test_a_suggestion_sent_is_on_screen_while_the_agent_investigates(
    at: AppTest, monkeypatch: pytest.MonkeyPatch
) -> None:
    shown: list[str] = []
    markdown = st.markdown
    monkeypatch.setattr(st, "markdown", lambda body, *a, **k: (shown.append(str(body)), markdown(body, *a, **k))[1])
    on_screen_when_called: list[list[str]] = []
    investigate = integrator_module.investigate

    def spy(agent, question, **kw):
        on_screen_when_called.append(list(shown))
        return investigate(agent, question, **kw)

    monkeypatch.setattr(integrator_module, "investigate", spy)
    suggestion(at, QUESTION).click().run()
    send(at, draft(at))
    assert QUESTION in on_screen_when_called[0]


def test_every_turn_is_drawn_once_in_order_after_the_second_question(at: AppTest) -> None:
    send(at, QUESTION)
    send(at, "And which transaction did I just ask about?")
    assert not at.exception
    assert [m.name for m in at.chat_message] == ["user", "assistant", "user", "assistant"]
    users = [m.markdown[0].value for m in at.chat_message if m.name == "user"]
    assert users == [QUESTION, "And which transaction did I just ask about?"]
    assert S01["truth"]["refund_brl"] in at.chat_message[1].markdown[0].value  # the answer sits under its question


# ---- the portal: account, statement, "Ask" per line, what the agent read -----------------------------------


def ask_button(app: AppTest, record_id: str, tab: str = "activity"):
    return app.button(key=f"ask-{tab}-{record_id}")


def asks(app: AppTest, tab: str = "activity") -> list[str]:
    prefix = f"ask-{tab}-"
    return [b.key.removeprefix(prefix) for b in app.button if b.key and b.key.startswith(prefix)]


def row_text(app: AppTest, record_id: str) -> str:
    """The label of the record's line: amount, title, date, status pill and marks (the id is in its details)."""
    return next((e.label for e in app.expander if any(f"`{record_id}`" in m.value for m in e.markdown)), "")


def sign_in(app: AppTest, account_id: str) -> AppTest:
    return app.selectbox(key="account").set_value(account_id).run()


def find(app: AppTest, record_id: str) -> AppTest:
    """Types the id in the statement's search box, as a person looking for one line among many."""
    return app.text_input(key="f_search").set_value(record_id).run()


def test_the_signed_in_customer_sees_only_their_own_statement(at: AppTest) -> None:
    assert at.selectbox(key="account").value == "C-0412"
    assert set(asks(at)) == {"TX-2048", "R-0731"}  # the payment and its refund, nothing from another customer
    assert asks(at, "refunds") == ["R-0731"] and asks(at, "disputes") == []
    assert not asks(at, "payouts")  # a customer has no payouts tab
    assert "Mariana Albuquerque Costa" in page_text(at)
    payment = row_text(at, "TX-2048")
    assert "Lumen Travel GmbH" in payment and "EUR 100.00" in payment and "Refunded" in payment
    assert "Oct 15, 2026" in payment
    assert any(m.value == "BRL 549.31" for m in at.markdown)  # the refund's detail: what was paid back
    assert any("1 EUR = 5.4931 BRL" in m.value for m in at.markdown)  # and the FX rate applied to it


def test_ask_on_a_line_fills_the_box_marks_the_line_and_sends_nothing(
    at: AppTest, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(integrator_module, "investigate", lambda agent, question, **kw: calls.append(question))
    ask_button(at, "TX-2048").click().run()
    assert not at.exception
    assert draft(at) == QUESTION  # the planted complaint for this line, ready to edit
    assert calls == [] and at.session_state["turns"] == []
    assert "asked about" in row_text(at, "TX-2048")
    assert "asked about" not in row_text(at, "R-0731")


def test_the_account_and_the_line_picked_reach_the_agent_as_context(
    at: AppTest, monkeypatch: pytest.MonkeyPatch
) -> None:
    contexts: list[str | None] = []
    investigate = integrator_module.investigate

    def spy(agent, question, **kw):
        contexts.append(kw.get("context"))
        return investigate(agent, question, **kw)

    monkeypatch.setattr(integrator_module, "investigate", spy)
    ask_button(at, "TX-2048").click().run()
    send(at, draft(at))
    assert not at.exception
    assert len(contexts) == 1
    assert "customer C-0412" in contexts[0] and "TX-2048" in contexts[0]
    assert "only this account's records" in contexts[0]


def test_after_an_answer_the_tool_calls_badge_and_the_lines_read_appear(at: AppTest) -> None:
    ask_button(at, "TX-2048").click().run()
    send(at, draft(at))
    assert not at.exception
    expander = next(e for e in at.expander if e.label == "What the assistant checked")
    inside = "\n".join(m.value for m in expander.markdown) + "\n".join(c.value for c in expander.caption)
    for tool in S01["expected_tools"]:
        assert f"`{tool}`" in inside
    assert "Arguments: " in inside and "Result:" in inside
    assert "Ledger records read: TX-2048" in inside
    assert "read by assistant" in row_text(at, "TX-2048")  # the statement line the agent read is marked
    assert "read by assistant" not in row_text(at, "R-0731")
    badge = next(m.value for m in at.markdown if m.value.startswith("Verification:"))
    assert "supported]" in badge and "review" in badge
    assert "0 contradicted" not in badge  # a zero count is left out


@pytest.mark.parametrize(
    ("account", "record", "question"),
    [
        ("C-0412", "TX-2048", QUESTION),
        ("M-17", "TX-2048", QUESTION),
        (
            "C-0733",
            "TX-2052",
            "I was charged twice for the same amount, TX-2051 and TX-2052. Was it a duplicate charge?",
        ),
        ("M-09", "CB-0310", "What is the deadline for dispute CB-0310 and what do we need to do?"),
        ("C-0291", "CB-0310", "What is the deadline for my dispute CB-0310 and what happens next?"),
        ("M-03", "ST-0044", "How was payout ST-0044 for merchant M-03 calculated and when is it paid?"),
    ],
)
def test_each_planted_complaint_is_one_sign_in_and_one_click_away(
    at: AppTest, account: str, record: str, question: str
) -> None:
    sign_in(at, account)
    find(at, record)
    ask_button(at, record, "payouts" if record.startswith("ST-") else "activity").click().run()
    assert not at.exception
    assert draft(at) == question


def test_switching_account_starts_a_new_conversation(at: AppTest) -> None:
    send(at, QUESTION)
    first_thread = at.session_state["thread_id"]
    sign_in(at, "M-03")
    assert not at.exception
    assert at.session_state["turns"] == [] and at.session_state["thread_id"] != first_thread
    assert len(at.chat_message) == 0
    assert "Casa Verde Foods" in page_text(at)


def test_statement_filters_and_tabs_narrow_the_lines(at: AppTest) -> None:
    sign_in(at, "M-09")
    assert asks(at, "disputes") and all(i.startswith("CB-") for i in asks(at, "disputes"))
    assert asks(at, "payouts") and all(i.startswith("ST-") for i in asks(at, "payouts"))
    at.multiselect(key="f_status").set_value(["Action needed"]).run()
    shown = asks(at)
    assert "CB-0310" in shown and all(i.startswith("CB-") for i in shown)


def test_by_default_the_reply_reads_like_support_and_hides_the_checks(
    ledger_db: Path,  # noqa: F811  (fixtures imported from the integrator tests)
    index_root: Path,  # noqa: F811
    cases,  # noqa: F811
) -> None:
    script = s01_script()
    app = AppTest.from_file(str(APP), default_timeout=30)
    app.session_state["agent"] = integrator_for(ledger_db, index_root, cases, script, verifier=verifier)
    app.run()
    assert app.toggle(key="observer").value is False
    ask_button(app, "TX-2048").click().run()
    send(app, draft(app))
    assert not app.exception
    answer = app.chat_message[1].markdown[0].value
    assert S01["truth"]["refund_brl"] in answer and "[sql:" not in answer and "[calc:" not in answer
    assert not any(e.label == "What the assistant checked" for e in app.expander)
    assert "read by assistant" not in row_text(app, "TX-2048") and "asked about" not in row_text(app, "TX-2048")
    app.toggle(key="observer").set_value(True).run()  # the demo viewer turns the checks on
    assert any(e.label == "What the assistant checked" for e in app.expander)
    assert "read by assistant" in row_text(app, "TX-2048")


def test_an_id_that_is_on_no_statement_is_offered_as_a_question_to_try(at: AppTest) -> None:
    labels = [b.label for b in at.button if b.key and b.key.startswith("suggestion-")]
    assert "What is the status of TX-9999?" in labels
    assert "TX-9999" not in asks(at)


def test_offline_ask_is_offered_only_on_lines_with_a_scripted_answer() -> None:
    """Offline, a line whose question has no script would only get the refusal: its button is disabled."""
    app = AppTest.from_file(str(APP), default_timeout=300).run()
    sign_in(app, "M-09")
    assert ask_button(app, "CB-0310", "disputes").disabled is False
    others = [k for k in asks(app, "disputes") if k != "CB-0310"]
    assert others and all(ask_button(app, k, "disputes").disabled for k in others)


def test_ask_confirms_where_the_question_went(at: AppTest) -> None:
    ask_button(at, "TX-2048").click().run()
    assert any("Question ready in Help" in c.value for c in at.caption)
    assert any("Question added to Help" in t.value for t in at.toast)


def test_after_sending_the_line_picked_is_cleared(at: AppTest) -> None:
    ask_button(at, "TX-2048").click().run()
    send(at, draft(at))
    assert at.session_state["selected"] == []
    assert at.session_state["turns"][0]["selected"] == ["TX-2048"]
