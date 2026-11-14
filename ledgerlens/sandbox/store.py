"""The branch store: the rows of a branch, the rows of its events, and the interface every implementation follows.

Why it exists: the branch layer of ADR-018 must be able to replace the file backed store with a database one without
the domain logic changing. So the persistence sits behind `BranchStore`, a protocol with one method per operation,
and every method that names a branch also names the owner session: a branch that belongs to another visitor is
refused with `BranchNotFound`, the same error as a branch that does not exist, so nothing about the existence of a
branch leaks. The isolation is therefore proven in the data and not only in the path of the domain layer.

The store writes no domain rule and decides nothing. It stores what it is given: the fork, the owner check and the
reuse rule live in `ledgerlens/sandbox/branch.py`, and the rule of the expiry lives in `ledgerlens/sandbox/ttl.py`.
"""

from __future__ import annotations

import json
import secrets
import shutil
import threading
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from ledgerlens.sim.events import AppendResult, canonical_json

# The message of the refusal. The same for a branch of another visitor and for a branch that does not exist, so an
# answer never discloses that the branch exists.
GENERIC_NOT_FOUND = "no branch is available for this session"


class BranchNotFound(Exception):
    """The branch is not available to this session.

    Why one error for two cases: a caller must not be able to tell a branch of another visitor from a branch that
    does not exist. The message is therefore the same in both cases.
    """

    def __init__(self, message: str = GENERIC_NOT_FOUND) -> None:
        super().__init__(message)


class BranchRevisionConflict(Exception):
    """The branch moved while the request was being prepared.

    Why the store raises it: the append of the events and the move of the row happen together, so the store is the
    only place where the revision of the branch can be compared with the revision the visitor expected. The loser of
    two concurrent commits is refused here, and nothing is written.
    """


@dataclass(frozen=True)
class SandboxBranchRow:
    """One branch, as the store keeps it.

    `owner_session` is the canonical form of the session identifier, because the identifier lands in a path and a
    filesystem may ignore the case of a name. `base_snapshot_id` names the published snapshot the branch was forked
    from and `base_canonical_hash` is the canonical hash of the account scoped projection the branch reads.
    `last_activity_at` is the moment of the last activity of the visitor, and the idle deadline of the branch is
    computed from it.

    `generation` counts the resets the branch went through. It is what marks the answers of the past as stale, and it
    is compared instead of a flag, because a flag can drift away from the truth (ADR-022).
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
    state: str = "active"
    generation: int = 0


@dataclass(frozen=True)
class SandboxEventRow:
    """One event of a branch, as the store keeps it.

    The event identity is given by the caller: the store stores what it is given and never decides what an event
    means. `origin` is the label that tells a sandbox event from a published one.
    """

    event_uid: str
    branch_id: str
    event_type: str
    aggregate_id: str
    occurred_at: str
    payload: dict[str, Any]
    origin: str = "sandbox"
    command_id: str | None = None


@dataclass(frozen=True)
class SandboxCommandRow:
    """The answer of a request that was committed, remembered with the branch.

    `idempotency_key` names the request, `payload_digest` is the digest of the payload it carried, and the other
    fields are the answer: the revision the commit produced, the canonical hash of the branch, the diff of the
    mutation, the verdict of the case and the invariants of the domain. The whole answer is stored so that the
    same request, sent twice, is answered the same way, and the verdict and the invariants are part of it because
    a later mutation may have moved the case (FR-012, FR-013).

    `generation` is the generation the branch was in when the answer was produced. The answer of a generation behind
    the current one of the branch is stale, and the branch marks it instead of presenting it as the current result
    (FR-022, ADR-022).
    """

    branch_id: str
    idempotency_key: str
    payload_digest: str
    revision: int
    canonical_hash: str
    response_diff: list[dict[str, Any]]
    response_verdict: dict[str, Any] = field(default_factory=dict)
    response_invariants: list[dict[str, Any]] = field(default_factory=list)
    generation: int = 0


@runtime_checkable
class BranchStore(Protocol):
    """One method per operation of the branch layer.

    Every method that names a branch also names the owner session, and refuses a branch whose owner differs by
    raising `BranchNotFound`. The two implementations of the protocol, the file backed one and the database one,
    behave identically under the same contract test suite.
    """

    def create_branch(self, branch: SandboxBranchRow) -> SandboxBranchRow:
        """Stores a new branch and returns it."""

    def get_branch(self, branch_id: str, owner_session: str) -> SandboxBranchRow:
        """The branch of this session. Raises `BranchNotFound` when it is not there or not its own."""

    def list_branches(self, owner_session: str) -> list[SandboxBranchRow]:
        """Every branch of this session, in the order of the store."""

    def save_branch(self, branch: SandboxBranchRow) -> SandboxBranchRow:
        """Stores the row of a branch of this session again.

        The store writes no rule: the caller computes the new deadline and hands the row over.
        """

    def touch_branch(
        self, branch_id: str, owner_session: str, last_activity_at: datetime, expires_at: datetime
    ) -> SandboxBranchRow:
        """Moves the deadline of the branch of this session and writes no other field of the row.

        Why the method exists: the deadline is part of the row of the branch, and a write that carries the whole
        row carries the revision and the hash that a reader held a moment ago. A mutation that landed between the
        read and the write would be rolled back by it, and the branch would lose the proof of its own state
        (ADR-021, ADR-027).

        The row that is returned is the row that is kept after the write, so the caller holds the state of the
        branch and not the state it read before.

        The branch of another visitor is refused with `BranchNotFound`, like every other operation of the store.
        """

    def append_events(self, branch_id: str, owner_session: str, events: Sequence[SandboxEventRow]) -> AppendResult:
        """Appends events to the branch. The append is idempotent on the event uid."""

    def read_events(self, branch_id: str, owner_session: str) -> list[SandboxEventRow]:
        """The events of the branch of this session, in the order they were appended."""

    def delete_events(self, branch_id: str, owner_session: str) -> int:
        """Drops every event of the branch and returns how many were dropped."""

    def list_expired(self, now: datetime) -> list[SandboxBranchRow]:
        """Every branch whose expiry has passed, whatever its owner. The cleanup job uses it."""

    def delete_branch(self, branch_id: str, owner_session: str) -> bool:
        """Drops the branch and its events. Raises `BranchNotFound` when it is not there or not its own."""

    def commit_events(
        self,
        branch_id: str,
        owner_session: str,
        events: Sequence[SandboxEventRow],
        branch: SandboxBranchRow,
        answer: SandboxCommandRow,
    ) -> AppendResult:
        """Appends the events, moves the row of the branch and remembers the answer of the request, together.

        Why the three happen together: the append of the events and the move of the row are one operation of the
        domain, and a request that is answered has to be answered the same way the second time (ADR-021). The row
        that is written is the one the branch moves to, so the store moves it only when the branch is still at the
        revision before it, and it refuses the request otherwise with `BranchRevisionConflict`.
        """

    def command_answer(self, branch_id: str, owner_session: str, idempotency_key: str) -> SandboxCommandRow | None:
        """The answer already given to the request with this key, or None when there is none.

        The branch of another visitor is refused with `BranchNotFound`, like every other read of the store.
        """

    def commit_undo(
        self,
        branch_id: str,
        owner_session: str,
        event: SandboxEventRow,
        branch: SandboxBranchRow,
        answer: SandboxCommandRow,
    ) -> SandboxBranchRow:
        """Appends the marker of the undo, moves the row of the branch back and remembers the answer, together.

        Why the three happen together: the undo is one operation of the domain, and the revision of the branch and
        the marker of the log cannot drift apart (ADR-024). The row that is written is the one the branch moves to,
        so the store moves it only when the branch is still at the revision after it, and it refuses the request
        otherwise with `BranchRevisionConflict`.

        The branch of another visitor is refused with `BranchNotFound`, like every other operation of the store.
        """

    def reset_branch(self, branch_id: str, owner_session: str, branch: SandboxBranchRow) -> SandboxBranchRow:
        """Drops every event of the branch, writes the row of it, and returns the row it wrote.

        Why the two happen together: the reset is one operation of the domain, and a branch whose row does not agree
        with its events is refused instead of being served (ADR-021, ADR-022). The answers the branch remembers are
        kept with the generation they were produced in, because an answer that is deleted cannot be marked stale.

        Why the store moves the generation: the store is the only place where the row of the branch is locked, so the
        store is the only place where the number can move safely. The store reads the generation it finds in the row
        and writes one more, and it ignores the generation of the row the caller hands over. The caller therefore
        receives the truth and not a hope (ADR-022).

        The branch of another visitor is refused with `BranchNotFound`, like every other operation of the store.
        """

    def list_commands(self, branch_id: str, owner_session: str) -> list[SandboxCommandRow]:
        """Every answer the branch remembers, in the order the requests were committed.

        The branch of another visitor is refused with `BranchNotFound`, like every other read of the store.
        """


def _safe_name(name: str) -> str:
    """A name that can be a folder of the store: no separator, no dot segment and no empty name.

    Why: the owner session comes from a visitor, and a name that walks out of the folder of the store would put the
    branches of the product where they do not belong.
    """
    if not name or name in {".", ".."} or "/" in name or "\\" in name or "\0" in name:
        raise ValueError(f"not a usable name: {name!r}")
    return name


def _branch_to_dict(row: SandboxBranchRow) -> dict[str, Any]:
    return {
        "branch_id": row.branch_id,
        "owner_session": row.owner_session,
        "scenario_id": row.scenario_id,
        "base_snapshot_id": row.base_snapshot_id,
        "base_canonical_hash": row.base_canonical_hash,
        "revision": row.revision,
        "current_canonical_hash": row.current_canonical_hash,
        "created_at": row.created_at.isoformat(),
        "last_activity_at": row.last_activity_at.isoformat(),
        "expires_at": row.expires_at.isoformat(),
        "state": row.state,
        "generation": row.generation,
    }


def _branch_from_dict(data: dict[str, Any]) -> SandboxBranchRow:
    return SandboxBranchRow(
        branch_id=data["branch_id"],
        owner_session=data["owner_session"],
        scenario_id=data["scenario_id"],
        base_snapshot_id=data["base_snapshot_id"],
        base_canonical_hash=data["base_canonical_hash"],
        revision=int(data["revision"]),
        current_canonical_hash=data["current_canonical_hash"],
        created_at=datetime.fromisoformat(data["created_at"]),
        last_activity_at=datetime.fromisoformat(data["last_activity_at"]),
        expires_at=datetime.fromisoformat(data["expires_at"]),
        state=data.get("state", "active"),
        # The generation is read with a default of zero, so a file written by an older version still loads.
        generation=int(data.get("generation", 0)),
    )


def _event_to_dict(row: SandboxEventRow) -> dict[str, Any]:
    return {
        "event_uid": row.event_uid,
        "branch_id": row.branch_id,
        "event_type": row.event_type,
        "aggregate_id": row.aggregate_id,
        "occurred_at": row.occurred_at,
        "payload": row.payload,
        "origin": row.origin,
        "command_id": row.command_id,
    }


def _event_from_dict(data: dict[str, Any]) -> SandboxEventRow:
    return SandboxEventRow(
        event_uid=data["event_uid"],
        branch_id=data["branch_id"],
        event_type=data["event_type"],
        aggregate_id=data["aggregate_id"],
        occurred_at=data["occurred_at"],
        payload=data["payload"],
        origin=data.get("origin", "sandbox"),
        command_id=data.get("command_id"),
    )


def _command_to_dict(row: SandboxCommandRow) -> dict[str, Any]:
    return {
        "branch_id": row.branch_id,
        "idempotency_key": row.idempotency_key,
        "payload_digest": row.payload_digest,
        "revision": row.revision,
        "canonical_hash": row.canonical_hash,
        "response_diff": row.response_diff,
        "response_verdict": row.response_verdict,
        "response_invariants": row.response_invariants,
        "generation": row.generation,
    }


def _command_from_dict(data: dict[str, Any]) -> SandboxCommandRow:
    return SandboxCommandRow(
        branch_id=data["branch_id"],
        idempotency_key=data["idempotency_key"],
        payload_digest=data["payload_digest"],
        revision=int(data["revision"]),
        canonical_hash=data["canonical_hash"],
        response_diff=list(data["response_diff"]),
        response_verdict=dict(data.get("response_verdict") or {}),
        response_invariants=list(data.get("response_invariants") or []),
        # The generation is read with a default of zero, so a file written by an older version still loads.
        generation=int(data.get("generation", 0)),
    )


def _write_atomic(path: Path, text: str) -> None:
    """Writes a file with a temporary file and a rename, so a reader never sees half a file.

    Why: the reader of the store may read a file while the process writes it, and a file that is half written is a
    branch that cannot be served.
    """
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _restore(path: Path, kept: str | None) -> None:
    """Puts the content of a file back, or drops the file when there was none.

    Why it exists: the store writes the files of a branch one after the other, and a write that fails has to leave
    the branch exactly where it was, so the content of the files that were written is kept and put back.

    Why the file is read before it is written: a write that failed left the file as it was, and writing it again
    would fail the same way, so the restore would break a branch that was still whole. A file that cannot be read
    is a file that has to be written back.
    """
    try:
        changed = (path.read_text(encoding="utf-8") if path.exists() else None) != kept
    except (OSError, UnicodeDecodeError):
        changed = True
    if not changed:
        return
    if kept is None:
        path.unlink(missing_ok=True)
        return
    _write_atomic(path, kept)


class FileBranchStore:
    """The branch store over a directory of files.

    The layout of the store::

        <root>/<canonical session>/<storage token>/branch.json    the row of the branch
        <root>/<canonical session>/<storage token>/events.jsonl   the events of the branch, one per line
        <root>/<canonical session>/<storage token>/commands.jsonl the answers of the requests, one per line

    The folder of a branch is named after a storage token and not after the branch id, so the path of a file never
    carries the identity of the branch and the isolation never depends on the path. The row names the branch id and
    its owner, and the owner check is made on the row.

    Why the store holds one lock: the instance owns the files, and the write paths of a branch take the lock, so
    the check of the revision and the write of the row are one step and two writes that cross cannot both pass the
    check (ADR-026).
    """

    BRANCH_FILE = "branch.json"
    EVENTS_FILE = "events.jsonl"
    COMMANDS_FILE = "commands.jsonl"

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        # The lock of the writes of a branch. It belongs to the instance, because the instance owns the files.
        self._lock = threading.Lock()

    # -- the branches ------------------------------------------------------------------------------

    def create_branch(self, branch: SandboxBranchRow) -> SandboxBranchRow:
        """Stores the row of a branch that was forked.

        Why the row is written with a temporary file and a rename: a reader that finds a row that is half written
        cannot read the branch at all, and the row is the one file a reader always needs (ADR-025).
        """
        if self._find(branch.branch_id, branch.owner_session) is not None:
            raise ValueError(f"the branch {branch.branch_id} already exists")
        folder = self._new_folder(self._session_folder(branch.owner_session))
        _write_atomic(folder / self.BRANCH_FILE, canonical_json(_branch_to_dict(branch)))
        return branch

    def get_branch(self, branch_id: str, owner_session: str) -> SandboxBranchRow:
        return self._owned(branch_id, owner_session)[1]

    def list_branches(self, owner_session: str) -> list[SandboxBranchRow]:
        folder = self._session_folder(owner_session)
        if not folder.is_dir():
            return []
        rows = []
        for path in sorted(folder.glob(f"*/{self.BRANCH_FILE}")):
            rows.append(_branch_from_dict(_read_json(path)))
        return rows

    def save_branch(self, branch: SandboxBranchRow) -> SandboxBranchRow:
        """Stores the row of a branch of this session again.

        The branch is looked for inside the folder of its owner, so a branch of another visitor is never touched.

        Why the row is written with a temporary file and a rename: a reader that finds a row that is half written
        cannot read the branch at all, and the row is the one file a reader always needs (ADR-025).
        """
        for path in sorted(self._session_folder(branch.owner_session).glob(f"*/{self.BRANCH_FILE}")):
            row = _branch_from_dict(_read_json(path))
            if row.branch_id == branch.branch_id:
                _write_atomic(path, canonical_json(_branch_to_dict(branch)))
                return branch
        raise BranchNotFound()

    def touch_branch(
        self, branch_id: str, owner_session: str, last_activity_at: datetime, expires_at: datetime
    ) -> SandboxBranchRow:
        """Moves the deadline of the branch of this session and writes no other field of the row (ADR-027).

        Why the lock of the instance: the row that is read is the row that is written, so a mutation that landed
        between the read and the write is not rolled back by this write (ADR-026).

        Why the row of the owner is looked for and not the row of the branch: a branch of another visitor is not
        even on the path of the request, and the refusal is the generic one.
        """
        with self._lock:
            folder, row = self._owned(branch_id, owner_session)
            moved = replace(row, last_activity_at=last_activity_at, expires_at=expires_at)
            _write_atomic(folder / self.BRANCH_FILE, canonical_json(_branch_to_dict(moved)))
            return moved

    def delete_branch(self, branch_id: str, owner_session: str) -> bool:
        folder, _ = self._owned(branch_id, owner_session)
        shutil.rmtree(folder)
        return True

    def list_expired(self, now: datetime) -> list[SandboxBranchRow]:
        rows = []
        for path in sorted(self.root.glob(f"*/*/{self.BRANCH_FILE}")):
            row = _branch_from_dict(_read_json(path))
            if row.expires_at <= now:
                rows.append(row)
        return rows

    # -- the events --------------------------------------------------------------------------------

    def append_events(self, branch_id: str, owner_session: str, events: Sequence[SandboxEventRow]) -> AppendResult:
        folder, _ = self._owned(branch_id, owner_session)
        path = folder / self.EVENTS_FILE
        stored = self._read_events(path)
        known = {row.event_uid for row in stored}
        appended = duplicates = 0
        for event in events:
            if event.branch_id != branch_id:
                raise ValueError(f"the event {event.event_uid} does not belong to the branch {branch_id}")
            if event.event_uid in known:
                # The same event twice is a duplicate and not an error, exactly like the event store of the simulator.
                duplicates += 1
                continue
            known.add(event.event_uid)
            stored.append(event)
            appended += 1
        if appended or path.exists():
            path.write_text(
                "".join(canonical_json(_event_to_dict(row)) + "\n" for row in stored),
                encoding="utf-8",
            )
        return AppendResult(appended, duplicates)

    def read_events(self, branch_id: str, owner_session: str) -> list[SandboxEventRow]:
        folder, _ = self._owned(branch_id, owner_session)
        return self._read_events(folder / self.EVENTS_FILE)

    def delete_events(self, branch_id: str, owner_session: str) -> int:
        folder, _ = self._owned(branch_id, owner_session)
        path = folder / self.EVENTS_FILE
        count = len(self._read_events(path))
        path.unlink(missing_ok=True)
        return count

    # -- the commit and the answers of the requests ---------------------------------------------------

    def commit_events(
        self,
        branch_id: str,
        owner_session: str,
        events: Sequence[SandboxEventRow],
        branch: SandboxBranchRow,
        answer: SandboxCommandRow,
    ) -> AppendResult:
        """Appends the events, moves the row of the branch and remembers the answer, together.

        Why the row is written last: a reader that finds a row that is older than the events refuses the branch
        instead of serving it half applied. The three files are written with a temporary file and a rename, so a
        reader never sees half a file either.

        Why the content of the two files is kept: a write that fails leaves the branch exactly where it was, in
        this store and in the database one, so the two implementations of the protocol lose the same thing when a
        commit fails, which is nothing (FR-040). The three writes are inside one block, because the branch is
        broken by the first of them that fails and the other two have to go back with it.

        Why the lock of the store: the check of the revision and the write of the row are one step, so the loser of
        two commits that cross is refused with `BranchRevisionConflict` and writes nothing (ADR-026).
        """
        with self._lock:
            folder, current = self._owned(branch_id, owner_session)
            if current.revision != branch.revision - 1:
                raise BranchRevisionConflict(
                    f"the branch {branch_id} is at revision {current.revision}, and the request expected"
                    f" {branch.revision - 1}"
                )
            events_path = folder / self.EVENTS_FILE
            commands_path = folder / self.COMMANDS_FILE
            kept_events = events_path.read_text(encoding="utf-8") if events_path.exists() else None
            kept_commands = commands_path.read_text(encoding="utf-8") if commands_path.exists() else None
            stored = self._read_events(events_path)
            known = {row.event_uid for row in stored}
            appended = duplicates = 0
            for event in events:
                if event.branch_id != branch_id:
                    raise ValueError(f"the event {event.event_uid} does not belong to the branch {branch_id}")
                if event.event_uid in known:
                    # The same event twice is a duplicate and not an error, exactly like the event store of the
                    # simulator.
                    duplicates += 1
                    continue
                known.add(event.event_uid)
                stored.append(event)
                appended += 1
            commands = self._read_commands(commands_path)
            new_answer = not any(row.idempotency_key == answer.idempotency_key for row in commands)
            if new_answer:
                commands.append(answer)
            try:
                if appended or events_path.exists():
                    _write_atomic(
                        events_path, "".join(canonical_json(_event_to_dict(row)) + "\n" for row in stored)
                    )
                if new_answer:
                    _write_atomic(
                        commands_path, "".join(canonical_json(_command_to_dict(row)) + "\n" for row in commands)
                    )
                _write_atomic(folder / self.BRANCH_FILE, canonical_json(_branch_to_dict(branch)))
            except Exception:
                # The commit did not happen, so the events and the answers go back where they were (FR-040).
                _restore(events_path, kept_events)
                _restore(commands_path, kept_commands)
                raise
            return AppendResult(appended, duplicates)

    def command_answer(self, branch_id: str, owner_session: str, idempotency_key: str) -> SandboxCommandRow | None:
        """The answer already given to the request with this key, or None when there is none."""
        folder, _ = self._owned(branch_id, owner_session)
        for row in self._read_commands(folder / self.COMMANDS_FILE):
            if row.idempotency_key == idempotency_key:
                return row
        return None

    def commit_undo(
        self,
        branch_id: str,
        owner_session: str,
        event: SandboxEventRow,
        branch: SandboxBranchRow,
        answer: SandboxCommandRow,
    ) -> SandboxBranchRow:
        """Appends the marker of the undo, moves the row of the branch back and remembers the answer, together.

        Why the row is written last: a reader that finds a row that is older than the events refuses the branch
        instead of serving it half applied. The three files are written with a temporary file and a rename, so a
        reader never sees half a file either.

        Why the content of the two files is kept: a write that fails leaves the branch exactly where it was, in
        this store and in the database one, so the two implementations of the protocol lose the same thing when an
        undo fails, which is nothing (ADR-024, FR-040). The three writes are inside one block, because the branch
        is broken by the first of them that fails and the other two have to go back with it.

        Why the lock of the store: the check of the revision and the write of the row are one step, so the loser of
        two undos that cross is refused with `BranchRevisionConflict` and writes nothing (ADR-026).
        """
        with self._lock:
            folder, current = self._owned(branch_id, owner_session)
            if current.revision != branch.revision + 1:
                # The undo moves the branch back by one revision, so the row it hands over has to follow the branch.
                raise BranchRevisionConflict(
                    f"the branch {branch_id} is at revision {current.revision}, and the request expected"
                    f" {branch.revision + 1}"
                )
            if event.branch_id != branch_id:
                raise ValueError(f"the event {event.event_uid} does not belong to the branch {branch_id}")
            events_path = folder / self.EVENTS_FILE
            commands_path = folder / self.COMMANDS_FILE
            kept_events = events_path.read_text(encoding="utf-8") if events_path.exists() else None
            kept_commands = commands_path.read_text(encoding="utf-8") if commands_path.exists() else None
            stored = self._read_events(events_path)
            if event.event_uid not in {row.event_uid for row in stored}:
                stored.append(event)
            commands = self._read_commands(commands_path)
            new_answer = not any(row.idempotency_key == answer.idempotency_key for row in commands)
            if new_answer:
                commands.append(answer)
            try:
                _write_atomic(events_path, "".join(canonical_json(_event_to_dict(row)) + "\n" for row in stored))
                if new_answer:
                    _write_atomic(
                        commands_path, "".join(canonical_json(_command_to_dict(row)) + "\n" for row in commands)
                    )
                _write_atomic(folder / self.BRANCH_FILE, canonical_json(_branch_to_dict(branch)))
            except Exception:
                # The undo did not happen, so the marker and the answer go back where they were (ADR-024).
                _restore(events_path, kept_events)
                _restore(commands_path, kept_commands)
                raise
            return branch

    def list_commands(self, branch_id: str, owner_session: str) -> list[SandboxCommandRow]:
        """Every answer the branch remembers, in the order the requests were committed."""
        folder, _ = self._owned(branch_id, owner_session)
        return self._read_commands(folder / self.COMMANDS_FILE)

    def reset_branch(self, branch_id: str, owner_session: str, branch: SandboxBranchRow) -> SandboxBranchRow:
        """Drops every event of the branch, writes the row of it, and returns the row it wrote.

        Why the store moves the generation: the generation is what marks the answers of the past as stale, and the
        store is the place where the row of the branch is read and written. The store reads the generation it finds
        in the row on the disk and writes one more, so the caller never computes the number itself (ADR-022).

        Why the file of the events is emptied first: a failure in between leaves a branch whose row does not agree
        with its events, and such a branch is detected and refused by the verification of the read instead of being
        served (ADR-021). The row is written with a temporary file and a rename, so a reader never sees half a file.

        Why the content of the file of the events is kept: a reset that did not happen leaves the branch exactly where
        it was, in this store and in the database one, so the two implementations of the protocol lose the same thing
        when a reset fails, which is nothing (ADR-022, FR-040). The content is put back when the write of the row
        fails, and the failure travels to the caller.

        Why the lock of the store: the drop of the events and the write of the row are one step, so the generation
        the store writes is the one it found plus one and two resets that cross cannot write the same number twice
        (ADR-026).
        """
        with self._lock:
            folder, current = self._owned(branch_id, owner_session)
            moved = replace(branch, generation=current.generation + 1)
            events_path = folder / self.EVENTS_FILE
            # The content of the events is kept before it is dropped, so a reset that did not happen puts it back
            # (ADR-022, ADR-025).
            kept = events_path.read_text(encoding="utf-8") if events_path.exists() else None
            _write_atomic(events_path, "")
            try:
                _write_atomic(folder / self.BRANCH_FILE, canonical_json(_branch_to_dict(moved)))
            except Exception:
                # The reset did not happen, so the events of the branch go back where they were (ADR-022).
                _restore(events_path, kept)
                raise
            return moved

    # -- the maintenance ---------------------------------------------------------------------------

    def truncate(self) -> None:
        """Drops every branch of the store, the way the database store drops every row of its tables.

        Why it exists: the two implementations of the protocol offer the same maintenance operations, so a test that
        empties the store before it starts does the same thing on both (ADR-022).
        """
        for path in sorted(self.root.glob("*")):
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

    def close(self) -> None:
        """Closes the store. The file backed store holds nothing open, so there is nothing to close.

        Why it exists: the two implementations of the protocol offer the same maintenance operations, and the suite
        closes what it opens (ADR-022).
        """
        return None

    # -- the internals -----------------------------------------------------------------------------

    def _session_folder(self, owner_session: str) -> Path:
        return self.root / _safe_name(owner_session)

    def _new_folder_name(self) -> str:
        """The name of the folder of a branch: a storage token, never the branch id."""
        return secrets.token_hex(12)

    def _new_folder(self, session_folder: Path) -> Path:
        """The folder of a new branch, with a name that is not taken yet."""
        for _ in range(8):
            folder = session_folder / self._new_folder_name()
            try:
                folder.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                continue
            return folder
        raise RuntimeError("could not allocate a folder for the branch")

    def _find(self, branch_id: str, owner_session: str) -> tuple[Path, SandboxBranchRow] | None:
        """The folder and the row of the branch, inside the folder of its owner.

        Why the folder of the owner and not the whole store: a read of a branch must not open the file of another
        visitor. The branch of another session is not even on the path of the request.
        """
        folder = self._session_folder(owner_session)
        if not folder.is_dir():
            return None
        for path in sorted(folder.glob(f"*/{self.BRANCH_FILE}")):
            row = _branch_from_dict(_read_json(path))
            if row.branch_id == branch_id:
                return path.parent, row
        return None

    def _owned(self, branch_id: str, owner_session: str) -> tuple[Path, SandboxBranchRow]:
        """The folder and the row of the branch, when it belongs to this session.

        Why the same error for a missing branch and for the branch of another visitor: the caller must not be able to
        tell one from the other.
        """
        found = self._find(branch_id, owner_session)
        if found is None:
            raise BranchNotFound()
        folder, row = found
        if row.owner_session != owner_session:
            raise BranchNotFound()
        return folder, row

    def _read_events(self, path: Path) -> list[SandboxEventRow]:
        if not path.exists():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(_event_from_dict(json.loads(line)))
        return rows

    def _read_commands(self, path: Path) -> list[SandboxCommandRow]:
        if not path.exists():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(_command_from_dict(json.loads(line)))
        return rows


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


__all__ = [
    "BranchNotFound",
    "BranchRevisionConflict",
    "BranchStore",
    "FileBranchStore",
    "GENERIC_NOT_FOUND",
    "SandboxBranchRow",
    "SandboxCommandRow",
    "SandboxEventRow",
]
