"""The session of the demo: the cookie that carries the identifier and the key that signs it.

The session is issued by the server, so the tests here are about what the browser receives and what the server
accepts back.
"""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from ledgerlens.sandbox.session import InvalidSession, SessionIssuer


def test_the_key_of_the_signature_is_created_with_the_mode_of_a_secret(tmp_path: Path) -> None:
    """The key must never be readable by anyone else, not even in the window of its creation."""
    path = tmp_path / "session.key"
    SessionIssuer(path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_the_cookie_carries_the_identifier_the_expiry_and_the_signature(tmp_path: Path) -> None:
    issuer = SessionIssuer(tmp_path / "session.key")
    session = issuer.issue()
    cookie = issuer.cookie_value(session)
    assert cookie.startswith(f"{session.id}.")
    assert len(cookie.split(".")) == 3
    assert issuer.session_id(cookie) == session.id


def test_a_cookie_that_was_not_signed_here_is_refused(tmp_path: Path) -> None:
    issuer = SessionIssuer(tmp_path / "session.key")
    session = issuer.issue()
    forged = f"{session.id}.{int(session.expires_at.timestamp())}.{'0' * 32}"
    with pytest.raises(InvalidSession):
        issuer.session_id(forged)


def test_a_cookie_without_a_cookie_is_refused(tmp_path: Path) -> None:
    issuer = SessionIssuer(tmp_path / "session.key")
    with pytest.raises(InvalidSession):
        issuer.session_id(None)
    with pytest.raises(InvalidSession):
        issuer.session_id("not-a-cookie")


def test_the_key_survives_a_new_issuer_on_the_same_file(tmp_path: Path) -> None:
    path = tmp_path / "session.key"
    cookie = SessionIssuer(path).cookie_value(SessionIssuer(path).issue())
    assert SessionIssuer(path).session_id(cookie)
