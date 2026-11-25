"""The parts of a capture that every capture shares: the tree of the repository, the question of the scenario and the
account of the run.

Why it exists: a capture is the writing of a recording, and the repository writes two kinds of them. The capture of
the scripted model is a formula: the same commit gives the same bytes. The capture of a real model is a run: the same
commit gives a different answer every time, and it is the recording of that answer (ADR-075). What the two do not
differ in is how they read the repository, how they choose the question of the scenario and how they choose the
account that signs in. Those three things live here, so that the two captures cannot drift apart on them.

Why the capture refuses a dirty tracked tree: the recording names the commit it was made from, and the claim has to
be true. Only the tracked tree counts, because the repository keeps untracked material on purpose, such as the
paused frontend and the local notes, and the commit the recording names is the commit of the tracked code. The
output folder of the capture is left out of that check as well, so a second capture into the same folder is not
blocked by the bundle the first one wrote.

Why the account is chosen by what the ledger shows and not by the order of the manifest: the scenario S08 names a
customer and a merchant, and the question is about the payout of the merchant. Signing in as the customer reads
nothing, and the recording would publish an answer with no evidence behind it. The scenario S04 is about an
identifier that is not in the ledger, so no account shows anything and the run still needs one to sign in: the first
customer of the ledger is used and the note of the bundle says which account it was.

Why the helpers live in the product and not in a script: the two captures are scripts, and a script that copies the
other one is a script that drifts from it.
"""

from __future__ import annotations

import hashlib
import sqlite3
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ledgerlens import demo
from ledgerlens.api.accounts import scoped_ledger

__all__ = [
    "CaptureError",
    "account_that_holds",
    "code_sha",
    "dirty_paths",
    "ensure_clean_tree",
    "first_customer",
    "git",
    "planted_question",
    "sha256_of",
    "visible_records",
]


class CaptureError(Exception):
    """The capture refuses to run: the tree is dirty, the commit cannot be read or the ledger holds no account.

    The refusal is an exception and not an exit, because the rule lives in the product. The script that calls it
    turns it into the exit of a command, with the reason the reader needs.
    """


# The table of the ledger that holds each kind of id, by the prefix of the id.
_TABLE_OF_PREFIX = {"TX": "transactions", "R": "refunds", "CB": "chargebacks", "ST": "settlements"}


def git(root: Path, *args: str) -> str:
    """The output of a git command in the repository.

    The hooks of the repository are never touched and no flag bypasses them: a capture only reads. The output
    comes back as it is, because the status of the working tree starts with the column of the status.
    """
    try:
        done = subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as error:
        raise CaptureError(f"git {args[0]} cannot answer in {root}: {error}") from error
    return done.stdout


def code_sha(root: Path) -> str:
    """The commit of the repository, the one the recording names as the provenance of the code.

    A capture that cannot state a commit refuses to run, because a recording that names a commit it does not know is
    a claim that cannot be checked.
    """
    try:
        commit = git(root, "rev-parse", "HEAD").strip()
    except CaptureError as error:
        raise CaptureError(
            f"the commit of the repository cannot be read, so the capture refuses to run: {error}"
        ) from error
    if not commit:
        raise CaptureError("the commit of the repository cannot be read, so the capture refuses to run")
    return commit


def _status_entries(text: str) -> list[tuple[str, str]]:
    """The status and the path of every line of `git status --porcelain`."""
    entries: list[tuple[str, str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        status, path = line[:2], line[3:]
        if " -> " in path:
            # A rename carries the old path and the new one, and the new one is the path on the disk.
            path = path.split(" -> ", 1)[1]
        entries.append((status.strip(), path.strip().strip('"')))
    return entries


def _relative_to_root(path: Path | None, root: Path) -> str | None:
    """The path of a folder relative to the root of the repository, when it is inside it."""
    if path is None:
        return None
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def _covered_by_output(path: str, out_relative: str) -> bool:
    """Whether a path of the status is the output folder of the capture, or a part of it."""
    clean = path.rstrip("/")
    return clean == out_relative or clean.startswith(out_relative + "/")


def dirty_paths(root: Path, out: Path | None = None) -> list[str]:
    """The paths of the tracked tree that are not clean, without the output folder of the capture.

    Only the tracked tree counts: the repository keeps untracked material on purpose, such as the paused frontend and
    the local notes, and the commit the recording names is the commit of the tracked code. The output folder is left
    out because the bundle of a previous capture is the output of the capture, not a change of the code, and the
    canonical bundle is tracked, so it shows up as a modification.
    """
    try:
        text = git(root, "status", "--porcelain", "--untracked-files=no")
    except CaptureError as error:
        raise CaptureError(
            "the state of the working tree cannot be read, so the capture cannot check that the recording names the "
            f"commit it was made from, and it refuses to run: {error}"
        ) from error
    out_relative = _relative_to_root(out, root)
    dirty: list[str] = []
    for _status, path in _status_entries(text):
        if out_relative is not None and _covered_by_output(path, out_relative):
            continue
        dirty.append(path)
    return dirty


def ensure_clean_tree(root: Path, out: Path | None = None) -> None:
    """The refusal of a dirty tracked tree, because the recording names a commit and the claim has to be true.

    Only the tracked tree counts: an untracked file or folder is material the repository keeps on purpose, and it is
    not part of the commit the recording names.
    """
    dirty = dirty_paths(root, out)
    if dirty:
        raise CaptureError(
            "the tracked tree is dirty, and the recording names the commit it was made from, so the claim would be "
            f"a lie. Commit or drop the changes and capture again: {', '.join(dirty[:5])}"
        )


def sha256_of(path: Path) -> str:
    """The hash of a file, to identify the ledger the execution read."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def planted_question(manifest: dict[str, Any], scenario_id: str) -> tuple[str, str | None]:
    """The planted question of the scenario and the account of the run, when the scenario names one.

    Why the account may be absent: the question of the scenario S04 is about a transaction that is not in the
    ledger, so the scenario names no customer and no merchant. The run still needs an account to sign in, because
    the agent reads the ledger of one account, and the caller resolves the account from the ledger when it is
    absent.

    Why the planted list is not the only source of the question: the scenario S11 asks the question of the scenario
    S01 and is not a complaint of its own on the page, so the capture reads the question of the dataset. The bundle
    it writes is the published proof that the same question, answered with the reference source in fault, is not the
    answer the source gives when it works.
    """
    item = next((entry for entry in demo.planted(manifest) if entry.scenario == scenario_id), None)
    scenario = demo.scenario_of(manifest, scenario_id)
    question = item.question if item is not None else str(scenario["questions"][0])
    accounts = demo.accounts_of(manifest, scenario_id)
    return question, accounts[0] if accounts else None


def first_customer(ledger: Path) -> str:
    """The first customer of the ledger, by id, for a scenario that names no account.

    Why the ledger decides and not the manifest: the accounts of a run are the accounts of the ledger the run
    reads, and the manifest of the scenarios does not list them. The customer is the one that can sign in, because
    the ledger of a merchant holds the payouts and the ledger of a customer holds the payments.
    """
    connection = sqlite3.connect(f"file:{ledger}?mode=ro", uri=True)
    try:
        row = connection.execute("SELECT id FROM customers ORDER BY id LIMIT 1").fetchone()
    finally:
        connection.close()
    if row is None:
        raise CaptureError("the ledger holds no customer, so the capture has no account to sign in")
    return str(row[0])


def visible_records(account_db: Path, ids: Sequence[str]) -> int:
    """How many of the ids of the scenario the ledger of the account shows.

    Why it matters: the ledger of a customer holds the payments of that customer and no settlement, and the ledger
    of a merchant holds the payouts and no payment of another merchant. A recording that signs in as the wrong kind
    of account reads nothing, and then the answer of the recording is a claim with no evidence behind it.
    """
    connection = sqlite3.connect(f"file:{account_db}?mode=ro", uri=True)
    try:
        seen = 0
        for identifier in ids:
            table = _TABLE_OF_PREFIX.get(identifier.split("-", 1)[0])
            if table is None:
                continue
            row = connection.execute(f"SELECT 1 FROM {table} WHERE id = ?", (identifier,)).fetchone()
            seen += 1 if row is not None else 0
        return seen
    finally:
        connection.close()


def account_that_holds(manifest: dict[str, Any], scenario_id: str, base: Path, work_root: Path) -> str:
    """The account of the scenario whose ledger shows the records the question is about.

    Why the account is chosen by what the ledger shows and not by the order of the manifest: the scenario S08 names
    a customer and a merchant, and the question is about the payout of the merchant. Signing in as the customer
    reads nothing, and the recording would publish an answer with no evidence behind it.

    Why the fallback exists: the scenario S04 is about an identifier that is not in the ledger, so no account shows
    anything, and the run still needs an account to sign in. The first customer of the ledger is used and the note
    of the bundle says which account it was.
    """
    scenario = demo.scenario_of(manifest, scenario_id)
    ids = [
        identifier
        for key in ("transaction_ids", "refund_ids", "chargeback_ids", "settlement_ids")
        for identifier in scenario["ids"].get(key, [])
    ]
    best_account = ""
    best_seen = -1
    for index, account_id in enumerate(demo.accounts_of(manifest, scenario_id)):
        candidate = scoped_ledger(base, account_id, work_root / f"candidate-{index}.db")
        seen = visible_records(candidate, ids)
        if seen > best_seen:
            best_account, best_seen = account_id, seen
    if best_seen > 0:
        return best_account
    return first_customer(base)
