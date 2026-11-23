"""The project's prompts package.

Import the templates from here (`from ledgerlens.prompts import TRIAGE_PROMPT`) instead of from
`templates.py`, so the rest of the code does not depend on where each prompt is stored.

The package exports the templates and nothing else. The sentence of the disclosure of the AI agent lives in
`ledgerlens.prompts.ai_disclosure`, and it is imported from that module and not from here, because a package
that exports a sentence is not a package of prompts.
"""

from ledgerlens.prompts.templates import REPAIR_PROMPT, ROUTER_PROMPT, SUMMARY_PROMPT, TRIAGE_PROMPT

__all__ = ["REPAIR_PROMPT", "ROUTER_PROMPT", "SUMMARY_PROMPT", "TRIAGE_PROMPT"]
