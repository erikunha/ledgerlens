"""The flag of the laboratory: off in the shipped configuration, and the traces of the exercises readable offline.

What they guarantee, and why: (a) the flag of the laboratory is off in the shipped configuration, because the
laboratory is a research feature and its output is a trace and a published page, never a route a stranger may
call; (b) the traces of the exercises are readable offline with no key, because a reader may look at the
attacks and at the layers that answered them without spending the money of anybody.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from ledgerlens.adversarial.exercises import exercise_of
from ledgerlens.adversarial.runner import run_exercise
from ledgerlens.config import Settings, get_settings


def test_the_flag_of_the_laboratory_is_off_in_the_shipped_configuration() -> None:
    """The laboratory is a research feature, and the shipped configuration keeps it off."""
    assert Settings().adversarial_lab is False


def test_the_environment_reads_the_flag_of_the_laboratory() -> None:
    """The flag comes from the environment, like every other flag of the deployment."""
    settings = get_settings({"LEDGERLENS_ADVERSARIAL_LAB": "1"})

    assert settings.adversarial_lab is True


def test_the_traces_of_the_exercises_are_readable_offline_with_no_key(tmp_path) -> None:
    """A reader may look at the attacks and at the layers that answered them, with no key."""
    result = run_exercise(exercise_of("s09-injected-note"), work_dir=tmp_path)

    assert result.events
    for event in result.events:
        assert event.payload["reason"]
