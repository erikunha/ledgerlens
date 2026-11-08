"""Embeddings: fastembed wrapper (model loaded lazily), OpenAI factory, dimension read at build time.

The default tests use a stand-in for the fastembed model so they need no download. The test marked
`slow` loads the real model: `uv run pytest -m slow tests/test_embeddings.py` (first run downloads
BAAI/bge-small-en-v1.5, about 67 MB; set FASTEMBED_CACHE_PATH to
keep the cache between runs).
"""

from __future__ import annotations

import numpy as np
import pytest
from langchain_core.embeddings import Embeddings

from ledgerlens import embeddings as emb
from ledgerlens.embeddings import (
    DEFAULT_FASTEMBED_MODEL,
    DEFAULT_OPENAI_MODEL,
    FastEmbedEmbeddings,
    embedding_dimension,
    embedding_id,
    openai_embeddings,
)


class FakeTextEmbedding:
    """Stands in for fastembed.TextEmbedding: records calls, returns fixed-size numpy vectors."""

    instances: list[FakeTextEmbedding] = []

    def __init__(self, model_name: str, **kwargs: object) -> None:
        self.model_name = model_name
        self.kwargs = kwargs
        self.calls: list[tuple[str, list[str]]] = []
        FakeTextEmbedding.instances.append(self)

    def _vectors(self, kind: str, texts: list[str]):
        self.calls.append((kind, list(texts)))
        for text in texts:
            yield np.full(4, float(len(text)), dtype=np.float32)

    def embed(self, texts, **kwargs):
        return self._vectors("embed", list(texts))

    def passage_embed(self, texts, **kwargs):
        return self._vectors("passage", list(texts))

    def query_embed(self, query, **kwargs):
        return self._vectors("query", [query] if isinstance(query, str) else list(query))


@pytest.fixture
def fake_fastembed(monkeypatch: pytest.MonkeyPatch) -> type[FakeTextEmbedding]:
    FakeTextEmbedding.instances = []
    monkeypatch.setattr(emb, "_text_embedding_class", lambda: FakeTextEmbedding)
    return FakeTextEmbedding


def test_is_a_langchain_embeddings_subclass() -> None:
    assert issubclass(FastEmbedEmbeddings, Embeddings)


def test_default_model_is_an_english_model_supported_by_fastembed() -> None:
    """The policies and the questions are in English, so the offline default is an English model.

    Checks the name against fastembed's own catalog (no download), so a typo or a model the installed
    fastembed cannot load fails here and not on the first embedding.
    """
    from fastembed import TextEmbedding

    assert DEFAULT_FASTEMBED_MODEL == "BAAI/bge-small-en-v1.5"
    supported = {entry["model"]: entry for entry in TextEmbedding.list_supported_models()}
    assert DEFAULT_FASTEMBED_MODEL in supported
    assert supported[DEFAULT_FASTEMBED_MODEL]["dim"] == 384


def test_construction_loads_nothing(fake_fastembed: type[FakeTextEmbedding]) -> None:
    model = FastEmbedEmbeddings()
    assert model.is_loaded is False
    assert fake_fastembed.instances == []
    assert model.model_name == DEFAULT_FASTEMBED_MODEL


def test_documents_and_query_are_plain_float_lists(fake_fastembed: type[FakeTextEmbedding]) -> None:
    model = FastEmbedEmbeddings()
    docs = model.embed_documents(["abc", "abcdef"])
    query = model.embed_query("abcd")
    assert docs == [[3.0] * 4, [6.0] * 4]
    assert query == [4.0] * 4
    for vector in (*docs, query):
        assert all(type(x) is float for x in vector)


def test_documents_use_passage_embedding_and_queries_use_query_embedding(
    fake_fastembed: type[FakeTextEmbedding],
) -> None:
    model = FastEmbedEmbeddings()
    model.embed_documents(["a"])
    model.embed_query("b")
    (instance,) = fake_fastembed.instances
    assert [kind for kind, _ in instance.calls] == ["passage", "query"]


def test_model_loads_once(fake_fastembed: type[FakeTextEmbedding]) -> None:
    model = FastEmbedEmbeddings(cache_dir="/tmp/cache-x")
    model.embed_query("a")
    model.embed_documents(["b"])
    assert model.is_loaded is True
    (instance,) = fake_fastembed.instances
    assert instance.kwargs == {"cache_dir": "/tmp/cache-x"}


def test_empty_document_list(fake_fastembed: type[FakeTextEmbedding]) -> None:
    assert FastEmbedEmbeddings().embed_documents([]) == []


def test_dimension_is_read_from_the_vectors(fake_fastembed: type[FakeTextEmbedding]) -> None:
    assert embedding_dimension(FastEmbedEmbeddings()) == 4


def test_embedding_id_names_provider_and_model() -> None:
    assert embedding_id(FastEmbedEmbeddings()) == f"fastembed:{DEFAULT_FASTEMBED_MODEL}"
    assert embedding_id(FastEmbedEmbeddings()).endswith("BAAI/bge-small-en-v1.5")
    assert embedding_id(FastEmbedEmbeddings(model_name="BAAI/bge-base-en-v1.5")) == "fastembed:BAAI/bge-base-en-v1.5"
    assert embedding_id(openai_embeddings(api_key="sk-test")) == f"openai:{DEFAULT_OPENAI_MODEL}"


def test_embedding_id_rejects_unknown_embeddings() -> None:
    class Other(Embeddings):
        def embed_documents(self, texts):
            return [[0.0] for _ in texts]

        def embed_query(self, text):
            return [0.0]

    with pytest.raises(TypeError, match="Other"):
        embedding_id(Other())


def test_openai_factory_builds_without_network() -> None:
    from langchain_openai import OpenAIEmbeddings

    model = openai_embeddings(api_key="sk-test")
    assert isinstance(model, OpenAIEmbeddings)
    assert model.model == DEFAULT_OPENAI_MODEL
    assert "sk-test" not in repr(model)


def test_openai_factory_accepts_another_model() -> None:
    assert openai_embeddings(model="text-embedding-3-large", api_key="sk-test").model == "text-embedding-3-large"


@pytest.mark.slow
def test_real_fastembed_model() -> None:
    """Needs the model files: downloads the default model on the first run."""
    model = FastEmbedEmbeddings()
    vectors = model.embed_documents(["refund of a card payment", "weather forecast in Lisbon"])
    query = model.embed_query("money back for what I paid by card")

    assert embedding_dimension(model) == len(vectors[0]) == len(query)
    assert len(vectors[0]) == 384

    def cosine(a: list[float], b: list[float]) -> float:
        a_, b_ = np.asarray(a), np.asarray(b)
        return float(a_ @ b_ / (np.linalg.norm(a_) * np.linalg.norm(b_)))

    assert cosine(query, vectors[0]) > cosine(query, vectors[1])
    assert model.embed_query("money back for what I paid by card") == query  # deterministic
