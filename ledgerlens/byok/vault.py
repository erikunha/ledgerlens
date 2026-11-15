"""The credential vault of the live mode: the key of a visitor lives in the memory of the process.

Why it exists: the third story of the specification asks for a key that never reaches a file, a log, a trace or an
answer to the client (FR-003, FR-004). The only place a secret can live without leaving a trace on the disk is the
memory of the process that received it, so the vault is that memory, and the only thing it hands out is an opaque
handle.

What the vault holds:

* one entry per accepted key, with the provider, the session that owns it, the moment of the creation and the moment
  of the expiry, and the secret itself in a buffer of the process;
* a handle per entry: opaque, random and never derived from the secret, so a handle tells nothing about the key;
* a tombstone per credential that is gone, so a refusal can say whether the credential expired, was revoked or never
  existed, and the tombstone carries no secret.

What the vault guarantees:

* the secret is never written to a file, a database, a log, an environment variable or a URL, and it is never
  returned to a client: the handle is what travels (FR-003, FR-004);
* a handle of another session is refused with the same answer as a handle that never existed (FR-006);
* the vault is bounded, so a flood of keys cannot grow the memory of the process without a limit (FR-002);
* every credential expires, the expiry is decided by the injected clock, and the sweep runs on every access and in
  the sweeper thread, so a vault nobody touches still forgets (FR-002, FR-022, SC-011);
* the number of failures of a credential is bounded, and the credential is dropped when the bound is reached (FR-023);
* the vault scrubs its own secret out of a text, so a provider exception that carries the key cannot carry it out of
  the vault while the credential is alive (FR-018). The boundary that scrubs the key of a run out of the error of a
  provider is the adapter, which holds the key; the scrub of the vault is the second layer, and it is the tool of
  the facade of the live mode, which is the task of the next milestone.

Why the secret is kept in a buffer and not in a text: a buffer can be overwritten when the credential is dropped,
which is the best effort that a runtime offers. It is not a promise, and ADR-033 says so out loud (FR-021).

Why the clock is injected: the expiry is decided by the server and never by the visitor, and a test that waits for an
hour proves nothing.
"""

from __future__ import annotations

import logging
import secrets
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from ledgerlens.byok.errors import (
    CredentialExpired,
    CredentialRefused,
    CredentialRevoked,
    CredentialUnknown,
    UnknownProvider,
)
from ledgerlens.byok.registry import PROVIDERS
from ledgerlens.observability.callbacks import redact

log = logging.getLogger(__name__)

# The number of credentials the vault holds at the same time. A visitor holds one, and the bound is what keeps a
# flood of keys from growing the memory of the process (FR-002).
DEFAULT_MAX_ENTRIES = 64
# The time to live of a credential, counted from its creation (FR-002, FR-022).
DEFAULT_TTL_SECONDS = 3600
# The number of failures a credential survives before it is dropped (FR-023).
DEFAULT_MAX_FAILURES = 3
# The number of bytes of the random handle. The handle is opaque and random, never derived from the secret.
_HANDLE_BYTES = 32
# The longest secret the vault accepts. A key is a short text, and the bound keeps one entry from eating the memory.
_MAX_SECRET_CHARS = 512
# The marker that replaces a secret in a text.
_REDACTED = "[REDACTED]"
# How long the sweeper waits when the vault holds nothing that can expire.
_SWEEPER_IDLE_SECONDS = 30.0
# The longest wait of the sweeper between two sweeps.
_SWEEPER_MAX_WAIT_SECONDS = 3600.0

# The reasons of the drops, written in the refusal that the visitor reads.
_EXPIRED_REASON = "the credential outlived its time to live"
_FORGOTTEN_REASON = "the credential was forgotten by its owner"
_FULL_REASON = "the credential was dropped because the vault was full"
_SESSION_REASON = "the session of the credential ended"


@dataclass(frozen=True)
class CredentialHandle:
    """The opaque handle of a credential: the handle, the provider, the creation and the expiry.

    Why the secret is not a field: the handle travels to the client and to the logs, and a field that carries the
    secret would leak it as soon as the handle was printed (FR-004).

    Why the handle is frozen: it is the identity of a credential, and nobody may change it behind the back of the
    vault that issued it.
    """

    handle: str
    provider: str
    created_at: datetime
    expires_at: datetime

    def to_public_dict(self) -> dict[str, str]:
        """The handle as the client sees it: the handle, the provider, the creation and the expiry, and nothing else.

        Why the names of the dataclass are used: the facade answers with this map and the published contract of the
        credential endpoint names the fields `handle`, `provider`, `created_at` and `expires_at`, so the answer of the
        server validates against the contract. The name `credential_handle` belongs to the request that REFERENCES a
        handle, and not to the answer that carries one.
        """
        return {
            "handle": self.handle,
            "provider": self.provider,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
        }


class _SecretBuffer:
    """The buffer of a secret: the bytes of the key live in it and no representation of it ever shows them.

    Why the secret is not a plain text: a text prints itself, and a debug print or a traceback with the locals of
    the vault would show the key. Why it is not a plain `bytes`: the same thing, and `bytes` cannot be overwritten
    when the credential dies (FR-003, FR-021).
    """

    def __init__(self, text: str) -> None:
        self._bytes = bytearray(text.encode("utf-8"))

    def read(self) -> str:
        """The secret as text, for the code that builds the client of the provider."""
        return bytes(self._bytes).decode("utf-8")

    def wipe(self) -> None:
        """Overwrites the bytes of the secret on a best effort basis (FR-021)."""
        for index in range(len(self._bytes)):
            self._bytes[index] = 0

    def __repr__(self) -> str:
        """The buffer without its content, because a representation ends up in the logs."""
        return "SecretBuffer([REDACTED])"

    __str__ = __repr__


@dataclass
class _Entry:
    """One credential of the vault: the secret and everything the vault needs to police it.

    Why the secret is a buffer and not a text: the representation of an entry ends up in a debug print and in a
    traceback with the locals, and neither may show the key (FR-003, FR-018).
    """

    handle: str
    provider: str
    session_id: str
    created_at: datetime
    expires_at: datetime
    secret: _SecretBuffer
    failures: int = 0


class CredentialVault:
    """The in-process memory that maps an opaque handle to a provider secret.

    Why the vault is not a store: the key must never reach the disk (FR-003), and a store interface would invite a
    second implementation that writes it somewhere. The vault is a plain object of the process and nothing else.
    """

    def __init__(
        self,
        *,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        max_failures: int = DEFAULT_MAX_FAILURES,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if max_entries < 1:
            raise ValueError("the vault must hold at least one credential")
        if ttl_seconds < 1:
            raise ValueError("a credential must live at least one second")
        if max_failures < 1:
            raise ValueError("a credential must survive at least one failure")
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self.max_failures = max_failures
        self._clock = clock or (lambda: datetime.now(UTC))
        self._entries: dict[str, _Entry] = {}
        # The credentials that are gone: the handle, the session that owned it, the kind of the end and the reason.
        self._gone: dict[str, tuple[str, str, str]] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __len__(self) -> int:
        """The number of credentials the vault holds right now."""
        with self._lock:
            return len(self._entries)

    def __repr__(self) -> str:
        """A representation that says how much the vault holds and never what it holds."""
        with self._lock:
            return f"CredentialVault(entries={len(self._entries)}, max_entries={self.max_entries})"

    # --- the lifecycle of a credential ------------------------------------------------------------------

    def accept(self, secret: str, provider: str, *, session_id: str) -> CredentialHandle:
        """Accepts the key of a visitor and answers the handle that stands for it.

        Why the key is stripped: a visitor pastes a key with a newline or a space around it, and the provider
        refuses it. The space is not part of the secret, so it is removed before the secret is kept.

        Why the handle is random: a handle that is derived from the secret would tell something about it, and a
        handle that a visitor can guess would let another visitor try to use it (FR-005, FR-006).

        Why the provider has to be one the registry publishes: the public form of the handle carries the provider,
        and the published contract of the handle enumerates the providers of the live mode. A vault that accepted
        any text would break that contract on the day a visitor pastes a name that nobody publishes (FR-004).
        """
        key = secret.strip() if isinstance(secret, str) else ""
        if not key:
            raise CredentialRefused("the key is empty")
        if len(key) > _MAX_SECRET_CHARS:
            raise CredentialRefused(f"the key is longer than {_MAX_SECRET_CHARS} characters")
        name = provider.strip() if isinstance(provider, str) else ""
        if not name:
            raise CredentialRefused("the provider is empty")
        if name not in PROVIDERS:
            raise UnknownProvider(
                f"the provider '{name}' is not one of the providers of the live mode: {', '.join(PROVIDERS)}"
            )

        now = self._clock()
        expires_at = now + timedelta(seconds=self.ttl_seconds)
        with self._lock:
            self._sweep_locked(now)
            self._make_room_locked()
            handle = self._new_handle()
            self._entries[handle] = _Entry(
                handle=handle,
                provider=name,
                session_id=session_id,
                created_at=now,
                expires_at=expires_at,
                secret=_SecretBuffer(key),
            )
        return CredentialHandle(handle=handle, provider=name, created_at=now, expires_at=expires_at)

    def resolve(self, handle: str, *, session_id: str) -> str:
        """The secret behind a handle, for the code that builds the client of the provider.

        Why the session is a parameter and not a property of the vault: the vault is shared by the process and the
        session is what decides who may read a handle (FR-006).
        """
        now = self._clock()
        with self._lock:
            entry = self._entries.get(handle)
            if entry is not None and entry.session_id == session_id:
                if entry.expires_at <= now:
                    self._drop_locked(handle, kind="expired", reason=_EXPIRED_REASON)
                    raise CredentialExpired(_EXPIRED_REASON)
                self._sweep_locked(now)
                return entry.secret.read()
            # The handle is unknown, or it belongs to another session. The two answers are the same, so a visitor
            # cannot learn that the handle of another session exists (FR-006).
            self._sweep_locked(now)
            if entry is None:
                self._raise_gone(handle, session_id)
            raise CredentialUnknown()

    def forget(self, handle: str, *, session_id: str) -> bool:
        """Drops a credential at once, and answers whether there was one to drop.

        Why a handle of another session is not dropped: the session that owns a credential is the only one that may
        revoke it, and a foreign handle is not even acknowledged (FR-006).
        """
        now = self._clock()
        with self._lock:
            self._sweep_locked(now)
            entry = self._entries.get(handle)
            if entry is None or entry.session_id != session_id:
                return False
            self._drop_locked(handle, kind="revoked", reason=_FORGOTTEN_REASON)
            return True

    def forget_session(self, session_id: str) -> int:
        """Drops every credential of a session, at the end of that session (FR-022)."""
        now = self._clock()
        with self._lock:
            self._sweep_locked(now)
            handles = [entry.handle for entry in self._entries.values() if entry.session_id == session_id]
            for handle in handles:
                self._drop_locked(handle, kind="revoked", reason=_SESSION_REASON)
            return len(handles)

    def record_failure(self, handle: str, *, session_id: str) -> None:
        """Counts a failure of a credential and drops it when the bound is reached (FR-023).

        Why the count is the count of the whole life of the credential: a key that fails often is a key that does
        not work, and a visitor that keeps it alive only spends more of it.
        """
        now = self._clock()
        with self._lock:
            self._sweep_locked(now)
            entry = self._entries.get(handle)
            if entry is None:
                self._raise_gone(handle, session_id)
            if entry.session_id != session_id:
                raise CredentialUnknown()
            entry.failures += 1
            if entry.failures >= self.max_failures:
                reason = f"the credential was dropped after {entry.failures} failures"
                self._drop_locked(handle, kind="revoked", reason=reason)
                log.warning(
                    "the credential of provider %s was dropped after %d failures",
                    entry.provider,
                    entry.failures,
                )

    def sweep(self) -> int:
        """Drops every credential that outlived its time to live, and answers how many were dropped."""
        now = self._clock()
        with self._lock:
            return self._sweep_locked(now)

    def scrub(self, text: str) -> str:
        """Removes the secrets the vault holds from a text, and then anything that looks like a key.

        Why the vault scrubs its own secrets first: a key of a provider that the repository does not know has a shape
        that the helper `redact` never matches, and only the vault knows the exact text of the key it holds
        (FR-018).

        Why the helper of the repository comes second: it covers the keys that this vault never held, the ones that
        arrive inside an exception of a provider or inside a header of a request, and it keeps one definition of what
        looks like a key in the codebase.

        Why the scrub stops at the credentials that are alive: the vault does not keep the secret of a credential
        that is gone, on purpose, and a text that a dead credential produced is not a text the vault can scrub.
        The boundary that scrubs the key of a run is the adapter, which holds the key while the provider answers
        (FR-018).
        """
        if not text:
            return text
        with self._lock:
            held = [entry.secret.read() for entry in self._entries.values()]
        cleaned = text
        for secret in held:
            if secret and secret in cleaned:
                cleaned = cleaned.replace(secret, _REDACTED)
        return redact(cleaned)

    # --- the sweeper of a vault nobody touches ---------------------------------------------------------

    def start_sweeper(self) -> None:
        """Starts the thread that drops the expired credentials of a vault that nobody touches.

        Why the thread is a daemon: a process that is killed does not wait for the sweep, and the sweep never keeps
        the process alive.
        """
        with self._lock:
            if self._thread is not None:
                return
            self._stop.clear()
            thread = threading.Thread(target=self._sweeper_loop, name="ledgerlens-credential-sweep", daemon=True)
            self._thread = thread
        thread.start()

    def stop_sweeper(self, timeout: float = 5.0) -> None:
        """Stops the thread of the sweep and waits for the sweep that is running to end."""
        with self._lock:
            thread = self._thread
            self._thread = None
        self._stop.set()
        if thread is not None:
            thread.join(timeout)

    def _sweeper_loop(self) -> None:
        """The loop of the thread: wait for the next expiry, sweep, and wait again."""
        while not self._stop.is_set():
            self._stop.wait(self._seconds_to_the_next_expiry())
            if self._stop.is_set():
                break
            self.sweep()

    def _seconds_to_the_next_expiry(self) -> float:
        """The wait until the next credential expires, so the sweep happens when it has to."""
        now = self._clock()
        with self._lock:
            expiries = [entry.expires_at for entry in self._entries.values()]
        if not expiries:
            return _SWEEPER_IDLE_SECONDS
        delay = (min(expiries) - now).total_seconds()
        return max(0.05, min(delay, _SWEEPER_MAX_WAIT_SECONDS))

    # --- the rules of the memory -----------------------------------------------------------------------

    def _new_handle(self) -> str:
        """A handle that no other credential holds."""
        while True:
            handle = secrets.token_urlsafe(_HANDLE_BYTES)
            if handle not in self._entries and handle not in self._gone:
                return handle

    def _make_room_locked(self) -> None:
        """Drops the oldest credential when the vault is full, and says so.

        Why the oldest goes: the newest credential is the one the visitor is working with, and the oldest is the one
        that has been idle the longest.
        """
        while len(self._entries) >= self.max_entries:
            oldest = min(self._entries.values(), key=lambda entry: entry.created_at)
            log.warning(
                "the credential vault is full: the oldest credential of provider %s was dropped",
                oldest.provider,
            )
            self._drop_locked(oldest.handle, kind="revoked", reason=_FULL_REASON)

    def _sweep_locked(self, now: datetime) -> int:
        """Drops every credential that expired, and answers how many were dropped."""
        expired = [entry.handle for entry in self._entries.values() if entry.expires_at <= now]
        for handle in expired:
            self._drop_locked(handle, kind="expired", reason=_EXPIRED_REASON)
        return len(expired)

    def _drop_locked(self, handle: str, *, kind: str, reason: str) -> None:
        """Removes a credential from the vault and remembers that it is gone."""
        entry = self._entries.pop(handle, None)
        if entry is None:
            return
        # The buffer is overwritten on a best effort basis. The runtime cannot promise that no copy of the secret
        # survives somewhere else, and ADR-033 says so out loud (FR-021).
        entry.secret.wipe()
        self._remember_gone_locked(handle, entry.session_id, kind, reason)

    def _remember_gone_locked(self, handle: str, session_id: str, kind: str, reason: str) -> None:
        """Keeps the tombstone of a credential that is gone, and keeps the map bounded."""
        self._gone[handle] = (session_id, kind, reason)
        while len(self._gone) > self.max_entries:
            self._gone.pop(next(iter(self._gone)))

    def _raise_gone(self, handle: str, session_id: str) -> None:
        """Raises the refusal of a handle that is not in the vault anymore.

        Why the owner is checked: a handle that is gone and belongs to another session must have the same answer as
        a handle that never existed (FR-006).
        """
        record = self._gone.get(handle)
        if record is not None:
            owner, kind, reason = record
            if owner == session_id:
                if kind == "expired":
                    raise CredentialExpired(reason)
                raise CredentialRevoked(reason)
        raise CredentialUnknown()


__all__ = [
    "DEFAULT_MAX_ENTRIES",
    "DEFAULT_MAX_FAILURES",
    "DEFAULT_TTL_SECONDS",
    "CredentialHandle",
    "CredentialVault",
]
