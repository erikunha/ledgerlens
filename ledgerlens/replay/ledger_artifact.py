"""The ledger of the recorded demo, as an artifact of the site: the movements of the account and the reads it made.

Why it exists: the home page of the site promises the ledger rows it read, and today those rows live inside the
recording and nowhere else. This module turns the recording and the ledger of its account into one JSON document, the
artifact of the site, and it reads that document back.

What the artifact carries: the digest of the ledger the recording read (the claim of identity between the artifact and
the recording), the movements of the account in the shape of the ledger of the branch of the sandbox, and the reads of
the recording with the rows those reads returned. The money is a decimal text and never a float, because the browser
never calculates money and a float of a financial amount is a different amount.

Where the rules live, and why: the shape of a movement comes from `_ledger_items` of `ledgerlens/sandbox/branch.py`,
so that the table of the recorded demo and the table of the branch of the sandbox render one row and not two; the kind
of an account comes from `account_kind` of `ledgerlens/api/accounts.py`, so that there is one spelling of an account
identifier and not two; and the account of a recording comes from the note of its manifest, because the note is the
place where the capture names the account it ran against.

Why the artifact is a file beside the bundle and never inside it: `load_bundle` refuses a folder that holds a file the
manifest does not declare, so an artifact inside the bundle would make the recording unreadable and would move the
digest of the bundle. The artifact is therefore written beside the bundle and the export copies it into the folder of
the scenario.

Why the reads are a projection and never a decision: `ledger_reads_from_events` reads the events that the recording
holds and publishes what they say. It never fills a gap, never repairs a value and never invents a column, because a
row the run did not read is a row the site would publish without a witness.
"""

from __future__ import annotations

import json
import re
import sqlite3
import tempfile
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ledgerlens.api.accounts import account_kind, load_accounts, scoped_ledger
from ledgerlens.api.ledger_service import open_ledger
from ledgerlens.replay.bundle import EVENTS_FILE, BundleError, BundleManifest, load_bundle
from ledgerlens.sandbox.branch import LEDGER_PAGE_SIZE, _ledger_items
from ledgerlens.sim.config import SimConfig
from ledgerlens.sim.pipeline import build_ledger
from ledgerlens.sim.projector import dump_rows

__all__ = [
    "ACCOUNT_PATTERN",
    "LEDGER_FILE",
    "LEDGER_PAGE_SIZE",
    "LEDGER_SCHEMA_VERSION",
    "LedgerArtifactError",
    "account_of_manifest",
    "build_ledger_artifact",
    "check_ledger_artifact",
    "ledger_artifact_bytes",
    "ledger_reads_from_events",
    "read_ledger_artifact",
    "write_ledger_artifact",
]

# The name of the published file of the ledger, beside the events, the manifest and the provenance of the scenario.
LEDGER_FILE = "ledger.json"

# The version of the shape of the artifact. It grows when the shape grows, and never in place.
LEDGER_SCHEMA_VERSION = "1"

# The shape of the identifier of an account, the one the note of a manifest carries. It is the gate of the reading of
# the note: an identifier that is not in this shape is not an account and never reaches the artifact.
ACCOUNT_PATTERN = re.compile(r"^[CM]-[0-9]+$")

# The tool that reads the ledger. A read of the artifact is one call of this tool, and the projection looks for no
# other: the recording that called another tool read no ledger.
LEDGER_TOOL = "query_ledger"

# The candidates of an account inside the free text of a note. The note is prose written by the capture, so the rule
# looks for the shape of an identifier and lets the pattern of the account decide.
_ACCOUNT_CANDIDATE_PATTERN = re.compile(r"\b[A-Z]{1,2}-[0-9]+\b")

# The identifiers of the records of the ledger, in the shape the core gives them. The reads publish the identifiers
# that the statement named, and the statement is read as it was recorded.
_RECORD_PATTERN = re.compile(r"\b(?:TX|R|CB|ST)-[0-9]{4}\b|\bM-[0-9]{2}\b|\bC-[0-9]{4}\b")

# The tables of the ledger that hold the movements of an account, in the order the branch layer reads them.
_MOVEMENT_TABLES = ("transactions", "refunds", "chargebacks")


class LedgerArtifactError(Exception):
    """The artifact cannot be built or does not hold up.

    Why the refusal exists: an artifact without an account, an artifact of another recording and an artifact that
    cannot be read are three claims the site cannot make. They are refused with a reason a person can read, and never
    with a traceback.
    """


@dataclass(frozen=True)
class _LedgerRows:
    """The rows of a ledger, in the shape the branch layer reads them.

    Why the shape is borrowed and not written again: the row of a ledger is one contract in this repository, and the
    branch layer already writes it. This holder only gives the rows to the rule that writes them.
    """

    rows: dict[str, list[dict[str, Any]]]


def account_of_manifest(manifest: BundleManifest) -> str | None:
    """The account the note of the manifest names, or None when the note names no account.

    Why the note and not the events: the events never name the account, the note is the place where the capture says
    which account it ran against, and an artifact without an account is a table without a subject. A note that names
    more than one account is refused, because the artifact of an ambiguous recording would publish rows of an account
    that nobody chose.
    """
    found: list[str] = []
    for candidate in _ACCOUNT_CANDIDATE_PATTERN.findall(manifest.note):
        if ACCOUNT_PATTERN.match(candidate) and candidate not in found:
            found.append(candidate)
    if not found:
        return None
    if len(found) > 1:
        raise LedgerArtifactError(f"the note of the manifest names more than one account: {found}")
    return found[0]


def ledger_reads_from_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The reads of the ledger that the recorded events hold, one per call of the tool of the ledger.

    Why it is a projection: the recording is the witness. The projection reads the event of the tool, takes the data of
    its output and publishes the citation, the sequence number, the statement, the columns, the number of rows, the
    flag of the cut and the rows. It never fills a gap and never repairs a value: a read whose output carries no rows
    is published with no rows.
    """
    reads: list[dict[str, Any]] = []
    for event in events:
        payload = event.get("payload")
        if not isinstance(payload, dict) or payload.get("name") != LEDGER_TOOL:
            continue
        outputs = payload.get("outputs")
        if not isinstance(outputs, dict):
            continue
        data = outputs.get("data")
        if not isinstance(data, dict):
            continue
        reads.append(_read_of(event, outputs, data))
    return reads


def _text_of(value: Any) -> str:
    """The text of a value of a row, in the form the published artifact carries.

    Why the text and not the value: the published artifact is read by the browser, and the contract of the browser
    is that every value of a row is a string. A number written as a number is a file the browser refuses, and a
    panel that says `Invalid input: expected string, received number` is a panel that shows no ledger at all.

    Why this is not a repair of the value: the value does not change, the form of the value in the published file
    does. The artifact never repairs a value (ADR-045), and a number written as its own text is the same number.
    The recording keeps the original form, so nothing is lost.

    Why the JSON form and not a hand written one: the JSON text of a value is the text of the value for every
    kind of value, and it does not invent a form for the kinds that have no text of their own.
    """
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _read_of(event: dict[str, Any], outputs: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    """One read of the ledger, as the artifact publishes it.

    The values of the rows are the values the recording wrote and the names of the columns are the names the recording
    declared, in the order it declared them. A value that the recording wrote as a list is named with the columns of
    the read, and a value that the recording wrote as an object keeps its own names.
    """
    columns = [str(column) for column in (data.get("columns") or [])]
    rows: list[dict[str, str]] = []
    for row in data.get("rows") or []:
        if isinstance(row, dict):
            rows.append({str(key): _text_of(value) for key, value in row.items()})
        elif isinstance(row, list):
            # A row with more values than the read declares columns is a recording that says something the artifact
            # cannot publish without repairing it, and the artifact never repairs a value. The read is refused with
            # the number of columns and the number of values, and nothing is written.
            if len(row) != len(columns):
                raise LedgerArtifactError(
                    f"the read of the sequence {event.get('seq')} declares {len(columns)} columns and one of its rows "
                    f"carries {len(row)} values: the artifact never repairs a value"
                )
            rows.append({column: _text_of(value) for column, value in zip(columns, row, strict=True)})
    evidence_ids = outputs.get("evidence_ids")
    evidence_id = ""
    if isinstance(evidence_ids, list) and evidence_ids:
        evidence_id = str(evidence_ids[0])
    sql = str(data.get("sql") or "")
    return {
        "evidence_id": evidence_id,
        "seq": int(event.get("seq") or 0),
        "tool": LEDGER_TOOL,
        "sql": sql,
        "columns": columns,
        "row_count": int(data.get("row_count") or 0),
        "truncated": bool(data.get("truncated")),
        "records": _records_of(sql),
        "rows": rows,
    }


def _records_of(sql: str) -> list[str]:
    """The identifiers of the records that the statement named, in the order the statement names them.

    Why they are read out of the statement: a read that named nothing publishes an empty list and never an invented
    one. The identifiers keep the order of the statement, so the reader of the artifact sees them as the run saw them.
    """
    found: list[str] = []
    for candidate in _RECORD_PATTERN.findall(sql):
        if candidate not in found:
            found.append(candidate)
    return found


def build_ledger_artifact(bundle_dir: Path, ledger_db: Path) -> dict[str, Any]:
    """The artifact of the scenario of the bundle, built from the recording and the ledger of its account.

    Why the two inputs: the recording says what the run read and the ledger says what the account holds. The artifact
    is the account of the recording (from the note of the manifest), the movements of that account (read with the rule
    of the branch layer) and the reads of the recording (read with the projection of the events).

    Why the digest of the snapshot is the one of the manifest: the digest is the claim of identity between the artifact
    and the recording, and the manifest of the bundle is the authority of that claim.
    """
    manifest = _manifest_of(bundle_dir)
    account_id = account_of_manifest(manifest)
    if account_id is None:
        raise LedgerArtifactError(
            f"the note of the manifest of {bundle_dir.name} names no account, so the recording owes no ledger"
        )
    if not manifest.snapshot_sha256:
        raise LedgerArtifactError(
            f"the manifest of {bundle_dir.name} declares no digest of the ledger, so the artifact could not prove "
            "which ledger it is"
        )
    try:
        kind = account_kind(account_id)
    except ValueError as exc:
        raise LedgerArtifactError(f"the note of the manifest names {account_id}, which is not an account") from exc

    try:
        accounts = load_accounts(ledger_db, [account_id])
    except (OSError, sqlite3.Error) as exc:
        raise LedgerArtifactError(f"the ledger {ledger_db} cannot be read: {exc}") from exc
    if not accounts:
        raise LedgerArtifactError(f"the ledger {ledger_db} does not hold the account {account_id} of the recording")

    return {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "scenario": str(manifest.scenario),
        "snapshot_sha256": str(manifest.snapshot_sha256),
        "page_size": LEDGER_PAGE_SIZE,
        "accounts": [
            {
                "id": account_id,
                "kind": kind,
                "name": accounts[0].name,
                "rows": _movements_of(ledger_db),
                "reads": ledger_reads_from_events(_recorded_events(bundle_dir)),
            }
        ],
    }


def ledger_artifact_bytes(artifact: dict[str, Any]) -> bytes:
    """The bytes of the artifact, in the format the repository uses everywhere.

    Why the format: sorted keys, two spaces and a final line. The artifact is a pure function of the ledger and of the
    recording, so the same artifact always gives the same bytes and a digest of them is a proof of what it holds.
    """
    text = json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True)
    return (text + "\n").encode("utf-8")


def write_ledger_artifact(path: Path, artifact: dict[str, Any]) -> Path:
    """The artifact written on the disk, and the path of the file.

    Why the writer is a function of its two arguments: the file of the artifact is frozen with the recording, so the
    same artifact always gives the same file and never a file that depends on the moment of the write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(ledger_artifact_bytes(artifact))
    return path


def read_ledger_artifact(path: Path) -> dict[str, Any]:
    """The artifact of a file, read back.

    Why it refuses and never guesses: a file that is not a JSON object is not an artifact, and an artifact that cannot
    be read is a claim the site cannot make.
    """
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise LedgerArtifactError(f"the artifact of the ledger cannot be read: {path}") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LedgerArtifactError(f"the artifact of the ledger is not a JSON document: {path}") from exc
    if not isinstance(payload, dict):
        raise LedgerArtifactError(f"the artifact of the ledger is not a JSON object: {path}")
    return payload


def check_ledger_artifact(bundle_dir: Path, path: Path) -> list[str]:
    """The differences between the file on the disk and the artifact the bundle and the ledger produce.

    Why it rebuilds the ledger: the artifact is a function of the recording and of the ledger of the account, and the
    only way to know that the file on the disk is that one is to build it again and to compare. The check writes
    nothing: the ledger it rebuilds lives in a temporary folder that goes away with the check.

    The differences are one line each, so the operator sees what moved and not only that something moved.
    """
    manifest = _manifest_of(bundle_dir)
    account_id = account_of_manifest(manifest)
    if account_id is None:
        return [f"the note of the manifest of {bundle_dir.name} names no account, so the recording owes no ledger"]
    with _account_ledger(account_id) as ledger_db:
        expected = ledger_artifact_bytes(build_ledger_artifact(bundle_dir, ledger_db))

    if not path.is_file():
        return [f"missing: {path.name}"]
    observed = path.read_bytes()
    if observed == expected:
        return []

    differences: list[str] = []
    expected_lines = expected.decode("utf-8").splitlines()
    observed_lines = observed.decode("utf-8", errors="replace").splitlines()
    for number, (expected_line, observed_line) in enumerate(zip(expected_lines, observed_lines, strict=False), start=1):
        if expected_line != observed_line:
            differences.append(f"differs at line {number}: expected {expected_line!r}, observed {observed_line!r}")
    for number in range(
        min(len(expected_lines), len(observed_lines)) + 1,
        max(len(expected_lines), len(observed_lines)) + 1,
    ):
        line = expected_lines[number - 1] if number <= len(expected_lines) else observed_lines[number - 1]
        differences.append(f"differs at line {number}: {line!r}")
    return differences


def _manifest_of(bundle_dir: Path) -> BundleManifest:
    """The manifest of a bundle, after the core checked the hashes, the secret and the order of the events.

    Why the core is the authority: a bundle whose hash does not match is not a recording, and an artifact of a
    recording that does not hold up would publish rows without a witness.
    """
    try:
        manifest, _events = load_bundle(bundle_dir)
    except BundleError as exc:
        raise LedgerArtifactError(f"the bundle in {bundle_dir.name} does not hold up: {exc}") from exc
    return manifest


def _recorded_events(bundle_dir: Path) -> list[dict[str, Any]]:
    """The recorded events of a bundle, parsed as they were recorded.

    Why the recorded text and not the event the core re-derives: a re-derivation would coerce a wrong type into a
    right one, and the artifact would publish a read the recording never had.
    """
    text = (bundle_dir / EVENTS_FILE).read_text(encoding="utf-8")
    events: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            events.append(payload)
    return events


def _movements_of(ledger_db: Path) -> list[dict[str, Any]]:
    """The movements of the account, in the shape of the ledger of the branch of the sandbox.

    Why the rule of the branch layer: the table of the recorded demo and the table of the branch of the sandbox render
    one row, so the shape of the row is written in one place and the interface reads one row.

    Why the currency of a refund that was never paid out is the currency that was asked back: the row of the branch
    layer carries the currency of the payout, and a refund that was rejected has no payout and so has no currency of
    a payout. The published file types every value as text and its contract asks for a currency that is not empty,
    so the row carries the currency of the refund, which is the currency of the money that was asked back.

    Why every value is text: the contract of the published file is the contract of the browser, and the browser types
    the values of a row as text. A value that is not text is a file the browser refuses, and a panel that shows the
    reason of the refusal is a panel that shows no ledger at all.
    """
    try:
        with closing(open_ledger(ledger_db)) as conn:
            rows = {table: dump_rows(conn, table) for table in _MOVEMENT_TABLES}
    except (OSError, sqlite3.Error) as exc:
        raise LedgerArtifactError(f"the ledger {ledger_db} cannot be read: {exc}") from exc
    items = list(_ledger_items(_LedgerRows(rows)))
    requested = {
        str(row.get("id")): str(row.get("requested_currency") or "")
        for row in rows.get("refunds", [])
    }
    published: list[dict[str, Any]] = []
    for item in items:
        currency = str(item.get("currency") or "") or requested.get(str(item.get("id")), "")
        published.append(
            {
                str(key): _text_of(currency if key == "currency" else value)
                for key, value in item.items()
            }
        )
    return published


@contextmanager
def _account_ledger(account_id: str) -> Iterator[Path]:
    """The ledger of the account, rebuilt the way the capture built it, in a temporary folder.

    Why it is rebuilt and not read: the ledger of the account is not in the repository, it is a file the capture wrote
    and the producer reproduced. The rebuild is deterministic, and the digest of the file it produces is the proof that
    it is the ledger the recording read.
    """
    with tempfile.TemporaryDirectory(prefix="ledgerlens_ledger_") as work:
        root = Path(work)
        base = root / "ledger.db"
        result = build_ledger(SimConfig(source="sample"), base)
        result.conn.close()
        yield scoped_ledger(base, account_id, root / "account.db")
