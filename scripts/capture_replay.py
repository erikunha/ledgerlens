"""Captures the replay bundle of a planted scenario, in a deterministic execution.

Why it exists: the phase R2 will repeat an execution without calling any model. For that it needs a recorded trace, in
the public contract format, that anyone can read and check by hash. This script produces that file from the offline path
of the product itself: scripted model, recorded exchange rate, no key and no network. It calls no model at all, and the
bundle manifest says the execution is deterministic, never live.

What the script writes is the canonical bundle, in `data/eval/replay/<scenario>/`: the public events as JSON lines and
the manifest, with the hash of each part and the hash of the ledger the execution read. To redo the bundle, run the
script again: the content changes in the timestamps and in the execution identifiers, and the rest is the same.

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
import sys
import tempfile
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
from ledgerlens.sim.config import SimConfig  # noqa: E402
from ledgerlens.sim.pipeline import build_ledger  # noqa: E402
from ledgerlens.tools.fx import FxClient  # noqa: E402


def _sha256(path: Path) -> str:
    """The hash of the file, to identify the ledger the execution read."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _planted(manifest: dict, scenario_id: str) -> tuple[str, str]:
    """The planted question of the scenario and its first account."""
    item = next(entry for entry in demo.planted(manifest) if entry.scenario == scenario_id)
    accounts = demo.accounts_of(manifest, scenario_id)
    if not accounts:
        raise SystemExit(f"the scenario {scenario_id} has no account")
    return item.question, accounts[0]


def capture(scenario_id: str, out: Path) -> Path:
    """Runs the planted scenario in deterministic mode and writes the bundle."""
    manifest = demo.load_manifest()
    question, account_id = _planted(manifest, scenario_id)

    with tempfile.TemporaryDirectory(prefix="ledgerlens_replay_") as work:
        root = Path(work)
        base = root / "ledger.db"
        build_ledger(SimConfig(source="sample"), base).conn.close()
        account_db = scoped_ledger(base, account_id, root / "account.db")

        model, query_model, triage_model = (ScriptedChatModel(script=[]) for _ in range(3))
        agent = build_integrator(
            model,
            db_path=account_db,
            query_model=query_model,
            triage_model=triage_model,
            fx_client=FxClient(mode="fixtures", sleep=lambda _: None),
        )
        triage_model.script.append(demo.offline_triage(question, manifest))
        script = demo.offline_script(question, manifest)
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
