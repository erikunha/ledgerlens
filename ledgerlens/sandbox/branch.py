"""The branch layer: the fork of an immutable base, the owner rule, the reuse rule, the status and the expiry.

Why it exists: a visitor of the public demo needs a private working copy of a published case, and one visitor must
never see the work of another one. The rules live here and not in the store, so the storage can be replaced without
the rules changing, and the layer never writes SQL and never writes to the published base.

The four rules of this module:

* the fork reads the base, computes its canonical hash and creates a branch at revision zero;
* the identifier of the branch is opaque: it carries no session, no scenario and no path;
* a second fork of the same scenario by the same session returns the branch that already exists;
* a branch belongs to exactly one owner session, and a session that asks for the branch of another one gets the same
  generic answer as for a branch that does not exist.

Two rules keep the owner honest and the branch alive. The session identifier is accepted only when it matches the
pattern of ADR-015, because the canonical form is injective only over that alphabet, so an identifier outside it is
refused instead of becoming the owner of another visitor. The expiry of a branch is the earlier of the idle deadline,
counted from the last activity of the visitor, and the absolute deadline, counted from the creation.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from ledgerlens.run_context import SESSION_ID_PATTERN, canonical_session_id
from ledgerlens.sandbox.snapshot import BaseSnapshot
from ledgerlens.sandbox.store import BranchNotFound, BranchStore, SandboxBranchRow

BRANCH_ID_PREFIX = "sb_"
BRANCH_ID_HEX_CHARS = 24
STATE_ACTIVE = "active"
STATE_EXPIRED = "expired"


class InvalidSessionId(ValueError):
    """The session identifier is not one of the accepted alphabet and is refused.

    Why the check: the canonical form of ADR-015 escapes the characters that are not in the pattern of an identifier,
    and the marker it uses is not in the pattern itself. Over every string the canonical form is therefore not
    injective, and two identifiers that differ only in the marker would become one owner, so the second visitor would
    receive the branch of the first one. Over the accepted alphabet the canonical form is injective.
    """


class BranchExpired(Exception):
    """The branch outlived its time to live.

    The caller owns the branch, so the message may name the state. It offers to fork the scenario again.
    """


def new_branch_id() -> str:
    """An opaque branch identifier: the prefix and twenty four hexadecimal characters from `secrets`.

    Why opaque: the identifier appears in every answer and in every path of the interface, so a reader must learn
    nothing about the owner, about the scenario or about the disk from it.
    """
    return f"{BRANCH_ID_PREFIX}{secrets.token_hex(BRANCH_ID_HEX_CHARS // 2)}"


@dataclass(frozen=True)
class SandboxBranch:
    """A private working copy of a published case, owned by one session.

    `owner_session` is the canonical form of the session identifier, because the identifier lands in a path and a
    filesystem may ignore the case of a name. `base_snapshot_id` names the published snapshot the branch was forked
    from and `base_canonical_hash` is the canonical hash of the account scoped projection the branch reads.
    """

    branch_id: str
    owner_session: str
    scenario_id: str
    base_snapshot_id: str
    base_canonical_hash: str
    revision: int
    current_canonical_hash: str
    created_at: datetime
    last_activity_at: datetime
    expires_at: datetime
    state: str = STATE_ACTIVE


@dataclass(frozen=True)
class ForkOutcome:
    """The result of a fork: the branch, and whether the fork created it or returned the one that already existed.

    Why the difference matters to a client: one answer is a creation and the other is not.
    """

    branch: SandboxBranch
    created: bool


class BranchLayer:
    """The domain of the branch: the fork, the reuse rule, the owner check, the status and the expiry.

    Why the clock is injected: the expiry is decided by the server, and a test needs to move it without waiting an
    hour.
    """

    def __init__(
        self,
        store: BranchStore,
        base_resolver: Callable[[str], BaseSnapshot],
        *,
        idle_ttl_seconds: int = 3600,
        absolute_ttl_seconds: int = 14400,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.base_resolver = base_resolver
        self.idle_ttl_seconds = idle_ttl_seconds
        self.absolute_ttl_seconds = absolute_ttl_seconds
        self._clock = clock or (lambda: datetime.now(UTC))

    # -- the fork ----------------------------------------------------------------------------------

    def fork(self, session_id: str, scenario_id: str) -> ForkOutcome:
        """The private branch of the scenario for this session, at revision zero.

        The second fork of the same scenario by the same session returns the branch that already exists, so the
        number of branches of the session does not grow, and the outcome says that the branch was reused.
        """
        owner = self._owner(session_id)
        base = self.base_resolver(scenario_id)
        existing = self._existing(owner, scenario_id)
        if existing is not None:
            return ForkOutcome(branch=existing, created=False)
        now = self._clock()
        row = SandboxBranchRow(
            branch_id=new_branch_id(),
            owner_session=owner,
            scenario_id=scenario_id,
            base_snapshot_id=base.snapshot_id,
            base_canonical_hash=base.canonical_hash,
            revision=0,
            # At revision zero the state of the branch is the base itself.
            current_canonical_hash=base.canonical_hash,
            created_at=now,
            last_activity_at=now,
            expires_at=self._expiry(now, now),
            state=STATE_ACTIVE,
        )
        return ForkOutcome(branch=self._view(self.store.create_branch(row)), created=True)

    # -- the status --------------------------------------------------------------------------------

    def status(self, session_id: str, branch_id: str) -> SandboxBranch:
        """The status of the branch, for the session that owns it.

        A branch of another session is refused with the same generic answer as a branch that does not exist, so
        nothing about the existence of the branch leaks. Reading the branch is an activity: the idle deadline of the
        branch moves, the absolute deadline never does.
        """
        owner = self._owner(session_id)
        row = self.store.get_branch(branch_id, owner)
        if row.owner_session != owner:
            # The store already refuses this, but the layer does not rely on that alone.
            raise BranchNotFound()
        if self._expired(row):
            raise BranchExpired(f"the branch {branch_id} expired; fork the scenario again")
        return self._view(self._refresh(row))

    # -- the internals -----------------------------------------------------------------------------

    def _owner(self, session_id: str) -> str:
        """The canonical owner of a session, after checking that the identifier is one.

        Why the check: the canonical form is injective only over the accepted alphabet, and the owner is the name of
        a folder of the store. An identifier outside the pattern is refused before it reaches the store.
        """
        if not SESSION_ID_PATTERN.match(session_id):
            raise InvalidSessionId(f"not a session identifier: {session_id!r}")
        return canonical_session_id(session_id)

    def _existing(self, owner: str, scenario_id: str) -> SandboxBranch | None:
        """The branch of this session on this scenario, when it is still alive."""
        for row in self.store.list_branches(owner):
            if row.scenario_id == scenario_id and not self._expired(row):
                return self._view(row)
        return None

    def _view(self, row: SandboxBranchRow) -> SandboxBranch:
        return SandboxBranch(
            branch_id=row.branch_id,
            owner_session=row.owner_session,
            scenario_id=row.scenario_id,
            base_snapshot_id=row.base_snapshot_id,
            base_canonical_hash=row.base_canonical_hash,
            revision=row.revision,
            current_canonical_hash=row.current_canonical_hash,
            created_at=row.created_at,
            last_activity_at=row.last_activity_at,
            expires_at=row.expires_at,
            state=STATE_EXPIRED if self._expired(row) else row.state,
        )

    def _refresh(self, row: SandboxBranchRow) -> SandboxBranchRow:
        """The activity of the visitor moves the idle deadline; the absolute deadline never moves.

        Why the row is written again: the deadline is part of the row, so the store has to keep the new one.
        """
        now = self._clock()
        expires_at = self._expiry(now, row.created_at)
        if now == row.last_activity_at and expires_at == row.expires_at:
            return row
        return self.store.save_branch(replace(row, last_activity_at=now, expires_at=expires_at))

    def _expiry(self, last_activity_at: datetime, created_at: datetime) -> datetime:
        """The expiry of a branch: the idle deadline from the last activity, never past the absolute deadline."""
        idle = last_activity_at + timedelta(seconds=self.idle_ttl_seconds)
        absolute = created_at + timedelta(seconds=self.absolute_ttl_seconds)
        return min(idle, absolute)

    def _expired(self, row: SandboxBranchRow) -> bool:
        return self._clock() >= row.expires_at


__all__ = [
    "BRANCH_ID_PREFIX",
    "BranchExpired",
    "BranchLayer",
    "ForkOutcome",
    "InvalidSessionId",
    "SandboxBranch",
    "STATE_ACTIVE",
    "STATE_EXPIRED",
    "new_branch_id",
]
