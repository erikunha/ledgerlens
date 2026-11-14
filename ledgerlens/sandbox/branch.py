"""The branch layer: the fork of an immutable base, the owner rule, the reuse rule, the status and the expiry.

Why it exists: a visitor of the public demo needs a private working copy of a published case, and one visitor must
never see the work of another one. The rules live here and not in the store, so the storage can be replaced without
the rules changing, and the layer never writes SQL and never writes to the published base.

The four rules of the fork:

* the fork reads the base, computes its canonical hash and creates a branch at revision zero;
* the identifier of the branch is opaque: it carries no session, no scenario and no path;
* a second fork of the same scenario by the same session returns the branch that already exists;
* a branch belongs to exactly one owner session, and a session that asks for the branch of another one gets the same
  generic answer as for a branch that does not exist.

Two rules keep the owner honest and the branch alive. The session identifier is accepted only when it matches the
pattern of ADR-015, because the canonical form is injective only over that alphabet, so an identifier outside it is
refused instead of becoming the owner of another visitor. The expiry of a branch is the earlier of the idle deadline,
counted from the last activity of the visitor, and the absolute deadline, counted from the creation.

A fifth rule keeps the branch honest: every read of a branch recomputes the canonical hash of the projection of its
events and compares it with the hash the row of the branch declares. A branch whose row does not agree with its
events may be half applied, and it is refused with the code `HASH_MISMATCH` and never served as valid (ADR-021). The
same rule compares the base hash recorded at fork time with the base the resolver hands over, so a branch whose base
moved under it is refused on every route and not only where it is repaired (ADR-022).
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any

from ledgerlens.run_context import SESSION_ID_PATTERN, canonical_session_id
from ledgerlens.sandbox.mutation import (
    CODE_HASH_MISMATCH,
    CODE_IDEMPOTENCY_MISMATCH,
    CODE_INVALID_REQUEST,
    CODE_INVARIANT_VIOLATION,
    CODE_RESOURCE_LIMIT,
    CODE_REVISION_CONFLICT,
    MutationCommand,
    MutationPreview,
    MutationRejected,
    MutationResult,
    command_id_of,
    format_minor,
    payload_digest,
    plan_mutation,
)
from ledgerlens.sandbox.projector import ProjectedState, project
from ledgerlens.sandbox.snapshot import BaseSnapshot
from ledgerlens.sandbox.store import (
    BranchNotFound,
    BranchRevisionConflict,
    BranchStore,
    SandboxBranchRow,
    SandboxCommandRow,
)

BRANCH_ID_PREFIX = "sb_"
BRANCH_ID_HEX_CHARS = 24
STATE_ACTIVE = "active"
STATE_EXPIRED = "expired"
# The number of rows of one page of the ledger of a branch.
LEDGER_PAGE_SIZE = 50
# The resources of one branch (FR-025). A branch that reaches one of them is refused, and the branch is not
# bigger than the resources of the server that holds it.
MAX_COMMITTED_MUTATIONS = 20
MAX_EVENTS = 200


def _ledger_items(state: Any) -> list[dict[str, object]]:
    """The rows of the ledger of a branch: the movements of the account, oldest first.

    Why the amounts are decimal texts: the interface never calculates money, and the rows of the ledger are the
    same rows the projection holds.
    """
    items: list[dict[str, object]] = []
    for row in state.rows.get("transactions", []):
        items.append(
            {
                "kind": "transaction",
                "id": row["id"],
                "at": row["created_at"],
                "amount": format_minor(int(row["amount_minor"]), str(row["currency"])),
                "currency": row["currency"],
                "status": row["status"],
            }
        )
    for row in state.rows.get("refunds", []):
        items.append(
            {
                "kind": "refund",
                "id": row["id"],
                "at": row["created_at"],
                "amount": format_minor(int(row["payout_amount_minor"] or 0), str(row["payout_currency"])),
                "currency": row["payout_currency"],
                "status": row["status"],
            }
        )
    for row in state.rows.get("chargebacks", []):
        items.append(
            {
                "kind": "chargeback",
                "id": row["id"],
                "at": row["opened_at"],
                "amount": format_minor(int(row["amount_minor"]), str(row["currency"])),
                "currency": row["currency"],
                "status": row["stage"],
            }
        )
    items.sort(key=lambda item: (str(item["at"]), str(item["kind"]), str(item["id"])))
    return items


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


class BranchHashMismatch(Exception):
    """The row of the branch does not agree with the projection of its events.

    Why the branch is refused instead of served: a branch that cannot prove its own state is a branch that may be
    half applied, and a visitor must never be shown a ledger that says one thing and holds another (ADR-021). The
    message offers a fresh fork, because the branch itself cannot be repaired.
    """

    code = CODE_HASH_MISMATCH

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


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

    `generation` counts the resets the branch went through, and it is what tells an answer of the past from the
    current result of the branch (ADR-022).
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
    generation: int = 0


@dataclass(frozen=True)
class RecordedAnswer:
    """One answer the branch remembers, with the mark of the staleness.

    The fields are the ones of the stored answer, plus the mark. `stale` says that the answer was produced in a
    generation behind the one of the branch, and `stale_against` is the base canonical hash of the branch, the hash of
    the original snapshot the answer was computed against. An answer of the current generation is not stale and
    `stale_against` is None (FR-022, ADR-022).
    """

    branch_id: str
    idempotency_key: str
    payload_digest: str
    revision: int
    canonical_hash: str
    response_diff: list[dict[str, Any]]
    response_verdict: dict[str, Any]
    response_invariants: list[dict[str, Any]]
    generation: int
    stale: bool = False
    stale_against: str | None = None


@dataclass(frozen=True)
class ForkOutcome:
    """The result of a fork: the branch, and whether the fork created it or returned the one that already existed.

    Why the difference matters to a client: one answer is a creation and the other is not.
    """

    branch: SandboxBranch
    created: bool


@dataclass(frozen=True)
class LedgerPage:
    """One page of the ledger of a branch: the rows of the account and the cursor of the next page.

    The cursor is None when the page is the last one, so the interface knows that it has read everything.
    """

    items: tuple[dict[str, object], ...]
    next_cursor: str | None = None


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

        The branch is verified before it is served: the hash of the projection of its events has to be the hash the
        row declares, or the branch cannot prove its own state and is refused (ADR-021).
        """
        owner = self._owner(session_id)
        row = self.store.get_branch(branch_id, owner)
        if row.owner_session != owner:
            # The store already refuses this, but the layer does not rely on that alone.
            raise BranchNotFound()
        if self._expired(row):
            raise BranchExpired(f"the branch {branch_id} expired; fork the scenario again")
        self._verified(row, owner)
        return self._view(self._refresh(row))

    # -- the mutation loop ---------------------------------------------------------------------------

    def preview_mutation(self, session_id: str, branch_id: str, command: MutationCommand) -> MutationPreview:
        """What the command would do to the branch, computed in memory and written nowhere.

        The preview reads the branch, projects it with the event the command would produce over a copy of the base
        and answers with the values before and after, the records, the invariants and the verdict. The revision,
        the canonical hash and the events of the branch are the same before and after (FR-016).
        """
        owner = self._owner(session_id)
        row = self.store.get_branch(branch_id, owner)
        if self._expired(row):
            raise BranchExpired(f"the branch {branch_id} expired; fork the scenario again")
        branch = self._view(row)
        base = self.base_resolver(branch.scenario_id)
        events = self.store.read_events(branch_id, owner)
        state = self._verified(row, owner, events)
        plan = plan_mutation(
            base,
            branch.branch_id,
            branch.scenario_id,
            branch.revision,
            events,
            command,
            self._clock(),
            before=state,
        )
        return plan.to_preview(branch.current_canonical_hash)

    def commit_mutation(self, session_id: str, branch_id: str, command: MutationCommand) -> MutationResult:
        """The commit of a command: the events, the revision and the canonical hash move together.

        The order of the three rules is the order of the promises. The idempotency key comes first, so that a
        request that was already committed is answered with the answer that was stored, whatever the expected
        revision of the request says: the second delivery of a request carries the expected revision it was sent
        with, and that revision is stale by then, because the first delivery moved the branch (FR-012). A key that
        was seen with another payload is a conflict, whatever the expected revision says (FR-013). The expected
        revision of a request that was never seen has to match the current one, or the request is refused and
        never rebased (FR-014). The rules of the payload and the invariants are checked last, over the projection
        the command would produce, and a rule that does not hold means that nothing is written at all (FR-018).
        """
        owner = self._owner(session_id)
        row = self.store.get_branch(branch_id, owner)
        if self._expired(row):
            raise BranchExpired(f"the branch {branch_id} expired; fork the scenario again")
        branch = self._view(row)
        base = self.base_resolver(branch.scenario_id)
        events = self.store.read_events(branch_id, owner)
        # Every read of the branch is verified: a branch that cannot prove its own state is never served (ADR-021).
        state = self._verified(row, owner, events)
        if not command.idempotency_key:
            raise MutationRejected(CODE_INVALID_REQUEST, "the request carries no idempotency key")
        if command.expected_revision is None:
            raise MutationRejected(CODE_INVALID_REQUEST, "the request carries no expected revision")
        digest = payload_digest(command)
        stored = self.store.command_answer(branch_id, owner, command.idempotency_key)
        if stored is not None:
            return self._replay(branch, stored, command, digest)
        if command.expected_revision != branch.revision:
            raise MutationRejected(
                CODE_REVISION_CONFLICT,
                f"the branch is at revision {branch.revision} and the request expected {command.expected_revision}",
            )
        self._check_the_resources(branch, events)
        now = self._clock()
        plan = plan_mutation(
            base, branch.branch_id, branch.scenario_id, branch.revision, events, command, now, before=state
        )
        failed = [result for result in plan.invariants if not result["passed"]]
        if failed:
            raise MutationRejected(CODE_INVARIANT_VIOLATION, str(failed[0]["reason"]))
        new_row = replace(
            row,
            revision=branch.revision + 1,
            current_canonical_hash=plan.canonical_hash,
            last_activity_at=now,
            expires_at=self._expiry(now, row.created_at),
        )
        answer = SandboxCommandRow(
            branch_id=branch_id,
            idempotency_key=command.idempotency_key,
            payload_digest=digest,
            revision=new_row.revision,
            canonical_hash=plan.canonical_hash,
            response_diff=list(plan.diff),
            response_verdict=plan.verdict.to_dict(),
            response_invariants=list(plan.invariants),
            # The answer remembers the generation it was produced in, so that a reset can mark it stale (ADR-022).
            generation=branch.generation,
        )
        try:
            self.store.commit_events(branch_id, owner, plan.events, new_row, answer)
        except BranchRevisionConflict:
            # The branch moved between the read and the write: the request is stale, and nothing was written.
            raise MutationRejected(
                CODE_REVISION_CONFLICT, "the branch moved while the request was being prepared"
            ) from None
        return plan.to_result()

    def _check_the_resources(self, branch: SandboxBranch, events: list[Any]) -> None:
        """The resources of the branch: the number of its mutations and the number of its events.

        Why the refusal comes before the work: a branch that reached its limit is refused without a projection,
        so the server never spends the resources of a request it will refuse anyway (FR-025).
        """
        if branch.revision >= MAX_COMMITTED_MUTATIONS:
            raise MutationRejected(
                CODE_RESOURCE_LIMIT,
                f"the branch already holds {branch.revision} mutations, and the limit is {MAX_COMMITTED_MUTATIONS}",
            )
        if len(events) >= MAX_EVENTS:
            raise MutationRejected(
                CODE_RESOURCE_LIMIT,
                f"the branch already holds {len(events)} events, and the limit is {MAX_EVENTS}",
            )

    def _replay(
        self, branch: SandboxBranch, stored: SandboxCommandRow, command: MutationCommand, digest: str
    ) -> MutationResult:
        """The answer of a request that was already committed, with the same key and the same payload.

        The answer that is returned is the answer that was remembered: the revision, the hash, the diff, the
        invariants and the verdict of the request that was committed. They are not recomputed from the current
        projection, because a later mutation may have moved the case and the answer of a request is the answer of
        that request (ADR-021).
        """
        if stored.payload_digest != digest:
            raise MutationRejected(
                CODE_IDEMPOTENCY_MISMATCH,
                "the idempotency key was already used with another payload",
            )
        # An answer of a generation behind the current one of the branch is stale, and it is answered with the mark,
        # so that the answer of the past is never presented as the current result of the branch (FR-022, ADR-022).
        stale = stored.generation < branch.generation
        return MutationResult(
            command_id=command_id_of(command, digest),
            kind=command.kind,
            revision=stored.revision,
            canonical_hash=stored.canonical_hash,
            diff=tuple(stored.response_diff),
            invariants=tuple(stored.response_invariants),
            verdict=dict(stored.response_verdict),
            replayed=True,
            stale=stale,
            stale_against=branch.base_canonical_hash if stale else None,
        )

    def _verified(
        self, row: SandboxBranchRow, owner: str, events: list[Any] | None = None
    ) -> ProjectedState:
        """The projection of the branch, after the row, the events and the base have been compared.

        Why the comparison is made on every read: the row of the branch and the events of the branch move together,
        and a crash between the two leaves a branch that says one thing and holds another. Such a branch is refused
        with `HASH_MISMATCH` and is never served as valid (ADR-021, FR-032).

        Why the base hash is compared here and not only in the reset: the comparison of the base hash is part of the
        verification of the branch, so a branch whose recorded base hash does not match the base it names is refused
        wherever it is asked for and not only where it is repaired (ADR-022).
        """
        if events is None:
            events = self.store.read_events(row.branch_id, owner)
        base = self.base_resolver(row.scenario_id)
        self._check_the_base(row, base)
        state = project(base, events)
        if state.canonical_hash != row.current_canonical_hash:
            raise BranchHashMismatch(
                f"the branch {row.branch_id} cannot prove its own state; fork the scenario again"
            )
        return state

    def _check_the_base(self, row: SandboxBranchRow, base: BaseSnapshot) -> None:
        """The base hash recorded at fork time against the base the resolver hands over.

        Why the comparison is part of the verification of the branch: a base that moved under the branch is a branch
        that cannot prove its own state, and the message offers a fresh fork, because the branch itself cannot be
        repaired (ADR-022, FR-032).
        """
        if base.canonical_hash != row.base_canonical_hash:
            raise BranchHashMismatch(
                f"the base of the branch {row.branch_id} does not match the base it was forked from;"
                " fork the scenario again"
            )

    # -- the reset and the answers of the branch -----------------------------------------------------

    def reset(self, session_id: str, branch_id: str) -> SandboxBranch:
        """The branch back at the published base: no events, revision zero and the hash of the fork.

        The reset is refused before anything moves when the branch is not the one of this session, when it outlived
        its time to live, when the projection of its events does not agree with its row, or when the base moved under
        it. The two last cases are refused with `HASH_MISMATCH` and the message offers a fresh fork, because a
        branch that cannot prove its own state cannot be repaired (FR-021, FR-032, ADR-022).

        The generation of the branch moves forward by one, and the answers the branch remembers keep the generation
        they were produced in, so that the answers of the past can be marked stale. The number is not computed here:
        the store moves it under its own lock and hands back the row it wrote, so two resets that cross cannot write
        the same generation twice (ADR-022).
        """
        owner = self._owner(session_id)
        row = self.store.get_branch(branch_id, owner)
        if row.owner_session != owner:
            # The store already refuses this, but the layer does not rely on that alone.
            raise BranchNotFound()
        if self._expired(row):
            raise BranchExpired(f"the branch {branch_id} expired; fork the scenario again")
        base = self.base_resolver(row.scenario_id)
        if base.canonical_hash != row.base_canonical_hash:
            # The reset keeps its own message for the case in which the base moved under the branch.
            raise BranchHashMismatch(
                f"the base of the branch {branch_id} moved under it; fork the scenario again"
            )
        events = self.store.read_events(branch_id, owner)
        # The branch proves its own state before it moves anything: the projection of its events has to agree with
        # its row, and the base it names has to be the base the resolver hands over (ADR-021, ADR-022).
        self._verified(row, owner, events)
        now = self._clock()
        reset = replace(
            row,
            revision=0,
            current_canonical_hash=row.base_canonical_hash,
            last_activity_at=now,
            expires_at=self._expiry(now, row.created_at),
        )
        # The store moves the generation under its own lock and returns the row it wrote.
        written = self.store.reset_branch(branch_id, owner, reset)
        return self._view(written)

    def answers(self, session_id: str, branch_id: str) -> list[RecordedAnswer]:
        """Every answer the branch remembers, each one marked stale or not.

        An answer whose generation is behind the generation of the branch is stale, and it carries the base canonical
        hash of the branch, the hash of the original snapshot it was computed against. The mark is derived from the
        two generations, so it cannot drift away from the truth (FR-022, ADR-022).

        The base of the branch is verified as well, because a branch whose recorded base hash is wrong is refused
        wherever it is asked for (ADR-022).
        """
        owner = self._owner(session_id)
        row = self.store.get_branch(branch_id, owner)
        if row.owner_session != owner:
            raise BranchNotFound()
        if self._expired(row):
            raise BranchExpired(f"the branch {branch_id} expired; fork the scenario again")
        self._check_the_base(row, self.base_resolver(row.scenario_id))
        return [self._recorded(row, stored) for stored in self.store.list_commands(branch_id, owner)]

    def _recorded(self, row: SandboxBranchRow, stored: SandboxCommandRow) -> RecordedAnswer:
        """One stored answer, with the mark of the staleness that its generation decides."""
        stale = stored.generation < row.generation
        return RecordedAnswer(
            branch_id=stored.branch_id,
            idempotency_key=stored.idempotency_key,
            payload_digest=stored.payload_digest,
            revision=stored.revision,
            canonical_hash=stored.canonical_hash,
            response_diff=list(stored.response_diff),
            response_verdict=dict(stored.response_verdict),
            response_invariants=list(stored.response_invariants),
            generation=stored.generation,
            stale=stale,
            stale_against=row.base_canonical_hash if stale else None,
        )

    # -- the ledger of the branch ---------------------------------------------------------------------

    def ledger(
        self, session_id: str, branch_id: str, account_id: str, cursor: str | None = None
    ) -> LedgerPage:
        """The ledger of the account of the branch: the rows of the projection, one page at a time.

        The rows are the ones of the account of the branch, and the account of another one is refused, so a read
        never returns a row of another account (FR-026).
        """
        owner = self._owner(session_id)
        row = self.store.get_branch(branch_id, owner)
        if self._expired(row):
            raise BranchExpired(f"the branch {branch_id} expired; fork the scenario again")
        branch = self._view(row)
        base = self.base_resolver(branch.scenario_id)
        if account_id != base.account_id:
            # The branch holds the rows of one account, and the account of the request is not that one.
            raise BranchNotFound()
        events = self.store.read_events(branch_id, owner)
        state = self._verified(row, owner, events)
        items = _ledger_items(state)
        keys = [f"{item['kind']}:{item['id']}" for item in items]
        start = 0
        if cursor:
            if cursor not in keys:
                raise MutationRejected(CODE_INVALID_REQUEST, "the cursor is not one of the rows of this ledger")
            start = keys.index(cursor) + 1
        page = items[start : start + LEDGER_PAGE_SIZE]
        following = None
        if page and start + len(page) < len(items):
            following = f"{page[-1]['kind']}:{page[-1]['id']}"
        return LedgerPage(items=tuple(page), next_cursor=following)

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
            generation=row.generation,
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
    "RecordedAnswer",
    "SandboxBranch",
    "STATE_ACTIVE",
    "STATE_EXPIRED",
    "new_branch_id",
]
