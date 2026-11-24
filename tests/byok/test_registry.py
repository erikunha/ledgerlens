"""The model registry: the allowlist the server answers, and the price that is never a guess.

What they guarantee, and why: (a) the catalog holds only the profiles of the allowlist and only the ones whose
tool calling was tested, so the visitor never picks a model the agent cannot drive (FR-016, SC-009); (b) a model
identifier that is not in the allowlist is refused by the server and not by the interface alone (FR-027); (c) a
profile that lacks a capability the architecture needs is refused with the missing capability named (FR-015);
(d) a price that was not verified is absent and never a guess, so the cost panel can say unknown (FR-011);
(e) a price is money, so it is a Decimal and never a float; (f) the catalog exposes the tested status and the
capabilities of each profile (FR-030) and a price carries its provenance and the date of the last verification
(FR-031); (h) no refusal of the registry names the identifier that the visitor sent, and it names the reason
instead (FR-018, SC-001); (i) the contract of the profile and the dataclass of the domain agree field for field, so
the interface cannot read a field the server does not fill.

Everything offline, with no key and no network: the registry is data and the tests never leave the process.
"""

from __future__ import annotations

import json
from dataclasses import fields, replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from ledgerlens.byok.errors import CapabilityMissing, ContractRefused
from ledgerlens.byok.registry import (
    ALLOWLIST,
    ARCHITECTURE_CAPABILITIES,
    ModelNotAllowed,
    ModelProfile,
    Pricing,
    ProviderRegistry,
    required_capabilities,
)
from ledgerlens.run_context import RunBudget

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "specs" / "003-r3-bring-your-own-key" / "contracts"
MODEL_PROFILE_SCHEMA = CONTRACTS / "model-profile.schema.json"
LIVE_RUN_REQUEST_SCHEMA = CONTRACTS / "live-run-request.schema.json"
CREDENTIAL_HANDLE_SCHEMA = CONTRACTS / "credential-handle.schema.json"


def priced_profile(profile_id: str = "openai-gpt-4.1-mini") -> ModelProfile:
    """A profile with a verified price, the shape the shipped catalog uses."""
    return ModelProfile(
        profile_id=profile_id,
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
    )


def unpriced_profile(profile_id: str = "openai-gpt-4.1") -> ModelProfile:
    """A profile whose price was never verified, so its price is absent."""
    return ModelProfile(
        profile_id=profile_id,
        provider="openai",
        model_id="gpt-4.1",
        display_name="GPT-4.1",
        capabilities=("chat",),
        status="experimental",
        enabled_in_public_demo=False,
        pricing=Pricing(source="unknown", last_verified=None, input_per_1m_usd=None, output_per_1m_usd=None),
    )


def test_the_catalog_lists_only_tested_models_with_tool_calling() -> None:
    """FR-016 and SC-009: the catalog is the tested part of the allowlist and nothing else."""
    catalog = ProviderRegistry().catalog()

    assert catalog, "the allowlist ships at least one model the visitor may run"
    for profile in catalog:
        assert profile.status == "tested", f"{profile.profile_id} is offered without being tested"
        assert profile.enabled_in_public_demo is True
        assert "tool_calling" in profile.capabilities, f"{profile.profile_id} was offered without tool calling"


def test_each_rule_of_the_catalog_is_proved_by_a_profile_that_fails_it() -> None:
    """SC-009: the catalog filters on the status, on the flag and on the capability, and each filter is proved.

    The four profiles are the ones that tell the filters apart: a profile that breaks one rule and holds the three
    others stays out of the catalog, so a catalog that forgot one of its rules would show it.
    """
    good = priced_profile(profile_id="good")
    without_tools = replace(priced_profile(profile_id="without-tools"), capabilities=("chat",))
    experimental = replace(priced_profile(profile_id="experimental"), status="experimental")
    disabled = replace(priced_profile(profile_id="disabled"), enabled_in_public_demo=False)

    catalog = ProviderRegistry([good, without_tools, experimental, disabled]).catalog()

    assert [profile.profile_id for profile in catalog] == ["good"]


def test_a_model_outside_the_allowlist_is_refused_by_the_server() -> None:
    """FR-027: the interface is not the only place that refuses an unknown model.

    Why the refusal does not name the identifier: the identifier is a value the visitor sent, and the refusal of the
    domain travels to the client of the facade, so a refusal that quotes it carries the value of the visitor out of
    the process, whatever that value is (FR-018, SC-001).
    """
    registry = ProviderRegistry()

    with pytest.raises(ModelNotAllowed) as unknown:
        registry.require("gpt-4o")

    assert "not in the allowlist" in str(unknown.value)
    assert "the run is refused" in str(unknown.value)
    assert "gpt-4o" not in str(unknown.value)

    with pytest.raises(ModelNotAllowed):
        registry.require("no-such-profile-id")


def test_no_refusal_of_the_registry_carries_the_identifier_of_the_visitor() -> None:
    """FR-018, SC-001: every refusal of the registry names the reason and never the value of the visitor.

    Why every refusal: the identifier of a model may be the profile identifier or the model identifier, and the
    visitor may have put a key of their provider in either of them.
    """
    registry = ProviderRegistry([priced_profile(), unpriced_profile()])

    refusals = []
    for identifier in ("gpt-4o", "openai-gpt-4.1", "gpt-4.1"):
        with pytest.raises(ModelNotAllowed) as refused:
            registry.require(identifier)
        refusals.append((identifier, str(refused.value)))

    for identifier, refusal in refusals:
        assert identifier not in refusal, refusal


def test_a_profile_that_is_not_offered_is_refused_with_its_reason() -> None:
    """A profile of the allowlist that is not tested is refused, and the reason is readable."""
    registry = ProviderRegistry([priced_profile(), unpriced_profile()])

    with pytest.raises(ModelNotAllowed) as refused:
        registry.require("openai-gpt-4.1")

    assert "experimental" in str(refused.value)
    assert "openai-gpt-4.1" not in str(refused.value)


def test_a_profile_without_tool_calling_is_refused_naming_the_capability() -> None:
    """FR-015: the refusal names the missing capability instead of swapping the model silently.

    Why the profile is not named: the profile came out of the allowlist because the identifier of the visitor
    matched it, and that identifier is a value of the visitor (FR-018, SC-001).
    """
    registry = ProviderRegistry([unpriced_profile(profile_id="openai-chat-only")])
    profile = registry.get("openai-chat-only")
    assert profile is not None

    with pytest.raises(CapabilityMissing) as refused:
        registry.require_capabilities(profile, required_capabilities("B"))

    assert "tool_calling" in str(refused.value)
    assert "openai-chat-only" not in str(refused.value)


def test_the_architectures_that_need_tool_calling_are_b_and_c() -> None:
    """The architecture needs tool calling for the architectures B and C, and A needs no tool."""
    assert required_capabilities("B") == frozenset({"tool_calling"})
    assert required_capabilities("C") == frozenset({"tool_calling"})
    assert required_capabilities("A") == frozenset()
    assert ARCHITECTURE_CAPABILITIES["B"] == frozenset({"tool_calling"})


def test_a_price_that_was_not_verified_is_absent_and_never_a_guess() -> None:
    """FR-011: the price of an unverified profile is None and the registry says so."""
    registry = ProviderRegistry([unpriced_profile()])

    assert registry.price_for("gpt-4.1") is None
    assert registry.estimate_usd("gpt-4.1", input_tokens=1000, output_tokens=500) is None

    profile = registry.get("openai-gpt-4.1")
    assert profile is not None
    assert profile.pricing.input_per_1m_usd is None
    assert profile.pricing.output_per_1m_usd is None
    assert profile.pricing.is_verified is False


def test_a_verified_price_carries_its_provenance_and_its_date() -> None:
    """FR-031: a price that exists says where it comes from and when it was last checked."""
    profile = ProviderRegistry([priced_profile()]).get("openai-gpt-4.1-mini")
    assert profile is not None

    assert profile.pricing.source == "manual"
    assert profile.pricing.last_verified == date(2026, 11, 8)
    assert profile.pricing.is_verified is True


def test_a_price_is_money_and_never_a_float() -> None:
    """Money is a Decimal: a float in the price path is a defect, not a rounding detail."""
    profile = ProviderRegistry([priced_profile()]).get("openai-gpt-4.1-mini")
    assert profile is not None

    assert isinstance(profile.pricing.input_per_1m_usd, Decimal)
    assert isinstance(profile.pricing.output_per_1m_usd, Decimal)
    assert isinstance(profile.pricing.last_verified, date)


def test_the_catalog_exposes_the_tested_status_and_the_capabilities() -> None:
    """FR-030: the interface needs the status and the capabilities of every model it lists."""
    catalog = ProviderRegistry().catalog()

    for profile in catalog:
        assert profile.status in {"tested", "experimental", "disabled", "retired"}
        assert profile.capabilities
        assert "tool_calling" in profile.capabilities


def test_the_estimate_of_a_price_is_decimal_math_over_the_registry_price() -> None:
    """The estimate is computed by the code, never by the model, and it is a Decimal."""
    registry = ProviderRegistry([priced_profile()])

    assert registry.estimate_usd("gpt-4.1-mini", input_tokens=1_000_000, output_tokens=0) == Decimal("0.40")
    assert registry.estimate_usd("gpt-4.1-mini", input_tokens=0, output_tokens=1_000_000) == Decimal("1.60")
    assert registry.estimate_usd("gpt-4.1-mini", input_tokens=0, output_tokens=0) == Decimal("0")


def test_the_shipped_allowlist_is_honest_about_what_was_tested() -> None:
    """Only a profile whose tool calling was tested may carry the status tested, and a price is never a guess."""
    for profile in ALLOWLIST:
        if profile.status == "tested":
            assert "tool_calling" in profile.capabilities, f"{profile.profile_id} claims tested without tool calling"
            assert profile.enabled_in_public_demo is True
        if profile.pricing.is_verified:
            assert profile.pricing.last_verified is not None
            assert profile.pricing.source in {"provider", "manual"}
            assert profile.pricing.input_per_1m_usd is not None
            assert profile.pricing.output_per_1m_usd is not None
        else:
            assert profile.pricing.input_per_1m_usd is None
            assert profile.pricing.output_per_1m_usd is None


def test_the_allowlist_is_data_and_the_registry_does_not_mutate_it() -> None:
    """The allowlist is data in the repository, and the registry hands it over as it is."""
    registry = ProviderRegistry()

    assert registry.all_profiles() == ALLOWLIST
    assert ProviderRegistry().catalog() == ProviderRegistry().catalog()


def test_the_model_profile_contract_agrees_with_the_dataclass_field_for_field() -> None:
    """The contract of the profile and the dataclass of the domain must not drift apart."""
    schema = json.loads(MODEL_PROFILE_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)

    assert set(schema["properties"]) == {field.name for field in fields(ModelProfile)}
    assert set(schema["properties"]["pricing"]["properties"]) == {field.name for field in fields(Pricing)}
    assert set(schema["required"]) == {field.name for field in fields(ModelProfile)}


def test_a_profile_serialises_into_the_contract() -> None:
    """A profile of the domain validates against the published contract."""
    schema = json.loads(MODEL_PROFILE_SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)

    for profile in ALLOWLIST:
        validator.validate(profile.to_contract())


def test_the_live_run_request_contract_names_the_profile_and_the_handle() -> None:
    """The request of a live run carries the profile of the allowlist and the opaque handle."""
    schema = json.loads(LIVE_RUN_REQUEST_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)

    properties = set(schema["properties"])
    assert "model_profile_id" in properties
    assert "credential_handle" in properties
    assert "limits" in properties


def test_the_limits_of_the_request_agree_with_the_budget_of_the_run_field_for_field() -> None:
    """Every limit of the request is a cap of the `RunBudget` of the run context, under the same name.

    The run context carries the budget and the whole core uses it (FR-025), so a limit of the request that the
    budget does not know would be a limit that holds nothing.
    """
    schema = json.loads(LIVE_RUN_REQUEST_SCHEMA.read_text(encoding="utf-8"))
    limits = schema["properties"]["limits"]

    budget_fields = {field.name for field in fields(RunBudget)}

    assert set(limits["properties"]) <= budget_fields
    assert set(limits["required"]) <= set(limits["properties"])
    assert {
        "max_model_calls",
        "max_tool_calls",
        "max_wall_seconds",
        "max_output_tokens",
    } == set(limits["required"])


def test_the_credential_handle_contract_agrees_with_the_dataclass_field_for_field() -> None:
    """The contract of the handle and the dataclass of the domain agree field for field.

    The dataclass is the `CredentialHandle` of the vault, whose fields are the handle, the provider, the creation
    and the expiry. The module of the vault is built in parallel, so the check is done when the module is there:
    the contract and the dataclass have to meet on the same names, and a name that drifts breaks the facade
    that joins them.
    """
    schema = json.loads(CREDENTIAL_HANDLE_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)

    assert set(schema["properties"]) == {"handle", "provider", "created_at", "expires_at"}
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["additionalProperties"] is False

    vault = pytest.importorskip("ledgerlens.byok.vault", reason="the vault is built in parallel")
    dataclass_fields = {field.name for field in fields(vault.CredentialHandle)}
    assert dataclass_fields == set(schema["properties"]), (
        "the contract of the handle and the dataclass of the vault must carry the same names"
    )


def test_the_credential_handle_contract_carries_no_secret() -> None:
    """The handle is opaque and it never carries the key: the contract has no field for a secret."""
    schema = json.loads(CREDENTIAL_HANDLE_SCHEMA.read_text(encoding="utf-8"))

    for name in schema["properties"]:
        assert "secret" not in name
        assert "key" not in name


# --- a payload that cannot be read is refused, and not raised ----------------------------------------


def test_a_price_that_cannot_be_read_is_refused_and_not_raised() -> None:
    """FR-011: a bad payload is a refusal of the family and not an error of the language.

    The money that is not a number and the day that is not a day would otherwise answer with the error of the
    decimal library or of the date library, and the caller of the domain would get something it cannot read. The
    message names what is wrong with the payload.
    """
    payloads = (
        (
            {
                "source": "manual",
                "last_verified": "2026-11-08",
                "input_per_1m_usd": "abc",
                "output_per_1m_usd": "1.60",
            },
            "abc",
        ),
        (
            {
                "source": "manual",
                "last_verified": "2026-11-08",
                "input_per_1m_usd": "0.40",
                "output_per_1m_usd": None,
            },
            "output amount",
        ),
        (
            {
                "source": "manual",
                "last_verified": "not-a-date",
                "input_per_1m_usd": "0.40",
                "output_per_1m_usd": "1.60",
            },
            "not-a-date",
        ),
        (
            {
                "source": "invented",
                "last_verified": "2026-11-08",
                "input_per_1m_usd": "0.40",
                "output_per_1m_usd": "1.60",
            },
            "invented",
        ),
    )

    for payload, mentioned in payloads:
        with pytest.raises(ContractRefused) as refused:
            Pricing.from_contract(payload)
        assert mentioned in str(refused.value), payload


def test_a_price_that_cannot_be_read_says_that_it_cannot_be_read() -> None:
    """FR-011: the refusal says what is wrong with the amount, and not only that it is not a price.

    The two messages are different: an amount that cannot be read is a payload the domain did not understand, and a
    price that is negative is a price that is not a price. A refusal that tells the two apart leaves the caller
    guessing.
    """
    payload = {
        "source": "manual",
        "last_verified": "2026-11-08",
        "input_per_1m_usd": "abc",
        "output_per_1m_usd": "1.60",
    }

    with pytest.raises(ContractRefused) as refused:
        Pricing.from_contract(payload)

    assert "not an amount that can be read" in str(refused.value)


def test_a_negative_price_is_refused() -> None:
    """FR-011: a price that is less than zero is not a price, and a price is money.

    A negative amount would make the cost of a run smaller than nothing, and the caps of the money would read it
    as money that was never spent.
    """
    payload = {
        "source": "manual",
        "last_verified": "2026-11-08",
        "input_per_1m_usd": "-0.40",
        "output_per_1m_usd": "1.60",
    }

    with pytest.raises(ContractRefused) as refused:
        Pricing.from_contract(payload)

    assert "price" in str(refused.value)


def test_a_profile_that_cannot_be_read_is_refused_and_not_raised() -> None:
    """FR-030: a payload without the names of the profile is a refusal and not a `KeyError`."""
    with pytest.raises(ContractRefused) as refused:
        ModelProfile.from_contract({"provider": "openai"})

    assert "profile_id" in str(refused.value)


def test_a_payload_of_the_contract_round_trips_through_the_domain() -> None:
    """FR-031: what the contract carries is what the domain reads, field for field."""
    for profile in ALLOWLIST:
        assert ModelProfile.from_contract(profile.to_contract()) == profile
