"""The protocol of the vector sites: the three operations, and a search that returns the closest texts.

What they guarantee, and why: the protocol has the three operations of the project (the load, the search and
the add), and a search returns the closest texts with the distance, because the project promises the three
operations and not the library.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from pathlib import Path

from langchain_core.documents import Document

from ledgerlens.embeddings import FastEmbedEmbeddings
from ledgerlens.vectorstore import add_to_index, load_index, search_index


def test_a_search_returns_the_closest_texts_with_the_distance(tmp_path: Path, embeddings: FastEmbedEmbeddings) -> None:
    """The add, the save, the load and the search of the protocol, over a small index of the test."""
    documents = [
        Document(page_content="the refund window is thirty days", metadata={"chunk_id": "a"}),
        Document(page_content="the settlement is weekly", metadata={"chunk_id": "b"}),
    ]
    store = add_to_index(documents, embeddings, ids=["a", "b"])
    assert store.dimension > 0
    assert store.count == 2
    store.save_local(str(tmp_path))

    loaded = load_index(tmp_path, embeddings)
    hits = search_index(loaded, "how many days is the refund window", k=2)

    assert hits
    assert hits[0].document.page_content == "the refund window is thirty days"
    assert hits[0].distance <= hits[-1].distance
    assert all(hit.distance >= 0 for hit in hits)
