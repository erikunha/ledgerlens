"""The triage chain in two styles: imperative with `@chain` and declarative with LCEL.

What it is for: reading a customer's complaint and returning a `Triage` (intent, entities,
urgency and plan). It is the first piece of LedgerLens, before any agent exists.

Both styles use the same prompt, the same model and the same repairing parser, and so they give the
same result. The difference is only in how the composition is written (see `docs/architecture.md`).

Input: `{"complaint": "<text>"}`. Output: a `Triage`, or a `TriageError` if the model's answer
cannot be read even after a repair. `invoke`, `batch` and `stream` work in both.

This module also reads the 10 fixed cases of `data/eval/triage_cases.jsonl`, used by the tests, the
demo and the evaluation.
"""

from __future__ import annotations

from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, chain

from ledgerlens.chains.parsers import TriageError, make_repairing_parser, triage_format_instructions
from ledgerlens.config import PROJECT_ROOT
from ledgerlens.prompts import TRIAGE_PROMPT
from ledgerlens.schemas import Strict, Triage

CASES_PATH = PROJECT_ROOT / "data" / "eval" / "triage_cases.jsonl"


class TriageCase(Strict):
    """A fixed complaint with the expected triage (`expected`)."""

    id: str
    scenario: str | None  # simulator scenario S01 to S12 the text comes from; None for a standalone case
    complaint: str
    tags: list[str]
    expected: Triage


def load_triage_cases(path: Path = CASES_PATH) -> list[TriageCase]:
    """Reads the fixed cases, in file order (one JSON object per line)."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [TriageCase.model_validate_json(line) for line in lines if line.strip()]


def triage_prompt() -> ChatPromptTemplate:
    """The triage prompt with the format instructions already filled in; only `complaint` is left."""
    # `partial` fixes one variable now, so whoever uses the chain only passes the complaint.
    return TRIAGE_PROMPT.partial(format_instructions=triage_format_instructions())


def build_triage_declarative(model: BaseChatModel) -> Runnable[dict, Triage | TriageError]:
    """Declarative style (LCEL): prompt, model and parser joined with `|`."""
    return triage_prompt() | model | make_repairing_parser(model)


def build_triage_imperative(model: BaseChatModel) -> Runnable[dict, Triage | TriageError]:
    """Imperative style: the same three steps as plain Python code inside an `@chain` function."""
    prompt = triage_prompt()
    parser = make_repairing_parser(model)

    @chain
    def triage(inputs: dict) -> Triage | TriageError:
        messages = prompt.invoke(inputs)
        reply = model.invoke(messages)
        return parser.invoke(reply)

    return triage
