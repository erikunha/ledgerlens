"""The project's prompts package.

Import the templates from here (`from ledgerlens.prompts import TRIAGE_PROMPT`) instead of from
`templates.py`, so the rest of the code does not depend on where each prompt is stored.
"""

from ledgerlens.prompts.templates import REPAIR_PROMPT, ROUTER_PROMPT, SUMMARY_PROMPT, TRIAGE_PROMPT

__all__ = ["REPAIR_PROMPT", "ROUTER_PROMPT", "SUMMARY_PROMPT", "TRIAGE_PROMPT"]
