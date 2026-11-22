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
counted from the last activity of the visitor, and the absolute deadline, counted from the creation. That rule does
not live here: it lives in `ledgerlens/sandbox/ttl.py`, and the layer asks that module for the expiry of a branch,
because the job that deletes the expired branches uses the same rule (ADR-029).

A fifth rule keeps the branch honest: every read of a branch recomputes the canonical hash of the projection of its
events and compares it with the hash the row of the branch declares. A branch whose row does not agree with its
events may be half applied, and it is refused with the code `HASH_MISMATCH` and never served as valid (ADR-021). The
same rule compares the base hash recorded at fork time with the base the resolver hands over, so a branch whose base
moved under it is refused on every route and not only where it is repaired (ADR-022).

A sixth rule keeps the log honest: the undo of the last mutation is an event of the vocabulary of the sandbox, the
revision of the branch goes back to the previous value, and the event that was undone stays in the log and carries the
mark that it was undone (ADR-024). The undo is a request with a key and with an expected revision, exactly like a
mutation, so a request that is delivered twice undoes one mutation and not two.

A seventh rule keeps the resources of a branch honest: the branch carries the two counters of its resources, the
number of the mutations it committed and the number of the events of its log, and the checks of the limits read those
counters and never a guess (FR-025). The revision cannot stand for the first counter, because
the revision goes back on an undo and the number of the committed mutations does not, and the number of the events is
in no field of the row of the branch. Both counters are read from the log of the branch, which is the truth of the
branch, so they cannot drift away from it. The two limits are the settings of the configuration, and the layer takes
them as arguments of its constructor, the way it takes the two lives of a branch.

Two reads of the branch follow from those rules (ADR-028). The diff of the branch is the difference between the
published base and the state the branch holds now, and not the diff of the last mutation: a branch that was mutated
and then undone answers an empty diff and the hash of the base, because the state of the branch after the undo IS the
state of the base, row for row. The history of the branch carries the events of the log in the order of the log and
the answers the branch remembers, with the mark of the staleness (ADR-022) and the mark of the undo (ADR-024). Both
reads verify the branch before they answer it, exactly like every other read.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ledgerlens.run_context import SESSION_ID_PATTERN, canonical_session_id
from ledgerlens.sandbox.invariants import evaluate
from ledgerlens.sandbox.ledger_view import (
    LedgerAccountMismatch,
    LedgerRevisionMoved,
    LedgerView,
    materialize,
)
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
    command_id_from,
    command_id_of,
    format_minor,
    payload_digest,
    plan_mutation,
    plan_undo,
)
from ledgerlens.sandbox.projector import (
    ProjectedState,
    ProjectionError,
    UndoMarks,
    diff_of,
    is_undo_marker,
    project,
    undo_marks,
    verdict_of,
)
from ledgerlens.sandbox.snapshot import BaseSnapshot
from ledgerlens.sandbox.store import (
    BranchNotFound,
    BranchRevisionConflict,
    BranchStore,
    SandboxBranchRow,
    SandboxCommandRow,
)
from ledgerlens.sandbox.ttl import expiry_of, is_expired

BRANCH_ID_PREFIX = "sb_"
BRANCH_ID_HEX_CHARS = 24
STATE_ACTIVE = "active"
STATE_EXPIRED = "expired"
# The number of rows of one page of the ledger of a branch.
LEDGER_PAGE_SIZE = 50
# The resources of one branch (FR-025). A branch that reaches one of them is refused, and the branch is not
# bigger than the resources of the server that holds it.
# The two numbers are the DEFAULTS of the layer: the deployment that declares nothing keeps the limits of today, and
# the deployment that declares something hands the limits to the constructor of the layer, the way it hands the two
# lives of a branch. The settings of the configuration carry the same defaults.
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

    `committed_mutations` and `event_count` are the counters of the resources of the branch (FR-025). They are
    derived from the log of the branch, which is the truth of the branch, so they cannot drift away from it. The
    revision cannot stand for the first one: the revision goes back on an undo and the number of the committed
    mutations does not, and the number of the events of the log is in no field of the row of the branch.
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
    # The number of the mutations the branch committed, and the number of the events of its log. The marker of an undo
    # is an event of the log and is not a mutation.
    committed_mutations: int = 0
    event_count: int = 0


@dataclass(frozen=True)
class RecordedAnswer:
    """One answer the branch remembers, with the mark of the staleness and the mark of the undo.

    The fields are the ones of the stored answer, plus the marks. `stale` says that the answer was produced in a
    generation behind the one of the branch, and `stale_against` is the base canonical hash of the branch, the hash of
    the original snapshot the answer was computed against. An answer of the current generation is not stale and
    `stale_against` is None (FR-022, ADR-022).

    `undone` says that the mutation this answer describes was undone afterwards. It is true for the answer of a
    mutation that was undone and false for the answer of an undo, because an undo can never be undone: the undo only
    takes back a mutation, and a marker of the log is not a mutation. `undone_event_uid` says which event the request
    that this answer describes undid, and it is filled only for the answer of an undo. The two marks never overlap, and
    they are derived from the log of the branch, so they cannot drift away from the truth (ADR-024).
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
    undone: bool = False
    undone_event_uid: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """The answer as the interface reads it, with the two marks of the branch.

        Why the marks travel with the answer: an answer of the past is stale and an answer of a mutation that was
        undone is not the current result of the branch either, so the reader of the answer has to see both (ADR-022,
        ADR-024).
        """
        return {
            "branch_id": self.branch_id,
            "idempotency_key": self.idempotency_key,
            "payload_digest": self.payload_digest,
            "revision": self.revision,
            "canonical_hash": self.canonical_hash,
            "response_diff": list(self.response_diff),
            "response_verdict": dict(self.response_verdict),
            "response_invariants": list(self.response_invariants),
            "generation": self.generation,
            "stale": self.stale,
            "stale_against": self.stale_against,
            "undone": self.undone,
            "undone_event_uid": self.undone_event_uid,
        }


@dataclass(frozen=True)
class BranchDiff:
    """The difference between the published base of the branch and the state the branch holds now (ADR-028).

    `base_canonical_hash` names the published case the branch was forked from and `canonical_hash` names the state
    the branch holds now. They are the same hash when the branch was never mutated, and they are the same hash again
    when the branch was mutated and then undone, because the state of the branch after the undo IS the state of the
    base, row for row: that is the cost ADR-024 already accepted.

    The entries are the ones of the projector and the values are texts, so the interface never reads a number and
    never calculates one. `invariants` are the rules of the domain over the current state and `verdict` is the
    verdict of the case over it, the same two things the answer of the commit carries.
    """

    revision: int
    base_canonical_hash: str
    canonical_hash: str
    diff: list[dict[str, Any]]
    invariants: list[dict[str, Any]]
    verdict: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """The answer of the diff, as the interface reads it."""
        return {
            "revision": self.revision,
            "base_canonical_hash": self.base_canonical_hash,
            "canonical_hash": self.canonical_hash,
            "diff": list(self.diff),
            "invariants": list(self.invariants),
            "verdict": dict(self.verdict),
        }


@dataclass(frozen=True)
class BranchHistory:
    """The log of the branch and the answers the branch remembers, with their marks (ADR-028).

    The events come in the order of the log, and every one of them carries the mark that says it was undone. The
    marks come from the log and never from a stored flag, so they cannot drift away from the truth of the log
    (ADR-024).

    The answers carry the mark of the staleness of ADR-022 and the mark of the undo of ADR-024, and they carry the
    same fields they carry everywhere else, so the interface reads one vocabulary.
    """

    revision: int
    canonical_hash: str
    events: list[dict[str, Any]]
    answers: list[RecordedAnswer]

    def to_dict(self) -> dict[str, Any]:
        """The answer of the history, as the interface reads it."""
        return {
            "revision": self.revision,
            "canonical_hash": self.canonical_hash,
            "events": list(self.events),
            "answers": [answer.to_dict() for answer in self.answers],
        }


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

    Why the limits of the resources are injected: the limits of a deployment are settings of the configuration, and
    the layer reads them the way it reads the two lives of a branch, as arguments of its constructor. The layer never
    reads the environment and never imports the configuration.
    """

    def __init__(
        self,
        store: BranchStore,
        base_resolver: Callable[[str], BaseSnapshot],
        *,
        idle_ttl_seconds: int = 3600,
        absolute_ttl_seconds: int = 14400,
        max_committed_mutations: int = MAX_COMMITTED_MUTATIONS,
        max_events: int = MAX_EVENTS,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.base_resolver = base_resolver
        self.idle_ttl_seconds = idle_ttl_seconds
        self.absolute_ttl_seconds = absolute_ttl_seconds
        # The limits of the resources of a branch. They are the defaults of the layer, and a deployment that declares
        # nothing keeps the limits of today.
        self.max_committed_mutations = max_committed_mutations
        self.max_events = max_events
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
        return ForkOutcome(branch=self._view(self.store.create_branch(row), []), created=True)

    # -- the status --------------------------------------------------------------------------------

    def status(self, session_id: str, branch_id: str) -> SandboxBranch:
        """The status of the branch, for the session that owns it.

        A branch of another session is refused with the same generic answer as a branch that does not exist, so
        nothing about the existence of the branch leaks. Reading the branch is an activity: the idle deadline of the
        branch moves, the absolute deadline never does.

        The branch is verified before it is served: the hash of the projection of its events has to be the hash the
        row declares, or the branch cannot prove its own state and is refused (ADR-021).

        The branch carries the counters of its resources, and they are read from the log of the branch, so the status
        of a branch tells how many mutations it committed and how many events its log holds (FR-025).
        """
        owner = self._owner(session_id)
        row = self.store.get_branch(branch_id, owner)
        if row.owner_session != owner:
            # The store already refuses this, but the layer does not rely on that alone.
            raise BranchNotFound()
        if self._expired(row):
            raise BranchExpired(f"the branch {branch_id} expired; fork the scenario again")
        events = self.store.read_events(branch_id, owner)
        self._verified(row, owner, events)
        return self._view(self._refresh(row), events)

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
        events = self.store.read_events(branch_id, owner)
        branch = self._view(row, events)
        base = self.base_resolver(branch.scenario_id)
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
        events = self.store.read_events(branch_id, owner)
        branch = self._view(row, events)
        base = self.base_resolver(branch.scenario_id)
        # Every read of the branch is verified: a branch that cannot prove its own state is never served (ADR-021).
        state = self._verified(row, owner, events)
        if not command.idempotency_key:
            raise MutationRejected(CODE_INVALID_REQUEST, "the request carries no idempotency key")
        if command.expected_revision is None:
            raise MutationRejected(CODE_INVALID_REQUEST, "the request carries no expected revision")
        digest = payload_digest(command)
        stored = self.store.command_answer(branch_id, owner, command.idempotency_key)
        if stored is not None:
            return self._replay(branch, stored, command, digest, events)
        if command.expected_revision != branch.revision:
            raise MutationRejected(
                CODE_REVISION_CONFLICT,
                f"the branch is at revision {branch.revision} and the request expected {command.expected_revision}",
            )
        self._check_the_resources(branch)
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

    def undo(self, session_id: str, branch_id: str, command: MutationCommand) -> MutationResult:
        """The undo of the last mutation of the branch: the revision goes back and the history stays (ADR-024).

        The order of the three rules is the order of the promises, and it is the order of the commit: the idempotency
        key comes first, so a request that was already answered is answered with the answer that was stored, whatever
        the expected revision says: a second delivery that was answered with a new undo would undo another mutation,
        because it would find another mutation to undo (FR-012). A key that was seen with another payload is a
        conflict, whatever the expected revision says (FR-013). A key that was never seen has to carry the expected
        revision of the branch, and a stale one is a conflict (FR-014).

        The branch is verified before it moves anything, so a branch that cannot prove its own state is refused with
        `HASH_MISMATCH` and never served (ADR-021). An undo that has nothing to undo is refused with
        `NOTHING_TO_UNDO`, and the branch stays untouched (FR-038).

        The revision goes back to the previous value and the hash becomes the hash of the state the branch returns to.
        The event that was undone stays in the log and the marker is appended to it, so the history is append only
        (FR-037).
        """
        owner = self._owner(session_id)
        row = self.store.get_branch(branch_id, owner)
        if row.owner_session != owner:
            # The store already refuses this, but the layer does not rely on that alone.
            raise BranchNotFound()
        if self._expired(row):
            raise BranchExpired(f"the branch {branch_id} expired; fork the scenario again")
        events = self.store.read_events(branch_id, owner)
        branch = self._view(row, events)
        base = self.base_resolver(branch.scenario_id)
        # Every read of the branch is verified: a branch that cannot prove its own state is never served (ADR-021).
        state = self._verified(row, owner, events)
        if not command.idempotency_key:
            raise MutationRejected(CODE_INVALID_REQUEST, "the request carries no idempotency key")
        if command.expected_revision is None:
            raise MutationRejected(CODE_INVALID_REQUEST, "the request carries no expected revision")
        digest = payload_digest(command)
        stored = self.store.command_answer(branch_id, owner, command.idempotency_key)
        if stored is not None:
            return self._replay(branch, stored, command, digest, events)
        if command.expected_revision != branch.revision:
            raise MutationRejected(
                CODE_REVISION_CONFLICT,
                f"the branch is at revision {branch.revision} and the request expected {command.expected_revision}",
            )
        self._check_the_events(branch)
        now = self._clock()
        plan = plan_undo(
            base, branch.branch_id, branch.scenario_id, branch.revision, events, command, now, before=state
        )
        failed = [result for result in plan.invariants if not result["passed"]]
        if failed:
            raise MutationRejected(CODE_INVARIANT_VIOLATION, str(failed[0]["reason"]))
        new_row = replace(
            row,
            # The revision of the branch is the number of the mutations that are still live, so it goes back.
            revision=branch.revision - 1,
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
            self.store.commit_undo(branch_id, owner, plan.event, new_row, answer)
        except BranchRevisionConflict:
            # The branch moved between the read and the write: the request is stale, and nothing was written.
            raise MutationRejected(
                CODE_REVISION_CONFLICT, "the branch moved while the request was being prepared"
            ) from None
        return plan.to_result()

    def _check_the_resources(self, branch: SandboxBranch) -> None:
        """The resources of the branch: the number of its mutations and the number of its events.

        Why the refusal comes before the work: a branch that reached its limit is refused without a projection,
        so the server never spends the resources of a request it will refuse anyway (FR-025).

        Why the counters of the branch and not the revision: the revision goes back on an undo and the number of the
        committed mutations does not, so the revision is not the number of the mutations the branch committed.
        """
        if branch.committed_mutations >= self.max_committed_mutations:
            raise MutationRejected(
                CODE_RESOURCE_LIMIT,
                f"the branch already holds {branch.committed_mutations} committed mutations, and the limit is"
                f" {self.max_committed_mutations}",
            )
        self._check_the_events(branch)

    def _check_the_events(self, branch: SandboxBranch) -> None:
        """The number of events of the branch.

        Why the undo is measured against this limit and not against the limit of the mutations: an undo frees a
        mutation and appends an event, so what grows is the number of the events of the log (ADR-024).
        """
        if branch.event_count >= self.max_events:
            raise MutationRejected(
                CODE_RESOURCE_LIMIT,
                f"the branch already holds {branch.event_count} events, and the limit is {self.max_events}",
            )

    def _replay(
        self,
        branch: SandboxBranch,
        stored: SandboxCommandRow,
        command: MutationCommand,
        digest: str,
        events: list[Any],
    ) -> MutationResult:
        """The answer of a request that was already committed, with the same key and the same payload.

        The answer that is returned is the answer that was remembered: the revision, the hash, the diff, the
        invariants and the verdict of the request that was committed. They are not recomputed from the current
        projection, because a later mutation may have moved the case and the answer of a request is the answer of
        that request (ADR-021).

        The mark of the undo is the one of the log: the marker of an undo names the command id of the request it
        undoes, so the answer of a request that was undone carries the mark, and the answer of the undo itself
        carries the uid of the event it undid (ADR-024).
        """
        if stored.payload_digest != digest:
            raise MutationRejected(
                CODE_IDEMPOTENCY_MISMATCH,
                "the idempotency key was already used with another payload",
            )
        # An answer of a generation behind the current one of the branch is stale, and it is answered with the mark,
        # so that the answer of the past is never presented as the current result of the branch (FR-022, ADR-022).
        stale = stored.generation < branch.generation
        command_id = command_id_of(command, digest)
        marks = undo_marks(events)
        # The two marks of the undo never overlap: the answer of a mutation that was undone says that it was undone
        # and names no event, and the answer of the undo names the event it undid (ADR-024).
        undone = command_id in marks.undone_command_ids
        undone_event_uid = marks.undone_event_uid_by_command.get(command_id)
        return MutationResult(
            command_id=command_id,
            kind=command.kind,
            revision=stored.revision,
            canonical_hash=stored.canonical_hash,
            diff=tuple(stored.response_diff),
            invariants=tuple(stored.response_invariants),
            verdict=dict(stored.response_verdict),
            replayed=True,
            stale=stale,
            stale_against=branch.base_canonical_hash if stale else None,
            undone=undone,
            undone_event_uid=undone_event_uid,
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

        Why a log that cannot be projected is refused here: an event of a kind the interpreter does not know, or an
        event that names a record the projection does not hold, is a branch that cannot prove its own state. The
        refusal is the one of a branch whose row does not agree with its events, so every route answers it the same
        way (ADR-024).
        """
        if events is None:
            events = self.store.read_events(row.branch_id, owner)
        base = self.base_resolver(row.scenario_id)
        self._check_the_base(row, base)
        try:
            state = project(base, events)
        except ProjectionError as failure:
            raise BranchHashMismatch(
                f"the log of the branch {row.branch_id} cannot be projected, so the branch cannot prove its own"
                " state; fork the scenario again"
            ) from failure
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
        """Every answer the branch remembers, each one marked stale or not, and marked undone or not.

        An answer whose generation is behind the generation of the branch is stale, and it carries the base canonical
        hash of the branch, the hash of the original snapshot it was computed against. The mark is derived from the
        two generations, so it cannot drift away from the truth (FR-022, ADR-022).

        The mark of the undo is derived from the log of the branch in the same way: the marker of an undo names the
        command id of the request it undoes, and the answers of the branch that carry that command id are the ones
        that were undone (ADR-024).

        The base of the branch is verified as well, because a branch whose recorded base hash is wrong is refused
        wherever it is asked for (ADR-022).

        Why the branch is verified like every other read: the answers are derived from the log of the branch, and a
        branch whose log cannot be projected cannot prove its own state, so it is refused with `HASH_MISMATCH` and
        never served (ADR-021, ADR-026). The log is read once and the same events are used for the verification
        and for the marks of the undo.
        """
        owner = self._owner(session_id)
        row = self.store.get_branch(branch_id, owner)
        if row.owner_session != owner:
            raise BranchNotFound()
        if self._expired(row):
            raise BranchExpired(f"the branch {branch_id} expired; fork the scenario again")
        events = self.store.read_events(branch_id, owner)
        # Every read of the branch is verified: a branch that cannot prove its own state is never served (ADR-021).
        self._verified(row, owner, events)
        marks = undo_marks(events)
        return [self._recorded(row, stored, marks) for stored in self.store.list_commands(branch_id, owner)]

    def _recorded(self, row: SandboxBranchRow, stored: SandboxCommandRow, marks: UndoMarks) -> RecordedAnswer:
        """One stored answer, with the mark of the staleness its generation decides and the mark of the undo."""
        stale = stored.generation < row.generation
        # The command id of the remembered request, computed from the two values the branch keeps.
        command_id = command_id_from(stored.idempotency_key, stored.payload_digest)
        # The two marks of the undo never overlap: the answer of a mutation that was undone says that it was undone
        # and names no event, and the answer of the undo names the event it undid (ADR-024).
        undone = command_id in marks.undone_command_ids
        undone_event_uid = marks.undone_event_uid_by_command.get(command_id)
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
            undone=undone,
            undone_event_uid=undone_event_uid,
        )

    # -- the diff and the history of the branch -------------------------------------------------------

    def diff(self, session_id: str, branch_id: str) -> BranchDiff:
        """The difference between the published base of the branch and the state the branch holds now (ADR-028).

        Why the base and not the last mutation: there are three diffs in the sandbox and they are not the same
        thing. The diff of a mutation is in the answer of the commit and of the preview, the diff of the undo is
        in the answer of the undo, and this one is the difference between the base and the state of the branch as it
        is now, so the interface can show the before and after of a revision (FR-034).

        Why a branch that was mutated and then undone answers an empty diff: the state of the branch after the undo
        IS the state of the base, row for row. That is the cost ADR-024 already accepted, and the route shows it
        honestly instead of hiding it: only the history tells that something happened.

        The branch is verified before it is answered: a branch that cannot prove its own state is refused with
        `HASH_MISMATCH` and is never served (ADR-021).
        """
        owner = self._owner(session_id)
        row = self.store.get_branch(branch_id, owner)
        if row.owner_session != owner:
            # The store already refuses this, but the layer does not rely on that alone.
            raise BranchNotFound()
        if self._expired(row):
            raise BranchExpired(f"the branch {branch_id} expired; fork the scenario again")
        base = self.base_resolver(row.scenario_id)
        events = self.store.read_events(branch_id, owner)
        # Every read of the branch is verified: a branch that cannot prove its own state is never served (ADR-021).
        state = self._verified(row, owner, events)
        # The published base is the other side of the difference: the branch holds it plus the events.
        base_state = project(base, [])
        entries = diff_of(base_state, state)
        results = evaluate(state)
        return BranchDiff(
            revision=row.revision,
            base_canonical_hash=row.base_canonical_hash,
            canonical_hash=state.canonical_hash,
            diff=[entry.to_dict() for entry in entries],
            invariants=[result.to_dict() for result in results],
            verdict=verdict_of(state, row.scenario_id).to_dict(),
        )

    def history(self, session_id: str, branch_id: str) -> BranchHistory:
        """The log of the branch and the answers the branch remembers, with their marks (ADR-028).

        The log is read once and the same log is used for the verification of the branch and for the marks, so the
        marks of the history are the marks of the log that was verified (ADR-021, ADR-024).

        The marks come from the log and never from a stored flag: the marker of an undo names the event it undid and
        the request that produced it, and the answers of the branch that carry that command id are the ones that were
        undone (ADR-024). The mark of the staleness comes from the two generations of the branch and of the answer
        (ADR-022).
        """
        owner = self._owner(session_id)
        row = self.store.get_branch(branch_id, owner)
        if row.owner_session != owner:
            raise BranchNotFound()
        if self._expired(row):
            raise BranchExpired(f"the branch {branch_id} expired; fork the scenario again")
        events = self.store.read_events(branch_id, owner)
        # Every read of the branch is verified: a branch that cannot prove its own state is never served (ADR-021).
        self._verified(row, owner, events)
        marks = undo_marks(events)
        return BranchHistory(
            revision=row.revision,
            canonical_hash=row.current_canonical_hash,
            events=[self._event_of(event, marks) for event in events],
            answers=[self._recorded(row, stored, marks) for stored in self.store.list_commands(branch_id, owner)],
        )

    def _event_of(self, event: Any, marks: UndoMarks) -> dict[str, Any]:
        """One event of the log, with the mark that says it was undone.

        Why the marker of an undo is never marked as undone: an undo can never be undone, because the undo only takes
        back a mutation and a marker of the log is not a mutation (ADR-024).
        """
        return {
            "event_uid": event.event_uid,
            "event_type": event.event_type,
            "aggregate_id": event.aggregate_id,
            "occurred_at": event.occurred_at,
            "payload": dict(event.payload),
            "undone": not is_undo_marker(event) and event.event_uid in marks.undone_event_uids,
        }

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
            # The branch holds the rows of one account and the counterparties of its transactions, and the account of
            # the request is not that one.
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

    # -- the ledger of the visitor ---------------------------------------------------------------------

    def ledger_view(
        self,
        session_id: str,
        branch_id: str,
        *,
        account_id: str,
        expected_revision: int | None = None,
        target: Path | str,
    ) -> LedgerView:
        """The ledger of the visitor, materialized in the file of the target.

        The order of the checks is the order of the promises of ADR-038, and the file is written only when every one
        of them passed, so a refused branch leaves no file behind:

        * a branch of another session is refused with the same generic answer as a branch that does not exist, so
          nothing about the existence of the branch leaks;
        * a branch that outlived its time to live is refused with `BranchExpired`;
        * the account of the request has to be the account of the branch, the account of the branch being the account
          of the base it was forked from, and a mismatch is refused with `LedgerAccountMismatch`;
        * the revision the request expected has to be the revision the branch is at, or the run would answer about a
          state the visitor never saw, and a revision that moved is refused with `LedgerRevisionMoved`;
        * the branch proves its own state before anything is written, so a branch that cannot prove it has no ledger.

        Why the state of the branch and not the state of the base: the branch is the only truth of the visitor, and
        the mutations of the visitor are in it (ADR-038).

        Why the idle deadline of the branch moves: a live run is an activity of the visitor on the branch, exactly
        like a read of the status is, so the branch of a visitor who is looking at it does not expire under the
        feet of the visitor. The file of the run is a copy of the state, so the run itself is safe even when the
        cleanup job deletes the branch.

        Why the refresh comes after the verification: a branch that cannot prove its own state is never touched, so
        a refusal leaves the row of the branch exactly where it was.
        """
        owner = self._owner(session_id)
        row = self.store.get_branch(branch_id, owner)
        if row.owner_session != owner:
            # The store already refuses this, but the layer does not rely on that alone.
            raise BranchNotFound()
        if self._expired(row):
            raise BranchExpired(f"the branch {branch_id} expired; fork the scenario again")
        base = self.base_resolver(row.scenario_id)
        if account_id != base.account_id:
            # The branch holds the rows of one account and the counterparties of its transactions, and the account of
            # the request is not that one.
            raise LedgerAccountMismatch(f"the account {account_id} is not the account of the branch {branch_id}")
        if expected_revision is not None and expected_revision != row.revision:
            raise LedgerRevisionMoved(
                f"the branch {branch_id} is at revision {row.revision}, not at the revision {expected_revision}"
                " the request expected"
            )
        events = self.store.read_events(branch_id, owner)
        state = self._verified(row, owner, events)
        # The refresh is after the verification: a branch that cannot prove its own state is never touched.
        row = self._refresh(row)
        try:
            path = materialize(state, target)
        finally:
            # The projection holds a connection of its own, and the run keeps no reference to it.
            state.close()
        return LedgerView(
            path=path,
            account_id=base.account_id,
            branch_id=row.branch_id,
            revision=row.revision,
            canonical_hash=state.canonical_hash,
        )

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

    def _view(self, row: SandboxBranchRow, events: list[Any] | None = None) -> SandboxBranch:
        """The branch as the domain sees it, with the counters of its resources.

        Why the counters come from the log: the log is the truth of the branch, the number of its events is in no
        other place, and the number of the committed mutations is the number of the events that are not the marker of
        an undo, because an undo is not a mutation. An undone mutation stays counted: the revision of the branch goes
        back and the count of the committed mutations does not (FR-025).

        Why the events are an argument: the callers that already read the log hand it over, so the log is read once,
        and the branch and the check of its limits always see the same log.
        """
        if events is None:
            events = self.store.read_events(row.branch_id, row.owner_session)
        committed = sum(1 for event in events if not is_undo_marker(event))
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
            committed_mutations=committed,
            event_count=len(events),
        )

    def _refresh(self, row: SandboxBranchRow) -> SandboxBranchRow:
        """The activity of the visitor moves the idle deadline; the absolute deadline never moves.

        Why the deadline is moved by the method of the store that moves only the deadline: the write of a whole row
        carries the revision and the hash that a reader held a moment ago, so a mutation that landed between the
        read and the write would be rolled back by it. The branch would lose the proof of its own state and would
        be refused with `HASH_MISMATCH` on every route (ADR-021, ADR-027).

        Why nothing is written when the deadline did not move: a read that finds the deadline where it is leaves
        the branch exactly where it was.
        """
        now = self._clock()
        expires_at = self._expiry(now, row.created_at)
        if now == row.last_activity_at and expires_at == row.expires_at:
            return row
        return self.store.touch_branch(row.branch_id, row.owner_session, now, expires_at)

    def _expiry(self, last_activity_at: datetime, created_at: datetime) -> datetime:
        """The expiry of a branch, asked to the module that holds the rule of the time to live (ADR-029).

        Why the layer asks and does not compute: the job that deletes the expired branches uses the same rule, and
        two copies of it would drift apart. A branch that the layer refuses and a branch that the job deletes have
        to be the same branch at the same moment.
        """
        return expiry_of(
            last_activity_at,
            created_at,
            idle_ttl_seconds=self.idle_ttl_seconds,
            absolute_ttl_seconds=self.absolute_ttl_seconds,
        )

    def _expired(self, row: SandboxBranchRow) -> bool:
        """Whether the branch outlived its time to live, asked to the module that holds the rule (ADR-029)."""
        return is_expired(row, self._clock())


__all__ = [
    "BRANCH_ID_PREFIX",
    "BranchDiff",
    "BranchExpired",
    "BranchHashMismatch",
    "BranchHistory",
    "BranchLayer",
    "ForkOutcome",
    "InvalidSessionId",
    "LedgerPage",
    "RecordedAnswer",
    "SandboxBranch",
    "STATE_ACTIVE",
    "STATE_EXPIRED",
    "new_branch_id",
]
