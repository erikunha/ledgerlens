"""The one module of the project that talks to the vector library.

Why one module: the promise of the repository is that the vector library is behind one protocol, and a promise
about the shape of the repository becomes a test. The three operations of the project over a vector index are
the load, the search and the add, and they live here and nowhere else: the policy index and the case memory
use the same three operations, and no other module imports the library.

Why the handle is a protocol: the project does not promise the library, it promises the three operations. The
day the library changes, the change is in this module and in no other, and the guard of the boundary refuses
any other import of the library.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

__all__ = ["VectorHit", "VectorStore", "add_to_index", "load_index", "search_index"]


@dataclass(frozen=True)
class VectorHit:
    """One result of a search: the document and the distance of it to the query. Lower is closer."""

    document: Document
    distance: float


class VectorStore(Protocol):
    """The handle of a vector index: what the project may do with an index, and nothing else."""

    def save_local(self, folder: str) -> None:
        """Writes the index to the folder."""
        ...

    @property
    def dimension(self) -> int:
        """The dimension of the vectors of the index."""
        ...

    @property
    def count(self) -> int:
        """The number of the vectors of the index."""
        ...


class _FaissStore:
    """The handle of the FAISS library: the only place of the project that touches the library."""

    def __init__(self, store: FAISS) -> None:
        self._store = store

    def save_local(self, folder: str) -> None:
        self._store.save_local(folder)

    @property
    def dimension(self) -> int:
        return int(self._store.index.d)

    @property
    def count(self) -> int:
        return int(self._store.index.ntotal)

    def _add(self, documents: list[Document], ids: list[str]) -> None:
        self._store.add_documents(documents, ids=ids)


def load_index(folder: Path, embeddings: Embeddings) -> VectorStore:
    """The index of the folder, loaded with the consent of the project. Never builds anything.

    The index is ours: it was written by the project and it is only read from the folder of the project. FAISS
    keeps the text of the documents in a pickle, and LangChain requires this consent to open it. This is the
    only place of the project that gives it, and no outside file may be pointed at this function.
    """
    store = FAISS.load_local(str(folder), embeddings, allow_dangerous_deserialization=True, normalize_L2=True)
    return _FaissStore(store)


def search_index(store: VectorStore, query: str, k: int = 4) -> list[VectorHit]:
    """The `k` closest documents to the query, from closest to farthest, with the distance of each one."""
    if not isinstance(store, _FaissStore):
        raise TypeError("the store is not a store of this module")
    return [
        VectorHit(document, float(distance))
        for document, distance in store._store.similarity_search_with_score(query, k=k)
    ]


def add_to_index(
    documents: list[Document], embeddings: Embeddings, ids: list[str], *, into: VectorStore | None = None
) -> VectorStore:
    """A new index over the documents, or the documents added to the index of `into`, with the ids of the project.

    The ids are the ids of the project, so rebuilding with the same vectors gives the same bytes and no random
    uuid lands in the index. With `into`, the documents are added to the index that is already loaded, and the
    same handle comes back.
    """
    if into is not None:
        if not isinstance(into, _FaissStore):
            raise TypeError("the store is not a store of this module")
        into._add(documents, ids)
        return into
    return _FaissStore(FAISS.from_documents(documents, embeddings, ids=ids, normalize_L2=True))
