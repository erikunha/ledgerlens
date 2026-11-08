"""Session history in SQLite: short-term working memory with a token window (CoALA).

Why it exists: the model remembers nothing, so the conversation must be saved and sent again on each turn.
This module keeps the history per session in SQLite and manages the context window: what
fits in the token budget goes into the prompt as is, what does not fit becomes a summary line marked as a
summary, and what does not fit even in the summary is recovered by vector search over past cases
(`ledgerlens/memory/long_term.py`).

In the CoALA taxonomy, this is working memory: what the agent has at hand in the session and uses in the current
step. The summary is still working memory, not semantic memory: it summarizes the conversation, it does not become a
lasting fact.

Three decisions the code makes visible:

1. **Token counting is an estimate** of four characters per token, the same as
   `ledgerlens/chains/sequential.py`. The model's tokenizer is not installed and the
   `transformers` library cannot come into the project, so the count is stable and runs offline.
2. **The summary is pinned by ids.** The summary prompt asks to keep identifiers, amounts and dates, but
   a model can forget one. After summarizing, the history checks which entities were in the condensed messages and
   the ones missing from the summary are appended, so TX-2048 does not vanish from the context.
3. **Condensed messages stay in the database**, marked with `{"condensed": true}`, and leave the window.
   The audit shows what was summarized, and only the summary line goes into the prompt.

The history is also the factory for the integrator's `RunnableWithMessageHistory` (ADR-010): each
`thread_id` becomes a session, and a new session starts empty.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Callable, Sequence
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    get_buffer_string,
)
from langchain_core.output_parsers import StrOutputParser
from pydantic import PrivateAttr

from ledgerlens.config import get_settings
from ledgerlens.prompts import SUMMARY_PROMPT

DEFAULT_MAX_TOKENS = 2000
KEEP_RECENT = 4
HISTORY_FILE = "history.db"
CHARS_PER_TOKEN = 4

SUMMARY_MARKER = json.dumps({"summary": True})
CONDENSED_MARKER = json.dumps({"condensed": True})

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    role TEXT NOT NULL CHECK (role IN ('human', 'ai', 'system', 'tool')),
    content TEXT NOT NULL,
    tool_calls TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_by_session ON messages (session_id, id);
"""

# Entities the summary cannot lose: identifiers, amounts with currency and dates.
_ID = re.compile(r"\b(?:TX|R|CB|ST|M|C)-\d+\b")
_AMOUNT = re.compile(r"\b\d+(?:,\d{3})*(?:\.\d+)?\s+[A-Z]{3}\b|\b[A-Z]{3}\s+\d+(?:,\d{3})*(?:\.\d+)?\b")
_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


class SQLiteChatHistory(BaseChatMessageHistory):
    """Session history in SQLite, with a token window and a summary that keeps the entities."""

    _session_id: str = PrivateAttr()
    _db_path: Path = PrivateAttr()
    _max_tokens: int = PrivateAttr(default=DEFAULT_MAX_TOKENS)
    _model: BaseChatModel | None = PrivateAttr(default=None)
    _keep_recent: int = PrivateAttr(default=KEEP_RECENT)
    _token_counter: Callable[[list[BaseMessage]], int] | None = PrivateAttr(default=None)

    def __init__(
        self,
        session_id: str,
        db_path: Path | str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        *,
        model: BaseChatModel | None = None,
        keep_recent: int = KEEP_RECENT,
        token_counter: Callable[[list[BaseMessage]], int] | None = None,
    ) -> None:
        super().__init__()
        self._session_id = session_id
        self._db_path = Path(db_path)
        self._max_tokens = max_tokens
        self._model = model
        self._keep_recent = keep_recent
        self._token_counter = token_counter
        self._prepare()

    # --- what the library expects ----------------------------------------------------------

    @property
    def session_id(self) -> str:
        """This history's session. One history per session, as ADR-010 says."""
        return self._session_id

    @property
    def db_path(self) -> Path:
        """The SQLite file where the messages live."""
        return self._db_path

    @property
    def max_tokens(self) -> int:
        """The token budget of the context window."""
        return self._max_tokens

    @property
    def messages(self) -> list[BaseMessage]:
        """What goes into the prompt: first the summary, then the recent exchanges, in the order they happened."""
        rows = self._read_rows()
        summaries = [row for row in rows if _marker(row) == "summary"]
        recent = [row for row in rows if not _marker(row)]
        return [self._to_message(row) for row in [*summaries, *recent]]

    def add_message(self, message: BaseMessage) -> None:
        """Saves one message and evaluates the window again."""
        self._insert(message)
        self._condense_if_needed()

    def add_messages(self, messages: Sequence[BaseMessage]) -> None:
        """Saves several messages at once (a whole turn) and evaluates the window again only once."""
        for message in messages:
            self._insert(message)
        self._condense_if_needed()

    def clear(self) -> None:
        """Deletes the session's messages. The other sessions in the same file are not touched."""
        with closing(self._connect()) as connection:
            connection.execute("DELETE FROM messages WHERE session_id = ?", (self._session_id,))
            connection.commit()

    async def aget_messages(self) -> list[BaseMessage]:
        """Async version of `messages`."""
        return self.messages

    async def aadd_message(self, message: BaseMessage) -> None:
        """Async version of `add_message`."""
        self.add_message(message)

    async def aadd_messages(self, messages: Sequence[BaseMessage]) -> None:
        """Async version of `add_messages`."""
        self.add_messages(messages)

    async def aclear(self) -> None:
        """Async version of `clear`."""
        self.clear()

    # --- SQLite ----------------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _prepare(self) -> None:
        """Creates the tables and registers the session, so the file is born in the project's format."""
        with closing(self._connect()) as connection:
            connection.executescript(SCHEMA)
            connection.execute(
                "INSERT OR IGNORE INTO sessions (session_id, created_at) VALUES (?, ?)",
                (self._session_id, datetime.now(UTC).isoformat()),
            )
            connection.commit()

    def _read_rows(self) -> list[sqlite3.Row]:
        with closing(self._connect()) as connection:
            return list(
                connection.execute(
                    "SELECT id, role, content, tool_calls FROM messages WHERE session_id = ? ORDER BY id",
                    (self._session_id,),
                )
            )

    def _insert(self, message: BaseMessage) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT INTO messages (session_id, role, content, tool_calls, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    self._session_id,
                    _role_of(message),
                    str(message.content),
                    _payload_of(message),
                    datetime.now(UTC).isoformat(),
                ),
            )
            connection.commit()

    def _to_message(self, row: sqlite3.Row) -> BaseMessage:
        """Rebuilds the message that was saved."""
        payload = json.loads(row["tool_calls"]) if row["tool_calls"] else {}
        content = row["content"]
        if row["role"] == "ai":
            return AIMessage(content=content, tool_calls=list(payload.get("tool_calls") or []))
        if row["role"] == "system":
            return SystemMessage(content=content)
        if row["role"] == "tool":
            return ToolMessage(content=content, tool_call_id=str(payload.get("tool_call_id", "")))
        return HumanMessage(content=content)

    # --- token window and summary ----------------------------------------------------------

    def _count_tokens(self, messages: list[BaseMessage]) -> int:
        """Estimated tokens: four characters per token, as in `ledgerlens/chains/sequential.py`."""
        if self._token_counter is not None:
            return int(self._token_counter(messages))
        return sum(len(str(message.content)) for message in messages) // CHARS_PER_TOKEN + len(messages)

    def _condense_if_needed(self) -> None:
        """If the window went over the budget, the oldest messages become a summary."""
        rows = self._read_rows()
        summaries = [row for row in rows if _marker(row) == "summary"]
        recent = [row for row in rows if not _marker(row)]
        if len(recent) <= self._keep_recent:
            return

        budget = self._max_tokens - self._count_tokens([self._to_message(row) for row in summaries])
        keep = self._messages_to_keep(recent, budget)
        condensed = recent[: len(recent) - keep]
        if not condensed:
            return

        old_messages = [self._to_message(row) for row in condensed]
        summary = self._summarize(old_messages)
        with closing(self._connect()) as connection:
            for row in condensed:
                connection.execute("UPDATE messages SET tool_calls = ? WHERE id = ?", (CONDENSED_MARKER, row["id"]))
            existing = connection.execute(
                "SELECT id, content FROM messages WHERE session_id = ? AND tool_calls = ? ORDER BY id LIMIT 1",
                (self._session_id, SUMMARY_MARKER),
            ).fetchone()
            if existing is None:
                connection.execute(
                    "INSERT INTO messages (session_id, role, content, tool_calls, created_at) VALUES (?, ?, ?, ?, ?)",
                    (self._session_id, "system", summary, SUMMARY_MARKER, datetime.now(UTC).isoformat()),
                )
            else:
                # The new summary goes on top of the old one: summarizing again over a summary is the way
                # to forget facts, so both versions stay on the same line.
                connection.execute(
                    "UPDATE messages SET content = ? WHERE id = ?",
                    (f"{existing['content']}\n{summary}", existing["id"]),
                )
            connection.commit()

    def _messages_to_keep(self, rows: list[sqlite3.Row], budget: int) -> int:
        """How many of the most recent messages fit in the budget (at least `keep_recent`)."""
        total = 0
        keep = 0
        for row in reversed(rows):
            cost = self._count_tokens([self._to_message(row)])
            if keep >= self._keep_recent and total + cost > budget:
                break
            total += cost
            keep += 1
        return keep

    def _summarize(self, old_messages: list[BaseMessage]) -> str:
        """Summarizes the messages that left the window and returns the text with the entities kept."""
        if self._model is None:
            summary = _fallback_summary(old_messages)
        else:
            conversation = get_buffer_string(old_messages)
            summary = str((SUMMARY_PROMPT | self._model | StrOutputParser()).invoke({"conversation": conversation}))
        return _preserve_entities(summary, old_messages)


def get_session_history(
    session_id: str,
    *,
    db_path: Path | str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    model: BaseChatModel | None = None,
) -> SQLiteChatHistory:
    """Per-session history factory, for the integrator's `RunnableWithMessageHistory`.

    With no extra arguments, the history lives in the `history.db` file of the configured runtime folder.
    """
    path = Path(db_path) if db_path is not None else get_settings().runtime_dir / HISTORY_FILE
    return SQLiteChatHistory(session_id, path, max_tokens, model=model)


# --- helpers ---------------------------------------------------------------------------------


def _role_of(message: BaseMessage) -> str:
    """The message role, as the table's `CHECK` expects."""
    role = getattr(message, "type", "")
    return role if role in {"human", "ai", "system", "tool"} else "human"


def _payload_of(message: BaseMessage) -> str | None:
    """The message's extra JSON: tool calls, call id or nothing."""
    if isinstance(message, AIMessage) and message.tool_calls:
        return json.dumps({"tool_calls": list(message.tool_calls)}, ensure_ascii=False)
    if isinstance(message, ToolMessage):
        return json.dumps({"tool_call_id": message.tool_call_id}, ensure_ascii=False)
    return None


def _marker(row: sqlite3.Row) -> str:
    """The row's mark: `summary`, `condensed` or nothing."""
    if not row["tool_calls"]:
        return ""
    try:
        payload = json.loads(row["tool_calls"])
    except ValueError:
        return ""
    if payload.get("summary"):
        return "summary"
    if payload.get("condensed"):
        return "condensed"
    return ""


def _entities_in(messages: list[BaseMessage]) -> list[str]:
    """The identifiers, amounts and dates that appear in the messages, in order of appearance."""
    found: list[str] = []
    for message in messages:
        text = str(message.content)
        for pattern in (_ID, _AMOUNT, _DATE):
            for match in pattern.findall(text):
                token = match if isinstance(match, str) else match[0]
                if token not in found:
                    found.append(token)
    return found


def _preserve_entities(summary: str, old_messages: list[BaseMessage]) -> str:
    """Appends to the summary the entities the model left out."""
    missing = [token for token in _entities_in(old_messages) if token not in summary]
    if not missing:
        return summary
    return f"{summary}\nKept identifiers: {', '.join(missing)}"


def _fallback_summary(old_messages: list[BaseMessage]) -> str:
    """Summary with no model: the first sentence of each message, plus the kept entities."""
    pieces = []
    for message in old_messages:
        text = " ".join(str(message.content).split())
        first = text.split(". ")[0].strip()
        if first:
            pieces.append(first)
    return "Automatic summary: " + " | ".join(pieces)
