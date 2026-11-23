"""Captures the replay bundle of a planted scenario, in a deterministic execution.

Why it exists: the phase R2 will repeat an execution without calling any model. For that it needs a recorded trace, in
the public contract format, that anyone can read and check by hash. This script produces that file from the offline path
of the product itself: scripted model, recorded exchange rate, no key and no network. It calls no model at all, and the
bundle manifest says the execution is deterministic, never live.

What the script writes is the canonical bundle, in `data/eval/replay/<scenario>/`: the public events as JSON lines and
the manifest, with the hash of each part, the hash of the ledger the execution read and the provenance of the
recording. The provenance is the commit the capture ran from, the kind of the capture, the moment of the capture, the
model profile and the policy version. The hash of the prompt and the version of the redaction are not written, because
the repository has neither of them, and a value that is invented is worse than a value that is missing.

The capture refuses to run on a dirty tracked tree, because the recording names a commit and the claim has to be
true. That check looks only at the tracked tree, because the repository keeps untracked material on purpose, such as
the paused frontend and the local notes, and the commit the recording names is the commit of the tracked code. The
output folder of the capture is left out of that check as well, so a second capture into the same folder is not
blocked by the bundle the first one wrote. To redo the bundle, run the script again: the content changes in the
timestamps, in the execution identifiers and in the commit, and the rest is the same.

Usage:

```bash
uv run python scripts/capture_replay.py                              # S01, the first scenario
uv run python scripts/capture_replay.py --scenario S03 --out data/eval/replay/s03
```
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# The capture is deterministic: the model is scripted and the exchange rate is recorded, so nothing goes to the network.
os.environ.setdefault("LEDGERLENS_OFFLINE", "1")

sys.path.insert(0, str(ROOT))

from ledgerlens import demo  # noqa: E402  (the offline environment is set up before the import)
from ledgerlens.agents.integrator import build_integrator, investigate  # noqa: E402
from ledgerlens.api.accounts import scoped_ledger  # noqa: E402
from ledgerlens.observability.trace_event import InMemoryTraceSink, TraceEventStream  # noqa: E402
from ledgerlens.offline import ScriptedChatModel  # noqa: E402
from ledgerlens.replay.bundle import bundle_digest, write_bundle  # noqa: E402
from ledgerlens.run_context import POLICY_VERSION  # noqa: E402
from ledgerlens.sim.config import SimConfig  # noqa: E402
from ledgerlens.sim.pipeline import build_ledger  # noqa: E402
from ledgerlens.tools.fx import FxClient  # noqa: E402

# The kind of the capture and the model behind it: the capture runs the scripted model, never a real one.
CAPTURE_KIND = "scripted_fixture"
MODEL_PROFILE = "scripted-fixture"

# The scenarios whose run has the reference source in fault, and the scenarios whose run does not: the scenario S11
# is the scenario S01 with the source broken, and the recording is the proof that the agent then says less.
SCENARIO_FX_FAULT = {"S11": True}


class GitError(Exception):
    """Git cannot answer in the repository."""


def _git(root: Path, *args: str) -> str:
    """The output of a git command in the repository.

    The hooks of the repository are never touched and no flag bypasses them: the capture only reads. The output
    comes back as it is, because the status of the working tree starts with the column of the status.
    """
    try:
        done = subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as error:
        raise GitError(f"git {args[0]} cannot answer in {root}: {error}") from error
    return done.stdout


def code_sha(root: Path) -> str:
    """The commit of the repository, the one the recording names as the provenance of the code.

    A capture that cannot state a commit refuses to run, because a recording that names a commit it does not know is
    a claim that cannot be checked.
    """
    try:
        commit = _git(root, "rev-parse", "HEAD").strip()
    except GitError as error:
        raise SystemExit(
            f"the commit of the repository cannot be read, so the capture refuses to run: {error}"
        ) from error
    if not commit:
        raise SystemExit("the commit of the repository cannot be read, so the capture refuses to run")
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
        text = _git(root, "status", "--porcelain", "--untracked-files=no")
    except GitError as error:
        raise SystemExit(
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
        raise SystemExit(
            "the tracked tree is dirty, and the recording names the commit it was made from, so the claim would be "
            f"a lie. Commit or drop the changes and capture again: {', '.join(dirty[:5])}"
        )


def _sha256(path: Path) -> str:
    """The hash of the file, to identify the ledger the execution read."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _planted(manifest: dict, scenario_id: str) -> tuple[str, str | None]:
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


def _first_customer(ledger: Path) -> str:
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
        raise SystemExit("the ledger holds no customer, so the capture has no account to sign in")
    return str(row[0])


# The table of the ledger that holds each kind of id, by the prefix of the id.
_TABLE_OF_PREFIX = {"TX": "transactions", "R": "refunds", "CB": "chargebacks", "ST": "settlements"}


def _visible_records(account_db: Path, ids: Sequence[str]) -> int:
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


def _account_that_holds(manifest: dict, scenario_id: str, base: Path, work_root: Path) -> str:
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
        seen = _visible_records(candidate, ids)
        if seen > best_seen:
            best_account, best_seen = account_id, seen
    if best_seen > 0:
        return best_account
    return _first_customer(base)


def capture(scenario_id: str, out: Path, root: Path = ROOT) -> Path:
    """Runs the planted scenario in deterministic mode and writes the bundle.

    The capture names the commit it ran from and refuses to run on a dirty tracked tree, because the recording
    claims a commit and the claim has to be true. The tree is checked before the commit is read, so the refusal a
    reader needs comes first. Only the tracked tree counts: the repository keeps untracked material on purpose, and
    the commit named is the commit of the tracked code.
    """
    ensure_clean_tree(root, out)
    commit = code_sha(root)

    manifest = demo.load_manifest()
    question, account_id = _planted(manifest, scenario_id)

    with tempfile.TemporaryDirectory(prefix="ledgerlens_replay_") as work:
        work_root = Path(work)
        base = work_root / "ledger.db"
        build_ledger(SimConfig(source="sample"), base).conn.close()
        account_id = _account_that_holds(manifest, scenario_id, base, work_root)
        account_db = scoped_ledger(base, account_id, work_root / "account.db")

        model, query_model, triage_model = (ScriptedChatModel(script=[]) for _ in range(3))
        agent = build_integrator(
            model,
            db_path=account_db,
            query_model=query_model,
            triage_model=triage_model,
            fx_client=FxClient(
                mode="fixtures",
                fault=SCENARIO_FX_FAULT.get(scenario_id, False),
                sleep=lambda _: None,
            ),
        )
        triage_model.script.append(demo.offline_triage(question, manifest, scenario_id))
        script = demo.offline_script(question, manifest, scenario_id)
        if script is None:
            raise SystemExit(f"the scenario {scenario_id} has no offline script")
        messages, sqls = script
        model.script.extend(messages)
        query_model.script.extend(sqls)

        sink = InMemoryTraceSink()
        stream = TraceEventStream(
            f"replay-{scenario_id.lower()}",
            sink,
            mode="deterministic_sandbox",
            snapshot_sha256=_sha256(account_db),
        )
        investigate(agent, question, thread_id=f"replay-{scenario_id.lower()}", on_event=stream.on_span)
        events = sink.read_from(f"replay-{scenario_id.lower()}", after_seq=0, limit=10000)

        manifest_bundle = write_bundle(
            out,
            events,
            scenario=scenario_id,
            snapshot_sha256=_sha256(account_db),
            note=(
                f"Deterministic execution of the scenario {scenario_id}, account {account_id}, with the scripted model "
                "and the recorded exchange rate. This is not a live execution and it calls no model."
            ),
            capture_kind=CAPTURE_KIND,
            recorded_at=datetime.now(UTC).isoformat(timespec="seconds"),
            model_profile=MODEL_PROFILE,
            code_sha=commit,
            policy_version=POLICY_VERSION,
        )
        print(f"bundle in {out}")
        print(f"events: {manifest_bundle.events}")
        print(f"sha256 of the manifest: {bundle_digest(out)}")
        return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Captures the replay bundle of a planted scenario.")
    parser.add_argument("--scenario", default="S01", help="identifier of the planted scenario")
    parser.add_argument("--out", default=None, help="folder of the bundle (by default data/eval/replay/<scenario>)")
    args = parser.parse_args()

    out = Path(args.out) if args.out else ROOT / "data" / "eval" / "replay" / args.scenario.lower()
    capture(args.scenario, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
