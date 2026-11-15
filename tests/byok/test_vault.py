"""The credential vault of the live mode: the key stays in the memory of the process.

Why this file exists: the third story of the specification asks for a key that never reaches a file, a log, a trace or
an answer to the client (FR-002, FR-003, FR-004, FR-005, FR-006, FR-018, FR-021, FR-022, FR-023). The proof is
adversarial: a marker key goes through the vault and every place where it could have landed is inspected afterwards.

What the tests hold:

* the vault keeps the secret in the memory of the process and nowhere else: no file of the repository, no file of the
  runtime folder that the configuration names, no variable of the environment and no record of the log carries the
  marker (FR-003);
* the handle is opaque, random and never derived from the secret, and it carries the provider and the expiry and
  never the secret (FR-004, FR-005);
* the vault refuses a provider that the registry does not publish, because the public form of the handle carries
  the provider and the published contract enumerates it (FR-004);
* a handle of another session is refused with the same answer as a handle that never existed (FR-006);
* the vault is bounded, so the oldest credential is dropped when the vault is full, and the vault says so (FR-002);
* every credential expires, the expiry is decided by the injected clock, and the sweep runs on every access
  (FR-002, FR-022, SC-011);
* the number of failures of a credential is bounded, and the credential is dropped when the bound is reached (FR-023);
* the vault scrubs its own secret out of a text, so a provider exception that carries the key cannot carry it out of
  the vault while the credential is alive (FR-018);
* the messages of the refusals never carry the secret, and the ADR discloses that the runtime cannot guarantee the
  zeroization of the memory (FR-021).

Why the clock is injected: the expiry is decided by the server and never by the visitor, and a test that waits for an
hour proves nothing.

Why the marker of the secret has a shape the repository does not know: the scrub of the vault has to work on the
exact text of the secret, and not only on the shapes of the keys that the `redact` helper of the repository knows.
"""

from __future__ import annotations

import dataclasses
import hashlib
import logging
import os
import secrets
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from ledgerlens.byok import (
    DEFAULT_TTL_SECONDS,
    ByokError,
    CapabilityMissing,
    CredentialExpired,
    CredentialRefused,
    CredentialRevoked,
    CredentialUnknown,
    CredentialVault,
    UnknownProvider,
)
from ledgerlens.config import get_settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
# The published contract of the answer of the credential endpoint. The answer of the server has to validate against
# it, and not only carry the same names as the dataclass: a shape that drifts breaks the client that reads it.
CREDENTIAL_HANDLE_SCHEMA = (
    PROJECT_ROOT / "specs" / "003-r3-bring-your-own-key" / "contracts" / "credential-handle.schema.json"
)

# The marker of the secret: a shape that no known pattern of the repository matches, so only the vault itself can
# scrub it out of a text.
MARKER = "ledgerlens-marker-" + "4f3a9c2b7e1d"
# The marker of a key of a known shape: the helper `redact` of the observability package removes it on its own.
SHAPED_MARKER = "sk-" + "test-marker-0123456789abcdef"
OTHER_MARKER = "ledgerlens-marker-" + "88ce10"

# The folders of the tree that are not inspected, because they hold the environment of the machine and not the
# artifacts of the repository.
SKIPPED_FOLDERS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache", ".serena"}
# A file bigger than this is not read: the marker of the test cannot be in a file of that size, and reading every
# byte of the repository would make the suite slow.
MAX_SCANNED_BYTES = 64 * 1024 * 1024


class FakeClock:
    """A clock the test moves by hand, so that the expiry of a credential is proved without waiting."""

    def __init__(self, now: datetime | None = None) -> None:
        self.now = now or datetime.now(UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


@pytest.fixture
def clock() -> FakeClock:
    """The clock of the vault, moved by hand."""
    return FakeClock()


@pytest.fixture
def vault(clock: FakeClock) -> CredentialVault:
    """A vault with the default bounds and the clock of the test."""
    return CredentialVault(clock=clock)


def _files_under(root: Path) -> Iterator[Path]:
    """Every file of a tree that is worth reading."""
    if not root.exists():
        return
    for path in root.rglob("*"):
        if any(part in SKIPPED_FOLDERS for part in path.parts):
            continue
        try:
            if not path.is_file() or path.stat().st_size > MAX_SCANNED_BYTES:
                continue
        except OSError:
            # A file that another process removed while the tree was read is not a file of the tree.
            continue
        yield path


def _files_carrying(root: Path, marker: bytes) -> list[Path]:
    """The files of a tree that carry the marker, so a test can prove that it inspected the tree."""
    found: list[Path] = []
    for path in _files_under(root):
        try:
            content = path.read_bytes()
        except OSError:
            continue
        if marker in content:
            found.append(path)
    return found


def _runtime_dir() -> Path:
    """The folder of the runtime that the configuration names, whatever the folder is.

    Why the folder comes from the configuration and not from a constant of the test: the ADR claims that the test
    inspects the runtime folder, and that claim is only true when the test asks the configuration where it is
    (FR-003).
    """
    return Path(get_settings().runtime_dir)


# --- the key never reaches the disk, the environment or the log ---------------------------------------


def test_the_vault_holds_nothing_on_disk(vault: CredentialVault, tmp_path: Path) -> None:
    """FR-003: the secret is never written to a file, not in the repository and not in the runtime folder."""
    marker = "ledgerlens-disk-marker-" + secrets.token_hex(8)
    vault.accept(marker, "openai", session_id="sess-a")

    for root in (PROJECT_ROOT, tmp_path, _runtime_dir()):
        for path in _files_under(root):
            try:
                content = path.read_bytes()
            except OSError:
                continue
            assert marker.encode() not in content, f"the vault wrote the secret in {path}"


def test_the_runtime_folder_the_configuration_names_is_inspected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-003: the test inspects the folder the configuration names, even outside of the repository.

    The canary proves that the inspection reaches the folder: a marker that is planted in the folder is found by
    the same scan that looks for the secret of the vault.
    """
    runtime = tmp_path / "runtime-outside-the-repository"
    runtime.mkdir()
    monkeypatch.setenv("LEDGERLENS_RUNTIME_DIR", str(runtime))

    assert _runtime_dir() == runtime
    assert PROJECT_ROOT not in runtime.parents, "the runtime folder of this test has to be outside of the repository"

    canary = runtime / "canary.txt"
    canary.write_text("ledgerlens-canary-marker", encoding="utf-8")

    assert canary in _files_carrying(runtime, b"ledgerlens-canary-marker")


def test_the_vault_writes_nothing_in_a_runtime_folder_outside_the_repository(
    vault: CredentialVault, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-003: the secret does not reach the runtime folder of the configuration, wherever that folder is."""
    runtime = tmp_path / "runtime-outside-the-repository"
    runtime.mkdir()
    monkeypatch.setenv("LEDGERLENS_RUNTIME_DIR", str(runtime))
    marker = "ledgerlens-runtime-marker-" + secrets.token_hex(8)

    vault.accept(marker, "openai", session_id="sess-a")

    assert _files_carrying(runtime, marker.encode()) == []


def test_the_vault_never_touches_the_environment(vault: CredentialVault) -> None:
    """FR-007: the process environment is never mutated, so a visitor cannot see another visitor's key."""
    before = dict(os.environ)
    handle = vault.accept(MARKER, "openai", session_id="sess-a")
    vault.resolve(handle.handle, session_id="sess-a")
    assert dict(os.environ) == before
    assert not any(MARKER in value for value in os.environ.values())


def test_the_log_of_the_vault_never_carries_the_secret(
    clock: FakeClock, caplog: pytest.LogCaptureFixture
) -> None:
    """FR-018: what the vault writes in the log carries the reason and never the secret."""
    caplog.set_level(logging.DEBUG)
    vault = CredentialVault(max_entries=1, max_failures=1, clock=clock)
    handle = vault.accept(MARKER, "openai", session_id="sess-a")
    vault.record_failure(handle.handle, session_id="sess-a")
    vault.accept(OTHER_MARKER, "openai", session_id="sess-a")

    assert caplog.records, "the vault said nothing about the credentials it dropped"
    assert not any(MARKER in record.getMessage() for record in caplog.records)
    assert not any(OTHER_MARKER in record.getMessage() for record in caplog.records)
    assert not any(MARKER in str(record.args) for record in caplog.records)


# --- the handle is opaque, random and never carries the secret ----------------------------------------


def test_accepting_a_key_returns_the_handle_the_provider_and_the_expiry(vault: CredentialVault) -> None:
    """FR-005: the answer of the acceptance is the handle, the provider and the expiry."""
    handle = vault.accept(MARKER, "openai", session_id="sess-a")

    assert handle.provider == "openai"
    assert handle.handle
    assert handle.expires_at == handle.created_at + timedelta(seconds=vault.ttl_seconds)
    assert handle.expires_at > handle.created_at


def test_the_life_of_a_credential_can_be_given_to_the_vault(vault: CredentialVault) -> None:
    """FR-022: the vault applies the life that it is given, and its own life never changes.

    Why this matters: the layer that knows how much life the session of the visitor has left hands that life over,
    and the vault is never written to while the acceptance happens. A vault whose life the caller wrote for the
    moment of the acceptance would show a foreign life to every other reader of it, and two acceptances of the same
    process could swap their lives.
    """
    handle = vault.accept(MARKER, "openai", session_id="sess-a", ttl_seconds=60)

    assert handle.expires_at == handle.created_at + timedelta(seconds=60)
    assert vault.ttl_seconds == DEFAULT_TTL_SECONDS


def test_a_credential_without_a_life_of_its_own_lives_as_long_as_the_vault_says(vault: CredentialVault) -> None:
    """FR-022: the default of the vault is the life of a credential that is accepted without one."""
    handle = vault.accept(MARKER, "openai", session_id="sess-a")

    assert handle.expires_at == handle.created_at + timedelta(seconds=vault.ttl_seconds)


def test_a_credential_that_is_accepted_with_the_life_of_its_session_dies_with_it(
    vault: CredentialVault, clock: FakeClock
) -> None:
    """FR-022: the life that was given to the vault is the life the credential really has.

    Why the clock is moved: a credential that was accepted with a short life has to die at that short life and not at
    the life the vault would have given it.
    """
    handle = vault.accept(MARKER, "openai", session_id="sess-a", ttl_seconds=60)

    clock.advance(timedelta(seconds=59))
    assert vault.resolve(handle.handle, session_id="sess-a") == MARKER

    clock.advance(timedelta(seconds=2))
    with pytest.raises(CredentialExpired):
        vault.resolve(handle.handle, session_id="sess-a")


def test_a_life_that_is_shorter_than_a_second_is_refused(vault: CredentialVault) -> None:
    """FR-022: a credential that dies at once is a credential nobody can use."""
    with pytest.raises(CredentialRefused):
        vault.accept(MARKER, "openai", session_id="sess-a", ttl_seconds=0)

    assert len(vault) == 0


def test_the_handle_is_random_and_is_not_derived_from_the_secret(vault: CredentialVault) -> None:
    """FR-005: the handle tells nothing about the secret, because it is random and not derived from it."""
    first = vault.accept(MARKER, "openai", session_id="sess-a")
    second = vault.accept(MARKER, "openai", session_id="sess-a")

    assert first.handle != second.handle
    assert MARKER not in first.handle
    # The handle is not a digest of the secret either, so a handle cannot be used to guess the key.
    digest = hashlib.sha256(MARKER.encode("utf-8")).hexdigest()
    assert digest[:16] not in first.handle
    assert digest[:16] not in second.handle


def test_the_handle_carries_no_secret(vault: CredentialVault) -> None:
    """FR-004: the handle never carries the secret, not in its fields and not in its representation."""
    handle = vault.accept(MARKER, "openai", session_id="sess-a")

    assert MARKER not in repr(handle)
    assert MARKER not in str(dataclasses.asdict(handle))
    assert MARKER not in repr(vault)
    assert MARKER not in str(handle.to_public_dict())


def test_the_internal_entry_of_the_vault_carries_no_secret(vault: CredentialVault) -> None:
    """FR-003: the internals of the vault never show the key, not in a repr and not in a dump.

    The entry is a dataclass and the vault is an object of the process, so a debug print or a traceback with the
    locals of the vault would show the entry. The key of the entry never appears in the representation of the entry.
    """
    vault.accept(MARKER, "openai", session_id="sess-a")
    entry = next(iter(vault._entries.values()))

    assert MARKER not in repr(entry)
    assert MARKER not in repr(vault._entries)
    assert MARKER not in str(dataclasses.asdict(entry))


def test_a_provider_that_the_registry_does_not_publish_is_refused(vault: CredentialVault) -> None:
    """FR-004: the public form of the handle carries the provider, and the contract enumerates the providers.

    The vault and the registry never disagree about what a provider is: the list lives in the registry and the
    vault refuses a name that is not in it, so the answer of the server always validates against the contract.
    """
    with pytest.raises(UnknownProvider) as refused:
        vault.accept(MARKER, "acme-cloud", session_id="sess-a")

    assert "acme-cloud" in str(refused.value)
    assert MARKER not in str(refused.value)


def test_the_key_is_stripped_before_it_is_kept(vault: CredentialVault) -> None:
    """FR-003: the space and the newline around a pasted key are not part of the key."""
    handle = vault.accept(f"  {MARKER}\n", "openai", session_id="sess-a")

    assert vault.resolve(handle.handle, session_id="sess-a") == MARKER


def test_the_provider_is_stripped_before_it_is_kept(vault: CredentialVault) -> None:
    """FR-003 and FR-004: the space around a pasted provider is not part of the provider.

    The provider of the handle is one of the providers that the registry publishes, and a name with a space around
    it is not one of them, so the vault would refuse a provider that the visitor did paste.
    """
    handle = vault.accept(MARKER, " openai\n", session_id="sess-a")

    assert handle.provider == "openai"
    assert vault.resolve(handle.handle, session_id="sess-a") == MARKER


def test_the_bytes_of_the_secret_are_overwritten_when_the_credential_dies(clock: FakeClock) -> None:
    """FR-021: the buffer of the secret is overwritten when the credential is dropped.

    The proof is the best effort the runtime offers: the bytes of the buffer are zeroed, and the ADR says out loud
    that nobody can promise that no copy of the secret survives in the memory of the machine.
    """
    vault = CredentialVault(max_failures=1, clock=clock)
    handle = vault.accept(MARKER, "openai", session_id="sess-a")
    entry = next(iter(vault._entries.values()))

    vault.record_failure(handle.handle, session_id="sess-a")

    assert len(vault) == 0
    assert bytes(entry.secret._bytes) == b"\x00" * len(entry.secret._bytes)


def test_a_key_that_is_too_long_is_refused(vault: CredentialVault) -> None:
    """FR-002: the vault is bounded, and a key that is too long is refused instead of eating the memory."""
    with pytest.raises(CredentialRefused) as refused:
        vault.accept("k" * 513, "openai", session_id="sess-a")

    assert "512" in str(refused.value)
    assert len(vault) == 0


def test_the_public_form_of_the_handle_carries_the_handle_the_provider_and_the_expiry(vault: CredentialVault) -> None:
    """FR-005: what the client receives is the handle, the provider and the expiry, and nothing else.

    The names are the names of the dataclass, so the answer of the credential endpoint validates against the
    published contract of the handle. The name `credential_handle` belongs to the request that references a handle,
    and not to the answer that carries one.
    """
    handle = vault.accept(MARKER, "openai", session_id="sess-a")
    public = handle.to_public_dict()

    assert public["handle"] == handle.handle
    assert public["provider"] == "openai"
    assert public["created_at"] == handle.created_at.isoformat()
    assert public["expires_at"] == handle.expires_at.isoformat()
    assert set(public) == {"handle", "provider", "created_at", "expires_at"}


# --- the handle is bound to the session --------------------------------------------------------------


def test_a_handle_of_another_session_is_refused_like_a_handle_that_does_not_exist(vault: CredentialVault) -> None:
    """FR-006 and SC-002: the two answers are the same, so a visitor cannot learn that a handle exists."""
    handle = vault.accept(MARKER, "openai", session_id="sess-a")

    with pytest.raises(CredentialUnknown) as foreign:
        vault.resolve(handle.handle, session_id="sess-b")
    with pytest.raises(CredentialUnknown) as missing:
        vault.resolve("a-handle-that-never-existed", session_id="sess-b")

    assert str(foreign.value) == str(missing.value)


def test_the_secret_of_a_session_is_not_readable_from_another_session(vault: CredentialVault) -> None:
    """FR-006: the secret of the session A never reaches the session B."""
    handle = vault.accept(MARKER, "openai", session_id="sess-a")

    with pytest.raises(ByokError):
        vault.resolve(handle.handle, session_id="sess-b")

    assert vault.resolve(handle.handle, session_id="sess-a") == MARKER


def test_forgetting_a_handle_of_another_session_drops_nothing(vault: CredentialVault) -> None:
    """FR-006: a session cannot revoke the credential of another session."""
    handle = vault.accept(MARKER, "openai", session_id="sess-a")

    assert vault.forget(handle.handle, session_id="sess-b") is False
    assert vault.resolve(handle.handle, session_id="sess-a") == MARKER


def test_a_credential_that_is_gone_stays_unknown_for_another_session(vault: CredentialVault) -> None:
    """FR-006: the tombstone of a credential never tells another session that the credential existed."""
    handle = vault.accept(MARKER, "openai", session_id="sess-a")
    vault.forget(handle.handle, session_id="sess-a")

    with pytest.raises(CredentialUnknown) as foreign:
        vault.resolve(handle.handle, session_id="sess-b")
    with pytest.raises(CredentialUnknown) as missing:
        vault.resolve("a-handle-that-never-existed", session_id="sess-b")

    assert str(foreign.value) == str(missing.value)


# --- the vault is bounded ------------------------------------------------------------------------------


def test_the_vault_drops_the_oldest_credential_when_it_is_full(clock: FakeClock) -> None:
    """FR-002: the vault is bounded, and the oldest credential is the one that goes."""
    vault = CredentialVault(max_entries=2, clock=clock)
    first = vault.accept(MARKER, "openai", session_id="sess-a")
    clock.advance(timedelta(seconds=1))
    second = vault.accept(OTHER_MARKER, "openai", session_id="sess-a")
    clock.advance(timedelta(seconds=1))
    third = vault.accept(SHAPED_MARKER, "anthropic", session_id="sess-a")

    assert len(vault) == 2
    with pytest.raises(CredentialRevoked):
        vault.resolve(first.handle, session_id="sess-a")
    assert vault.resolve(second.handle, session_id="sess-a") == OTHER_MARKER
    assert vault.resolve(third.handle, session_id="sess-a") == SHAPED_MARKER


def test_the_vault_says_so_when_it_drops_the_oldest_credential(
    clock: FakeClock, caplog: pytest.LogCaptureFixture
) -> None:
    """FR-002: the vault announces the drop, and the announcement carries no secret."""
    caplog.set_level(logging.WARNING)
    vault = CredentialVault(max_entries=1, clock=clock)
    vault.accept(MARKER, "openai", session_id="sess-a")
    vault.accept(OTHER_MARKER, "anthropic", session_id="sess-a")

    assert "full" in caplog.text
    assert MARKER not in caplog.text


# --- every credential expires --------------------------------------------------------------------------


def test_an_expired_credential_is_refused_and_dropped(vault: CredentialVault, clock: FakeClock) -> None:
    """FR-002 and FR-022: the credential outlives its time to live and is dropped on the access."""
    handle = vault.accept(MARKER, "openai", session_id="sess-a")
    clock.advance(timedelta(seconds=vault.ttl_seconds + 1))

    with pytest.raises(CredentialExpired):
        vault.resolve(handle.handle, session_id="sess-a")
    assert len(vault) == 0


def test_the_sweep_drops_the_expired_credentials(vault: CredentialVault, clock: FakeClock) -> None:
    """FR-022: the sweep is the second way of forgetting, and it drops what expired."""
    handle = vault.accept(MARKER, "openai", session_id="sess-a")
    clock.advance(timedelta(seconds=vault.ttl_seconds + 1))

    assert vault.sweep() == 1
    assert len(vault) == 0
    with pytest.raises(CredentialExpired):
        vault.resolve(handle.handle, session_id="sess-a")


def test_the_sweep_runs_on_every_access(vault: CredentialVault, clock: FakeClock) -> None:
    """FR-002: an access sweeps the vault, so a credential nobody uses does not stay in the memory."""
    old = vault.accept(MARKER, "openai", session_id="sess-a")
    clock.advance(timedelta(seconds=vault.ttl_seconds + 1))

    vault.accept(OTHER_MARKER, "openai", session_id="sess-b")

    assert len(vault) == 1
    with pytest.raises(CredentialExpired):
        vault.resolve(old.handle, session_id="sess-a")


def test_a_vault_nobody_touches_still_forgets() -> None:
    """SC-011: the key survives in memory for no longer than its time to live, even with nobody around."""
    vault = CredentialVault(ttl_seconds=1)
    vault.accept(MARKER, "openai", session_id="sess-a")
    vault.start_sweeper()
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and len(vault) != 0:
            time.sleep(0.05)
    finally:
        vault.stop_sweeper()

    assert len(vault) == 0


def test_the_end_of_the_session_drops_every_credential_of_the_session(vault: CredentialVault) -> None:
    """FR-022: the reset of a session drops its credentials."""
    first = vault.accept(MARKER, "openai", session_id="sess-a")
    second = vault.accept(OTHER_MARKER, "anthropic", session_id="sess-a")
    other = vault.accept(SHAPED_MARKER, "openai", session_id="sess-b")

    assert vault.forget_session("sess-a") == 2
    assert len(vault) == 1
    with pytest.raises(CredentialRevoked):
        vault.resolve(first.handle, session_id="sess-a")
    with pytest.raises(CredentialRevoked):
        vault.resolve(second.handle, session_id="sess-a")
    assert vault.resolve(other.handle, session_id="sess-b") == SHAPED_MARKER


def test_a_restart_of_the_process_forgets_every_credential(vault: CredentialVault) -> None:
    """FR-022: the vault lives in the memory of the process, so a new process knows nothing."""
    handle = vault.accept(MARKER, "openai", session_id="sess-a")

    restarted = CredentialVault()

    with pytest.raises(CredentialUnknown):
        restarted.resolve(handle.handle, session_id="sess-a")


# --- the number of failures is bounded ------------------------------------------------------------------


def test_a_failure_below_the_bound_keeps_the_credential(vault: CredentialVault) -> None:
    """FR-023: the credential survives the failures that are below the bound."""
    handle = vault.accept(MARKER, "openai", session_id="sess-a")

    vault.record_failure(handle.handle, session_id="sess-a")

    assert vault.resolve(handle.handle, session_id="sess-a") == MARKER


def test_the_credential_is_dropped_when_the_failures_reach_the_bound(vault: CredentialVault) -> None:
    """FR-023: the bound of the failures drops the credential."""
    handle = vault.accept(MARKER, "openai", session_id="sess-a")

    for _ in range(vault.max_failures):
        vault.record_failure(handle.handle, session_id="sess-a")

    assert len(vault) == 0
    with pytest.raises(CredentialRevoked):
        vault.resolve(handle.handle, session_id="sess-a")


def test_the_reason_of_a_dropped_credential_names_the_failures(vault: CredentialVault) -> None:
    """FR-023: the refusal says why the credential is gone."""
    handle = vault.accept(MARKER, "openai", session_id="sess-a")
    for _ in range(vault.max_failures):
        vault.record_failure(handle.handle, session_id="sess-a")

    with pytest.raises(CredentialRevoked) as refusal:
        vault.resolve(handle.handle, session_id="sess-a")

    assert "failure" in str(refusal.value)
    assert MARKER not in str(refusal.value)


# --- the vault scrubs its own secret out of a text ------------------------------------------------------


def test_the_scrub_removes_the_secret_of_the_vault_from_a_provider_exception(vault: CredentialVault) -> None:
    """FR-018: a provider exception that carries the key cannot carry it out of the vault while it is alive."""
    vault.accept(MARKER, "openai", session_id="sess-a")

    message = vault.scrub(f"the provider said: 401 invalid api key {MARKER} for the model")

    assert MARKER not in message
    assert "[REDACTED]" in message


def test_the_tombstone_of_a_dead_credential_carries_no_secret(vault: CredentialVault) -> None:
    """FR-018: the vault does not keep the secret of a credential that is gone.

    The tombstone says why the credential is gone and never what it was: a secret that outlives its credential is
    exactly what the specification forbids. The boundary that scrubs the key of a run is the adapter, which holds
    the key while the provider answers.
    """
    handle = vault.accept(MARKER, "openai", session_id="sess-a")

    vault.forget(handle.handle, session_id="sess-a")

    assert MARKER not in repr(vault._gone)
    assert MARKER not in str(vault._gone)


def test_the_scrub_removes_a_key_of_a_shape_the_vault_never_saw(vault: CredentialVault) -> None:
    """FR-018: the helper of the repository covers the shapes of the keys that the vault never held."""
    message = vault.scrub(f"the provider said: {SHAPED_MARKER}")

    assert SHAPED_MARKER not in message


def test_the_scrub_keeps_a_text_that_carries_no_secret(vault: CredentialVault) -> None:
    """The scrub does not damage the text that has to stay readable."""
    vault.accept(MARKER, "openai", session_id="sess-a")

    message = vault.scrub("the provider refused the request")

    assert message == "the provider refused the request"


# --- the refusals carry a readable reason and never the secret ----------------------------------------


def test_the_message_of_every_refusal_carries_no_secret(vault: CredentialVault, clock: FakeClock) -> None:
    """FR-018: the refusal that the visitor reads never carries the key."""
    handle = vault.accept(MARKER, "openai", session_id="sess-a")
    expired = vault.accept(OTHER_MARKER, "openai", session_id="sess-a")
    clock.advance(timedelta(seconds=vault.ttl_seconds + 1))
    revoked = vault.accept(SHAPED_MARKER, "openai", session_id="sess-a")

    refusals: list[str] = []
    calls = (
        lambda: vault.accept("", "openai", session_id="sess-a"),
        lambda: vault.resolve("a-handle-that-never-existed", session_id="sess-a"),
        lambda: vault.resolve(expired.handle, session_id="sess-a"),
        lambda: vault.resolve(handle.handle, session_id="sess-b"),
    )
    for call in calls:
        with pytest.raises(ByokError) as refusal:
            call()
        refusals.append(str(refusal.value))

    vault.forget(revoked.handle, session_id="sess-a")
    with pytest.raises(ByokError) as refusal:
        vault.resolve(revoked.handle, session_id="sess-a")
    refusals.append(str(refusal.value))

    refusals.append(str(CredentialRefused("the key is empty")))
    refusals.append(str(UnknownProvider("the provider is not in the allowlist")))
    refusals.append(str(CapabilityMissing("the capability 'tool_calling' is missing")))

    assert refusals
    assert all(MARKER not in message for message in refusals)
    assert all(OTHER_MARKER not in message for message in refusals)
    assert all(SHAPED_MARKER not in message for message in refusals)


def test_every_refusal_names_its_reason() -> None:
    """Every error of the package carries a readable message that names the reason."""
    reasons = {
        CredentialRefused: "refused",
        CredentialExpired: "expired",
        CredentialUnknown: "unknown",
        CredentialRevoked: "revoked",
        UnknownProvider: "provider",
        CapabilityMissing: "capability",
    }

    for error, word in reasons.items():
        message = str(error())
        assert message
        assert word in message.lower(), f"{error.__name__} does not name its reason: {message}"


def test_the_errors_of_the_package_are_one_family() -> None:
    """A caller catches the refusals of the live mode with one name."""
    assert issubclass(CredentialRefused, ByokError)
    assert issubclass(CredentialExpired, ByokError)
    assert issubclass(CredentialUnknown, ByokError)
    assert issubclass(CredentialRevoked, ByokError)
    assert issubclass(UnknownProvider, ByokError)
    assert issubclass(CapabilityMissing, ByokError)


# --- the disclosure of the limitation -------------------------------------------------------------------


def test_the_adr_discloses_that_the_zeroization_cannot_be_guaranteed() -> None:
    """FR-021: the limitation is disclosed, and the disclosure is in the repository and not in a comment."""
    adrs = sorted((PROJECT_ROOT / "docs" / "decisions").glob("ADR-033-*.md"))
    assert adrs, "the ADR of the credential vault is missing"

    text = adrs[0].read_text(encoding="utf-8")

    assert "zeroization" in text
    assert "FR-021" in text
    assert "Alternatives considered" in text
    assert "\u2014" not in text and "\u2013" not in text


def test_the_public_form_of_the_handle_validates_against_the_published_contract(vault: CredentialVault) -> None:
    """The answer of the credential endpoint has to validate against the published contract.

    Why the answer itself and not only the dataclass: the names of the fields are what the client reads, and a map
    that carries the right names in the wrong shape is still a broken answer. The contract is the one of the feature
    specification and it is the one that the facade answers.
    """
    import json

    schema = json.loads(CREDENTIAL_HANDLE_SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    handle = vault.accept(MARKER, "openai", session_id="sess-a")

    errors = sorted(validator.iter_errors(handle.to_public_dict()), key=lambda error: error.path)

    assert errors == [], [error.message for error in errors]
