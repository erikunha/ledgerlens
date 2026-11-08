"""Dynamic routing: `LLMRouterChain` with `MultiPromptChain` (legacy) and the modern equivalent.

What it is for: deciding, for each question, which specialized prompt answers it. There are two
destinations here, `policy` (rule, deadline, procedure) and `investigation` (a concrete case that needs
crossing data), plus a default route for whatever fits neither.

Legacy flow (from `langchain-classic`; kept as a demonstration because it was deprecated):
1. `LLMRouterChain` sends the model the question plus the list of destinations and expects back a JSON
   block with `destination` and `next_inputs` (the question, possibly rewritten).
2. `MultiPromptChain` reads `destination` and runs that destination's chain. `DEFAULT` (or a name that
   does not exist) falls to the default route. That is two model calls per question: one to route, one to answer.
3. The output has the `text` key.

Modern flow (`build_modern_router`): the same one-word prompt from `ROUTER_PROMPT` picks the
route, and a routing function with `RunnableBranch` runs the right chain. No JSON in Markdown to
parse, with `invoke`, `batch` and `stream` for free. It is what new code uses; the legacy one is
marked as deprecated (ADR-010) and goes away in version 2.0.

Both use the same destination texts, so the comparison shows only the difference in mechanism.
The legacy deprecation warnings are expected and kept out of the tests.
"""

from __future__ import annotations

import warnings
from typing import Any

from langchain_classic.chains import LLMChain
from langchain_classic.chains.router import MultiPromptChain
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.runnables import Runnable, RunnableBranch

from ledgerlens.prompts import ROUTER_PROMPT

# Destination name (a code value) -> what it handles and the system text of its chain.
DESTINATIONS: dict[str, dict[str, str]] = {
    "policy": {
        "description": "a question about a rule, deadline or procedure, with no concrete case",
        "system": (
            "You answer questions about LedgerLens payment operating policies "
            "(refund, dispute, duplicate, payout, FX). Explain the rule in a few sentences, "
            "say which policy it comes from and warn when the answer depends on a concrete case."
        ),
    },
    "investigation": {
        "description": "a concrete case that needs crossing ledger data, policy, FX or a calculation",
        "system": (
            "You open a LedgerLens payment investigation. List the identifiers in the question, "
            "the data that must be looked up in the ledger and the rules to check, in short steps. "
            "Do not make up values: say what is left to look up."
        ),
    },
}

DEFAULT_SYSTEM = (
    "You handle first contact at LedgerLens. The question is neither about policy nor an investigation. "
    "Ask for the missing detail, such as the transaction identifier, and say what you can help with."
)

# The library's router prompt, rewritten for this project. JSON in Markdown is the format that
# `RouterOutputParser` understands, so the output example cannot change. `{{{{` becomes `{{` here
# and `{` later, when `PromptTemplate` fills in `{input}`.
ROUTER_TEMPLATE = """\
Given a question, pick the prompt best suited to answer it. You get the name of each prompt \
and a description of what it handles. If it helps, rewrite the question to get a better answer.

<< FORMAT >>
Answer with a Markdown code block holding a JSON object in this format:
```json
{{{{
    "destination": string \\ name of the prompt or "DEFAULT"
    "next_inputs": string \\ the original question, or an improved version of it
}}}}
```

REMEMBER: "destination" MUST be one of the names below, or "DEFAULT" if the question fits none of them.
REMEMBER: "next_inputs" can be the original question if it needs no change.

<< CANDIDATE PROMPTS >>
{destinations}

<< QUESTION >>
{{input}}

<< OUTPUT (start with ```json and end with ```) >>
"""


def build_legacy_router(model: BaseChatModel) -> MultiPromptChain:
    """The `langchain-classic` router: `LLMRouterChain` inside a `MultiPromptChain`.

    Input `{"input": "<question>"}`, output with the `text` key.
    """
    from langchain_classic.chains.router.llm_router import LLMRouterChain, RouterOutputParser

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # expected deprecation warning, see the module docstring
        listing = "\n".join(f"{name}: {info['description']}" for name, info in DESTINATIONS.items())
        router_prompt = PromptTemplate(
            template=ROUTER_TEMPLATE.format(destinations=listing),
            input_variables=["input"],
            output_parser=RouterOutputParser(),
        )
        router = LLMRouterChain.from_llm(model, router_prompt)
        chains: dict[str, Any] = {
            name: LLMChain(
                llm=model,
                prompt=PromptTemplate.from_template(f"{info['system']}\n\nQuestion: {{input}}"),
                output_key="text",
            )
            for name, info in DESTINATIONS.items()
        }
        default = LLMChain(
            llm=model,
            prompt=PromptTemplate.from_template(f"{DEFAULT_SYSTEM}\n\nQuestion: {{input}}"),
            output_key="text",
        )
        return MultiPromptChain(router_chain=router, destination_chains=chains, default_chain=default)


def build_modern_router(model: BaseChatModel) -> Runnable[dict, str]:
    """The same routing with no legacy classes: a one-word prompt and a `RunnableBranch`.

    Input `{"question": "<question>"}`, text output. The `status` route of `ROUTER_PROMPT` (a lookup
    of an identifier) goes on to the investigation; an unknown word falls to the default route.
    """

    def answer_with(system: str) -> Runnable[dict, str]:
        prompt = ChatPromptTemplate.from_messages([("system", system), ("human", "{question}")])
        return prompt | model | StrOutputParser()

    policy = answer_with(DESTINATIONS["policy"]["system"])
    investigation = answer_with(DESTINATIONS["investigation"]["system"])
    default = answer_with(DEFAULT_SYSTEM)

    # `strip().lower()` because the model may return "Policy." or a line break.
    def chosen(word_is: tuple[str, ...]):
        return lambda x: x["path"].strip().strip(".").lower() in word_is

    routed = {"path": ROUTER_PROMPT | model | StrOutputParser(), "question": lambda x: x["question"]}
    branch = RunnableBranch(
        (chosen(("policy",)), policy),
        (chosen(("investigation", "status")), investigation),
        default,
    )
    return routed | branch
