"""`scripts/build_index.py`: builds the policy index in a temporary folder, without downloading a model."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import zlib
from pathlib import Path

import numpy as np
import pytest

from ledgerlens import embeddings as emb
from ledgerlens.retrieval import load_policy_index, search_policy_index

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build_index.py"
POLICIES = Path(__file__).resolve().parents[2] / "data" / "policies"


def _load():
    spec = importlib.util.spec_from_file_location("build_index", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


build_index = _load()


class WordCountModel:
    def __init__(self, model_name: str, **kwargs: object) -> None:
        self.model_name = model_name

    @staticmethod
    def _vector(text: str) -> np.ndarray:
        vector = np.zeros(32, dtype=np.float32)
        for word in re.findall(r"\w+", text.lower()):
            vector[zlib.crc32(word.encode()) % 32] += 1.0
        return vector

    def passage_embed(self, texts, **kwargs):
        return (self._vector(t) for t in texts)

    def query_embed(self, query, **kwargs):
        return (self._vector(t) for t in ([query] if isinstance(query, str) else query))


@pytest.fixture(autouse=True)
def fake_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(emb, "_text_embedding_class", lambda: WordCountModel)


def test_main_builds_the_index_under_the_given_folder(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "index"
    assert build_index.main(["--policies", str(POLICIES), "--out", str(out)]) == 0
    folder = out / "policies_fastembed"
    meta = json.loads((folder / "index_meta.json").read_text())
    assert (folder / "index.faiss").is_file() and (folder / "index.pkl").is_file()
    assert meta["chunks"] > 100 and meta["dimension"] == 32
    printed = capsys.readouterr().out
    assert str(folder) in printed and f"{meta['chunks']} chunks" in printed
    store = load_policy_index(folder, emb.FastEmbedEmbeddings())
    assert search_policy_index(store, "processing fee on the gross volume", k=1)[0]["chunk_id"].startswith(
        "fees-and-pricing"
    )


def test_running_again_replaces_the_files_without_error(tmp_path: Path) -> None:
    args = ["--policies", str(POLICIES), "--out", str(tmp_path / "index")]
    assert build_index.main(args) == 0 and build_index.main(args) == 0


def test_the_default_output_is_the_configured_index_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEDGERLENS_INDEX_DIR", str(tmp_path / "configured"))
    assert build_index.main(["--policies", str(POLICIES)]) == 0
    assert (tmp_path / "configured" / "policies_fastembed" / "index.faiss").is_file()


def test_an_empty_policies_folder_is_an_error_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "policies").mkdir()
    assert build_index.main(["--policies", str(tmp_path / "policies"), "--out", str(tmp_path / "index")]) == 1
    assert "no policy documents" in capsys.readouterr().err
    assert not (tmp_path / "index").exists()


def test_a_missing_policies_folder_is_an_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert build_index.main(["--policies", str(tmp_path / "nope"), "--out", str(tmp_path / "index")]) == 1
    assert "nope" in capsys.readouterr().err
