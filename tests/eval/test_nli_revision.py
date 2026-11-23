"""The revision of the NLI weights that the loader asks for.

Why it exists: the calibration of the thresholds of the verifier names the model and the commit of the weights it
used, `ledgerlens/verify/thresholds.json` records it under `calibration.nli_model`, and the loader of
`ledgerlens/verify/nli.py` used to ask the hub for the `main` branch of the model. A number measured on one day and
the same number measured on another day are then two measurements, and the repository publishes numbers. The revision
is read from the file that already records it, so the two cannot drift, and these tests prove that the loader asks
for it and that the code holds no second copy of the value.

The loader is exercised with a stand-in of `transformers` and of `torch`, so the test never downloads the model and
never loads it: what is under test is the call that the loader makes, not the weights it downloads.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

import ledgerlens.verify.nli as nli_module
from ledgerlens.verify.nli import MODEL_ID, HuggingFaceNli, nli_revision

ROOT = Path(__file__).resolve().parents[2]
THRESHOLDS_PATH = ROOT / "ledgerlens" / "verify" / "thresholds.json"

__all__ = [
    "test_the_loader_asks_for_the_revision_that_the_calibration_pinned",
    "test_the_revision_is_read_from_the_thresholds_file_and_not_written_in_the_code",
    "test_the_thresholds_that_pin_the_weights_name_the_model_of_the_loader",
]


def _recorded() -> dict[str, str]:
    """The model and the revision that the calibration of the thresholds recorded."""
    thresholds = json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))
    nli_model = thresholds["calibration"]["nli_model"]
    return {"model": nli_model["model"], "revision": nli_model["revision"]}


def test_the_revision_is_read_from_the_thresholds_file_and_not_written_in_the_code() -> None:
    """The revision of the weights comes from the file that records it, and the code holds no second copy.

    Why it matters: a literal in the code is a second copy of a value that a calibration chose, and two copies drift.
    The file that names the commit is the one the calibration wrote, so the loader reads it at run time.
    """
    recorded = _recorded()

    assert nli_revision() == recorded["revision"], (
        "the revision that the loader asks for is not the one that the calibration of the thresholds recorded"
    )

    source = Path(nli_module.__file__).read_text(encoding="utf-8")
    assert recorded["revision"] not in source, (
        "the revision is written in the code of the loader, so it can drift from the thresholds file"
    )


def test_the_thresholds_that_pin_the_weights_name_the_model_of_the_loader() -> None:
    """The revision belongs to the model that the loader loads, and not to another one."""
    recorded = _recorded()

    assert recorded["model"] == MODEL_ID
    assert nli_revision(MODEL_ID) == recorded["revision"]


def test_the_loader_asks_for_the_revision_that_the_calibration_pinned(monkeypatch: pytest.MonkeyPatch) -> None:
    """The weights are loaded from the pinned commit and not from the branch of the hub.

    Why it matters: the branch of the hub moves, and a measurement made with the weights of one day and a measurement
    made with the weights of another day are two measurements. The commit is what makes the measurement of one day and
    the measurement of another day the same measurement.
    """
    recorded = _recorded()
    calls: list[tuple[str, str, dict[str, object]]] = []

    class FakeTokenizer:
        """A tokenizer that records the call and does nothing."""

        @classmethod
        def from_pretrained(cls, model_id: str, **kwargs: object) -> FakeTokenizer:
            calls.append(("tokenizer", model_id, kwargs))
            return cls()

    class FakeModel:
        """A model that records the call and does nothing."""

        config = types.SimpleNamespace(id2label={0: "entailment", 1: "neutral", 2: "contradiction"})

        @classmethod
        def from_pretrained(cls, model_id: str, **kwargs: object) -> FakeModel:
            calls.append(("model", model_id, kwargs))
            return cls()

        def to(self, device: str) -> FakeModel:
            return self

        def eval(self) -> FakeModel:
            return self

    transformers = types.ModuleType("transformers")
    transformers.AutoTokenizer = FakeTokenizer  # type: ignore[attr-defined]
    transformers.AutoModelForSequenceClassification = FakeModel  # type: ignore[attr-defined]
    torch = types.ModuleType("torch")
    torch.set_num_threads = lambda count: None  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    monkeypatch.setitem(sys.modules, "torch", torch)

    HuggingFaceNli()._load()

    assert calls, "the loader did not ask for the weights at all"
    for what, model_id, kwargs in calls:
        assert model_id == MODEL_ID
        assert kwargs.get("revision") == recorded["revision"], (
            f"the {what} was loaded without the pinned revision of the calibration"
        )
