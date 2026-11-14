"""The typed mutation of a branch: the command, the catalog, the rules of the payload and the money helpers.

Why it exists: a visitor of the sandbox edits one field of one record, and the sandbox has to answer three
questions about that edit before anything is written: is the command one the sandbox knows, does it obey the rules
of the domain, and what would it change. This module owns the command and those answers.

The rule that rules above all: no number of this path is a float. Every amount is an integer of minor units or a
`Decimal`, and the conversion between a rate and an amount is the one of the simulator, in `ledgerlens/sim/gaps.py`,
so the sandbox and the published ledger agree on the arithmetic (FR-017).

The catalog is the promise of the sandbox: only `refund.apply_fx_adjustment` is enabled, because it is the only
kind with a round trip test. The other four kinds of the published schema are known and refused with the same code
as a kind that does not exist, because the catalog says what the sandbox can do (ADR-021).

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
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Any

from ledgerlens.sandbox.invariants import evaluate
from ledgerlens.sandbox.projector import (
    EVENT_REFUND_FX_ADJUSTED,
    SANDBOX_ORIGIN,
    ProjectedState,
    Verdict,
    canonical_rate,
    diff_of,
    oldest_moment,
    project,
    verdict_of,
)
from ledgerlens.sandbox.snapshot import BaseSnapshot
from ledgerlens.sandbox.store import SandboxEventRow
from ledgerlens.sim.events import canonical_json

# The published schema of the command. The shape of a payload is checked against it and against nothing else.
COMMAND_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "v3" / "contracts" / "schemas" / "scenario-mutation.schema.json"
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
CODE_PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
CODE_NOTE_TOO_LONG = "NOTE_TOO_LONG"
CODE_RESOURCE_LIMIT = "RESOURCE_LIMIT_EXCEEDED"
CODE_HASH_MISMATCH = "HASH_MISMATCH"

# The status of the answer of a refusal. Everything that is not listed here is a rule of the payload.
STATUS_BY_CODE = {
    CODE_REVISION_CONFLICT: 409,
    CODE_IDEMPOTENCY_MISMATCH: 409,
    CODE_HASH_MISMATCH: 409,
    CODE_PAYLOAD_TOO_LARGE: 413,
    CODE_RESOURCE_LIMIT: 429,
}

# The size of a payload and the length of a note, the limits of the resources of a branch (FR-025).
MAX_PAYLOAD_BYTES = 32 * 1024
MAX_NOTE_LENGTH = 300

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
    """The answer of a commit: the new revision, the new canonical hash and the diff of the mutation."""

    command_id: str
    kind: str
    revision: int
    canonical_hash: str
    diff: tuple[dict[str, Any], ...]
    invariants: tuple[dict[str, Any], ...]
    verdict: dict[str, Any]
    replayed: bool = False

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
        }


class MutationRejected(Exception):
    """The sandbox refuses the command, and the reason names the rule that failed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ValidatedCommand:
    """A command that passed every rule, with the values the interpreter needs."""

    kind: str
    record_id: str
    rate: Decimal
    effective_at: str


# The catalog of the sandbox. Only the kinds with a round trip test are enabled (ADR-021).
CATALOG: tuple[MutationKind, ...] = (
    MutationKind(
        "refund.apply_fx_adjustment",
        True,
        "the FX rate applied to the payout of a refund",
    ),
    MutationKind("payment.simulate_duplicate", False, "a second charge of the same payment"),
    MutationKind("chargeback.change_deadline", False, "the deadline of a chargeback"),
    MutationKind("tool.fx_outage", False, "the FX tool is unavailable"),
    MutationKind("record.inject_untrusted_note", False, "an untrusted note on a record"),
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
    """The rules of the domain of the kind that is enabled."""
    if kind.name != "refund.apply_fx_adjustment":
        # The guard of a kind that is enabled before its rules are written: the catalog grows with a round trip
        # test, and a kind without one is refused rather than half done.
        raise MutationRejected(
            CODE_UNKNOWN_MUTATION_TYPE,
            f"the mutation kind {kind.name!r} is not enabled; the accepted kinds are: {', '.join(ENABLED_KINDS)}",
        )
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
    if record is not None and "currency" in payload:
        expected = str(record.get("payout_currency"))
        if payload["currency"] != expected:
            raise MutationRejected(
                CODE_CURRENCY_MISMATCH,
                f"the currency {payload['currency']!r} does not match the currency of the record, which is {expected}",
            )
    effective_at = None
    if "effective_at" in payload:
        effective_at = _validate_effective_date(payload["effective_at"], state, now)
    if record is None or rate is None or effective_at is None:
        # A field is missing or has the wrong shape: the check of the published schema names it.
        return ValidatedCommand(kind=kind.name, record_id=str(refund_id or ""), rate=Decimal(0), effective_at="")
    return ValidatedCommand(kind=kind.name, record_id=str(refund_id), rate=rate, effective_at=effective_at)


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
    except ImportError as exc:  # jsonschema is a development dependency, and the sandbox refuses without it
        raise MutationRejected(
            CODE_INVALID_PAYLOAD,
            "the check of the shape of a command needs jsonschema, which the development extra installs",
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
    seed = f"{command.idempotency_key or ''}:{digest}"
    return "cmd_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]


def build_events(
    command: MutationCommand, validated: ValidatedCommand, branch_id: str, command_id: str, now: datetime
) -> tuple[SandboxEventRow, ...]:
    """The events of the sandbox that a command produces.

    Why the events carry the rate and not the amount: the amount is computed by the interpreter from the rate, so
    the projection of a branch is the same whether it is built by the commit or rebuilt from the events alone.
    """
    occurred_at = now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "refund_id": validated.record_id,
        "applied_rate": canonical_rate(validated.rate),
        "effective_at": validated.effective_at,
    }
    event_uid = hashlib.sha256(
        canonical_json([branch_id, EVENT_REFUND_FX_ADJUSTED, validated.record_id, occurred_at, payload, command_id])
        .encode("utf-8")
    ).hexdigest()
    event = SandboxEventRow(
        event_uid=event_uid,
        branch_id=branch_id,
        event_type=EVENT_REFUND_FX_ADJUSTED,
        aggregate_id=validated.record_id,
        occurred_at=occurred_at,
        payload=payload,
        origin=SANDBOX_ORIGIN,
        command_id=command_id,
    )
    return (event,)


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
    before = _money_of(state, validated.record_id)
    after = _money_of(after_state, validated.record_id)
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


def _money_of(state: ProjectedState, refund_id: str) -> MoneyValue:
    """The payout of a refund in a projection, as the interface reads it."""
    row = state.row("refunds", refund_id) if refund_id else None
    if row is None:
        return MoneyValue("", "")
    currency = str(row.get("payout_currency") or "")
    return MoneyValue(format_minor(int(row.get("payout_amount_minor") or 0), currency), currency)


def new_idempotency_key() -> str:
    """A key for a request that did not bring one."""
    return "cmd_" + secrets.token_hex(12)


__all__ = [
    "CATALOG",
    "CODE_CURRENCY_MISMATCH",
    "CODE_HASH_MISMATCH",
    "CODE_IDEMPOTENCY_MISMATCH",
    "CODE_INVALID_AMOUNT",
    "CODE_INVALID_EFFECTIVE_DATE",
    "CODE_INVALID_PAYLOAD",
    "CODE_NOTE_TOO_LONG",
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
    "READ_ONLY_FIELDS",
    "MoneyValue",
    "MutationCommand",
    "MutationKind",
    "MutationPlan",
    "MutationRejected",
    "MutationResult",
    "ValidatedCommand",
    "build_events",
    "command_id_of",
    "currency_exponent",
    "format_minor",
    "new_idempotency_key",
    "parse_rate",
    "payload_digest",
    "plan_mutation",
    "read_only_field_in",
    "status_for_code",
    "validate_command",
    "validate_size",
]
