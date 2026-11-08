"""Session history in SQLite: persistence per session, a token window and a summary that keeps ids.

What they guarantee, and why: each session has its own history and survives a new object (the integrator
keeps state per `thread_id`); when the conversation goes past the token budget, the most recent exchanges
stay verbatim and the old ones become a summary; and the summary does not lose the identifiers or the dates,
because a summary that forgets TX-2048 makes the agent go wrong later.

The test budget is small on purpose: the mechanism is what is under test, and the project default
(`max_tokens` of 2000) is what runs in the integrator.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage

from ledgerlens.memory.history import SQLiteChatHistory, get_session_history
from ledgerlens.offline import ScriptedChatModel

SUMMARY_MARKER = '{"summary": true}'

OLD_QUESTION = HumanMessage(
    "I want the full history of TX-2048, with the dates 2026-10-15 and 2026-10-20, every amount and the reason "
    "for the FX difference on the refund."
)
OLD_ANSWER = AIMessage(
    "TX-2048 was captured on 2026-10-15 and refunded on 2026-10-20, with a 17.48 BRL difference in the amount paid."
)
RECENT_QUESTION = HumanMessage("And now?")
RECENT_ANSWER = AIMessage("Done.")


def _rows(db_path: Path) -> list[tuple[str, str, str | None]]:
    with sqlite3.connect(db_path) as connection:
        return list(connection.execute("SELECT role, content, tool_calls FROM messages ORDER BY id"))


def _history_with_one_condensation(tmp_path: Path) -> SQLiteChatHistory:
    """A history with a tight budget and the four messages of a long conversation."""
    history = SQLiteChatHistory(
        "s1",
        tmp_path / "history.db",
        max_tokens=40,
        model=ScriptedChatModel(script=["Summary of the support session."]),
        keep_recent=2,
    )
    history.add_messages([OLD_QUESTION, OLD_ANSWER, RECENT_QUESTION, RECENT_ANSWER])
    return history


def test_the_history_is_persisted_per_session(tmp_path: Path) -> None:
    db_path = tmp_path / "history.db"
    first = SQLiteChatHistory("s1", db_path)
    first.add_message(HumanMessage("What happened with TX-2048?"))
    first.add_message(AIMessage("TX-2048 was refunded in BRL."))

    again = SQLiteChatHistory("s1", db_path)
    assert [message.content for message in again.messages] == [
        "What happened with TX-2048?",
        "TX-2048 was refunded in BRL.",
    ]

    other = SQLiteChatHistory("s2", db_path)
    assert other.messages == []


def test_the_factory_points_at_the_runtime_directory(offline_environment: Path) -> None:
    history = get_session_history("s3")
    assert isinstance(history, SQLiteChatHistory)
    assert history.db_path == offline_environment / "history.db"

    history.add_message(HumanMessage("first"))
    assert (offline_environment / "history.db").is_file()
    assert SQLiteChatHistory("s3", offline_environment / "history.db").messages[0].content == "first"


def test_a_conversation_over_the_budget_keeps_the_recent_turns_verbatim(tmp_path: Path) -> None:
    history = _history_with_one_condensation(tmp_path)

    contents = [str(message.content) for message in history.messages]
    assert RECENT_QUESTION.content in contents
    assert RECENT_ANSWER.content in contents
    assert OLD_QUESTION.content not in contents


def test_the_old_turns_become_a_summary_row(tmp_path: Path) -> None:
    db_path = tmp_path / "history.db"
    _history_with_one_condensation(tmp_path)

    rows = _rows(db_path)
    summaries = [row for row in rows if row[2] == SUMMARY_MARKER]
    assert len(summaries) == 1
    assert summaries[0][0] == "system"
    assert summaries[0][1].startswith("Summary of the support session.")
    assert json.loads(SUMMARY_MARKER) == {"summary": True}


def test_the_summary_keeps_the_named_entities(tmp_path: Path) -> None:
    """The scripted model returns a summary with no ids; the history still keeps TX-2048 and the dates."""
    history = _history_with_one_condensation(tmp_path)

    summary = next(message for message in history.messages if message.type == "system")
    assert "TX-2048" in str(summary.content)
    assert "2026-10-15" in str(summary.content)
    assert "2026-10-20" in str(summary.content)


def test_the_history_below_the_budget_is_not_summarized(tmp_path: Path) -> None:
    db_path = tmp_path / "history.db"
    history = SQLiteChatHistory("s1", db_path, max_tokens=2000)

    history.add_messages([HumanMessage("TX-2048"), AIMessage("Answer.")])

    assert _rows(db_path) == [("human", "TX-2048", None), ("ai", "Answer.", None)]


def test_clear_removes_only_the_session(tmp_path: Path) -> None:
    db_path = tmp_path / "history.db"
    SQLiteChatHistory("s1", db_path).add_message(HumanMessage("first"))
    history = SQLiteChatHistory("s2", db_path)
    history.add_message(HumanMessage("second"))

    history.clear()

    assert history.messages == []
    assert [message.content for message in SQLiteChatHistory("s1", db_path).messages] == ["first"]
