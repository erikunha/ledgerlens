"""The public surface of the live mode: one import, one family of refusals and a complete `__all__`.

Why this file exists: the slice was built by two workers in parallel, each with its own files, and the package was
assembled afterwards. The names of the package are the public names of the slice, so a name that lives in a module and
never reaches the package is a name the caller cannot find, and a name in the `__all__` that does not exist is a
crash at the import of somebody else's code.

Why the refusals are one family: the model that is not allowed, the endpoint that is refused and the credential of
another session are three reasons of the same feature, and a caller has to catch them with one name (ADR-033,
ADR-034).
"""

from __future__ import annotations

import importlib

import pytest

from ledgerlens import byok

# The modules of the slice, and the one that holds the family of the refusals.
THE_MODULES = (
    "ledgerlens.byok.adapter",
    "ledgerlens.byok.budget",
    "ledgerlens.byok.errors",
    "ledgerlens.byok.registry",
    "ledgerlens.byok.vault",
)


def test_every_name_of_the_package_exists() -> None:
    """A name of the `__all__` that does not exist breaks the caller at the import."""
    missing = [name for name in byok.__all__ if not hasattr(byok, name)]

    assert missing == []


def test_the_package_exports_the_public_names_of_every_module() -> None:
    """A public name of a module that never reaches the package is a name the caller cannot find."""
    exported = set(byok.__all__)
    missing: dict[str, list[str]] = {}

    for module_name in THE_MODULES:
        module = importlib.import_module(module_name)
        names = [name for name in module.__all__ if not name.startswith("_")]
        absent = [name for name in names if name not in exported]
        if absent:
            missing[module_name] = absent

    assert missing == {}


def test_the_refusals_of_the_slice_are_one_family() -> None:
    """Every refusal of the slice descends from the base of the package, so a caller catches them with one name."""
    from ledgerlens.byok.errors import ByokError

    refusals = [
        byok.CapabilityMissing,
        byok.ContractRefused,
        byok.CredentialExpired,
        byok.CredentialRefused,
        byok.CredentialRevoked,
        byok.CredentialUnknown,
        byok.EndpointRefused,
        byok.ModelNotAllowed,
        byok.UnknownProvider,
        byok.BudgetExceededError,
        byok.BudgetRefused,
        byok.ProviderCallFailed,
        byok.UsageRefused,
    ]

    for refusal in refusals:
        assert issubclass(refusal, ByokError), refusal.__name__
        assert issubclass(refusal, Exception)


def test_the_package_does_not_import_the_api_layer() -> None:
    """The domain layer never imports the API layer, and the live mode is domain."""
    forbidden = "ledgerlens.api"

    for module_name in THE_MODULES:
        module = importlib.import_module(module_name)
        for value in vars(module).values():
            name = getattr(value, "__module__", "") or ""
            assert not name.startswith(forbidden), f"{module_name} imports {name}"
            if isinstance(value, type):
                for attribute in vars(value).values():
                    attribute_name = getattr(attribute, "__module__", "") or ""
                    assert not attribute_name.startswith(forbidden), f"{module_name} imports {attribute_name}"


@pytest.mark.parametrize("module_name", THE_MODULES)
def test_every_module_of_the_slice_carries_a_docstring(module_name: str) -> None:
    """Every module of the repository starts with a docstring that says what it does and why."""
    module = importlib.import_module(module_name)

    assert module.__doc__, module_name
    assert module.__doc__.strip(), module_name
