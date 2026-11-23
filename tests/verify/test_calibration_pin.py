"""The pin of the calibration: the manifest it was measured over, the datasets it was measured on and the sweep.

Why it exists: the accuracy of the verifier of `ledgerlens/verify/thresholds.json` is a number over a file, and
without a pin nobody can tell whether the file is still the one the number came from. The pin names the sha256 of
the manifest of the datasets, the datasets with the role `tuning` that the sweep was measured over, the model that
measured it and the sweep that chose the thresholds.

This test is red on purpose between the moment the manifest of the disk changes and the moment the pin is
rewritten: that is exactly the drift the pin exists to catch, and a green test over a manifest that moved would
say the calibration was measured over a file that is not there anymore. The coordinator rewrites the pin with
`scripts/pin_calibration.py` before the commit, and then this test is green again.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from ledgerlens.eval.manifest import MANIFEST_PATH, load_manifests
from ledgerlens.verify.checks import load_thresholds
from ledgerlens.verify.nli import MODEL_ID

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "pin_calibration.py"


def _script() -> object:
    """The module of the script of the pin, loaded from the file of the repository."""
    spec = importlib.util.spec_from_file_location("pin_calibration", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _calibration() -> dict:
    """The calibration of the thresholds, with the pin the sweep and the pin script write."""
    return load_thresholds()["calibration"]


def test_the_pin_names_the_manifest_of_the_disk() -> None:
    """The sha256 the calibration names is the sha256 of the manifest file that is on the disk."""
    digest = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    pinned = _calibration()["tuning_manifest_sha256"]

    assert pinned == digest, (
        f"the calibration names the manifest {pinned} and the manifest of the disk is {digest}: the calibration was "
        "measured over another manifest. Rewrite the pin with `python scripts/pin_calibration.py` before the commit."
    )


def test_the_pin_names_the_datasets_of_the_role_tuning() -> None:
    """The list of the pin is the list of the datasets the manifest declares with the role `tuning`."""
    tuning = sorted(entry.dataset_id for entry in load_manifests() if entry.split_role == "tuning")

    assert _calibration()["tuning_datasets"] == tuning, (
        "the pin names another set of tuning datasets than the manifest does. Rewrite the pin with "
        "`python scripts/pin_calibration.py` before the commit."
    )


def test_the_pin_names_a_dataset_that_exists() -> None:
    """Every dataset the pin names is declared by the manifest, so the pin cannot name a set that is not there."""
    declared = {entry.dataset_id: entry for entry in load_manifests()}

    for dataset_id in _calibration()["tuning_datasets"]:
        assert dataset_id in declared, f"the pin names the dataset '{dataset_id}' and the manifest does not declare it."


def test_the_pin_names_no_dataset_that_may_not_be_tuned_against() -> None:
    """The pin names only the datasets with the role `tuning`, never a validation one and never a held out one."""
    declared = {entry.dataset_id: entry for entry in load_manifests()}

    for dataset_id in _calibration()["tuning_datasets"]:
        assert declared[dataset_id].split_role == "tuning", (
            f"the pin names the dataset '{dataset_id}' and its role is '{declared[dataset_id].split_role}', so the "
            "calibration would be measured over a set that may not be tuned against."
        )


def test_the_pin_names_the_model_and_the_sweep_that_chose_the_thresholds() -> None:
    """The pin names the model of the sweep and the sweep itself, so a reader can reproduce the numbers."""
    calibration = _calibration()
    model = calibration["nli_model"]
    sweep = calibration["sweep_log"]

    assert model["model"] == MODEL_ID
    assert model["revision"], "the model id does not pin the weights, so the pin has to name the revision."
    assert sweep["file"] == "docs/decisions/ADR-007-nli-verification.md"
    assert sweep["section"]
    assert "scripts/sweep_nli_thresholds.py" in sweep["command"]


def test_the_pin_writes_the_revision_that_the_file_already_records(tmp_path: Path) -> None:
    """The revision the pin writes is the one the file records, because the file is the only source of it.

    Why it matters: the loader of the model asks for the revision that the file records, so a pin written with
    another revision would make the loader ask for the weights of one day while the file claims the calibration of
    the weights of another day. A second copy of the value in the script is a value that can drift away from the one
    the loader asks for, and the drift is invisible until a measurement is not reproducible (ADR-069).
    """
    module = _script()
    copy = tmp_path / "thresholds.json"
    copy.write_text((ROOT / "ledgerlens" / "verify" / "thresholds.json").read_text(encoding="utf-8"), encoding="utf-8")
    revision = json.loads(copy.read_text(encoding="utf-8"))["calibration"]["nli_model"]["revision"]

    code = module.main(["--root", str(ROOT), "--thresholds", str(copy)])

    assert code == 0
    assert json.loads(copy.read_text(encoding="utf-8"))["calibration"]["nli_model"]["revision"] == revision
    assert not hasattr(module, "NLI_REVISION"), (
        "the script holds a copy of the revision of the weights, and a second copy is a value that can drift away "
        "from the one the loader asks for."
    )


def test_the_pin_refuses_when_no_revision_is_known(tmp_path: Path) -> None:
    """A file that records no revision and no argument is a refusal, and nothing is written.

    Why it matters: the commit of the weights that the calibration was measured with is not a value the script may
    invent. A pin written with a revision nobody gave would claim a calibration over weights that were never used
    (ADR-069).
    """
    module = _script()
    copy = tmp_path / "thresholds.json"
    text = (ROOT / "ledgerlens" / "verify" / "thresholds.json").read_text(encoding="utf-8")
    raw = json.loads(text)
    del raw["calibration"]["nli_model"]["revision"]
    copy.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    before = copy.read_text(encoding="utf-8")

    code = module.main(["--root", str(ROOT), "--thresholds", str(copy)])

    assert code == 1
    assert copy.read_text(encoding="utf-8") == before, "the file was written even though the revision was unknown."


def test_the_pin_writes_the_revision_that_the_argument_gives(tmp_path: Path) -> None:
    """The argument `--nli-revision` writes the revision that the caller gives, over the one of the file.

    Why it matters: the argument is how the coordinator pins the weights of a calibration that was measured over
    another revision, without a second copy of the value in the script (ADR-069).
    """
    module = _script()
    copy = tmp_path / "thresholds.json"
    copy.write_text((ROOT / "ledgerlens" / "verify" / "thresholds.json").read_text(encoding="utf-8"), encoding="utf-8")

    code = module.main(["--root", str(ROOT), "--thresholds", str(copy), "--nli-revision", "0" * 40])

    assert code == 0
    assert json.loads(copy.read_text(encoding="utf-8"))["calibration"]["nli_model"]["revision"] == "0" * 40
