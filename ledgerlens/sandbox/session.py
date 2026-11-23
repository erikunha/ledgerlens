"""The anonymous demo session: the identifier the server issues and the cookie that carries it.

Why it exists: the visitor of the demo is anonymous, and the identifier that decides what a visitor may read must
never travel in a place a third party can read. The server therefore issues the identifier, keeps it in a cookie
that is HttpOnly and SameSite Lax, and signs it, so a cookie that was not issued here is refused with the same
answer as a cookie that is missing.

The identifier is the one the canonical form of ADR-015 protects: it has to look like an identifier and nothing else,
because it lands in a path of the store, and it is stored in its canonical form, so two identifiers that differ only
in the case never share the folder of a branch.

The cookie carries three parts: the identifier, the moment the session expires and the signature of the two. The
signature is an HMAC of the key of the deployment, so a forged cookie is refused.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ledgerlens.run_context import SESSION_ID_PATTERN, canonical_session_id

SESSION_ID_PREFIX = "sess_"
SESSION_ID_HEX_CHARS = 32
# The modes a run of an anonymous demo session may use: the deterministic sandbox and the recorded replay of a
# published case. The live agent mode needs a provider key, which an anonymous session never has.
MODE_CAPABILITIES = ("deterministic_sandbox", "recorded_replay")


class InvalidSession(Exception):
    """The cookie is missing, malformed, expired or was not signed by this deployment."""


@dataclass(frozen=True)
class DemoSession:
    """The session the server issued: the identifier, the expiry and the modes it may run."""

    id: str
    expires_at: datetime
    mode_capabilities: tuple[str, ...] = MODE_CAPABILITIES


class SessionIssuer:
    """Issues the sessions and verifies the cookie that carries them.

    Why a key in a file: the cookie of a visitor survives the restart of the process, so the signature has to be
    stable. Without a file the key lives in the process only and every cookie is refused after a restart, which is
    acceptable but sends the visitor back to the start.
    """

    def __init__(self, key_path: Path | str | None = None, *, ttl_seconds: int = 14400) -> None:
        self.ttl_seconds = ttl_seconds
        self.key = _load_or_create_key(Path(key_path) if key_path is not None else None)

    def issue(self) -> DemoSession:
        """A new session: an opaque identifier, an expiry and the modes it may run."""
        session_id = f"{SESSION_ID_PREFIX}{secrets.token_hex(SESSION_ID_HEX_CHARS // 2)}"
        return DemoSession(
            id=session_id,
            expires_at=datetime.now(UTC) + timedelta(seconds=self.ttl_seconds),
        )

    def cookie_value(self, session: DemoSession) -> str:
        """The value of the cookie: the identifier, the expiry and the signature of the two."""
        stamp = str(int(session.expires_at.timestamp()))
        return f"{session.id}.{stamp}.{self._sign(session.id, stamp)}"

    def session_id(self, cookie_value: str | None) -> str:
        """The canonical identifier of the cookie, or `InvalidSession`.

        Why the canonical form: the identifier lands in a path of the store, and a filesystem may ignore the case of
        a name.
        """
        if not cookie_value:
            raise InvalidSession()
        parts = cookie_value.split(".")
        if len(parts) != 3:
            raise InvalidSession()
        session_id, stamp, signature = parts
        if not SESSION_ID_PATTERN.match(session_id):
            raise InvalidSession()
        if not hmac.compare_digest(signature, self._sign(session_id, stamp)):
            raise InvalidSession()
        try:
            expires_at = datetime.fromtimestamp(int(stamp), UTC)
        except (OSError, OverflowError, ValueError):
            raise InvalidSession() from None
        if expires_at <= datetime.now(UTC):
            raise InvalidSession()
        return canonical_session_id(session_id)

    def _sign(self, session_id: str, stamp: str) -> str:
        return hmac.new(self.key, f"{session_id}.{stamp}".encode(), hashlib.sha256).hexdigest()[:32]


def _load_or_create_key(path: Path | None) -> bytes:
    """The key of the deployment: the one in the file, or a new one written there.

    Without a path the key lives in the process only, and the sessions it issued do not survive a restart.
    """
    if path is None:
        return secrets.token_bytes(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        key = path.read_bytes()
        if key:
            return key
    key = secrets.token_bytes(32)
    # The file is created with the mode of the secret itself, so there is no window in which it can be read.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(key)
    return key


__all__ = ["DemoSession", "InvalidSession", "MODE_CAPABILITIES", "SESSION_ID_PREFIX", "SessionIssuer"]
