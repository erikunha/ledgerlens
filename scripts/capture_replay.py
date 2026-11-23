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
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# The capture is deterministic: the model is scripted and the exchange rate is recorded, so nothing goes to the network.
os.environ.setdefault("LEDGERLENS_OFFLINE", "1")

sys.path.insert(0, str(ROOT))

from ledgerlens import demo  # noqa: E402  (the offline environment is set up before the import)
from ledgerlens.agents.integrator import build_integrator, investigate  # noqa: E402
from ledgerlens.api.accounts import scoped_ledger  # noqa: E402
from ledgerlens.memory.long_term import CaseMemory, scenario_case_id  # noqa: E402
from ledgerlens.observability.trace_event import InMemoryTraceSink, TraceEventStream  # noqa: E402
from ledgerlens.offline import ScriptedChatModel  # noqa: E402
from ledgerlens.replay.bundle import bundle_digest, write_bundle  # noqa: E402
from ledgerlens.replay.capture import (  # noqa: E402  (the path is set up before the import)
    CaptureError,
    account_that_holds,
    code_sha,
    dirty_paths,
    ensure_clean_tree,
    planted_question,
    sha256_of,
)
from ledgerlens.run_context import POLICY_VERSION, RunContext  # noqa: E402
from ledgerlens.sim.config import SimConfig  # noqa: E402
from ledgerlens.sim.pipeline import build_ledger  # noqa: E402
from ledgerlens.tools.fx import FxClient  # noqa: E402

__all__ = [
    "CAPTURE_KIND",
    "MODEL_PROFILE",
    "capture",
    "code_sha",
    "dirty_paths",
    "ensure_clean_tree",
    "main",
]

# The kind of the capture and the model behind it: the capture runs the scripted model, never a real one.
CAPTURE_KIND = "scripted_fixture"
MODEL_PROFILE = "scripted-fixture"

# The scenarios whose run has the reference source in fault, and the scenarios whose run does not: the scenario S11
# is the scenario S01 with the source broken, and the recording is the proof that the agent then says less.
SCENARIO_FX_FAULT = {"S11": True}


def capture(scenario_id: str, out: Path, root: Path = ROOT) -> Path:
    """Runs the planted scenario in deterministic mode and writes the bundle.

    The capture names the commit it ran from and refuses to run on a dirty tracked tree, because the recording
    claims a commit and the claim has to be true. The tree is checked before the commit is read, so the refusal a
    reader needs comes first. Only the tracked tree counts: the repository keeps untracked material on purpose, and
    the commit named is the commit of the tracked code.
    """
    try:
        ensure_clean_tree(root, out)
        commit = code_sha(root)
    except CaptureError as error:
        raise SystemExit(str(error)) from error

    manifest = demo.load_manifest()
    question, account_id = planted_question(manifest, scenario_id)

    with tempfile.TemporaryDirectory(prefix="ledgerlens_replay_") as work:
        work_root = Path(work)
        base = work_root / "ledger.db"
        build_ledger(SimConfig(source="sample"), base).conn.close()
        account_id = account_that_holds(manifest, scenario_id, base, work_root)
        account_db = scoped_ledger(base, account_id, work_root / "account.db")

        model, query_model, triage_model = (ScriptedChatModel(script=[]) for _ in range(3))
        # The memory of the capture lives in the folder of the capture and names its case after the scenario.
        # Why: the id of the case used to come from a counter over the store of the machine, so two captures of
        # the same commit wrote two different cases and the published bundle was not reproducible. The store of
        # the capture is its own, so the capture never writes into the store of the machine either.
        context = RunContext(
            run_id=f"replay-{scenario_id.lower()}",
            session_id=f"replay-{scenario_id.lower()}",
            mode="deterministic_sandbox",
            account_id=account_id,
            snapshot_sha256=sha256_of(account_db),
            memory_dir=work_root / "memory",
        )
        memory = CaseMemory(context.resolve_memory_dir(), case_id=scenario_case_id(scenario_id))
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
            run_context=context,
            case_memory=memory,
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
            snapshot_sha256=sha256_of(account_db),
        )
        investigate(agent, question, thread_id=f"replay-{scenario_id.lower()}", on_event=stream.on_span)
        events = sink.read_from(f"replay-{scenario_id.lower()}", after_seq=0, limit=10000)

        manifest_bundle = write_bundle(
            out,
            events,
            scenario=scenario_id,
            snapshot_sha256=sha256_of(account_db),
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
