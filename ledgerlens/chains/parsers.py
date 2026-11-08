"""Structured triage output: a Pydantic parser, one repair and a typed error.

What it is for: the language model returns text, and the rest of the system needs a validated `Triage`
object. This module bridges the two and decides what to do when the text does not fit.

The path of an answer:
1. `PydanticOutputParser` tries to read the JSON and validate it against the `Triage` schema.
2. If that fails, the broken answer goes once to the repair prompt, together with the validator's
   message, and the model tries again.
3. If the repair fails too, the result is a `TriageError`, not an exception. That way a `batch`
   of 50 items does not stop because of one bad item.

A failure of the model call itself (network, quota, exhausted script) still raises: that is not an
error reading the answer, and hiding it would mask an infrastructure problem.
"""

from __future__ import annotations

from typing import Literal

from langchain_core.exceptions import OutputParserException
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from langchain_core.runnables import Runnable, chain
from pydantic import ValidationError

from ledgerlens.prompts import REPAIR_PROMPT
from ledgerlens.schemas import Strict, Triage

TRIAGE_PARSER: PydanticOutputParser[Triage] = PydanticOutputParser(pydantic_object=Triage)


class TriageError(Strict):
    """What comes back when the model's answer does not become a `Triage`, even after a repair.

    `code` tells the two possible defects apart: JSON that is not even JSON (`invalid_json`) and readable JSON
    that does not meet the schema, such as an intent that does not exist (`schema_violation`).
    """

    code: Literal["invalid_json", "schema_violation"]
    message: str
    raw_output: str
    repair_attempted: bool
    repaired_output: str | None = None


def triage_format_instructions() -> str:
    """The `Triage` JSON schema, written for the model. It goes inside the prompt."""
    return TRIAGE_PARSER.get_format_instructions()


def _text(output: str | BaseMessage) -> str:
    # In the chain the parser gets the model message; in the tests, a string. It accepts both.
    return output if isinstance(output, str) else str(output.text)


def _reason(error: OutputParserException) -> str:
    # LangChain appends a documentation link to the error; it only gets in the way of the repair prompt.
    return str(error).split("\nFor troubleshooting")[0].strip()


def _code(error: OutputParserException) -> Literal["invalid_json", "schema_violation"]:
    # The parser chains the original cause: ValidationError (schema) or JSONDecodeError (JSON).
    return "schema_violation" if isinstance(error.__cause__, ValidationError) else "invalid_json"


def make_repairing_parser(model: BaseChatModel) -> Runnable[str | BaseMessage, Triage | TriageError]:
    """Builds the repairing parser: reads the model's answer and, if needed, calls `model` once to fix it."""
    repair = REPAIR_PROMPT | model | StrOutputParser()
    format_instructions = triage_format_instructions()

    # `@chain` because there is branching here (try, fail, repair, give up): it reads better as plain code.
    @chain
    def parse_with_repair(output: str | BaseMessage) -> Triage | TriageError:
        raw = _text(output)
        try:
            return TRIAGE_PARSER.parse(raw)
        except OutputParserException as first:
            reason = _reason(first)

        # A single repair call: no loop, so cost and time stay bounded.
        repaired = repair.invoke({"bad_output": raw, "error": reason, "format_instructions": format_instructions})
        try:
            return TRIAGE_PARSER.parse(repaired)
        except OutputParserException as second:
            # Returns the error as a value (does not raise): the caller decides what to do with it.
            return TriageError(
                code=_code(second),
                message=_reason(second),
                raw_output=raw,
                repair_attempted=True,
                repaired_output=repaired,
            )

    return parse_with_repair
