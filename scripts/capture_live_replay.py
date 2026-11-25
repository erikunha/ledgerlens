#!/usr/bin/env python3
"""Captures the replay bundle of a scenario with a real model, in a real execution.

Why it exists: the catalog the site publishes holds the recordings of the scripted model, and that is a
reproducible proof of what the product does. It is not the product: a real model reads the ledger, asks the
reference source and writes its own answer, and nothing in the repository recorded that. This script records it, and
the recording is published as a second catalog, distinct from the first in every part a reader can check
(ADR-075).

What it writes is the bundle of the run, in `data/eval/replay-real/<scenario>/`: the events of the execution as JSON
lines and the manifest, with the hash of each part, the hash of the ledger the execution read and the provenance of
the recording. The provenance carries the name of the model, the moment of the capture, the commit of the code and
the kind of the capture, which is `real_model_recorded`. The key never reaches any of it: it stays in the file of
the environment of the machine that made the recording, and the redaction of the trace is the last wall before the
file is written.

What it refuses, and why:

- **It refuses to run offline.** An offline machine runs the scripted model and the recorded exchange rate, so a
  recording made there would carry the mode `live_agent` and the label would be a lie.
- **It refuses to run without a key.** A recording without a model is the recording of the other catalog.
- **It refuses to run on a dirty tracked tree**, because the recording names the commit it was made from and the
  claim has to be true.

The judge of the verdicts is the deterministic verifier of the repository, the same one that computes the verdicts
of the sandbox catalog. The reason is the verifier that ADR-073 published: it re-verifies a bundle offline, with
no model and with no network, and a bundle whose verdicts came from the model of the NLI could not be re-verified by
the code of the repository. The note of the manifest says which judge computed the verdicts, in words (ADR-075).

What a recording of this script is and is not: it is the recording of a real run, and it is not reproducible byte
for byte. The same question asked twice of a real model does not give the same answer, so the digests of this
catalog are the digests of that run and not the digests of a formula.

Usage:

```bash
uv run python scripts/capture_live_replay.py --scenario S01
uv run python scripts/capture_live_replay.py --all
uv run python scripts/capture_live_replay.py --all --out data/eval/replay-real
```

Exit code 0 when every requested scenario was recorded, 1 when one of them was refused.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ledgerlens import demo  # noqa: E402  (the path is set up before the import)
from ledgerlens.agents.integrator import build_integrator, investigate  # noqa: E402
from ledgerlens.agents.routing import (  # noqa: E402
    SLOT_AGENT,
    SLOT_POLICY,
    SLOT_SQL,
    SLOT_TRIAGE,
    budget_of,
    candidates_of,
    models_of,
    route,
)
from ledgerlens.api.accounts import scoped_ledger  # noqa: E402
from ledgerlens.byok.registry import ALLOWLIST, profiles_by_name  # noqa: E402
from ledgerlens.config import get_chat_model, get_settings, model_cascade  # noqa: E402
from ledgerlens.memory.long_term import CaseMemory, scenario_case_id  # noqa: E402
from ledgerlens.observability.trace_event import InMemoryTraceSink, TraceEventStream  # noqa: E402
from ledgerlens.replay.bundle import bundle_digest, write_bundle  # noqa: E402
from ledgerlens.replay.capture import (  # noqa: E402  (the path is set up before the import)
    CaptureError,
    account_that_holds,
    code_sha,
    ensure_clean_tree,
    planted_question,
    sha256_of,
)
from ledgerlens.run_context import POLICY_VERSION, SHIPPED_RUN_BUDGET, RunContext  # noqa: E402
from ledgerlens.sim.config import SimConfig  # noqa: E402
from ledgerlens.sim.pipeline import build_ledger  # noqa: E402
from ledgerlens.tools.fx import FxClient  # noqa: E402

__all__ = [
    "CAPTURE_KIND",
    "DEFAULT_OUT",
    "PUBLISHED_SCENARIOS",
    "capture",
    "main",
]

# The kind of the capture and the mode of the run: this is a recording of a real model, and the manifest says so.
CAPTURE_KIND = "real_model_recorded"
RUN_MODE = "live_agent"

# The folder of the catalog of the recordings of a real model, beside the folder of the sandbox catalog.
DEFAULT_OUT = ROOT / "data" / "eval" / "replay-real"

# The ten scenarios the catalog of the site publishes. The capture of this script records the same ten, so that
# the two catalogs can be compared scenario by scenario.
PUBLISHED_SCENARIOS = ("S01", "S02", "S03", "S04", "S07", "S08", "S09", "S10", "S11", "S13")

# The scenarios whose run has the reference source in fault: the scenario S11 is the scenario S01 with the source
# broken, and the recording is the proof that the agent then says less.
SCENARIO_FX_FAULT = {"S11": True}


def _deterministic_verifier(db_path: Path):
    """The verifier of the repository with the judge that the published bundles use.

    Why the judge is the deterministic one: the verifier that ADR-073 published re-verifies a bundle offline, with
    no model and with no network. A bundle whose verdicts came from the model of the NLI could not be re-verified by
    the code of the repository, and a catalog of claims is not a catalog of proofs (ADR-075).
    """
    from ledgerlens.verify import verify_result
    from ledgerlens.verify.nli import StubNli

    def verify(result):
        return verify_result(result, nli=StubNli(), ledger_db=db_path)

    return verify


def capture(scenario_id: str, catalog: Path, root: Path = ROOT) -> Path:
    """Runs the scenario with a real model and writes the bundle of the run.

    The capture names the commit it ran from and refuses to run on a dirty tracked tree, because the recording
    claims a commit and the claim has to be true. The refusal of an offline machine comes first: there the model
    would be the scripted one, and the label of the recording would be a lie.

    The whole catalog is left out of the check of the tree, and not only the folder of the scenario: this script
    records the ten scenarios of the catalog in one run, and the bundle that the first one wrote would otherwise
    block the second one. The catalog is the output of the capture, so what is in it is never part of the claim
    about the commit.
    """
    settings = get_settings()
    if settings.offline:
        raise SystemExit(
            "the capture of a real model refuses to run offline: an offline machine runs the scripted model and the "
            "recorded exchange rate, and the mode live_agent would be a lie. Set LEDGERLENS_OFFLINE to an empty "
            "value and provide a key."
        )
    if settings.openai_api_key is None:
        raise SystemExit(
            "the capture of a real model refuses to run without a key: the recording would be the recording of the "
            "other catalog. Put OPENAI_API_KEY in the file of the environment."
        )

    out = catalog / scenario_id.lower()
    try:
        ensure_clean_tree(root, catalog)
        commit = code_sha(root)
    except CaptureError as error:
        raise SystemExit(str(error)) from error

    manifest = demo.load_manifest()
    question, account_id = planted_question(manifest, scenario_id)

    # The router chooses the model of each slot by the task the slot does, and the decision is written down before
    # the run starts, because a run whose model changes in the middle is a run nobody can reason about (ADR-078).
    cascade = model_cascade(settings)
    candidates = candidates_of(cascade, profiles_by_name(ALLOWLIST))
    decisions = route(
        candidates,
        case_id=f"replay-real-{scenario_id.lower()}",
        case_type=scenario_id,
        budget=budget_of(SHIPPED_RUN_BUDGET),
    )
    models = models_of(decisions)
    # The profile the recording names is the model that wrote the answer, and not the model the environment names.
    # The two are the same when the deployment declares one model, and they differ as soon as the cascade has more
    # than one, and the recording has to say the truth in both cases.
    profile = models[SLOT_AGENT]

    with tempfile.TemporaryDirectory(prefix="ledgerlens_live_replay_") as work:
        work_root = Path(work)
        base = work_root / "ledger.db"
        build_ledger(SimConfig(source="sample"), base).conn.close()
        account_id = account_that_holds(manifest, scenario_id, base, work_root)
        account_db = scoped_ledger(base, account_id, work_root / "account.db")
        snapshot = sha256_of(account_db)

        run_id = f"replay-real-{scenario_id.lower()}"
        # The context declares the live mode, and the mode is only held down when the machine is offline. The
        # machine is not offline here, so the trace of the run carries the mode it really had.
        context = RunContext(
            run_id=run_id,
            session_id=run_id,
            mode=RUN_MODE,
            account_id=account_id,
            snapshot_sha256=snapshot,
            model_profile_id=profile or None,
            memory_dir=work_root / "memory",
        )
        memory = CaseMemory(context.resolve_memory_dir(), case_id=scenario_case_id(scenario_id))
        agent = build_integrator(
            get_chat_model(settings, model=models[SLOT_AGENT]),
            db_path=account_db,
            query_model=get_chat_model(settings, model=models[SLOT_SQL]),
            triage_model=get_chat_model(settings, model=models[SLOT_TRIAGE]),
            policy_model=get_chat_model(settings, model=models[SLOT_POLICY]),
            # The reference rate comes from the live source, because the live mode of the product asks the live
            # source, and a recording of the live mode that read the recorded rates would not be a recording of it.
            fx_client=FxClient(mode="live", fault=SCENARIO_FX_FAULT.get(scenario_id, False)),
            run_context=context,
            case_memory=memory,
            verifier=_deterministic_verifier(account_db),
            # The model of a retry is built by the deployment that holds the provider (ADR-084).
            fallback_factory=lambda name: get_chat_model(settings, model=name),
        )

        sink = InMemoryTraceSink()
        stream = TraceEventStream(run_id, sink, mode=RUN_MODE, snapshot_sha256=snapshot)
        investigate(agent, question, thread_id=run_id, on_event=stream.on_span)
        events = sink.read_from(run_id, after_seq=0, limit=10000)

        bundle = write_bundle(
            out,
            events,
            scenario=scenario_id,
            snapshot_sha256=snapshot,
            note=(
                f"Real execution of the scenario {scenario_id}, account {account_id}, with the model {profile} and "
                "the live reference rate. The work was split by the task: the triage and the rewrite of the search "
                f"of the policies ran on {models[SLOT_TRIAGE]}, the statement that reads the ledger ran on "
                f"{models[SLOT_SQL]} and the answer with the tools ran on {models[SLOT_AGENT]}. This is the "
                "recording of a real run and it is not reproducible byte for byte. The verdicts of the claims were "
                "computed by the deterministic verifier of the repository, the judge the sandbox catalog uses, "
                "so that anybody can re-verify this bundle offline."
            ),
            capture_kind=CAPTURE_KIND,
            recorded_at=datetime.now(UTC).isoformat(timespec="seconds"),
            model_profile=profile,
            model_profiles=models,
            code_sha=commit,
            policy_version=POLICY_VERSION,
        )
        print(f"bundle in {out}")
        print(f"events: {bundle.events}")
        print(f"sha256 of the manifest: {bundle_digest(out)}")
        return out


def main(argv: Sequence[str] | None = None) -> int:
    """Runs the capture of every requested scenario and returns the exit code of the answer."""
    parser = argparse.ArgumentParser(description="Captures the replay bundle of a scenario with a real model.")
    parser.add_argument("--scenario", default=None, help="identifier of the scenario to record")
    parser.add_argument("--all", action="store_true", help="records the ten scenarios the site publishes")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="folder of the catalog (data/eval/replay-real)")
    args = parser.parse_args(argv)

    scenarios = PUBLISHED_SCENARIOS if args.all else (args.scenario or "S01",)
    out_root = Path(args.out)

    for scenario_id in scenarios:
        try:
            capture(scenario_id, out_root)
        except SystemExit as refusal:
            print(f"capture_live_replay: {refusal}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
