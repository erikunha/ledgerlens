"""The typed mutation of a branch: the command, the catalog, the rules of the payload and the money helpers.

Why it exists: a visitor of the sandbox edits one field of one record, and the sandbox has to answer three
questions about that edit before anything is written: is the command one the sandbox knows, does it obey the rules
of the domain, and what would it change. This module owns the command and those answers.

The rule that rules above all: no number of this path is a float. Every amount is an integer of minor units or a
`Decimal`, and the conversion between a rate and an amount is the one of the simulator, in `ledgerlens/sim/gaps.py`,
so the sandbox and the published ledger agree on the arithmetic (FR-017).

The catalog is the promise of the sandbox: a kind is enabled only when it has a round trip test and a coherent
domain event (ADR-021). Five kinds are enabled: the adjustment of the rate of a refund, the duplicate of a
payment, the deadline of a chargeback, the outage of the FX tool of the branch and the untrusted note of a record
of the branch. The last two kinds change the state of the branch and not the rows of the ledger, and the state of a
branch is a derived state that the hash of the branch covers (ADR-032).

The undo is not a kind of the catalog: it does not change a record of the case, it changes the log of the branch,
and it is an event of the vocabulary of the sandbox in its own right (ADR-024). This module owns the plan of the
undo: the marker it appends, the revision the branch goes back to, the hash of the state it returns to, the diff
between the two states, the invariants of the new state and the verdict of the case over it.

The shape of a payload is checked against the published command schema with `jsonschema`, the same way the export
checks the events it publishes. The one field the published schema does not declare is the optional `currency` of
the data: it is an assertion of the visitor about the record, and the domain checks it against the record before
the shape is checked, so a currency that does not match is refused with its own code and not with the code of a
shape.

The money helpers live here and not in the projector, because the projector writes the values of the rows and needs
them: `ledgerlens/sandbox/projector.py` imports them inside the function that formats a value, so that the two
modules do not import each other at the top.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Any

from ledgerlens.sandbox.invariants import evaluate
from ledgerlens.sandbox.projector import (
    EVENT_BRANCH_UNDONE,
    EVENT_CHARGEBACK_DEADLINE_CHANGED,
    EVENT_PAYMENT_DUPLICATED,
    EVENT_RECORD_NOTE_INJECTED,
    EVENT_REFUND_FX_ADJUSTED,
    EVENT_TOOL_FX_OUTAGE,
    SANDBOX_ORIGIN,
    TOOL_FX,
    UNDO_COMMAND_ID,
    UNDO_EVENT_UID,
    ProjectedState,
    Verdict,
    canonical_rate,
    diff_of,
    holds_the_record,
    is_undo_marker,
    next_transaction_id,
    oldest_moment,
    project,
    table_of_the_record,
    undo_marks,
    verdict_of,
)
from ledgerlens.sandbox.snapshot import BaseSnapshot
from ledgerlens.sandbox.store import SandboxEventRow
from ledgerlens.sim.events import canonical_json

# The published schema of the command. The shape of a payload is checked against it and against nothing else.
COMMAND_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "design" / "contracts" / "schemas" / "scenario-mutation.schema.json"
)

# The codes of the refusals. Each rule of the domain has its own, and the reason names the rule that failed.
CODE_UNKNOWN_MUTATION_TYPE = "UNKNOWN_MUTATION_TYPE"
CODE_READ_ONLY_FIELD = "READ_ONLY_FIELD"
CODE_INVALID_AMOUNT = "INVALID_AMOUNT"
CODE_CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
CODE_INVALID_EFFECTIVE_DATE = "INVALID_EFFECTIVE_DATE"
CODE_INVARIANT_VIOLATION = "INVARIANT_VIOLATION"
CODE_REVISION_CONFLICT = "REVISION_CONFLICT"
CODE_IDEMPOTENCY_MISMATCH = "IDEMPOTENCY_MISMATCH"
CODE_UNKNOWN_RECORD = "UNKNOWN_RECORD"
CODE_INVALID_PAYLOAD = "INVALID_PAYLOAD"
CODE_INVALID_REQUEST = "INVALID_REQUEST"
# The state of a record does not allow the change the visitor asks for. The record exists and the payload has the
# shape of the published schema, so what does not hold is the state of the record and not the shape of the payload.
# The status of the answer is the default one of the rules of the payload, 422 (ADR-031).
CODE_INVALID_STATE = "INVALID_STATE"
CODE_PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
CODE_NOTE_TOO_LONG = "NOTE_TOO_LONG"
CODE_RESOURCE_LIMIT = "RESOURCE_LIMIT_EXCEEDED"
CODE_HASH_MISMATCH = "HASH_MISMATCH"
CODE_NOTHING_TO_UNDO = "NOTHING_TO_UNDO"
# The check of the shape of a command needs the library that the api extra installs, and a deployment without it
# cannot serve a mutation. The refusal is a problem of the deployment and not a bad payload of the visitor, so it
# has its own code and its own status (ADR-035).
CODE_CONTRACT_UNAVAILABLE = "CONTRACT_UNAVAILABLE"

# The status of the answer of a refusal. Everything that is not listed here is a rule of the payload.
STATUS_BY_CODE = {
    CODE_REVISION_CONFLICT: 409,
    CODE_IDEMPOTENCY_MISMATCH: 409,
    CODE_HASH_MISMATCH: 409,
    CODE_NOTHING_TO_UNDO: 409,
    CODE_PAYLOAD_TOO_LARGE: 413,
    CODE_RESOURCE_LIMIT: 429,
    CODE_CONTRACT_UNAVAILABLE: 503,
}

# The size of a payload and the length of a note, the limits of the resources of a branch (FR-025).
MAX_PAYLOAD_BYTES = 32 * 1024
MAX_NOTE_LENGTH = 300

# The kind of the command of an undo. It is not a kind of the catalog: the undo does not change a record of the
# case, it changes the log of the branch, and the catalog holds the kinds that change a record (ADR-021, ADR-024).
UNDO_KIND = "branch.undo"

# The fields of the domain the visitor may not set. They belong to the branch and to the event log, and a visitor
# that sends one of them wants to change something the sandbox owns (FR-029).
READ_ONLY_FIELDS = frozenset(
    {
        "aggregate_id",
        "amount_minor",
        "base_canonical_hash",
        "base_snapshot_id",
        "branch_id",
        "branch_owner",
        "canonical_hash",
        "command_id",
        "event_id",
        "event_type",
        "event_uid",
        "expected_revision",
        "idempotency_key",
        "occurred_at",
        "origin",
        "owner_session",
        "payout_amount_minor",
        "requested_amount_minor",
        "revision",
        "session_id",
        "snapshot_sha256",
        "state",
        "status",
    }
)

# The currencies without a minor unit. The list is the one of the simulator, in `ledgerlens/sim/gaps.py`, and it
# is repeated here because that helper is private to its module.
ZERO_EXPONENT_CURRENCIES = frozenset({"JPY", "KRW", "CLP", "ISK", "VND"})

# The accepted shape of a rate: a decimal text with at most eight decimals, the precision of the published schema.
RATE_TEXT = re.compile(r"^[0-9]+(?:\.[0-9]{1,8})?$")
# The rate of the client clock that is accepted: the server clock is the authority, and a client that is a little
# ahead is tolerated, a client that is ahead by a day is not.
EFFECTIVE_DATE_TOLERANCE = timedelta(minutes=5)

# The optional assertion of the visitor about the currency of the record. The published schema does not declare
# it, and the domain checks it against the record before the shape of the payload is checked.
CURRENCY_ASSERTION = "currency"


@dataclass(frozen=True)
class MutationKind:
    """One kind of the catalog: the name the visitor sends, and whether the sandbox can do it."""

    name: str
    enabled: bool
    description: str


@dataclass(frozen=True)
class MutationCommand:
    """A typed command of the visitor: the kind, the payload and the two names of the request.

    `expected_revision` is the revision the visitor believes the branch is at, and `idempotency_key` names the
    request, so that the same request sent twice is answered the same way.
    """

    kind: str
    payload: dict[str, Any]
    reason: str | None = None
    expected_revision: int | None = None
    idempotency_key: str | None = None


@dataclass(frozen=True)
class MoneyValue:
    """An amount as the interface reads it: a decimal text and the currency it is in."""

    value: str
    currency: str

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "currency": self.currency}


@dataclass(frozen=True)
class MutationPreview:
    """The answer of the preview: what the command would do, and nothing that happened.

    The revision and the canonical hash of the branch are the ones the branch has, and the projected hash is the
    one it would have. The visitor sees both, so the consequence of the edit is clear before it is applied.
    """

    valid: bool
    kind: str
    revision: int
    current_canonical_hash: str
    projected_canonical_hash: str
    before: MoneyValue
    after: MoneyValue
    records: tuple[dict[str, Any], ...]
    diff: tuple[dict[str, Any], ...]
    invariants: tuple[dict[str, Any], ...]
    verdict: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "kind": self.kind,
            "revision": self.revision,
            "current_canonical_hash": self.current_canonical_hash,
            "projected_canonical_hash": self.projected_canonical_hash,
            "before": self.before.to_dict(),
            "after": self.after.to_dict(),
            "records": list(self.records),
            "diff": list(self.diff),
            "invariants": list(self.invariants),
            "verdict": dict(self.verdict),
        }


@dataclass(frozen=True)
class MutationPlan:
    """Everything a command would do, computed in memory and not written yet.

    The plan holds the events the commit would append, the state they would produce and everything the visitor
    is told about it. A preview is a plan without the write, and a commit is a plan with it.
    """

    kind: str
    command_id: str
    events: tuple[SandboxEventRow, ...]
    revision: int
    canonical_hash: str
    diff: tuple[dict[str, Any], ...]
    invariants: tuple[dict[str, Any], ...]
    verdict: Verdict
    before: MoneyValue
    after: MoneyValue
    valid: bool

    def to_preview(self, current_canonical_hash: str) -> MutationPreview:
        """The answer of the preview: what would happen, and nothing that happened."""
        return MutationPreview(
            valid=self.valid,
            kind=self.kind,
            revision=self.revision - 1,
            current_canonical_hash=current_canonical_hash,
            projected_canonical_hash=self.canonical_hash,
            before=self.before,
            after=self.after,
            records=self.diff,
            diff=self.diff,
            invariants=self.invariants,
            verdict=self.verdict.to_dict(),
        )

    def to_result(self) -> MutationResult:
        """The answer of the commit: the new revision, the new canonical hash and the diff."""
        return MutationResult(
            command_id=self.command_id,
            kind=self.kind,
            revision=self.revision,
            canonical_hash=self.canonical_hash,
            diff=self.diff,
            invariants=self.invariants,
            verdict=self.verdict.to_dict(),
            replayed=False,
        )


@dataclass(frozen=True)
class MutationResult:
    """The answer of a commit: the new revision, the new canonical hash and the diff of the mutation.

    `stale` says that the answer was produced in a generation of the branch that a reset has closed, and
    `stale_against` is the base canonical hash of the branch, the hash of the original snapshot the answer was
    computed against. The answer of the past is answered with the mark, so that it is never presented as the current
    result of the branch (FR-022, ADR-022).

    `undone` says that the mutation this answer describes was undone afterwards. It is true for the answer of a
    mutation that was undone and false for the answer of an undo, because an undo can never be undone: the undo only
    takes back a mutation, and a marker of the log is not a mutation. `undone_event_uid` says which event the request
    that this answer describes undid, and it is filled only for the answer of an undo. The two marks never overlap, and
    they are derived from the log of the branch, so they cannot drift away from the truth (ADR-024).
    """

    command_id: str
    kind: str
    revision: int
    canonical_hash: str
    diff: tuple[dict[str, Any], ...]
    invariants: tuple[dict[str, Any], ...]
    verdict: dict[str, Any]
    replayed: bool = False
    stale: bool = False
    stale_against: str | None = None
    undone: bool = False
    undone_event_uid: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "command_id": self.command_id,
            "kind": self.kind,
            "revision": self.revision,
            "canonical_hash": self.canonical_hash,
            "diff": list(self.diff),
            "invariants": list(self.invariants),
            "verdict": dict(self.verdict),
            "replayed": self.replayed,
            "stale": self.stale,
            "stale_against": self.stale_against,
            "undone": self.undone,
            "undone_event_uid": self.undone_event_uid,
        }


@dataclass(frozen=True)
class UndoPlan:
    """What an undo would do to the branch, computed in memory and written nowhere.

    The plan holds the marker the undo appends, the revision the branch goes back to, the canonical hash of the
    state the branch returns to, the diff between the state before the undo and the state after it, the invariants
    of the new state and the verdict of the case over it (ADR-024).
    """

    kind: str
    command_id: str
    event: SandboxEventRow
    revision: int
    canonical_hash: str
    diff: tuple[dict[str, Any], ...]
    invariants: tuple[dict[str, Any], ...]
    verdict: Verdict
    undone_event_uid: str
    undone_command_id: str
    valid: bool

    def to_result(self) -> MutationResult:
        """The answer of the undo: the revision and the hash of the state the branch returns to."""
        return MutationResult(
            command_id=self.command_id,
            kind=self.kind,
            revision=self.revision,
            canonical_hash=self.canonical_hash,
            diff=self.diff,
            invariants=self.invariants,
            verdict=self.verdict.to_dict(),
            replayed=False,
            # The answer of the undo names the event it undid, and it is not an undone mutation: an undo can never be
            # undone, because the undo only takes back a mutation and a marker of the log is not a mutation (ADR-024).
            undone=False,
            undone_event_uid=self.undone_event_uid,
        )


class MutationRejected(Exception):
    """The sandbox refuses the command, and the reason names the rule that failed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ValidatedCommand:
    """A command that passed every rule, with the values the interpreter needs.

    Every kind carries what its own interpreter needs and nothing more: the rate and the moment of the adjustment, the
    elapsed seconds of the duplicate, the new deadline of the chargeback, the state of the FX tool and the text of
    the untrusted note. A field that the kind does not use is None, so the interpreter of a kind never reads a value
    that belongs to another one (ADR-031).
    """

    kind: str
    record_id: str
    rate: Decimal | None = None
    effective_at: str | None = None
    elapsed_seconds: int | None = None
    new_deadline: str | None = None
    enabled: bool | None = None
    error_code: str | None = None
    text: str | None = None
    record_table: str | None = None


# The names of the kinds of the catalog that the sandbox can do.
KIND_FX_ADJUSTMENT = "refund.apply_fx_adjustment"
KIND_DUPLICATE = "payment.simulate_duplicate"
KIND_DEADLINE = "chargeback.change_deadline"
KIND_FX_OUTAGE = "tool.fx_outage"
KIND_NOTE = "record.inject_untrusted_note"

# The stages of a chargeback that close the case. A case that was won or lost has no deadline to move (ADR-031).
CLOSED_CHARGEBACK_STAGES = frozenset({"won", "lost"})

# The status of a transaction that failed. A payment that failed is not charged twice (ADR-031).
FAILED_TRANSACTION_STATUS = "failed"

# The catalog of the sandbox. Only the kinds with a round trip test are enabled (ADR-021, ADR-031, ADR-032).
CATALOG: tuple[MutationKind, ...] = (
    MutationKind(
        KIND_FX_ADJUSTMENT,
        True,
        "the FX rate applied to the payout of a refund",
    ),
    MutationKind(KIND_DUPLICATE, True, "a second charge of the same payment"),
    MutationKind(KIND_DEADLINE, True, "the deadline of a chargeback"),
    MutationKind(KIND_FX_OUTAGE, True, "the FX tool is unavailable"),
    MutationKind(KIND_NOTE, True, "an untrusted note on a record"),
)
ENABLED_KINDS: tuple[str, ...] = tuple(kind.name for kind in CATALOG if kind.enabled)


# --- the money helpers ---------------------------------------------------------------------------------------


def currency_exponent(currency: str) -> int:
    """The number of decimals of a currency: two, except for the currencies without a minor unit."""
    return 0 if currency.upper() in ZERO_EXPONENT_CURRENCIES else 2


def format_minor(amount_minor: int, currency: str) -> str:
    """The amount as a decimal text in major units, the way the ledger writes it.

    Why the text and never a float: a float carries a rounding error that a money value must not have.
    """
    exponent = currency_exponent(currency)
    amount = (Decimal(amount_minor) / (Decimal(10) ** exponent)).quantize(
        Decimal(1).scaleb(-exponent), ROUND_HALF_EVEN
    )
    return format(amount, "f")


def parse_rate(value: str) -> Decimal:
    """The rate of a command, as a `Decimal`, when the text has the accepted shape.

    The accepted shape is the one of the published schema: a decimal text with at most eight decimals.
    """
    text = value.strip() if isinstance(value, str) else ""
    if not RATE_TEXT.match(text):
        raise ValueError(f"not a rate with at most eight decimals: {value!r}")
    return Decimal(text)


# --- the rules of the payload ---------------------------------------------------------------------------------


def status_for_code(code: str) -> int:
    """The status of the answer of a refusal: a conflict of the state, or a rule of the payload."""
    return STATUS_BY_CODE.get(code, 422)


def validate_size(command: MutationCommand) -> None:
    """The size of the command: the payload is not too big and the note is not too long.

    Why the check comes before the rules of the domain: a payload that is too big is refused before anything is
    read out of it, and the branch never spends its resources on a request it will refuse (FR-025).
    """
    body = canonical_json({"kind": command.kind, "data": command.payload, "reason": command.reason})
    size = len(body.encode("utf-8"))
    if size > MAX_PAYLOAD_BYTES:
        raise MutationRejected(
            CODE_PAYLOAD_TOO_LARGE,
            f"the payload of the command is {size} bytes, and the limit is {MAX_PAYLOAD_BYTES} bytes",
        )
    if command.reason is not None and len(command.reason) > MAX_NOTE_LENGTH:
        raise MutationRejected(
            CODE_NOTE_TOO_LONG,
            f"the note of the command is {len(command.reason)} characters, and the limit is {MAX_NOTE_LENGTH}",
        )


def read_only_field_in(fields: Any) -> str | None:
    """The name of the first read only field among the given names, or None."""
    for field in fields:
        if field in READ_ONLY_FIELDS:
            return str(field)
    return None


def validate_command(command: MutationCommand, state: ProjectedState, now: datetime) -> ValidatedCommand:
    """Checks a command against the catalog, the rules of the domain and the published schema.

    Why the order: the catalog first, because the shape of a payload is read with the rules of its kind. Then the
    read only fields, so a visitor that sends one of them is told which one it is. Then the rules of the domain,
    each with its own code. Then the shape of the payload against the published schema, which reports what is
    missing or what does not belong.
    """
    kind = _kind_of(command.kind)
    validate_size(command)
    _no_read_only_field(command.payload)
    validated = _validate_of_the_kind(kind, command, state, now)
    _validate_shape(command)
    return validated


def _kind_of(name: str) -> MutationKind:
    """The kind of the catalog, when the sandbox can do it.

    Why a kind that is not enabled is refused like a kind that does not exist: the catalog is the promise of the
    sandbox, and a kind the sandbox cannot do is not a kind the visitor may send.
    """
    for kind in CATALOG:
        if kind.name == name and kind.enabled:
            return kind
    accepted = ", ".join(ENABLED_KINDS)
    raise MutationRejected(
        CODE_UNKNOWN_MUTATION_TYPE,
        f"the mutation kind {name!r} is not in the catalog of the sandbox; the accepted kinds are: {accepted}",
    )


def _no_read_only_field(payload: dict[str, Any]) -> None:
    """Refuses a payload that carries a field of the domain the visitor may not set."""
    field = read_only_field_in(payload)
    if field is not None:
        raise MutationRejected(
            CODE_READ_ONLY_FIELD,
            f"the field {field!r} is a read only field; the visitor may not change it",
        )


def _validate_of_the_kind(
    kind: MutationKind, command: MutationCommand, state: ProjectedState, now: datetime
) -> ValidatedCommand:
    """The rules of the domain of the kind of the command.

    Why the dispatch is here: every kind has its own rules, and a rule that belongs to one kind must never refuse a
    command of another one. The kind that is enabled and has no rules yet is refused, because the catalog grows with
    a round trip test and a kind without one is refused rather than half done (ADR-021, ADR-031).
    """
    if kind.name == KIND_FX_ADJUSTMENT:
        return _validate_fx_adjustment(kind, command, state, now)
    if kind.name == KIND_DUPLICATE:
        return _validate_duplicate(kind, command, state)
    if kind.name == KIND_DEADLINE:
        return _validate_deadline(kind, command, state)
    if kind.name == KIND_FX_OUTAGE:
        return _validate_fx_outage(kind, command, state)
    if kind.name == KIND_NOTE:
        return _validate_note(kind, command, state)
    raise MutationRejected(
        CODE_UNKNOWN_MUTATION_TYPE,
        f"the mutation kind {kind.name!r} is not enabled; the accepted kinds are: {', '.join(ENABLED_KINDS)}",
    )


def _validate_fx_adjustment(
    kind: MutationKind, command: MutationCommand, state: ProjectedState, now: datetime
) -> ValidatedCommand:
    """The rules of the adjustment of the rate of a refund."""
    payload = command.payload
    refund_id = payload.get("refund_id")
    record = None
    if isinstance(refund_id, str) and refund_id:
        record = state.row("refunds", refund_id)
        if record is None:
            raise MutationRejected(
                CODE_UNKNOWN_RECORD,
                f"the refund {refund_id} is not in the branch; the branch holds no such record",
            )
    rate = None
    if "applied_rate" in payload:
        try:
            rate = parse_rate(payload["applied_rate"])
        except ValueError:
            raise MutationRejected(
                CODE_INVALID_AMOUNT,
                "the applied rate is not a decimal number with at most eight decimals",
            ) from None
    if record is not None:
        _assert_currency_of_the_record(payload, str(record.get("payout_currency")))
    effective_at = None
    if "effective_at" in payload:
        effective_at = _validate_effective_date(payload["effective_at"], state, now)
    if record is None or rate is None or effective_at is None:
        # A field is missing or has the wrong shape: the check of the published schema names it.
        return ValidatedCommand(kind=kind.name, record_id=str(refund_id or ""))
    return ValidatedCommand(kind=kind.name, record_id=str(refund_id), rate=rate, effective_at=effective_at)


def _assert_currency_of_the_record(payload: dict[str, Any], expected: str) -> None:
    """Refuses the assertion of the visitor about the currency when it does not match the record.

    Why the check is here and not in the shape of the payload: the published schema does not declare the assertion, and
    a currency that does not match the record is refused with its own code and not with the code of a shape
    (ADR-021, ADR-031).
    """
    if CURRENCY_ASSERTION not in payload:
        return
    sent = payload[CURRENCY_ASSERTION]
    if sent != expected:
        raise MutationRejected(
            CODE_CURRENCY_MISMATCH,
            f"the currency {sent!r} does not match the currency of the record, which is {expected}",
        )


def _validate_duplicate(
    kind: MutationKind, command: MutationCommand, state: ProjectedState
) -> ValidatedCommand:
    """The rules of the duplicate of a payment.

    The record the command names has to be in the branch, a payment that failed is not charged twice, and the branch
    has to hold a free identifier for the copy (ADR-031).
    """
    payload = command.payload
    transaction_id = payload.get("transaction_id")
    if not isinstance(transaction_id, str) or not transaction_id:
        # The identifier is missing or is not a text: the check of the published schema names it.
        return ValidatedCommand(kind=kind.name, record_id="")
    record = state.row("transactions", transaction_id)
    if record is None:
        raise MutationRejected(
            CODE_UNKNOWN_RECORD,
            f"the transaction {transaction_id} is not in the branch; the branch holds no such record",
        )
    # The assertion of the visitor is checked as soon as the record is known: it names the record the visitor means,
    # and the rules below would be judged against a record it did not name.
    _assert_currency_of_the_record(payload, str(record.get("currency")))
    if str(record.get("status")) == FAILED_TRANSACTION_STATUS:
        raise MutationRejected(
            CODE_INVALID_STATE,
            f"the transaction {transaction_id} failed, and a payment that failed is not charged twice",
        )
    elapsed = payload.get("elapsed_seconds")
    if isinstance(elapsed, bool) or not isinstance(elapsed, int):
        # The elapsed seconds are missing or are not a whole number of seconds: the schema names it.
        return ValidatedCommand(kind=kind.name, record_id=transaction_id)
    taken = {str(row.get("id")) for row in state.rows.get("transactions", [])}
    if next_transaction_id(taken, transaction_id) is None:
        raise MutationRejected(
            CODE_RESOURCE_LIMIT,
            f"the branch holds no free identifier for the duplicate of {transaction_id}",
        )
    return ValidatedCommand(kind=kind.name, record_id=transaction_id, elapsed_seconds=elapsed)


def _validate_deadline(
    kind: MutationKind, command: MutationCommand, state: ProjectedState
) -> ValidatedCommand:
    """The rules of the change of the deadline of a chargeback.

    The record the command names has to be in the branch, a chargeback that was won or lost is a closed case, and the
    new deadline has to be a day of the calendar (ADR-031).
    """
    payload = command.payload
    chargeback_id = payload.get("chargeback_id")
    if not isinstance(chargeback_id, str) or not chargeback_id:
        # The identifier is missing or is not a text: the check of the published schema names it.
        return ValidatedCommand(kind=kind.name, record_id="")
    record = state.row("chargebacks", chargeback_id)
    if record is None:
        raise MutationRejected(
            CODE_UNKNOWN_RECORD,
            f"the chargeback {chargeback_id} is not in the branch; the branch holds no such record",
        )
    # The assertion of the visitor is checked as soon as the record is known: it names the record the visitor means,
    # and the rules below would be judged against a record it did not name.
    _assert_currency_of_the_record(payload, str(record.get("currency")))
    stage = str(record.get("stage"))
    if stage in CLOSED_CHARGEBACK_STAGES:
        raise MutationRejected(
            CODE_INVALID_STATE,
            f"the chargeback {chargeback_id} was {stage}, and a closed case has no deadline to move",
        )
    deadline = payload.get("new_deadline")
    if not isinstance(deadline, str) or not deadline:
        # The deadline is missing: the check of the published schema names it.
        return ValidatedCommand(kind=kind.name, record_id=chargeback_id)
    if not _is_a_day(deadline):
        raise MutationRejected(
            CODE_INVALID_PAYLOAD,
            "the new deadline is not a day of the calendar, in the shape YYYY-MM-DD",
        )
    return ValidatedCommand(kind=kind.name, record_id=chargeback_id, new_deadline=deadline)


def _validate_fx_outage(kind: MutationKind, command: MutationCommand, state: ProjectedState) -> ValidatedCommand:
    """The rules of the outage of the FX tool of the branch.

    The rule of the state: a command that changes nothing is refused, because the hash of a branch only moves when
    its state moves, and a commit that moved the revision without moving the hash would break that promise for the
    visitor. So an outage that is already on is refused, and so is the end of an outage that does not exist
    (ADR-032).
    """
    payload = command.payload
    enabled = payload.get("enabled")
    if not isinstance(enabled, bool):
        # The flag is missing or is not a boolean: the check of the published schema names it.
        return ValidatedCommand(kind=kind.name, record_id=TOOL_FX)
    error_code = payload.get("error_code")
    if not isinstance(error_code, str) or not error_code:
        # The error code is missing: the check of the published schema names it.
        return ValidatedCommand(kind=kind.name, record_id=TOOL_FX, enabled=enabled)
    outage = state.derived.outage_of(TOOL_FX)
    if enabled and outage:
        raise MutationRejected(
            CODE_INVALID_STATE,
            f"the FX tool is already down with the error {outage}, and there is no outage left to start",
        )
    if not enabled and not outage:
        raise MutationRejected(
            CODE_INVALID_STATE,
            "the FX tool is available, and there is no outage to end",
        )
    return ValidatedCommand(kind=kind.name, record_id=TOOL_FX, enabled=enabled, error_code=error_code)


def _validate_note(kind: MutationKind, command: MutationCommand, state: ProjectedState) -> ValidatedCommand:
    """The rules of the untrusted note of a record of the branch.

    The record the command names has to be in the branch, and a note that says what the record already carries
    changes nothing and is refused, for the same reason the outage that changes nothing is refused (ADR-032).
    """
    payload = command.payload
    record_id = payload.get("record_id")
    if not isinstance(record_id, str) or not record_id:
        # The identifier is missing or is not a text: the check of the published schema names it.
        return ValidatedCommand(kind=kind.name, record_id="")
    table = table_of_the_record(record_id, holds_the_record(state.rows, record_id))
    if table is None:
        raise MutationRejected(
            CODE_UNKNOWN_RECORD,
            f"the record {record_id} is not in the branch; the branch holds no such record",
        )
    text = payload.get("text")
    if not isinstance(text, str) or not text:
        # The text is missing: the check of the published schema names it.
        return ValidatedCommand(kind=kind.name, record_id=record_id, record_table=table)
    if state.derived.note_of(table, record_id) == text:
        raise MutationRejected(
            CODE_INVALID_STATE,
            f"the record {record_id} already carries this note, and a note that says the same thing changes nothing",
        )
    return ValidatedCommand(kind=kind.name, record_id=record_id, record_table=table, text=text)


def _is_a_day(text: str) -> bool:
    """True when the text is a day of the calendar, in the shape YYYY-MM-DD.

    Why the check is here and not only in the schema: the published schema declares the format of the day, and the
    checker of the schema does not read the format, so a text that is not a day would reach the row of the ledger.
    """
    try:
        return date.fromisoformat(text).isoformat() == text
    except ValueError:
        return False


def _validate_effective_date(value: Any, state: ProjectedState, now: datetime) -> str:
    """The effective date of a command, when it is a moment inside the window the server accepts."""
    text = value.strip() if isinstance(value, str) else ""
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise MutationRejected(
            CODE_INVALID_EFFECTIVE_DATE,
            "the effective date is not an ISO 8601 moment with a time zone",
        ) from None
    if moment.tzinfo is None:
        raise MutationRejected(
            CODE_INVALID_EFFECTIVE_DATE,
            "the effective date is not an ISO 8601 moment with a time zone",
        )
    oldest = oldest_moment(state)
    if oldest is not None and moment < oldest:
        raise MutationRejected(
            CODE_INVALID_EFFECTIVE_DATE,
            f"the effective date {text} is before the first moment of the case, which is {oldest.isoformat()}",
        )
    if moment > now + EFFECTIVE_DATE_TOLERANCE:
        raise MutationRejected(
            CODE_INVALID_EFFECTIVE_DATE,
            f"the effective date {text} is after the clock of the server",
        )
    return text


def _validate_shape(command: MutationCommand) -> None:
    """The shape of the command against the published schema of the contract."""
    # The currency assertion is not a field of the published schema, and the domain has already checked it, so it
    # is not part of the shape that the schema judges.
    data = {key: value for key, value in command.payload.items() if key != CURRENCY_ASSERTION}
    body: dict[str, Any] = {"kind": command.kind, "data": data}
    if command.reason is not None:
        body["reason"] = command.reason
    validator = _validator_of(command.kind)
    errors = sorted(validator.iter_errors(body), key=lambda error: list(error.path))
    if errors:
        raise MutationRejected(
            CODE_INVALID_PAYLOAD,
            f"the command does not match the published schema: {errors[0].message}",
        )


def _validator_of(kind: str) -> Any:
    """The validator of the published schema for one kind of the catalog."""
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:  # jsonschema belongs to the api extra, and the sandbox refuses without it
        raise MutationRejected(
            CODE_CONTRACT_UNAVAILABLE,
            "the check of the shape of a command needs jsonschema, which the api extra and the dev extra install: "
            "this deployment cannot check the command, and the command of the visitor is not the reason",
        ) from exc
    schema = json.loads(COMMAND_SCHEMA_PATH.read_text(encoding="utf-8"))
    for branch in schema.get("oneOf", []):
        if branch.get("properties", {}).get("kind", {}).get("const") == kind:
            return Draft202012Validator(branch)
    raise MutationRejected(
        CODE_UNKNOWN_MUTATION_TYPE,
        f"the mutation kind {kind!r} is not in the published schema of the command",
    )


# --- the events of the sandbox ---------------------------------------------------------------------------------


def payload_digest(command: MutationCommand) -> str:
    """The digest of the payload of a command: the body the idempotency key is bound to."""
    body = {"kind": command.kind, "data": command.payload, "reason": command.reason}
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


def command_id_of(command: MutationCommand, digest: str) -> str:
    """The identifier of the request, which ties the events of the branch to the request that made them."""
    return command_id_from(command.idempotency_key or "", digest)


def command_id_from(idempotency_key: str, digest: str) -> str:
    """The identifier of the request, computed from its key and the digest of its payload.

    Why it is a function of two values and not of the command: the branch remembers the key and the digest of a
    request and never the command itself, and the mark of the undo names the command id of the request it undoes,
    so the layer has to be able to compute the command id of a remembered answer (ADR-024).
    """
    seed = f"{idempotency_key}:{digest}"
    return "cmd_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]


def build_events(
    command: MutationCommand, validated: ValidatedCommand, branch_id: str, command_id: str, now: datetime
) -> tuple[SandboxEventRow, ...]:
    """The events of the sandbox that a command produces.

    Why the events carry the rate and not the amount: the amount is computed by the interpreter from the rate, so
    the projection of a branch is the same whether it is built by the commit or rebuilt from the events alone. The
    same holds for the two other kinds: the event carries the published payload of the command and the interpreter
    writes the row (ADR-031).
    """
    occurred_at = now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    event_type, payload = _event_of(validated)
    event_uid = hashlib.sha256(
        canonical_json([branch_id, event_type, validated.record_id, occurred_at, payload, command_id])
        .encode("utf-8")
    ).hexdigest()
    event = SandboxEventRow(
        event_uid=event_uid,
        branch_id=branch_id,
        event_type=event_type,
        aggregate_id=validated.record_id,
        occurred_at=occurred_at,
        payload=payload,
        origin=SANDBOX_ORIGIN,
        command_id=command_id,
    )
    return (event,)


def _event_of(validated: ValidatedCommand) -> tuple[str, dict[str, Any]]:
    """The type of the event of a kind and its payload, which is the published payload of the command."""
    if validated.kind == KIND_FX_ADJUSTMENT:
        if validated.rate is None or validated.effective_at is None:
            raise MutationRejected(
                CODE_INVALID_PAYLOAD,
                "the command of an adjustment of the rate carries no rate and no effective date",
            )
        return (
            EVENT_REFUND_FX_ADJUSTED,
            {
                "refund_id": validated.record_id,
                "applied_rate": canonical_rate(validated.rate),
                "effective_at": validated.effective_at,
            },
        )
    if validated.kind == KIND_DUPLICATE:
        if validated.elapsed_seconds is None:
            raise MutationRejected(
                CODE_INVALID_PAYLOAD,
                "the command of a duplicate carries no elapsed seconds",
            )
        return (
            EVENT_PAYMENT_DUPLICATED,
            {
                "transaction_id": validated.record_id,
                "elapsed_seconds": validated.elapsed_seconds,
            },
        )
    if validated.kind == KIND_DEADLINE:
        if validated.new_deadline is None:
            raise MutationRejected(
                CODE_INVALID_PAYLOAD,
                "the command of a deadline carries no new deadline",
            )
        return (
            EVENT_CHARGEBACK_DEADLINE_CHANGED,
            {
                "chargeback_id": validated.record_id,
                "new_deadline": validated.new_deadline,
            },
        )
    if validated.kind == KIND_FX_OUTAGE:
        if validated.enabled is None or validated.error_code is None:
            raise MutationRejected(
                CODE_INVALID_PAYLOAD,
                "the command of an outage carries no state of the tool and no error code",
            )
        return (
            EVENT_TOOL_FX_OUTAGE,
            {
                "enabled": validated.enabled,
                "error_code": validated.error_code,
            },
        )
    if validated.kind == KIND_NOTE:
        if validated.text is None:
            raise MutationRejected(
                CODE_INVALID_PAYLOAD,
                "the command of a note carries no text",
            )
        return (
            EVENT_RECORD_NOTE_INJECTED,
            {
                "record_id": validated.record_id,
                "text": validated.text,
            },
        )
    raise MutationRejected(
        CODE_UNKNOWN_MUTATION_TYPE,
        f"the mutation kind {validated.kind!r} is not in the catalog of the sandbox;"
        f" the accepted kinds are: {', '.join(ENABLED_KINDS)}",
    )


# --- the plan of a command ------------------------------------------------------------------------------------


def plan_mutation(
    base: BaseSnapshot,
    branch_id: str,
    scenario_id: str,
    revision: int,
    events: list[SandboxEventRow],
    command: MutationCommand,
    now: datetime,
    before: ProjectedState | None = None,
) -> MutationPlan:
    """What the command would do to the branch, computed in memory and written nowhere.

    Why two projections: the diff is the difference between the state the branch is in and the state the command
    would produce, so both sides have to exist. The second one is built over a copy of the base, so the branch and
    the published case are never touched. The state the branch is in is given by the caller when it has already
    projected it, so the verification of the branch and the plan share one projection.
    """
    state = before if before is not None else project(base, events)
    validated = validate_command(command, state, now)
    digest = payload_digest(command)
    command_id = command_id_of(command, digest)
    new_events = build_events(command, validated, branch_id, command_id, now)
    after_state = project(base, [*events, *new_events])
    entries = diff_of(state, after_state)
    results = evaluate(after_state)
    verdict = verdict_of(after_state, scenario_id)
    before = _money_of(state, validated)
    after = _money_of(after_state, validated)
    return MutationPlan(
        kind=validated.kind,
        command_id=command_id,
        events=new_events,
        revision=revision + 1,
        canonical_hash=after_state.canonical_hash,
        diff=tuple(entry.to_dict() for entry in entries),
        invariants=tuple(result.to_dict() for result in results),
        verdict=verdict,
        before=before,
        after=after,
        valid=all(result.passed for result in results),
    )


def _money_of(state: ProjectedState, validated: ValidatedCommand) -> MoneyValue:
    """The amount of money the command is about, as the interface reads it.

    Why the dispatch: every kind is about a record of its own table, and the amount of the record is what the visitor
    reads before and after the change (ADR-031).
    """
    if validated.kind == KIND_FX_ADJUSTMENT:
        row = state.row("refunds", validated.record_id) if validated.record_id else None
        if row is None:
            return MoneyValue("", "")
        currency = str(row.get("payout_currency") or "")
        return MoneyValue(format_minor(int(row.get("payout_amount_minor") or 0), currency), currency)
    if validated.kind == KIND_DUPLICATE:
        row = state.row("transactions", validated.record_id) if validated.record_id else None
        if row is None:
            return MoneyValue("", "")
        currency = str(row.get("currency") or "")
        return MoneyValue(format_minor(int(row.get("amount_minor") or 0), currency), currency)
    if validated.kind == KIND_DEADLINE:
        row = state.row("chargebacks", validated.record_id) if validated.record_id else None
        if row is None:
            return MoneyValue("", "")
        currency = str(row.get("currency") or "")
        return MoneyValue(format_minor(int(row.get("amount_minor") or 0), currency), currency)
    return MoneyValue("", "")


# --- the plan of an undo ---------------------------------------------------------------------------------------


def plan_undo(
    base: BaseSnapshot,
    branch_id: str,
    scenario_id: str,
    revision: int,
    events: list[SandboxEventRow],
    command: MutationCommand,
    now: datetime,
    before: ProjectedState | None = None,
) -> UndoPlan:
    """What the undo of the last mutation would do to the branch, computed in memory and written nowhere.

    Why the undone event is the last live one: the marker of an undo names an event of the log, and the events that
    are not live are the ones a marker already undid. So the undo takes back the last mutation the branch still
    holds, and a branch that holds none has nothing to undo (FR-038, ADR-024).

    Why two projections: the diff is the difference between the state the branch is in and the state the undo would
    produce, so both sides have to exist. The second one is built over a copy of the base, so the branch and the
    published case are never touched. The state the branch is in is given by the caller when it has already
    projected it, so the verification of the branch and the plan share one projection.
    """
    digest = payload_digest(command)
    command_id = command_id_of(command, digest)
    undone = undo_marks(events).undone_event_uids
    live = [event for event in events if not is_undo_marker(event) and event.event_uid not in undone]
    if not live:
        raise MutationRejected(
            CODE_NOTHING_TO_UNDO,
            f"the branch {branch_id} holds no mutation left to undo",
        )
    target = live[-1]
    marker = build_undo_event(branch_id, target, command_id, now)
    before_state = before if before is not None else project(base, events)
    after_state = project(base, [*events, marker])
    entries = diff_of(before_state, after_state)
    results = evaluate(after_state)
    verdict = verdict_of(after_state, scenario_id)
    return UndoPlan(
        kind=command.kind,
        command_id=command_id,
        event=marker,
        revision=revision - 1,
        canonical_hash=after_state.canonical_hash,
        diff=tuple(entry.to_dict() for entry in entries),
        invariants=tuple(result.to_dict() for result in results),
        verdict=verdict,
        undone_event_uid=target.event_uid,
        undone_command_id=target.command_id or "",
        valid=all(result.passed for result in results),
    )


def build_undo_event(
    branch_id: str, target: SandboxEventRow, command_id: str, now: datetime
) -> SandboxEventRow:
    """The marker of the undo: it names the event it undoes and the request that produced it.

    Why the marker names the command id of the request that produced the undone event: the answers the branch
    remembers are keyed by their request, so the mark of the undo is the name of that request, and it is derived
    from the log instead of being stored as a flag (ADR-024).
    """
    occurred_at = now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        UNDO_EVENT_UID: target.event_uid,
        UNDO_COMMAND_ID: target.command_id or "",
    }
    event_uid = hashlib.sha256(
        canonical_json(
            [branch_id, EVENT_BRANCH_UNDONE, target.event_uid, occurred_at, payload, command_id]
        ).encode("utf-8")
    ).hexdigest()
    return SandboxEventRow(
        event_uid=event_uid,
        branch_id=branch_id,
        event_type=EVENT_BRANCH_UNDONE,
        aggregate_id=target.aggregate_id,
        occurred_at=occurred_at,
        payload=payload,
        origin=SANDBOX_ORIGIN,
        command_id=command_id,
    )


def new_idempotency_key() -> str:
    """A key for a request that did not bring one."""
    return "cmd_" + secrets.token_hex(12)


__all__ = [
    "CATALOG",
    "CLOSED_CHARGEBACK_STAGES",
    "CODE_CURRENCY_MISMATCH",
    "CODE_HASH_MISMATCH",
    "CODE_IDEMPOTENCY_MISMATCH",
    "CODE_INVALID_AMOUNT",
    "CODE_INVALID_EFFECTIVE_DATE",
    "CODE_INVALID_PAYLOAD",
    "CODE_INVALID_STATE",
    "CODE_NOTE_TOO_LONG",
    "CODE_NOTHING_TO_UNDO",
    "CODE_PAYLOAD_TOO_LARGE",
    "CODE_RESOURCE_LIMIT",
    "CODE_INVALID_REQUEST",
    "CODE_INVARIANT_VIOLATION",
    "CODE_READ_ONLY_FIELD",
    "CODE_REVISION_CONFLICT",
    "CODE_UNKNOWN_MUTATION_TYPE",
    "CODE_UNKNOWN_RECORD",
    "COMMAND_SCHEMA_PATH",
    "MAX_NOTE_LENGTH",
    "MAX_PAYLOAD_BYTES",
    "ENABLED_KINDS",
    "KIND_DEADLINE",
    "KIND_DUPLICATE",
    "KIND_FX_ADJUSTMENT",
    "KIND_FX_OUTAGE",
    "KIND_NOTE",
    "READ_ONLY_FIELDS",
    "UNDO_KIND",
    "MoneyValue",
    "MutationCommand",
    "MutationKind",
    "MutationPlan",
    "MutationRejected",
    "MutationResult",
    "UndoPlan",
    "ValidatedCommand",
    "build_events",
    "build_undo_event",
    "command_id_from",
    "command_id_of",
    "currency_exponent",
    "format_minor",
    "new_idempotency_key",
    "parse_rate",
    "payload_digest",
    "plan_mutation",
    "plan_undo",
    "read_only_field_in",
    "status_for_code",
    "validate_command",
    "validate_size",
]
