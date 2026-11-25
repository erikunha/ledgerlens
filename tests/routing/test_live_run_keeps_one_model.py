"""The live run keeps one model: every request of the run asks for the same model, and the trace names it.

What they guarantee, and why: a live run has exactly one model (ADR-037), and the four slots of the agent of
the demo are the model of the run. Every request of the run asks for that model, and the trace of the run names
it for the four slots, because a run whose model changed in the middle is a run that can be read as two runs.

Everything here runs offline, with no key and with no network: the provider is the fake adapter of the domain,
and the embeddings are a word count model, so nothing is downloaded.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ledgerlens import embeddings as emb
from ledgerlens.api.live_run import LiveRunCoordinator  # noqa: F401  (the coordinator of the case)
from ledgerlens.byok.vault import CredentialVault
from ledgerlens.embeddings import FastEmbedEmbeddings
from ledgerlens.retrieval import build_policy_index, index_dir_for, load_policy_documents
from ledgerlens.sim.config import SimConfig
from ledgerlens.sim.pipeline import build_ledger
from tests.byok.test_live_case import (
    MODEL_ID,
    SESSION,
    DemoCase,
    _coordinator,
    _plan,
    refusing_verifier,
    scripted_adapter,
)
from tests.tools import test_policies as base


@pytest.fixture(scope="module")
def ledger_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The ledger of the sample, built in a temporary folder."""
    path = tmp_path_factory.mktemp("ledger") / "ledger.db"
    build_ledger(SimConfig(source="sample"), path).conn.close()
    return path


@pytest.fixture
def embeddings(monkeypatch: pytest.MonkeyPatch) -> FastEmbedEmbeddings:
    """The embeddings of the tests: a word count model, so nothing is downloaded."""
    monkeypatch.setattr(emb, "_text_embedding_class", lambda: base.WordCountModel)
    return FastEmbedEmbeddings()


@pytest.fixture
def index_root(tmp_path: Path, embeddings: FastEmbedEmbeddings) -> Path:
    """The policy index of the tests, built in a temporary folder."""
    root = tmp_path / "index"
    build_policy_index(load_policy_documents(base.POLICIES), embeddings, index_dir_for(root, embeddings))
    return root


def test_a_live_run_asks_for_one_model_in_every_request(
    monkeypatch: pytest.MonkeyPatch,
    ledger_db: Path,
    index_root: Path,
    embeddings: FastEmbedEmbeddings,
) -> None:
    """Every request of the run asks for the model of the run, and the trace names it for the four slots."""
    # The live mode is off when the product runs offline, so the case turns the live mode on the way the live
    # tests of the repository do: with the flag of the offline mode off and the fake adapter of the provider.
    monkeypatch.setenv("LEDGERLENS_OFFLINE", "0")
    case = DemoCase(
        db_path=ledger_db,
        index_root=index_root,
        embeddings=embeddings,
        verifier=refusing_verifier(),
    )
    adapter = scripted_adapter()
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault, executor=case)
    handle = vault.accept("sk-fakefake1234", "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle))
    result = coordinator.wait("run-case", timeout=20.0)

    assert result is not None
    assert result.status == "completed"
    # Every request of the run asked for the model of the run, and there is exactly one.
    assert {call.model_id for call in adapter.calls} == {MODEL_ID}
    # The trace of the run names the model of the run for every call of the model.
    spans = [
        event
        for event in coordinator.events("run-case")
        if event.event_type == "span.started" and event.payload.get("name") == "model.call"
    ]
    assert spans
    assert {span.payload.get("model_id") for span in spans} == {MODEL_ID}
