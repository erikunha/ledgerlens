"""The server side allowlist of the models a visitor may run, with the price and its provenance.

Why it exists: the visitor picks a model from a list the server holds, and never from a name the visitor types.
The catalogue is the only answer the interface may show, and the server refuses by itself any identifier that is
not in the allowlist, so a request that skips the interface is refused exactly like one that goes through it
(FR-016, FR-027).

Two rules shape everything here. The first is honesty about what was tested: only a model whose tool calling was
actually exercised may carry the status `tested`, and a model that was not tested carries `experimental` or
`disabled`. The second is honesty about money: a price that was not verified is absent and never a guess, so the
cost panel can say unknown instead of showing a number nobody checked (FR-011). A price is money, so it is a
Decimal and the contract carries it as text.

A third rule is about the reading of a contract: a payload that cannot be read is refused with a refusal of the
family and a readable message, and not with an error of the language, because a bad payload is an answer of a
server and the caller has to be able to read what is wrong with it (FR-030, FR-031).

A fourth rule is about what a refusal carries: a refusal of the registry names the reason and never the value that
the visitor sent, because the identifier of a model is a value of the visitor and the visitor may have put a key of
their provider in that field (FR-018, SC-001).

The allowlist is data in this module, next to the code that reads it, so that the price and the date it was last
verified travel with the model they belong to (FR-031). The catalogue exposes the status and the capabilities of
each profile, because the interface has to show the visitor what the model can do (FR-030).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal

from ledgerlens.byok.errors import ByokError, CapabilityMissing, ContractRefused

__all__ = [
    "ALLOWLIST",
    "ARCHITECTURE_CAPABILITIES",
    "CAPABILITIES",
    "CATALOGUE_CAPABILITY",
    "PROVIDERS",
    "STATUSES",
    "Capability",
    "CapabilityMissing",
    "ContractRefused",
    "ModelNotAllowed",
    "ModelProfile",
    "Pricing",
    "ProfileStatus",
    "ProviderRegistry",
    "required_capabilities",
]

ProfileStatus = Literal["tested", "experimental", "disabled", "retired"]
Capability = Literal["chat", "tool_calling", "structured_output", "reasoning"]

# The status of a profile says what was actually verified with it. Only `tested` unlocks the catalogue.
STATUSES: tuple[ProfileStatus, ...] = ("tested", "experimental", "disabled", "retired")

# The capabilities a profile may declare.
CAPABILITIES: tuple[Capability, ...] = ("chat", "tool_calling", "structured_output", "reasoning")

# The capability each architecture needs. A is the chain with no tools; B and C drive the tools of the agent, so
# they need a model that calls tools natively (FR-015).
ARCHITECTURE_CAPABILITIES: Mapping[str, frozenset[str]] = {
    "A": frozenset(),
    "B": frozenset({"tool_calling"}),
    "C": frozenset({"tool_calling"}),
}

# The provider of each model, the way the provider itself names it.
PROVIDERS: tuple[str, ...] = ("openai", "anthropic", "google", "local")

# The capability every profile of the catalogue has to declare. The agent of the demo drives the tools of the
# case, so a model that cannot call a tool is not a model the demo can run (FR-015, SC-009).
CATALOGUE_CAPABILITY = "tool_calling"

# The tokens of one million, the unit the prices of the registry are quoted in.
TOKENS_PER_MILLION = Decimal(1_000_000)


class ModelNotAllowed(ByokError):
    """The requested model is not one the server is allowed to run.

    Why the refusal never names the identifier: the identifier is a value the visitor sent, and a refusal that
    repeats it carries the value of the visitor out of the process, whatever that value is. The refusal names the
    reason and not the value, and the reason is enough: the visitor reads it and a silent swap of the model would
    make the comparison dishonest (FR-016, FR-027, FR-018, SC-001).
    """

    reason = "the model is not allowed"


def required_capabilities(architecture: str) -> frozenset[str]:
    """The capabilities the architecture needs from the model.

    A is the only architecture that runs without the tools of the agent, so every other variant needs a model that
    calls tools natively. An architecture nobody named yet gets the strict requirement, because a run that ends in
    a broken tool call wastes the money of the visitor (FR-015).
    """
    return ARCHITECTURE_CAPABILITIES.get(architecture, frozenset({"tool_calling"}))


def _to_decimal(value: object) -> Decimal | None:
    """The money of the contract as a Decimal, whether it arrives as text or as a number.

    The contract carries a price as text so that no binary float ever touches it, and a number is accepted as
    well so that a caller that has one does not have to guess the format.
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _to_amount(value: object, kind: str) -> Decimal | None:
    """The money of the contract as a Decimal, or a refusal when the text is not an amount.

    Why the refusal and not the error of the language: a payload that carries an amount nobody can read is a bad
    answer of a server, and the caller has to receive a refusal of the family with a message it can read (FR-011).
    """
    if value is None:
        return None
    try:
        amount = _to_decimal(value)
    except (InvalidOperation, ValueError, TypeError) as error:
        raise ContractRefused(f"the {kind} price '{value}' is not an amount that can be read") from error
    if amount is None or amount < 0:
        raise ContractRefused(f"the {kind} price '{value}' is not a price")
    return amount


def _to_date(value: object) -> date | None:
    """The day of the contract as a date, or a refusal when the text is not a day."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ContractRefused(f"the day of the last verification '{value}' is not a day that can be read")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ContractRefused(f"the day of the last verification '{value}' is not a day that can be read") from error


@dataclass(frozen=True)
class Pricing:
    """The price of a model, where it comes from and when it was last checked.

    The price is absent unless it was verified: `source` says who publishes it, `last_verified` says when the
    server last compared it with the publisher, and the two amounts are the price itself. A price that was not
    verified has no amounts at all, because a guess is worse than an absence (FR-011).
    """

    source: Literal["provider", "manual", "unknown"]
    last_verified: date | None
    input_per_1m_usd: Decimal | None
    output_per_1m_usd: Decimal | None

    @property
    def is_verified(self) -> bool:
        """True when the price was really checked: a known source, a date and both amounts."""
        return (
            self.source != "unknown"
            and self.last_verified is not None
            and self.input_per_1m_usd is not None
            and self.output_per_1m_usd is not None
        )

    def to_contract(self) -> dict[str, object]:
        """The price as the contract carries it: text for the money and a date for the day."""
        return {
            "source": self.source,
            "last_verified": self.last_verified.isoformat() if self.last_verified is not None else None,
            "input_per_1m_usd": None if self.input_per_1m_usd is None else str(self.input_per_1m_usd),
            "output_per_1m_usd": None if self.output_per_1m_usd is None else str(self.output_per_1m_usd),
        }

    @classmethod
    def from_contract(cls, data: Mapping[str, object]) -> Pricing:
        """The price of a contract payload, with the money parsed into a Decimal.

        Why a payload that cannot be read is refused and not raised: the caller of the domain receives a refusal
        of the family with a readable message, and not an error of the language that says nothing about the price
        (FR-011, FR-031).
        """
        if not isinstance(data, Mapping):
            raise ContractRefused("the payload of the price is not a map")
        source = data.get("source", "unknown")
        if source not in {"provider", "manual", "unknown"}:
            raise ContractRefused(f"the source of the price '{source}' is not one the registry knows")
        last_verified = _to_date(data.get("last_verified"))
        input_amount = _to_amount(data.get("input_per_1m_usd"), "input")
        output_amount = _to_amount(data.get("output_per_1m_usd"), "output")
        if source == "unknown":
            # A price that was never verified carries no amount at all: an amount would be a guess (FR-011).
            if input_amount is not None or output_amount is not None:
                raise ContractRefused("a price that was never verified carries no amount at all")
        else:
            missing = []
            if last_verified is None:
                missing.append("the day it was verified")
            if input_amount is None:
                missing.append("the input amount")
            if output_amount is None:
                missing.append("the output amount")
            if missing:
                raise ContractRefused(
                    f"a price with the source '{source}' carries {', '.join(missing)}, and it carries nothing else"
                )
        return cls(
            source=source,  # type: ignore[arg-type]
            last_verified=last_verified,
            input_per_1m_usd=input_amount,
            output_per_1m_usd=output_amount,
        )


@dataclass(frozen=True)
class ModelProfile:
    """One model of the allowlist: what it is, what it can do and what it costs.

    The profile is the whole truth about a model for the interface: the provider and the exact identifier the
    provider knows it by, the capabilities that were really verified, the status that says how far the
    verification went, and the price with its provenance (FR-030, FR-031).
    """

    profile_id: str
    provider: str
    model_id: str
    display_name: str
    capabilities: tuple[str, ...]
    status: ProfileStatus
    enabled_in_public_demo: bool
    pricing: Pricing

    def to_contract(self) -> dict[str, object]:
        """The profile as the contract carries it."""
        return {
            "profile_id": self.profile_id,
            "provider": self.provider,
            "model_id": self.model_id,
            "display_name": self.display_name,
            "capabilities": list(self.capabilities),
            "status": self.status,
            "enabled_in_public_demo": self.enabled_in_public_demo,
            "pricing": self.pricing.to_contract(),
        }

    @classmethod
    def from_contract(cls, data: Mapping[str, object]) -> ModelProfile:
        """The profile of a contract payload, with the money parsed into a Decimal.

        Why a payload that cannot be read is refused and not raised: the caller of the domain receives a refusal
        of the family with a readable message, and not an error of the language that says nothing about the model
        (FR-030, FR-031).
        """
        if not isinstance(data, Mapping):
            raise ContractRefused("the payload of the profile is not a map")
        missing = [name for name in ("profile_id", "provider", "model_id", "display_name") if not data.get(name)]
        if missing:
            raise ContractRefused(f"the payload of the profile has no {', '.join(missing)}")
        provider = str(data["provider"])
        if provider not in PROVIDERS:
            raise ContractRefused(f"the provider '{provider}' of the profile is not one the registry knows")
        capabilities = data.get("capabilities", ())
        if not isinstance(capabilities, (list, tuple)) or not all(isinstance(name, str) for name in capabilities):
            raise ContractRefused("the capabilities of the profile are not a list of names")
        status = data.get("status", "experimental")
        if status not in STATUSES:
            raise ContractRefused(f"the status '{status}' of the profile is not one the registry knows")
        enabled = data.get("enabled_in_public_demo", False)
        if not isinstance(enabled, bool):
            raise ContractRefused("the flag of the public demo of the profile is not a boolean")
        pricing = data.get("pricing")
        if not isinstance(pricing, Mapping):
            raise ContractRefused("the payload of the profile carries no price")
        return cls(
            profile_id=str(data["profile_id"]),
            provider=provider,
            model_id=str(data["model_id"]),
            display_name=str(data["display_name"]),
            capabilities=tuple(capabilities),  # type: ignore[arg-type]
            status=status,  # type: ignore[arg-type]
            enabled_in_public_demo=enabled,
            pricing=Pricing.from_contract(pricing),
        )


# The allowlist of the server. It is data, and it is honest: a profile carries the status `tested` only when the
# tool calling of that model was really exercised, and a price carries the day it was last verified.
#
# The price of `gpt-4.1-mini` is the list price the published online evaluation of this repository used
# (`PRICE_PER_MTOK` of `ledgerlens/eval/run.py`), transcribed by hand on the day the evaluation ran, so the source
# is `manual` and the day is the day of that run.
#
# `gpt-4.1` is listed as experimental: this repository never exercised the tool calling of that model, so only the
# capability everybody expects of a chat model is claimed and the price is absent.
ALLOWLIST: tuple[ModelProfile, ...] = (
    ModelProfile(
        profile_id="openai-gpt-4.1-mini",
        provider="openai",
        model_id="gpt-4.1-mini",
        display_name="GPT-4.1 mini",
        capabilities=("chat", "tool_calling"),
        status="tested",
        enabled_in_public_demo=True,
        pricing=Pricing(
            source="manual",
            last_verified=date(2026, 11, 8),
            input_per_1m_usd=Decimal("0.40"),
            output_per_1m_usd=Decimal("1.60"),
        ),
    ),
    ModelProfile(
        profile_id="openai-gpt-4.1",
        provider="openai",
        model_id="gpt-4.1",
        display_name="GPT-4.1",
        capabilities=("chat",),
        status="experimental",
        enabled_in_public_demo=False,
        pricing=Pricing(source="unknown", last_verified=None, input_per_1m_usd=None, output_per_1m_usd=None),
    ),
)


class ProviderRegistry:
    """The allowlist of the models the server is allowed to call, and the only answer to a model request.

    The registry answers two questions and refuses a third. It answers which models the visitor may pick (the
    catalogue) and what a model costs (the price and its provenance). It refuses a model identifier that is not in
    the allowlist, and it refuses a profile that lacks a capability the architecture needs, naming the capability
    in both cases (FR-015, FR-016, FR-027).
    """

    def __init__(self, profiles: Iterable[ModelProfile] = ALLOWLIST) -> None:
        self._profiles: tuple[ModelProfile, ...] = tuple(profiles)

    def all_profiles(self) -> tuple[ModelProfile, ...]:
        """Every profile of the allowlist, whatever its status. The refresh of the registry reads this."""
        return self._profiles

    def catalogue(self) -> tuple[ModelProfile, ...]:
        """The profiles the visitor may pick: the tested ones that are enabled in the public demo.

        The catalogue never grows by itself. A profile enters it when its tool calling was really exercised and
        somebody marked it enabled, and it leaves it when it is disabled or retired (FR-016, SC-009).

        Why the capability is a filter and not a hope: the agent of the demo drives the tools of the case, so a
        profile without the tool calling would break in the middle of the run and spend the money of the visitor
        while it breaks. The catalogue answers only the profiles that have the capability (FR-015).
        """
        return tuple(
            profile
            for profile in self._profiles
            if profile.status == "tested"
            and profile.enabled_in_public_demo
            and CATALOGUE_CAPABILITY in profile.capabilities
        )

    def get(self, profile_id: str) -> ModelProfile | None:
        """The profile of the allowlist with this identifier, or None when there is none."""
        for profile in self._profiles:
            if profile.profile_id == profile_id:
                return profile
        return None

    def require(self, identifier: str) -> ModelProfile:
        """The profile the visitor asked for, or a refusal that names the reason and not the identifier.

        The identifier may be the profile identifier or the model identifier the provider knows, because the
        interface shows one and the request may carry the other. A profile the server knows but does not offer is
        refused too, and the reason says why: an experimental model is not a silent swap away from a tested one
        (FR-027).

        Why the refusal never quotes the identifier: the identifier came from the visitor, and the refusal of the
        domain reaches the client of the facade. A refusal that carries the value of the visitor carries it out of
        the process, and the visitor may have put a key of their provider in that field (FR-018, SC-001).
        """
        profile = self.get(identifier)
        if profile is None:
            for candidate in self._profiles:
                if candidate.model_id == identifier:
                    profile = candidate
                    break
        if profile is None:
            raise ModelNotAllowed("the model is not in the allowlist of the server, so the run is refused")
        if profile.status != "tested":
            # The status comes from the allowlist of the server and not from the request, so it is safe to name it.
            raise ModelNotAllowed(
                f"the model has the status '{profile.status}' and the server only runs tested models, "
                "so the run is refused"
            )
        if not profile.enabled_in_public_demo:
            raise ModelNotAllowed("the model is not enabled in the public demo, so the run is refused")
        return profile

    def require_capabilities(self, profile: ModelProfile, required: Iterable[str]) -> None:
        """Refuse a profile that lacks a capability the architecture needs, naming what is missing.

        The refusal never substitutes another model, because a comparison between two models that the visitor did
        not choose is a lie (FR-015).

        Why the refusal does not name the profile either: the profile came out of the allowlist because the
        identifier of the visitor matched it, and the identifier of the visitor may be a value that must not travel
        out of the process. The missing capability is the name of the server and it is enough (FR-018, SC-001).
        """
        missing = sorted(set(required) - set(profile.capabilities))
        if missing:
            names = ", ".join(f"'{capability}'" for capability in missing)
            raise CapabilityMissing(
                f"the model lacks the capability {names} that the architecture needs, "
                f"so the run is refused instead of running another model"
            )

    def price_for(self, model_id: str) -> Pricing | None:
        """The verified price of a model, or None when the price was never verified.

        None means unknown, not zero: a model with no verified price has no dollar amount anywhere (FR-011).
        """
        for profile in self._profiles:
            if profile.model_id == model_id and profile.pricing.is_verified:
                return profile.pricing
        return None

    def estimate_usd(self, model_id: str, *, input_tokens: int, output_tokens: int) -> Decimal | None:
        """What the tokens of a model cost at the price of the registry, or None when the price is unknown.

        The number comes from the code and never from the model, and it is a Decimal (FR-010, FR-011).
        """
        pricing = self.price_for(model_id)
        if pricing is None:
            return None
        assert pricing.input_per_1m_usd is not None and pricing.output_per_1m_usd is not None
        return (
            pricing.input_per_1m_usd * Decimal(input_tokens) / TOKENS_PER_MILLION
            + pricing.output_per_1m_usd * Decimal(output_tokens) / TOKENS_PER_MILLION
        )
