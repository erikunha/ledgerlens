"""The gap of the fiction marker: every chunk of the index and every result of the tool carries it.

What it guarantees, and why: the metadata of every chunk of the index carries the marker that Acme Payments
is a fictional company, and every result of the tool carries it too, so an excerpt says that the company is
fictional even when it is read out of its file (gap 10 of the audit).

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from pathlib import Path

from ledgerlens.embeddings import OfflineEmbeddings
from ledgerlens.retrieval import load_policy_documents, load_policy_index, search_policy_index

ROOT = Path(__file__).resolve().parents[2]
COMMITTED_INDEX = ROOT / "data" / "index" / "policies_offline"
MARKER = "fictional company"


def test_every_chunk_of_the_corpus_carries_the_marker_of_the_fiction() -> None:
    """Every chunk of the documents of the corpus carries the marker in its metadata."""
    documents = load_policy_documents()
    assert documents
    for document in documents:
        assert MARKER in document.metadata.get("fiction", ""), (
            f"the chunk {document.metadata['chunk_id']} does not carry the marker of the fiction"
        )


def test_every_chunk_of_the_committed_index_carries_the_marker_of_the_fiction() -> None:
    """Every chunk of the committed index carries the marker, so a served excerpt says the company is fictional."""
    index = load_policy_index(COMMITTED_INDEX, OfflineEmbeddings())
    hits = search_policy_index(index, "refund", k=200)
    assert hits
    for hit in hits:
        assert MARKER in hit.get("fiction", ""), f"the chunk {hit['chunk_id']} of the index does not carry the marker"
