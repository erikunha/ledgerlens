"""The refusals of the live mode: one error per reason, each with a readable message.

Why it exists: the live mode refuses a lot of things, and every refusal has to say why in words a visitor can read.
One generic error would leave the interface guessing, and a guess in a refusal is a refusal that does not explain
itself.

What the module holds:

* `ByokError`, the base of every refusal, so a caller catches the family with one name;
* `CredentialRefused`, when the key itself was refused;
* `CredentialExpired`, when the credential outlived its time to live;
* `CredentialUnknown`, when the handle is unknown to the vault, and also when the handle belongs to another session,
  because the two answers have to be the same (FR-006);
* `CredentialRevoked`, when the credential was dropped on purpose: forgotten by its owner, evicted because the vault
  was full, or dropped after too many failures (FR-023);
* `UnknownProvider`, when the provider is not in the allowlist of the registry;
* `CapabilityMissing`, when the model profile lacks a capability the architecture needs (FR-015);
* `ContractRefused`, when a payload of a published contract cannot be read by the domain;
* `ProviderCallFailed`, when the error of a provider keeps the credential of the run in a text that the generic
  path of the scrub cannot reach.

Why the detail of a refusal is scrubbed: a refusal is read by a visitor and written to a log, and a detail that
carries a key would leak it (FR-018). Every detail goes through the `redact` helper of the observability package,
which is the one definition of "what looks like a key" in the repository. That helper removes the keys of the known
shapes; the secret of a credential of any other shape is scrubbed by the vault itself, which knows the exact text.
"""

from __future__ import annotations

from ledgerlens.observability.callbacks import redact


class ByokError(Exception):
    """The base of every refusal of the live mode.

    Why the reason is a class attribute: the message of a refusal has to name the reason even when the caller adds
    no detail, and the reason of a class never drifts from the class.
    """

    reason = "the request was refused"

    def __init__(self, detail: str | None = None) -> None:
        self.detail = redact(detail) if detail else None
        super().__init__(f"{self.reason}: {self.detail}" if self.detail else self.reason)


class CredentialRefused(ByokError):
    """The key was refused: it is empty, it is too long, or the provider did not accept it."""

    reason = "the credential was refused"


class CredentialExpired(ByokError):
    """The credential outlived its time to live and was dropped."""

    reason = "the credential expired"


class CredentialUnknown(ByokError):
    """The handle is unknown to the vault.

    Why this is also the answer for a handle of another session: the two answers have to be the same, or a visitor
    learns that a handle of another session exists (FR-006).
    """

    reason = "the credential handle is unknown"


class CredentialRevoked(ByokError):
    """The credential was dropped on purpose: forgotten, evicted, or dropped after too many failures."""

    reason = "the credential was revoked"


class UnknownProvider(ByokError):
    """The provider is not in the allowlist of the registry."""

    reason = "the provider is unknown"


class CapabilityMissing(ByokError):
    """The model profile lacks a capability that the selected architecture needs."""

    reason = "the model profile lacks a capability"


class ContractRefused(ByokError):
    """The payload of a published contract cannot be read by the domain.

    Why the refusal and not the error of the language: a payload that carries a money that is not a number, or a
    day that is not a day, is a bad answer of a server, and the caller has to receive a refusal of the family with
    a message it can read (FR-011, FR-031).
    """

    reason = "the contract payload was refused"


class ProviderCallFailed(ByokError):
    """The provider failed and its error keeps the credential of the run.

    This is the last resort of the scrub of the adapter: an error whose message the generic path cannot rewrite is
    replaced by this refusal, so that the key never leaves the adapter (FR-018, SC-001).
    """

    reason = "the provider call failed"


__all__ = [
    "ByokError",
    "CapabilityMissing",
    "ContractRefused",
    "CredentialExpired",
    "CredentialRefused",
    "CredentialRevoked",
    "CredentialUnknown",
    "ProviderCallFailed",
    "UnknownProvider",
]
