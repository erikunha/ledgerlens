"""The spec of a specialist: what it may read, which tools it may call, what it may spend and what it must return.

Why the spec is versioned: a specialist that changed under a run is a specialist that nobody measured, and the
comparison of the studio names the version of every specialist it ran.

Why the registry lives in the code and not in a file of the configuration: the allowlist of the tools of a
specialist is a rule of safety, and a rule that a deployment may edit is a rule that may be edited away.

Why the registry holds specialists and not models: the model of a specialist is the model of the run, under ADR-037
and the ADR that chooses the model of each slot by the task it does. A specialist is a role and not another model.

Why every specialist must return what it says it returns: a specialist that returns nothing is a step that did not
run, and a run that counts it as a success is a run that reports a success it did not have.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

__all__ = ["SPECIALISTS", "SpecialistRefused", "spec_of"]


class SpecialistRefused(Exception):
    """The registry has no such specialist, and the message says so."""


@dataclass(frozen=True)
class SpecialistSpec:
    """What a specialist may do, with the version of the spec that says it.

    Why the tools are an allowlist and not a denylist: a tool that nobody thought of is a tool that may be called,
    and a specialist that may call anything is a specialist that may read anything.
    """

    name: str
    version: str
    # The tools the specialist may call. A tool outside this list is refused and never called.
    tools: tuple[str, ...]
    # What the specialist may read, in the words of the domain: "ledger", "policies", "fx", "cases".
    reads: tuple[str, ...]
    # The accounts the specialist may read. The scope of a run is never widened by a specialist.
    accounts: tuple[str, ...]
    # What the specialist must return: the fields the dispatcher reads of every result.
    returns: tuple[str, ...]
    # The most the specialist may spend, or None when the spend is bounded by the budget of the run alone.
    max_spend_usd: Decimal | None = None

    def allows(self, tool: str) -> bool:
        """Whether the specialist may call the tool."""
        return tool in self.tools

    def to_dict(self) -> dict[str, Any]:
        """The spec as a dictionary, for the trace of a run of the studio."""
        return {
            "name": self.name,
            "version": self.version,
            "tools": list(self.tools),
            "reads": list(self.reads),
            "accounts": list(self.accounts),
            "returns": list(self.returns),
            "max_spend_usd": None if self.max_spend_usd is None else str(self.max_spend_usd),
        }


# The registry of the specialists of the first version. Every one of them reads the ledger of the run and nothing
# else, and every one of them is a role and not a model.
SPECIALISTS: dict[str, SpecialistSpec] = {
    "ledger_reader": SpecialistSpec(
        name="ledger_reader",
        version="v1",
        tools=("query_ledger", "get_ledger_record"),
        reads=("ledger",),
        accounts=(),
        returns=("evidence_refs",),
    ),
    "policy_reader": SpecialistSpec(
        name="policy_reader",
        version="v1",
        tools=("search_policies",),
        reads=("policies",),
        accounts=(),
        returns=("evidence_refs",),
    ),
    "rate_reader": SpecialistSpec(
        name="rate_reader",
        version="v1",
        tools=("get_reference_fx",),
        reads=("fx",),
        accounts=(),
        returns=("evidence_refs",),
    ),
    "calculator": SpecialistSpec(
        name="calculator",
        version="v1",
        tools=("calculate",),
        reads=("ledger",),
        accounts=(),
        returns=("amount", "evidence_refs"),
    ),
    "case_recaller": SpecialistSpec(
        name="case_recaller",
        version="v1",
        tools=("recall_cases",),
        reads=("cases",),
        accounts=(),
        returns=("evidence_refs",),
    ),
}


def spec_of(name: str) -> SpecialistSpec:
    """The spec of a specialist of the registry, and a refusal when the registry has no such specialist.

    Why an unknown specialist is a refusal and not a default: a specialist that nobody wrote has no allowlist, and
    an empty allowlist that is treated as "everything" is a hole in the rule.
    """
    spec = SPECIALISTS.get(name)
    if spec is None:
        raise SpecialistRefused(
            f"the registry has no specialist named {name!r}, and the specialists it holds are "
            f"{sorted(SPECIALISTS)}"
        )
    return spec
