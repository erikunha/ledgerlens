"""`RunnableWithMessageHistory` over the SQLite history: stores and reloads by session id.

What they guarantee, and why: each session id has its own conversation; a new session starts empty; and the
conversation survives a new process, because it lives in the SQLite file and not in the object's memory. The
integrator uses the checkpointer for the same purpose inside the process; this is the demonstration of the
legacy API, over the history the project wrote. The model is a `ScriptedChatModel` that records what it gets.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from ledgerlens.agents.modern import build_history_runnable
from ledgerlens.offline import ScriptedChatModel, text_message

ROOT = Path(__file__).resolve().parents[2]


def seen(model: ScriptedChatModel, call: int) -> str:
    return " ".join(str(m.content) for m in model.calls[call])


def config(session_id: str) -> dict:
    return {"configurable": {"session_id": session_id}}


def test_the_history_is_kept_per_session_id(tmp_path: Path) -> None:
    script = [text_message("TX-2048 is paid."), text_message("It was TX-2048."), text_message("Hi.")]
    model = ScriptedChatModel(script=script)
    chain = build_history_runnable(model, db_path=tmp_path / "history.db")
    chain.invoke({"question": "What is the status of TX-2048?"}, config("s1"))
    chain.invoke({"question": "Which transaction was it again?"}, config("s1"))
    chain.invoke({"question": "Hello"}, config("s2"))

    assert "What is the status of TX-2048?" in seen(model, 1) and "TX-2048 is paid." in seen(model, 1)
    assert "TX-2048" not in seen(model, 2)  # the new session starts empty


def test_the_history_is_reloaded_by_a_new_chain_on_the_same_file(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    first = ScriptedChatModel(script=[text_message("Noted: TX-2048.")])
    build_history_runnable(first, db_path=db).invoke({"question": "Remember TX-2048"}, config("s1"))

    second = ScriptedChatModel(script=[text_message("It was TX-2048.")])
    build_history_runnable(second, db_path=db).invoke({"question": "Which one was it?"}, config("s1"))
    assert "Remember TX-2048" in seen(second, 0) and "Noted: TX-2048." in seen(second, 0)


PROCESS = """
import json, sys
from ledgerlens.agents.modern import build_history_runnable
from ledgerlens.offline import ScriptedChatModel, text_message

db, question, answer = sys.argv[1:4]
model = ScriptedChatModel(script=[text_message(answer)])
chain = build_history_runnable(model, db_path=db)
chain.invoke({"question": question}, {"configurable": {"session_id": "s1"}})
print(json.dumps([str(m.content) for m in model.calls[0]]))
"""


def run_process(db: Path, question: str, answer: str) -> list[str]:
    done = subprocess.run(
        [sys.executable, "-c", PROCESS, str(db), question, answer],
        cwd=ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_the_history_survives_a_process_restart(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    run_process(db, "Remember TX-2048", "Noted.")
    prompt = " ".join(run_process(db, "Which one was it?", "It was TX-2048."))
    assert "Remember TX-2048" in prompt and "Noted." in prompt
