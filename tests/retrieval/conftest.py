"""The shared fixtures of the retrieval tests.

Why the fixture lives here: the tests of the protocol of the vector sites and the tests of the policy index
need the same embedding of the tests, and a fixture that lives in one test file is a fixture the other file
cannot use. The embedding of the tests is the stand-in of the word count, so the tests run offline, with no
key and with no network.
"""

from __future__ import annotations

import pytest

from ledgerlens import embeddings as emb
from ledgerlens.embeddings import FastEmbedEmbeddings
from tests.tools import test_policies as base


@pytest.fixture
def embeddings(monkeypatch: pytest.MonkeyPatch) -> FastEmbedEmbeddings:
    """The embedding of the tests: the stand-in of the word count, with no model and no network."""
    monkeypatch.setattr(emb, "_text_embedding_class", lambda: base.WordCountModel)
    return FastEmbedEmbeddings()
