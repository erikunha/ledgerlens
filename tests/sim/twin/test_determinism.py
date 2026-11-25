"""The determinism of the twin: three runs of the same configuration produce byte for byte equal manifests.

What they guarantee, and why: two runs of the same configuration with the seed 42 produce a byte for byte
equal manifest, and so does a third run with another hash seed of the interpreter, because the bytes of the
manifest do not depend on the machine that wrote them, and a manifest that changed between two equal runs
would be a manifest that says nothing.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from ledgerlens.sim.twin.config import TwinConfig
from ledgerlens.sim.twin.manifest import canonical_bytes
from ledgerlens.sim.twin.run import run_twin

ROOT = Path(__file__).resolve().parents[3]


def test_three_runs_of_the_same_configuration_produce_equal_manifests() -> None:
    """The run is deterministic in the seed, and the bytes of the manifest do not depend on the machine."""
    config = TwinConfig(seed=42)
    first = run_twin(config, truth_path=ROOT / "data" / "scenarios.json", commit="abc123")
    second = run_twin(config, truth_path=ROOT / "data" / "scenarios.json", commit="abc123")

    assert canonical_bytes(first.manifest) == canonical_bytes(second.manifest)


def test_a_run_with_another_hash_seed_of_the_interpreter_produces_the_same_bytes() -> None:
    """The bytes of the manifest do not depend on the hash seed of the interpreter."""
    code = (
        "from pathlib import Path\n"
        "from ledgerlens.sim.twin.config import TwinConfig\n"
        "from ledgerlens.sim.twin.manifest import canonical_bytes\n"
        "from ledgerlens.sim.twin.run import run_twin\n"
        "run = run_twin(TwinConfig(seed=42), truth_path=Path('data/scenarios.json'), commit='abc123')\n"
        "import sys\n"
        "sys.stdout.write(canonical_bytes(run.manifest).decode('utf-8'))\n"
    )
    outputs = []
    for hash_seed in ("0", "1"):
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = hash_seed
        env["LEDGERLENS_OFFLINE"] = "1"
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )
        outputs.append(proc.stdout)

    assert outputs[0] == outputs[1]
