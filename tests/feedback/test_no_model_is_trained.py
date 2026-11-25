"""No model is trained: the folder of the feedback holds no weight, and the modules import no training library.

What they guarantee, and why: the folder of the feedback holds no weight and no model artifact, and the
modules of `ledgerlens/feedback/` import no training library, because ADR-P007 keeps the runtime a single
agent with a deterministic verifier and makes a specialist model a controlled experiment behind a flag, and
this milestone ships the loop and the measurement, not the training.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FEEDBACK_DATA = ROOT / "data" / "eval" / "feedback"
FEEDBACK_CODE = ROOT / "ledgerlens" / "feedback"

# The shapes of a weight and of a model artifact: the files a training run would leave behind.
_WEIGHT_SUFFIXES = (".pt", ".pth", ".bin", ".safetensors", ".ckpt", ".onnx", ".gguf", ".h5")

# The libraries of the training of a model: a module of the feedback that imports one of them is a module that
# trains, and this milestone does not train.
_TRAINING_LIBRARIES = (
    "torch",
    "transformers",
    "tensorflow",
    "sklearn",
    "jax",
    "sentence_transformers",
    "peft",
    "trl",
)


def test_the_folder_of_the_feedback_holds_no_weight_and_no_model_artifact() -> None:
    """The loop ships the records and the sets, and no weight of a model."""
    if not FEEDBACK_DATA.is_dir():
        return
    for path in FEEDBACK_DATA.rglob("*"):
        if path.is_file():
            assert not path.name.lower().endswith(_WEIGHT_SUFFIXES), f"a weight under the feedback: {path}"


def test_the_modules_of_the_feedback_import_no_training_library() -> None:
    """A module of the loop that imports a training library is a module that trains, and none does."""
    for path in sorted(FEEDBACK_CODE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                for name in names:
                    root = name.split(".", 1)[0]
                    assert root not in _TRAINING_LIBRARIES, f"the module {path.name} imports {name}"
