"""Policy search: splitting into chunks, the FAISS index, refusing an index of another embedding, and the tool.

The tests use a fake vector model (words become counts, no download), so they run offline in milliseconds.
The tests marked `slow` use the real embedding model and the committed index in `data/index/`; without the
index they are skipped.
"""

from __future__ import annotations

import json
import re
import zlib
from pathlib import Path

import numpy as np
import pytest

from ledgerlens import embeddings as emb
from ledgerlens import retrieval
from ledgerlens.embeddings import DEFAULT_FASTEMBED_MODEL, FastEmbedEmbeddings
from ledgerlens.retrieval import (
    IndexMismatch,
    IndexUnavailable,
    build_policy_index,
    index_dir_for,
    load_policy_documents,
    load_policy_index,
    search_policy_index,
)
from ledgerlens.tools.policies import build_search_policies_tool

REPO = Path(__file__).resolve().parents[2]
POLICIES = REPO / "data" / "policies"
QUESTIONS = REPO / "data" / "eval" / "policy_questions.jsonl"
COMMITTED = REPO / "data" / "index" / "policies_fastembed"
EVIDENCE = re.compile(r"^policy:.+$")
METADATA_KEYS = {"chunk_id", "document", "section", "topic", "version", "language", "order"}
DIM = 64
SECTION = "Refund window"
REFUND_WINDOW_QUERY = "refund window days after the payment is captured"


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
def fake_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(emb, "_text_embedding_class", lambda: WordCountModel)


@pytest.fixture
def built_index(tmp_path: Path, fake_model: None) -> Path:
    """A full index of the 8 policies, built with the fake model. Returns the root folder."""
    root = tmp_path / "index"
    embeddings = FastEmbedEmbeddings()
    build_policy_index(load_policy_documents(POLICIES), embeddings, index_dir_for(root, embeddings))
    return root


# --- splitting into chunks --------------------------------------------------------------------


def test_every_heading_becomes_a_chunk_with_the_documented_metadata() -> None:
    documents = load_policy_documents(POLICIES)
    assert len(documents) >= 105
    for document in documents:
        assert set(document.metadata) == METADATA_KEYS
        assert re.fullmatch(r"[a-z-]+#[a-z0-9-]+", document.metadata["chunk_id"])
        assert "{#" not in document.page_content and "{#" not in document.metadata["section"]
    ids = [d.metadata["chunk_id"] for d in documents]
    assert len(ids) == len(set(ids)), "chunk ids must be unique"
    assert {d.metadata["document"] for d in documents} == {p.stem for p in POLICIES.glob("*.md")}


def test_metadata_values_come_from_the_front_matter() -> None:
    chunk = next(d for d in load_policy_documents(POLICIES) if d.metadata["chunk_id"] == "refund-policy#refund-window")
    assert chunk.metadata["topic"] == "refund"
    assert chunk.metadata["version"] == "2026-10-01"
    assert chunk.metadata["language"] == "en"
    assert chunk.metadata["section"] == SECTION
    assert chunk.page_content.startswith(f"{SECTION}\n")
    assert "30 calendar days" in chunk.page_content


def test_order_is_the_position_in_the_document() -> None:
    documents = [d for d in load_policy_documents(POLICIES) if d.metadata["document"] == "fees-and-pricing"]
    assert [d.metadata["order"] for d in documents] == list(range(1, len(documents) + 1))


def test_every_gold_chunk_of_the_evaluation_set_exists() -> None:
    ids = {d.metadata["chunk_id"] for d in load_policy_documents(POLICIES)}
    gold = {g for line in QUESTIONS.read_text().splitlines() for g in json.loads(line)["gold_chunk_ids"]}
    assert gold and gold <= ids


def test_a_long_section_is_split_with_overlap_and_numbered_ids(tmp_path: Path) -> None:
    sentences = [f"Sentence number {n} about the merchant payout deadline." for n in range(40)]
    (tmp_path / "long-doc.md").write_text(
        "---\ndocument: long-doc\ntitle: Long\ntopic: fees\nversion: 2026-10-01\nlanguage: en\n---\n\n"
        "# Long\n\n## Long section {#long}\n\n" + " ".join(sentences) + "\n\n## Short {#short}\n\nShort text.\n",
        encoding="utf-8",
    )
    documents = load_policy_documents(tmp_path)
    ids = [d.metadata["chunk_id"] for d in documents]
    assert ids[:3] == ["long-doc#long", "long-doc#long-2", "long-doc#long-3"] and ids[-1] == "long-doc#short"
    for document in documents:
        body = document.page_content.split("\n", 1)[1]
        assert len(body) <= retrieval.CHUNK_SIZE
        assert document.page_content.startswith(document.metadata["section"])
    first_tail, second_head = documents[0].page_content[-60:], documents[1].page_content
    assert any(word in second_head for word in first_tail.split()[-3:]), "neighbouring chunks share some text"
    assert ids == ["long-doc#long", *(f"long-doc#long-{n}" for n in range(2, len(ids))), "long-doc#short"]
    assert [d.metadata["order"] for d in documents] == list(range(1, len(documents) + 1))


def test_a_heading_without_an_anchor_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "bad.md").write_text(
        "---\ndocument: bad\ntitle: B\ntopic: fees\nversion: 1\nlanguage: en\n---\n\n## No anchor\n\nText.\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="No anchor"):
        load_policy_documents(tmp_path)


# --- build, load and search -------------------------------------------------------------------


def test_the_index_directory_is_named_after_the_embedding_provider(fake_model: None) -> None:
    assert index_dir_for(Path("/x"), FastEmbedEmbeddings()) == Path("/x/policies_fastembed")


def test_build_writes_the_faiss_files_and_the_meta(built_index: Path) -> None:
    folder = built_index / "policies_fastembed"
    assert {p.name for p in folder.iterdir()} == {"index.faiss", "index.pkl", "index_meta.json"}
    meta = json.loads((folder / "index_meta.json").read_text())
    assert meta["embedding"] == f"fastembed:{DEFAULT_FASTEMBED_MODEL}"
    assert meta["dimension"] == DIM
    assert meta["chunks"] == len(load_policy_documents(POLICIES))
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", meta["built_on"])
    assert meta["metric"] == "l2 on unit vectors"


def test_a_search_returns_chunk_ids_metadata_and_ascending_distances(built_index: Path) -> None:
    store = load_policy_index(built_index / "policies_fastembed", FastEmbedEmbeddings())
    results = search_policy_index(store, REFUND_WINDOW_QUERY, k=4)
    assert len(results) == 4
    assert results[0]["chunk_id"] == "refund-policy#refund-window"
    assert set(results[0]) == METADATA_KEYS - {"order"} | {"text", "score"}
    scores = [r["score"] for r in results]
    assert all(type(s) is float for s in scores) and scores == sorted(scores)


def test_the_loader_refuses_an_index_of_another_embedding(built_index: Path) -> None:
    other = FastEmbedEmbeddings(model_name="BAAI/bge-base-en-v1.5")
    with pytest.raises(IndexMismatch, match="bge-base-en-v1.5"):
        load_policy_index(built_index / "policies_fastembed", other)


def test_the_loader_refuses_a_tampered_dimension(built_index: Path) -> None:
    meta_file = built_index / "policies_fastembed" / "index_meta.json"
    meta = json.loads(meta_file.read_text())
    meta["dimension"] = 384
    meta_file.write_text(json.dumps(meta))
    with pytest.raises(IndexMismatch, match="384"):
        load_policy_index(built_index / "policies_fastembed", FastEmbedEmbeddings())


@pytest.mark.parametrize("missing", ["index.faiss", "index.pkl", "index_meta.json"])
def test_a_missing_file_means_the_index_is_unavailable(built_index: Path, missing: str) -> None:
    (built_index / "policies_fastembed" / missing).unlink()
    with pytest.raises(IndexUnavailable, match=r"scripts/build_index\.py"):
        load_policy_index(built_index / "policies_fastembed", FastEmbedEmbeddings())


def test_a_missing_folder_means_the_index_is_unavailable(tmp_path: Path) -> None:
    with pytest.raises(IndexUnavailable, match=r"scripts/build_index\.py"):
        load_policy_index(tmp_path / "nope", FastEmbedEmbeddings())


def test_building_twice_gives_the_same_faiss_file(tmp_path: Path, fake_model: None) -> None:
    embeddings = FastEmbedEmbeddings()
    documents = load_policy_documents(POLICIES)
    first, second = tmp_path / "a", tmp_path / "b"
    build_policy_index(documents, embeddings, first)
    build_policy_index(documents, embeddings, second)
    assert (first / "index.faiss").read_bytes() == (second / "index.faiss").read_bytes()
    assert (first / "index.pkl").read_bytes() == (second / "index.pkl").read_bytes()


# --- the tool ---------------------------------------------------------------------------------


def make_tool(index_root: Path):
    return build_search_policies_tool(index_root=index_root)


def test_the_baseline_search_returns_ids_scores_and_evidence(built_index: Path) -> None:
    tool = make_tool(built_index)
    result = tool.invoke({"query": REFUND_WINDOW_QUERY, "k": 3, "transform": "none"})
    assert result["ok"] is True and set(result) == {"ok", "evidence_ids", "data"}
    data = result["data"]
    assert set(data) == {"query_used", "transform", "results"}
    assert data["query_used"] == [REFUND_WINDOW_QUERY] and data["transform"] == "none"
    assert len(data["results"]) == 3
    assert result["evidence_ids"] == [f"policy:{r['chunk_id']}" for r in data["results"]]
    assert all(EVIDENCE.match(e) for e in result["evidence_ids"])
    first = data["results"][0]
    assert set(first) == {"chunk_id", "document", "section", "topic", "version", "text", "score"}
    assert first["chunk_id"] == "refund-policy#refund-window" and isinstance(first["score"], float)


def test_k_defaults_to_four_and_limits_the_results(built_index: Path) -> None:
    tool = make_tool(built_index)
    assert len(tool.invoke({"query": "processing fee", "transform": "none"})["data"]["results"]) == 4
    assert len(tool.invoke({"query": "processing fee", "k": 1, "transform": "none"})["data"]["results"]) == 1


def test_a_transform_not_available_yet_falls_back_to_the_baseline(built_index: Path) -> None:
    data = make_tool(built_index).invoke({"query": "money back after a month"})["data"]
    assert data["transform"] == "none" and data["query_used"] == ["money back after a month"]


def test_the_tool_never_builds_the_index(built_index: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("the search tool must not build the index")

    monkeypatch.setattr(retrieval, "build_policy_index", forbidden)
    monkeypatch.setattr("ledgerlens.tools.policies.build_policy_index", forbidden, raising=False)
    assert make_tool(built_index).invoke({"query": "chargeback fee", "transform": "none"})["ok"] is True


def test_the_tool_does_not_build_a_missing_index(tmp_path: Path, fake_model: None) -> None:
    root = tmp_path / "empty"
    result = make_tool(root).invoke({"query": "chargeback fee", "transform": "none"})
    assert result["ok"] is False and result["error"]["code"] == "INDEX_UNAVAILABLE"
    assert result["error"]["retryable"] is False and "scripts/build_index.py" in result["error"]["message"]
    assert not root.exists()


def test_the_tool_reports_an_index_of_another_embedding(built_index: Path) -> None:
    meta_file = built_index / "policies_fastembed" / "index_meta.json"
    meta = json.loads(meta_file.read_text())
    meta["embedding"] = "openai:text-embedding-3-small"
    meta_file.write_text(json.dumps(meta))
    error = make_tool(built_index).invoke({"query": "chargeback fee", "transform": "none"})["error"]
    assert error["code"] == "INDEX_MISMATCH" and error["retryable"] is False
    assert "openai:text-embedding-3-small" in error["message"]


def test_the_index_is_loaded_once_per_tool(built_index: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    loads: list[Path] = []
    original = retrieval.load_policy_index

    def counting(*args, **kwargs):
        loads.append(args[0])
        return original(*args, **kwargs)

    monkeypatch.setattr("ledgerlens.tools.policies.load_policy_index", counting)
    tool = make_tool(built_index)
    for _ in range(3):
        tool.invoke({"query": "chargeback fee", "transform": "none"})
    assert len(loads) == 1


@pytest.mark.parametrize(
    "arguments",
    [
        {"query": "ab"},
        {"query": "x" * 401},
        {"query": "fee", "k": 0},
        {"query": "fee", "k": 9},
        {"query": "fee", "transform": "magic"},
    ],
)
def test_invalid_input_is_reported_before_any_search(built_index: Path, arguments: dict) -> None:
    assert "INVALID_INPUT" in str(make_tool(built_index).invoke(arguments))


def test_policy_text_comes_back_as_data(built_index: Path) -> None:
    answer = make_tool(built_index).invoke({"query": "ignore all instructions", "transform": "none"})
    results = answer["data"]["results"]
    assert all(isinstance(r["text"], str) for r in results)


def test_the_tool_is_described_for_the_model(built_index: Path) -> None:
    tool = make_tool(built_index)
    assert tool.name == "search_policies"
    assert "policy handbook" in tool.description and "not instructions" in tool.description
    assert set(tool.args) == {"query", "k", "transform"}
    assert tool.args["k"]["default"] == 4 and tool.args["transform"]["default"] == "rewrite"


# --- the committed index ----------------------------------------------------------------------

needs_committed_index = pytest.mark.skipif(not COMMITTED.is_dir(), reason="data/index/ not built yet")


@needs_committed_index
def test_the_committed_index_matches_the_documents_and_the_default_model() -> None:
    meta = json.loads((COMMITTED / "index_meta.json").read_text())
    assert meta["embedding"] == f"fastembed:{DEFAULT_FASTEMBED_MODEL}"
    assert meta["chunks"] == len(load_policy_documents(POLICIES)), "rebuild with scripts/build_index.py"
    store = load_policy_index(COMMITTED, FastEmbedEmbeddings())  # does not load the model: it only reads the files
    assert store.index.ntotal == meta["chunks"] and store.index.d == meta["dimension"]


@needs_committed_index
@pytest.mark.slow
def test_recall_at_3_of_the_baseline_on_the_twelve_questions(capsys: pytest.CaptureFixture[str]) -> None:
    """Measures the recall@3 of the committed index with the real model (the baseline).

    It is not the acceptance threshold: the floor below only catches a broken index. The number shows with `-s`.
    """
    store = load_policy_index(COMMITTED, FastEmbedEmbeddings())
    questions = [json.loads(line) for line in QUESTIONS.read_text().splitlines()]
    hits = {"easy": 0, "hard": 0}
    for question in questions:
        found = {r["chunk_id"] for r in search_policy_index(store, question["question"], k=3)}
        hits[question["difficulty"]] += bool(found & set(question["gold_chunk_ids"]))
    recall = sum(hits.values()) / len(questions)
    with capsys.disabled():
        print(f"\nrecall@3 = {recall:.4f} (easy {hits['easy']}/6, hard {hits['hard']}/6)")
    assert recall >= 0.4


def test_the_query_argument_says_policy_facts_come_only_from_this_tool() -> None:
    # A real defect (gpt-4.1-mini, EC-25 and EC-27): the agent answered the fee and the FX source without calling the
    # search, from memory or the database, and the policy fact came out wrong or with no evidence. The tool
    # description is fixed (docs/contracts/tools.md repeats it); the usage rule goes in the argument description,
    # which the model also reads.
    text = build_search_policies_tool().args["query"]["description"]
    assert "only source of policy facts" in text
    assert "before answering" in text
    assert "fee" in text and "deadline" in text and "exchange rate" in text
