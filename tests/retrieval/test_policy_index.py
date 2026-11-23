"""The digest of the corpus of the policies: the index carries it and the loader refuses a stale index.

Why these tests exist: a policy edited in the repository kept being answered from the index that was built
before the edit, silently. Every other test of the suite stayed green, the manifest of the datasets stayed
green and the answer was the text of a version of the policy that was not on the disk anymore. The digest of
the corpus is what makes that visible: the meta of the index names the corpus it was built from, the loader
refuses an index that does not describe the policies of the disk, and the gate refuses a repository whose
committed index and committed policies disagree.

The tests use a fake vector model (words become counts, no download), so they run offline in milliseconds.
The check of the gate is loaded as a module, the way `tests/tools/test_build_index.py` loads the builder.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
import zlib
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from ledgerlens import embeddings as emb
from ledgerlens import retrieval
from ledgerlens.embeddings import FastEmbedEmbeddings
from ledgerlens.retrieval import (
    IndexStale,
    build_policy_index,
    corpus_digest,
    index_dir_for,
    load_policy_documents,
    load_policy_index,
)

REPO = Path(__file__).resolve().parents[2]
POLICIES = REPO / "data" / "policies"
COMMITTED = REPO / "data" / "index" / "policies_fastembed"
SCRIPT = REPO / "scripts" / "check_policy_index.py"
DIM = 64
POLICY = "refund-policy.md"


class WordCountModel:
    """Stands in for fastembed's `TextEmbedding`: each word adds 1 at a fixed position out of 64."""

    def __init__(self, model_name: str, **kwargs: object) -> None:
        self.model_name = model_name

    @staticmethod
    def _vector(text: str) -> np.ndarray:
        vector = np.zeros(DIM, dtype=np.float32)
        for word in re.findall(r"\w+", text.lower()):
            vector[zlib.crc32(word.encode()) % DIM] += 1.0
        return vector

    def passage_embed(self, texts, **kwargs):
        return (self._vector(t) for t in texts)

    def query_embed(self, query, **kwargs):
        return (self._vector(t) for t in ([query] if isinstance(query, str) else query))


@pytest.fixture
def embeddings(monkeypatch: pytest.MonkeyPatch) -> FastEmbedEmbeddings:
    """The active embedding with the fake model behind it: no download, no network."""
    monkeypatch.setattr(emb, "_text_embedding_class", lambda: WordCountModel)
    return FastEmbedEmbeddings()


def _load_script() -> Any:
    """The check of the gate, loaded as a module so the test can call its entry point."""
    spec = importlib.util.spec_from_file_location("check_policy_index", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


check_policy_index = _load_script()


def _corpus(tmp_path: Path) -> Path:
    """A copy of the policies of the repository, so a test can edit a byte without touching the repository."""
    folder = tmp_path / "policies"
    shutil.copytree(POLICIES, folder)
    return folder


def _edit_a_byte(folder: Path) -> None:
    """Change one word of one policy, in place, without adding or removing a file."""
    path = folder / POLICY
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("30 calendar days", "31 calendar days"), encoding="utf-8")


# --- the digest of the corpus ---------------------------------------------------------------------


def test_the_digest_does_not_depend_on_the_order_of_the_files(tmp_path: Path) -> None:
    """The same files in another order are the same corpus, so they hash to the same digest."""
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    names = ["alpha.md", "beta.md", "gamma.md"]
    for name in names:
        (first / name).write_text(f"# {name}\n", encoding="utf-8")
    for name in reversed(names):  # the other folder is written in the other order
        (second / name).write_text(f"# {name}\n", encoding="utf-8")

    assert corpus_digest(first) == corpus_digest(second)


def test_a_different_corpus_has_a_different_digest(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "alpha.md").write_text("# alpha\n", encoding="utf-8")
    (second / "alpha.md").write_text("# alpha\n", encoding="utf-8")
    assert corpus_digest(first) == corpus_digest(second)

    (second / "alpha.md").write_text("# alpha changed\n", encoding="utf-8")
    assert corpus_digest(first) != corpus_digest(second)


def test_the_digest_moves_when_a_byte_moves_when_a_file_is_added_and_when_it_is_removed(tmp_path: Path) -> None:
    folder = tmp_path / "policies"
    folder.mkdir()
    (folder / "alpha.md").write_text("# alpha\n", encoding="utf-8")
    before = corpus_digest(folder)

    (folder / "alpha.md").write_text("# alpha!\n", encoding="utf-8")
    after_edit = corpus_digest(folder)
    assert after_edit != before, "the digest must move when a byte of a policy moves"

    (folder / "beta.md").write_text("# beta\n", encoding="utf-8")
    after_add = corpus_digest(folder)
    assert after_add != after_edit, "the digest must move when a file is added"

    (folder / "beta.md").unlink()
    assert corpus_digest(folder) == after_edit, "the digest must come back when the file is removed"


def test_the_digest_is_reproducible_by_hand(tmp_path: Path) -> None:
    """The digest is the sha256 of a text a reader can write down, so it can be checked with sha256sum."""
    import hashlib

    folder = tmp_path / "policies"
    folder.mkdir()
    (folder / "alpha.md").write_bytes(b"# alpha\n")
    (folder / "beta.md").write_bytes(b"# beta\n")
    canonical = (
        f"alpha.md:{hashlib.sha256(b'# alpha\n').hexdigest()}\nbeta.md:{hashlib.sha256(b'# beta\n').hexdigest()}\n"
    )
    assert corpus_digest(folder) == hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# --- the refusal of a stale index -----------------------------------------------------------------


def test_a_policy_edited_after_the_build_makes_the_loader_refuse(
    tmp_path: Path, embeddings: FastEmbedEmbeddings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The index was built from another corpus, so the loader refuses it instead of answering with the old text."""
    corpus = _corpus(tmp_path)
    folder = index_dir_for(tmp_path / "index", embeddings)
    meta = build_policy_index(load_policy_documents(corpus), embeddings, folder, policies_dir=corpus)
    built = meta["corpus_sha256"]

    _edit_a_byte(corpus)
    current = corpus_digest(corpus)
    assert built != current, "the digest of the meta must move when the policy moves"

    class ForbiddenFaiss:
        """Stands in for FAISS: the loader must refuse before it opens the store."""

        @staticmethod
        def load_local(*args: object, **kwargs: object) -> None:
            raise AssertionError("the store must never be loaded")

    monkeypatch.setattr(retrieval, "FAISS", ForbiddenFaiss)

    with pytest.raises(IndexStale) as refusal:
        load_policy_index(folder, embeddings, policies_dir=corpus)

    message = str(refusal.value)
    assert built in message, "the refusal must name the digest the index was built from"
    assert current in message, "the refusal must name the digest the corpus has now"
    assert isinstance(refusal.value, RuntimeError), "the refusal is a refusal, not a wrong answer"


def test_an_index_of_the_corpus_of_the_disk_is_accepted(tmp_path: Path, embeddings: FastEmbedEmbeddings) -> None:
    corpus = _corpus(tmp_path)
    folder = index_dir_for(tmp_path / "index", embeddings)
    build_policy_index(load_policy_documents(corpus), embeddings, folder, policies_dir=corpus)

    store = load_policy_index(folder, embeddings, policies_dir=corpus)
    assert store.index.ntotal > 0


def test_the_meta_carries_the_digest_of_the_corpus_it_was_built_from(
    tmp_path: Path, embeddings: FastEmbedEmbeddings
) -> None:
    corpus = _corpus(tmp_path)
    folder = index_dir_for(tmp_path / "index", embeddings)
    meta = build_policy_index(load_policy_documents(corpus), embeddings, folder, policies_dir=corpus)
    written = json.loads((folder / "index_meta.json").read_text(encoding="utf-8"))
    assert written["corpus_sha256"] == meta["corpus_sha256"] == corpus_digest(corpus)


# --- the check of the gate ------------------------------------------------------------------------


def test_the_check_of_the_gate_is_green_on_the_committed_tree() -> None:
    """The committed index describes the committed policies, so the check of the gate passes."""
    assert check_policy_index.main([]) == 0


def test_the_check_of_the_gate_refuses_a_tree_whose_policy_was_edited(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path)
    index = tmp_path / "index"
    shutil.copytree(COMMITTED, index)
    before = {p.name: p.read_bytes() for p in index.iterdir()}

    _edit_a_byte(corpus)
    assert check_policy_index.main(["--policies", str(corpus), "--index", str(index)]) == 1

    after = {p.name: p.read_bytes() for p in index.iterdir()}
    assert after == before, "the check writes nothing"
    assert {p.name for p in corpus.iterdir()} == {p.name for p in POLICIES.iterdir()}, "the check writes nothing"


def test_the_check_of_the_gate_refuses_a_meta_without_the_digest(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path)
    index = tmp_path / "index"
    shutil.copytree(COMMITTED, index)
    meta_file = index / "index_meta.json"
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    del meta["corpus_sha256"]
    meta_file.write_text(json.dumps(meta), encoding="utf-8")

    assert check_policy_index.main(["--policies", str(corpus), "--index", str(index)]) == 1


# --- the committed index ---------------------------------------------------------------------------


def test_the_committed_meta_carries_the_digest_of_the_committed_corpus() -> None:
    """The constant of the repository cannot drift from the files of the repository without a red test."""
    meta = json.loads((COMMITTED / "index_meta.json").read_text(encoding="utf-8"))
    assert "corpus_sha256" in meta, "the meta of the committed index must carry the digest of the corpus"
    assert meta["corpus_sha256"] == corpus_digest(POLICIES)
