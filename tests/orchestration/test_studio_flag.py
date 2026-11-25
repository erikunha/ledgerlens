"""The flag of the studio of the orchestration.

What they guarantee, and why: (a) the flag is off in the shipped configuration, because ADR-P007 keeps the runtime a
single agent with a deterministic verifier until a paired comparison measures a gain; (b) a run that asks for the
studio without a registered experiment is refused and the refusal names what is missing.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ledgerlens.config import Settings, get_settings
from ledgerlens.orchestration.studio import StudioRefused, open_studio, studio_manifest

ROOT = Path(__file__).resolve().parents[2]
COMPARISON = ROOT / "data" / "runtime" / "orchestration" / "comparison.json"


def test_the_flag_of_the_studio_is_off_in_the_shipped_configuration() -> None:
    """The runtime stays a single agent, because the comparison that would open the flag has not run."""
    assert Settings().orchestration_studio is False


def test_the_environment_reads_the_flag_of_the_studio() -> None:
    """The flag comes from the environment, like every other flag of the deployment."""
    settings = get_settings({"LEDGERLENS_ORCHESTRATION_STUDIO": "1"})

    assert settings.orchestration_studio is True


def test_a_run_that_asks_for_the_studio_with_the_flag_off_is_refused() -> None:
    """A flag that is off is a refusal with a reason, and the reason names the red line."""
    with pytest.raises(StudioRefused, match="ADR-P007"):
        open_studio(Settings(), path=COMPARISON)


def test_a_run_that_asks_for_the_studio_without_a_registered_experiment_is_refused() -> None:
    """The refusal names the experiment that is missing (SC-002)."""
    with pytest.raises(StudioRefused, match="no experiment of the studio is registered"):
        open_studio(
            Settings(orchestration_studio=True),
            path=ROOT / "data" / "runtime" / "orchestration" / "nothing.json",
        )


def test_the_manifest_of_the_registered_experiment_is_read_when_the_flag_is_on() -> None:
    """The studio opens for the experiment that was registered before it ran."""
    manifest = open_studio(Settings(orchestration_studio=True), path=COMPARISON)

    sections = {record["section"] for record in manifest["records"]}
    assert "experiment" in sections
    assert "rule" in sections


def test_the_manifest_of_a_missing_file_is_a_refusal() -> None:
    """A manifest that does not exist is a refusal and not an empty experiment."""
    with pytest.raises(StudioRefused, match="does not exist"):
        studio_manifest(ROOT / "data" / "runtime" / "orchestration" / "nothing.json")
