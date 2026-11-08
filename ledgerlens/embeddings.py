"""Embeddings: a fastembed wrapper for offline mode and a factory for OpenAI.

Why it exists: semantic search over the policies needs to turn text into vectors, and offline mode cannot
depend on an API. fastembed runs the local model in ONNX, with no torch.

The default model is English (`BAAI/bge-small-en-v1.5`), has 384 dimensions, is about 67 MB, and reads at most
512 tokens per text. It is loaded only on first use: creating the object costs nothing, and tests that never
produce vectors never download the model. The first real use downloads the files; set `FASTEMBED_CACHE_PATH`
to keep them between runs.
"""

from __future__ import annotations

from typing import Any

from langchain_core.embeddings import Embeddings

DEFAULT_FASTEMBED_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_OPENAI_MODEL = "text-embedding-3-small"


def _text_embedding_class() -> Any:
    """Import fastembed on demand (it is heavy and not needed by most tests)."""
    from fastembed import TextEmbedding

    return TextEmbedding


class FastEmbedEmbeddings(Embeddings):
    """Local embeddings through fastembed. Documents and queries use the model's own entry points."""

    def __init__(self, model_name: str = DEFAULT_FASTEMBED_MODEL, *, cache_dir: str | None = None) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir
        self._model: Any = None

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def _load(self) -> Any:
        if self._model is None:
            kwargs: dict[str, Any] = {}
            if self.cache_dir is not None:
                kwargs["cache_dir"] = self.cache_dir
            self._model = _text_embedding_class()(self.model_name, **kwargs)
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return [[float(x) for x in vector] for vector in self._load().passage_embed(list(texts))]

    def embed_query(self, text: str) -> list[float]:
        vector = next(iter(self._load().query_embed(text)))
        return [float(x) for x in vector]


def openai_embeddings(model: str = DEFAULT_OPENAI_MODEL, *, api_key: str | None = None) -> Embeddings:
    """OpenAI embeddings. With no `api_key`, the library reads `OPENAI_API_KEY` from the environment."""
    from langchain_openai import OpenAIEmbeddings

    if api_key is None:
        return OpenAIEmbeddings(model=model)
    return OpenAIEmbeddings(model=model, api_key=api_key)  # type: ignore[arg-type]


def embedding_dimension(embeddings: Embeddings) -> int:
    """Vector size, read from a real vector. Index builders store it in `index_meta.json`."""
    return len(embeddings.embed_query("dimension probe"))


def embedding_id(embeddings: Embeddings) -> str:
    """Stable name of the embedding model, such as `fastembed:<model name>` or `openai:<model>`."""
    if isinstance(embeddings, FastEmbedEmbeddings):
        return f"fastembed:{embeddings.model_name}"
    model = getattr(embeddings, "model", None)
    if type(embeddings).__name__ == "OpenAIEmbeddings" and isinstance(model, str):
        return f"openai:{model}"
    raise TypeError(f"cannot name the embedding model of {type(embeddings).__name__}")
