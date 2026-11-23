"""The live run reads the ledger of the branch of the visitor, and never the ledger of the configuration (ADR-038).

What they guarantee, and why: (a) the case of the demo reads the file of the ledger that the plan carries, and the
fallback to the ledger of the configuration is unreachable, so a run may not answer with the rows of another account;
(b) a run without a ledger of the visitor is refused before the first call of the provider, so no money of the visitor
is spent; (c) the tools of the agent cannot read the rows of another customer, whatever SQL the model writes; (d) the
route refuses a branch of another session, a branch whose revision moved and an account that is not the account of the
branch, and no run starts; (e) a live application without a branch layer refuses the run instead of answering with the
ledger of the configuration; (f) the trace of the run names the branch, the revision and the canonical hash of the
ledger that was read; (g) the file of the ledger of the run is removed when the run ends, on the path of the success
and on the path of the failure, and also when the run never starts; (h) the case memory of the run lives in the folder
of the session of the visitor, so two visitors never share it; (i) the run runs the case of the application and the
coordinator of the caller is never rewritten, so a coordinator keeps the case it was built with; (j) a refused run
leaves no folder of the run behind in the runtime folder.

Everything offline, with no key and no network: the provider is the fake adapter of the domain, the ledger of the run
is a copy of the published sample scoped to one account, and the branch layer is a double that speaks the interface of
ADR-038, because the layer itself belongs to the sandbox and to its own worker.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from ledgerlens import embeddings as emb  # noqa: E402
from ledgerlens.api import byok as byok_api  # noqa: E402
from ledgerlens.api import live_case  # noqa: E402
from ledgerlens.api.accounts import scoped_ledger  # noqa: E402
from ledgerlens.api.byok import RUNS_FOLDER_NAME, build_router, create_app  # noqa: E402
from ledgerlens.api.live_case import DemoCase  # noqa: E402
from ledgerlens.api.live_run import LiveRunCoordinator, LiveRunPlan  # noqa: E402
from ledgerlens.api.sandbox import ContractError  # noqa: E402
from ledgerlens.byok.adapter import FakeProviderAdapter  # noqa: E402
from ledgerlens.byok.errors import ByokError  # noqa: E402
from ledgerlens.byok.registry import ProviderRegistry  # noqa: E402
from ledgerlens.byok.vault import CredentialVault  # noqa: E402
from ledgerlens.embeddings import FastEmbedEmbeddings  # noqa: E402
from ledgerlens.retrieval import build_policy_index, index_dir_for, load_policy_documents  # noqa: E402
from ledgerlens.run_context import RunBudget  # noqa: E402
from ledgerlens.sandbox.branch import BranchLayer  # noqa: E402
from ledgerlens.sandbox.ledger_view import (  # noqa: E402
    LedgerAccountMismatch,
    LedgerRevisionMoved,
    LedgerView,
)
from ledgerlens.sandbox.session import SessionIssuer  # noqa: E402
from ledgerlens.sandbox.snapshot import BaseResolver  # noqa: E402
from ledgerlens.sandbox.store import BranchNotFound, FileBranchStore  # noqa: E402
from ledgerlens.sim.config import SimConfig  # noqa: E402
from ledgerlens.sim.pipeline import build_ledger  # noqa: E402
from tests.byok import test_live_case as harness  # noqa: E402
from tests.tools import test_policies as base  # noqa: E402

# The session of the visitor of the tests. The folder of the case memory is named after it.
SESSION = "sess-ledger"
# The account of the visitor of the tests, and the account of another customer of the same published ledger.
ACCOUNT = "C-0001"
OTHER_ACCOUNT = "C-0002"
BRANCH_ID = "br_0123456789abcdef01234567"
REVISION = 3
CANONICAL_HASH = "canonical-hash-of-the-branch"
RUN_ID = "run-ledger"
# The identifier of the mutation of the visitor: it is in the file of the run and in no other ledger.
MUTATION_ID = "TX-9999"
# How many runs the test of the maps of the case runs, so that a map that grows with every run is visible.
RUNS_OF_THE_TEST = 6

# The SQL of the row of the account of the visitor, and the SQL that asks for the rows of another customer.
SQL_OF_THE_ACCOUNT = "SELECT id, status, amount_minor, currency FROM transactions WHERE id = 'TX-9999'"
SQL_OF_ANOTHER_ACCOUNT = "SELECT id, customer_id FROM transactions WHERE customer_id = 'C-0002'"


@pytest.fixture(scope="module")
def ledger_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The published ledger of the sample, built in a temporary folder.

    Why the fixture is here and not imported from the harness: the linter of the repository refuses a name that a
    parameter of a test redefines, and a fixture of another module would have to be imported under its own name.
    """
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


@pytest.fixture(autouse=True)
def online(monkeypatch: pytest.MonkeyPatch) -> None:
    """The product is online for the tests of the live mode: a live run needs a live mode (FR-024)."""
    monkeypatch.setenv("LEDGERLENS_OFFLINE", "0")


def _refuses_the_configuration(*args: Any, **kwargs: Any) -> Any:
    """The configuration of the machine refuses to answer: the live path may never read it (ADR-038)."""
    raise AssertionError("the live path must never read the ledger of the configuration")


def _ledger_of_the_run(path: Path, *, revision: int = REVISION) -> LedgerView:
    """The view of the ledger of the visitor: the file, the account, the branch, the revision and the hash."""
    return LedgerView(
        path=path,
        account_id=ACCOUNT,
        branch_id=BRANCH_ID,
        revision=revision,
        canonical_hash=CANONICAL_HASH,
    )


def _scoped_ledger_of_the_run(published: Path, out_path: Path) -> Path:
    """The ledger of the run: the rows of the account of the visitor, and one mutation of the visitor in it.

    Why the mutation: the row of the mutation exists in no other ledger of the machine, so the evidence that the
    agent saw it proves that the agent read the file of the run and not the ledger of the configuration (ADR-038).
    """
    scoped_ledger(published, ACCOUNT, out_path)
    with sqlite3.connect(out_path) as connection:
        merchant = connection.execute(
            "SELECT merchant_id FROM transactions WHERE customer_id = ? LIMIT 1", (ACCOUNT,)
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO transactions (id, merchant_id, customer_id, amount_minor, currency, method, card_brand, "
            "status, created_at, origin) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                MUTATION_ID,
                merchant,
                ACCOUNT,
                12345,
                "BRL",
                "card",
                "visa",
                "refunded",
                "2026-11-21T10:00:00Z",
                "sandbox",
            ),
        )
        connection.commit()
    return out_path


def _plan(handle: str, *, ledger: LedgerView | None = None, **overrides: Any) -> LiveRunPlan:
    """A plan of a run: the question of the case, the caps of the visitor and the ledger of the run."""
    values: dict[str, Any] = {
        "run_id": RUN_ID,
        "session_id": SESSION,
        "model_profile_id": harness.PROFILE_ID,
        "credential_handle": handle,
        "question": harness.QUESTION,
        "budget": RunBudget(max_model_calls=8, max_tool_calls=8, max_wall_seconds=30, max_output_tokens=512),
        "account_id": ACCOUNT,
        "scenario_id": "S01",
        "variant": "B",
        "ledger": ledger,
    }
    values.update(overrides)
    return LiveRunPlan(**values)


def _coordinator(
    adapter: FakeProviderAdapter,
    vault: CredentialVault,
    *,
    executor: Any = None,
) -> LiveRunCoordinator:
    """A coordinator over the fake provider of the test, with no socket anywhere."""
    return LiveRunCoordinator(
        registry=harness.registry(),
        vault=vault,
        adapter_factory=lambda _provider, _key: adapter,
        executor=executor,
    )


def _case(index_root: Path, embeddings: Any, runtime_dir: Path) -> DemoCase:
    """The case of the demo of the tests: the index, the embeddings and the verifier, and no ledger of its own.

    Why no ledger of its own: the ledger of a run is the ledger of the plan, and a case that carries one of its own
    would be able to answer with a ledger that is not the one of the visitor (ADR-038).
    """
    return DemoCase(
        index_root=index_root,
        embeddings=embeddings,
        verifier=harness.refusing_verifier(),
        runtime_dir=runtime_dir,
    )


def _scripted_adapter(sql: str) -> FakeProviderAdapter:
    """The provider of the tests: the triage, the call of the tool, the SQL and the final answer.

    The order of the script is the order of the calls of the case, and it is what the case must count (FR-012).
    """
    adapter = FakeProviderAdapter(provider="openai", api_key=harness.MARKER)
    adapter.script_answer(harness.SIMPLE_TRIAGE_ANSWER)
    adapter.script_tool_call("query_ledger", json.dumps({"question": "the status of TX-0001"}), call_id="call_sql")
    adapter.script_answer(sql)
    adapter.script_answer(harness.FINAL_ANSWER)
    return adapter


def _the_answer_of_the_run(caller: Any, plan: LiveRunPlan) -> str:
    """A case that answers with a known text, so the test knows which case ran."""
    return "the answer of the run"


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """The result of the investigation of the run, so that the test can read the evidence of the tools.

    Why the case is watched and not the tool: the tool is wrapped by the case, and the evidence is what the agent
    really saw (ADR-038).
    """
    seen: dict[str, Any] = {}
    real = live_case.investigate

    def spy(agent: Any, question: str, **kwargs: Any) -> Any:
        result = real(agent, question, **kwargs)
        seen["result"] = result
        return result

    monkeypatch.setattr(live_case, "investigate", spy)
    return seen


def _rows_of_the_sql(captured: dict[str, Any]) -> list[list[Any]]:
    """The rows that the tool of the ledger returned, as the evidence of the run carries them."""
    result = captured.get("result")
    assert result is not None, "the case of the demo never finished"
    contents = [evidence.content for evidence in result.evidence if evidence.id.startswith("sql:")]
    assert contents, "the run has no evidence of the ledger"
    data = json.loads(contents[0])
    return list(data.get("rows") or [])


class FakeBranchLayer:
    """The branch layer of the tests: it speaks the interface of ADR-038 and never opens a socket.

    Why a double and not the layer of the sandbox: the layer owns the projection and the materialization of the
    branch, and another worker writes it. The double is here so that this file proves the facade: the mapping of the
    refusals, the wiring of the plan and the removal of the file at the end of the run.
    """

    def __init__(
        self,
        *,
        refusal: BaseException | None = None,
        source: Path | None = None,
        revision: int = REVISION,
        canonical_hash: str = CANONICAL_HASH,
    ) -> None:
        self.refusal = refusal
        self.source = source
        self.revision = revision
        self.canonical_hash = canonical_hash
        self.calls: list[dict[str, Any]] = []
        self.targets: list[Path] = []
        self.written: list[Path] = []

    def ledger_view(
        self,
        session_id: str,
        branch_id: str,
        *,
        account_id: str,
        expected_revision: int | None = None,
        target: Path | str,
    ) -> LedgerView:
        """The ledger of the visitor, materialized in the file of the target, or the refusal of the test."""
        path = Path(target)
        self.calls.append(
            {
                "session_id": session_id,
                "branch_id": branch_id,
                "account_id": account_id,
                "expected_revision": expected_revision,
                "target": path,
            }
        )
        self.targets.append(path)
        if self.refusal is not None:
            raise self.refusal
        if self.source is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.source, path)
            self.written.append(path)
        return LedgerView(
            path=path,
            account_id=account_id,
            branch_id=branch_id,
            revision=self.revision,
            canonical_hash=self.canonical_hash,
        )


@contextmanager
def _live_app(
    tmp_path: Path,
    *,
    branch_layer: Any = None,
    coordinator: LiveRunCoordinator | None = None,
    executor: Any = None,
    vault: CredentialVault | None = None,
    adapter: FakeProviderAdapter | None = None,
) -> Iterator[tuple[TestClient, CredentialVault, FakeProviderAdapter]]:
    """The application of the live mode, with the fake provider and a session of the visitor."""
    the_vault = vault if vault is not None else CredentialVault()
    the_adapter = adapter if adapter is not None else FakeProviderAdapter(provider="openai", api_key=harness.MARKER)
    app = create_app(
        vault=the_vault,
        registry=harness.registry(),
        session_issuer=SessionIssuer(tmp_path / "demo-session.key"),
        runtime_dir=tmp_path / "runtime",
        adapter_factory=lambda _provider, _key: the_adapter,
        branch_layer=branch_layer,
        coordinator=coordinator,
        executor=executor,
    )
    with TestClient(app) as client:
        client.post("/v1/sessions")
        yield client, the_vault, the_adapter


def _credential(client: TestClient) -> str:
    """The handle of a credential of the visitor."""
    response = client.post("/v1/credentials", json={"provider": "openai", "api_key": harness.MARKER})
    assert response.status_code == 201, response.text
    return str(response.json()["handle"])


def _run_body(handle: str, **overrides: Any) -> dict[str, Any]:
    """The body of the route of the live run, as the contract of the request asks for it."""
    body: dict[str, Any] = {
        "mode": "live_agent",
        "scenario_id": "S01",
        "sandbox_id": BRANCH_ID,
        "expected_revision": 0,
        "account_id": ACCOUNT,
        "question": harness.QUESTION,
        "variant": "B",
        "model_profile_id": harness.PROFILE_ID,
        "credential_handle": handle,
        "limits": {
            "max_model_calls": 4,
            "max_tool_calls": 4,
            "max_wall_seconds": 30,
            "max_output_tokens": 512,
        },
    }
    body.update(overrides)
    return body


def _wait_for_the_end(client: TestClient, run_id: str, timeout: float = 10.0) -> dict[str, Any]:
    """Waits for the end of a run and answers the state of it."""
    deadline = time.monotonic() + timeout
    state: dict[str, Any] = {}
    while time.monotonic() < deadline:
        response = client.get(f"/v1/live-runs/{run_id}")
        assert response.status_code == 200, response.text
        state = dict(response.json())
        if state["status"] != "running":
            return state
        time.sleep(0.01)
    return state


# --- the case of the demo reads the ledger of the plan -----------------------------------------------


def test_the_case_of_the_demo_reads_the_ledger_of_the_plan_and_never_the_configured_one(
    ledger_db: Path,
    index_root: Path,
    embeddings: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    captured: dict[str, Any],
) -> None:
    """ADR-038: the agent reads the file of the ledger of the plan, and the fallback is unreachable.

    Why the configuration raises: a case that fell back to the ledger of the configuration would fail here, and the
    fallback would hand the model the rows of every account of the repository.
    """
    monkeypatch.setattr("ledgerlens.tools.sql.get_settings", _refuses_the_configuration)
    monkeypatch.setattr("ledgerlens.tools.ledger_api.get_settings", _refuses_the_configuration)
    monkeypatch.setattr("ledgerlens.verify.escalation.get_settings", _refuses_the_configuration)
    the_ledger = _scoped_ledger_of_the_run(ledger_db, tmp_path / "ledger-of-the-run.db")

    adapter = _scripted_adapter(SQL_OF_THE_ACCOUNT)
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault, executor=_case(index_root, embeddings, tmp_path))
    handle = vault.accept(harness.MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle, ledger=_ledger_of_the_run(the_ledger)))
    result = coordinator.wait(RUN_ID, timeout=20.0)

    assert result is not None
    assert result.status == "completed", result.error
    rows = _rows_of_the_sql(captured)
    assert rows, "the case found no row of the account of the visitor"
    # The row is the mutation of the visitor, and it is in the file of the run and in no other ledger of the machine.
    assert rows[0][0] == MUTATION_ID
    with sqlite3.connect(ledger_db) as connection:
        assert not connection.execute("SELECT id FROM transactions WHERE id = ?", (MUTATION_ID,)).fetchall()


def test_a_run_without_a_ledger_is_refused_before_the_first_call_of_the_provider(
    index_root: Path,
    embeddings: Any,
    tmp_path: Path,
) -> None:
    """ADR-038: a run without a ledger of the visitor is a refusal, and no provider is called."""
    adapter = _scripted_adapter(SQL_OF_THE_ACCOUNT)
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault, executor=_case(index_root, embeddings, tmp_path))
    handle = vault.accept(harness.MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle))
    result = coordinator.wait(RUN_ID, timeout=20.0)

    assert result is not None
    assert result.status == "failed"
    assert "ledger" in (result.error or "").lower()
    # The refusal happens before the agent is built, so the provider saw no call at all.
    assert adapter.calls == []


def test_the_tools_of_the_agent_cannot_read_the_rows_of_another_account(
    ledger_db: Path,
    index_root: Path,
    embeddings: Any,
    tmp_path: Path,
    captured: dict[str, Any],
) -> None:
    """ADR-038: the file of the run holds the rows of the account of the branch, so the other rows are not there."""
    the_ledger = _scoped_ledger_of_the_run(ledger_db, tmp_path / "ledger-of-the-run.db")
    adapter = _scripted_adapter(SQL_OF_ANOTHER_ACCOUNT)
    vault = CredentialVault()
    coordinator = _coordinator(adapter, vault, executor=_case(index_root, embeddings, tmp_path))
    handle = vault.accept(harness.MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle, ledger=_ledger_of_the_run(the_ledger)))
    result = coordinator.wait(RUN_ID, timeout=20.0)

    assert result is not None
    assert result.status == "completed", result.error
    # The SQL asked for the rows of another customer and the tool returned none of them.
    assert _rows_of_the_sql(captured) == []
    # The published ledger does hold those rows, so the run read the ledger of the branch and not that one.
    with sqlite3.connect(ledger_db) as connection:
        assert connection.execute("SELECT id FROM transactions WHERE customer_id = ?", (OTHER_ACCOUNT,)).fetchall()


# --- the route of the live run ------------------------------------------------------------------------


def test_the_route_refuses_a_branch_of_another_session(tmp_path: Path) -> None:
    """ADR-038: a branch of another session answers 404, and no run starts."""
    layer = FakeBranchLayer(refusal=BranchNotFound())

    with _live_app(tmp_path, branch_layer=layer) as (client, _vault, adapter):
        handle = _credential(client)
        response = client.post("/v1/live-runs", json=_run_body(handle))

        assert response.status_code == 404
        assert "run_id" not in response.json()
        # The refusal happened before the run started, so no provider was called.
        assert adapter.calls == []
        assert layer.calls, "the route never asked the branch layer"


def test_the_route_refuses_a_revision_that_moved(tmp_path: Path) -> None:
    """ADR-038: a branch that moved away from the revision of the request answers 409, and no run starts."""
    layer = FakeBranchLayer(refusal=LedgerRevisionMoved("the branch moved to another revision"))

    with _live_app(tmp_path, branch_layer=layer) as (client, _vault, adapter):
        handle = _credential(client)
        response = client.post("/v1/live-runs", json=_run_body(handle))

        assert response.status_code == 409
        assert "run_id" not in response.json()
        assert adapter.calls == []


def test_the_route_refuses_an_account_that_is_not_the_account_of_the_branch(tmp_path: Path) -> None:
    """ADR-038: an account that is not the account of the branch answers 422, and no run starts."""
    layer = FakeBranchLayer(refusal=LedgerAccountMismatch("the account is not the account of the branch"))

    with _live_app(tmp_path, branch_layer=layer) as (client, _vault, adapter):
        handle = _credential(client)
        response = client.post("/v1/live-runs", json=_run_body(handle))

        assert response.status_code == 422
        assert "run_id" not in response.json()
        assert adapter.calls == []


def test_the_route_without_a_branch_layer_refuses_the_run(tmp_path: Path) -> None:
    """ADR-038: an application without a branch layer refuses the run, and it never reads the ledger of the setup."""
    with _live_app(tmp_path) as (client, _vault, adapter):
        handle = _credential(client)
        response = client.post("/v1/live-runs", json=_run_body(handle))

        assert response.status_code == 503
        body = response.json()
        assert "run_id" not in body
        assert "branch" in str(body["message"]).lower()
        # The run never started, so the provider was never called.
        assert adapter.calls == []


def test_the_trace_of_the_run_says_which_ledger_was_read(
    tmp_path: Path,
    ledger_db: Path,
) -> None:
    """ADR-038: the trace of the run names the branch, the revision and the canonical hash of the ledger."""
    the_ledger = _scoped_ledger_of_the_run(ledger_db, tmp_path / "ledger-of-the-run.db")
    layer = FakeBranchLayer(source=the_ledger)
    vault = CredentialVault()
    adapter = FakeProviderAdapter(provider="openai", api_key=harness.MARKER)
    coordinator = LiveRunCoordinator(
        registry=harness.registry(),
        vault=vault,
        adapter_factory=lambda _provider, _key: adapter,
        executor=_the_answer_of_the_run,
    )

    with _live_app(
        tmp_path,
        branch_layer=layer,
        coordinator=coordinator,
        vault=vault,
        adapter=adapter,
        executor=_the_answer_of_the_run,
    ) as (
        client,
        _vault,
        _adapter,
    ):
        handle = _credential(client)
        run_id = client.post("/v1/live-runs", json=_run_body(handle)).json()["run_id"]
        _wait_for_the_end(client, run_id)

    started = [event for event in coordinator.events(run_id) if event.event_type == "run.started"]
    assert started, "the trace of the run has no event of the start"
    payload = dict(started[0].payload)
    assert payload["branch_id"] == BRANCH_ID
    assert payload["branch_revision"] == REVISION
    assert payload["canonical_hash"] == CANONICAL_HASH


def test_the_file_of_the_ledger_of_the_run_is_removed_at_the_end_of_the_run(
    tmp_path: Path,
    ledger_db: Path,
) -> None:
    """ADR-038: the file of the run is removed when the run ends, on the path of the success and on the failure."""
    the_ledger = _scoped_ledger_of_the_run(ledger_db, tmp_path / "ledger-of-the-run.db")

    for fails in (False, True):
        layer = FakeBranchLayer(source=the_ledger)
        vault = CredentialVault()
        adapter = FakeProviderAdapter(provider="openai", api_key=harness.MARKER)

        def case(caller: Any, plan: LiveRunPlan, fails: bool = fails) -> str:
            if fails:
                raise RuntimeError("the case of the run failed")
            return "the answer of the run"

        coordinator = LiveRunCoordinator(
            registry=harness.registry(),
            vault=vault,
            adapter_factory=lambda _provider, _key, the_adapter=adapter: the_adapter,
            executor=case,
        )
        with _live_app(
            tmp_path,
            branch_layer=layer,
            coordinator=coordinator,
            vault=vault,
            adapter=adapter,
            executor=case,
        ) as (client, _vault, _adapter):
            handle = _credential(client)
            run_id = client.post("/v1/live-runs", json=_run_body(handle)).json()["run_id"]
            state = _wait_for_the_end(client, run_id)
            target = layer.targets[0]

            assert layer.written, "the layer of the branch never wrote the file of the run"
            assert state["status"] == ("failed" if fails else "completed")

        assert not target.exists(), "the file of the ledger of the run outlived the run"


def test_the_live_route_runs_the_case_of_the_demo_and_not_the_default_executor(
    tmp_path: Path,
    ledger_db: Path,
) -> None:
    """ADR-038: the route runs the case of the demo, and the case refuses a run whose ledger is gone.

    Why the file is missing here: the case of the demo refuses before it builds the agent, so the refusal proves
    that the case ran, and the default executor would have answered the model instead (ADR-038).
    """
    layer = FakeBranchLayer()
    with _live_app(tmp_path, branch_layer=layer) as (client, _vault, adapter):
        handle = _credential(client)
        run_id = client.post("/v1/live-runs", json=_run_body(handle)).json()["run_id"]
        state = _wait_for_the_end(client, run_id)

        assert state["status"] == "failed"
        assert "ledger" in str(state["error"]).lower()
        # The refusal of the case happens before the first call of the provider.
        assert adapter.calls == []


def test_the_route_reads_the_branch_of_the_visitor_with_the_layer_of_the_sandbox(tmp_path: Path) -> None:
    """ADR-038: the facade asks the layer of the sandbox, and the layer materializes the file of the run.

    Why this test uses the real layer: the double of the other tests proves the mapping of the refusals, and this
    one proves that the facade and the layer speak the same interface (ADR-038).
    """
    layer = BranchLayer(FileBranchStore(tmp_path / "store"), BaseResolver(tmp_path / "bases"))
    vault = CredentialVault()
    adapter = FakeProviderAdapter(provider="openai", api_key=harness.MARKER)
    coordinator = LiveRunCoordinator(
        registry=harness.registry(),
        vault=vault,
        adapter_factory=lambda _provider, _key: adapter,
        executor=_the_answer_of_the_run,
    )
    app = create_app(
        vault=vault,
        registry=harness.registry(),
        session_issuer=SessionIssuer(tmp_path / "demo-session.key"),
        runtime_dir=tmp_path / "runtime",
        adapter_factory=lambda _provider, _key: adapter,
        branch_layer=layer,
        coordinator=coordinator,
        executor=_the_answer_of_the_run,
    )

    with TestClient(app) as client:
        session = client.post("/v1/sessions").json()["id"]
        branch = layer.fork(session, "S01").branch
        account = layer.base_resolver("S01").account_id
        handle = _credential(client)
        response = client.post(
            "/v1/live-runs",
            json=_run_body(
                handle,
                sandbox_id=branch.branch_id,
                account_id=account,
                expected_revision=branch.revision,
            ),
        )
        assert response.status_code == 201, response.text
        run_id = response.json()["run_id"]
        state = _wait_for_the_end(client, run_id)

    assert state["status"] == "completed", state
    started = [event for event in coordinator.events(run_id) if event.event_type == "run.started"]
    assert started, "the trace of the run has no event of the start"
    payload = dict(started[0].payload)
    assert payload["branch_id"] == branch.branch_id
    assert payload["branch_revision"] == branch.revision
    assert payload["canonical_hash"] == branch.current_canonical_hash


class _Case_that_reads_the_context_while_the_run_lives(DemoCase):
    """The case of the demo that reads the context of the run while the run is still running.

    Why the context is read during the run: the case forgets the run when the run ends, so the context of a run
    that is over is gone, and a reader that wants it has to read it while the run lives (ADR-038).
    """

    def __init__(self, **options: Any) -> None:
        super().__init__(**options)
        self.contexts: list[Any] = []

    def __call__(self, caller: Any, plan: LiveRunPlan) -> str:
        """The answer of the case of the demo, with the context of the run read before the run ends."""
        answer = super().__call__(caller, plan)
        self.contexts.append(self.context_of(plan.run_id))
        return answer


def test_the_case_memory_of_the_run_lives_in_the_folder_of_the_session(
    ledger_db: Path,
    index_root: Path,
    embeddings: Any,
    tmp_path: Path,
) -> None:
    """ADR-038: the case memory of a run lives in the folder of its session, and not in the folder of the setup."""
    the_ledger = _scoped_ledger_of_the_run(ledger_db, tmp_path / "ledger-of-the-run.db")
    adapter = _scripted_adapter(SQL_OF_THE_ACCOUNT)
    vault = CredentialVault()
    case = _Case_that_reads_the_context_while_the_run_lives(
        index_root=index_root,
        embeddings=embeddings,
        verifier=harness.refusing_verifier(),
        runtime_dir=tmp_path,
    )
    coordinator = _coordinator(adapter, vault, executor=case)
    handle = vault.accept(harness.MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle, ledger=_ledger_of_the_run(the_ledger)))
    result = coordinator.wait(RUN_ID, timeout=20.0)

    assert result is not None
    assert result.status == "completed", result.error
    assert case.contexts, "the case never read the context of the run"
    context = case.contexts[0]
    assert context is not None
    # The memory of the case lives in the folder of the session of the visitor, and two sessions never share it.
    assert context.memory_dir == tmp_path / "sessions" / SESSION


# --- the case of the run travels with the run ---------------------------------------------------------


def _the_case_of_the_coordinator(caller: Any, plan: LiveRunPlan) -> str:
    """A case that answers with the name of the coordinator, so the test knows which case ran."""
    return "the case of the coordinator"


def _the_case_of_the_application(caller: Any, plan: LiveRunPlan) -> str:
    """A case that answers with the name of the application, so the test knows which case ran."""
    return "the case of the application"


def test_the_executor_that_the_application_is_given_is_the_case_of_the_run(tmp_path: Path) -> None:
    """ADR-038: the run runs the case of the application, and not the case the coordinator was built with.

    Why the coordinator carries a case of its own: a coordinator of a caller is a coordinator that somebody else
    uses too, and the facade may not answer with the case of somebody else (ADR-038).
    """
    layer = FakeBranchLayer()
    vault = CredentialVault()
    adapter = FakeProviderAdapter(provider="openai", api_key=harness.MARKER)
    coordinator = _coordinator(adapter, vault, executor=_the_case_of_the_coordinator)

    with _live_app(
        tmp_path,
        branch_layer=layer,
        coordinator=coordinator,
        vault=vault,
        adapter=adapter,
        executor=_the_case_of_the_application,
    ) as (client, _vault, _adapter):
        handle = _credential(client)
        run_id = client.post("/v1/live-runs", json=_run_body(handle)).json()["run_id"]
        state = _wait_for_the_end(client, run_id)

    assert state["status"] == "completed", state
    assert state["answer"] == "the case of the application"


def test_the_coordinator_of_the_caller_is_never_rewritten(tmp_path: Path) -> None:
    """ADR-038: the coordinator of the caller keeps the case it was built with, and the facade never rewrites it.

    Why two coordinators: a coordinator that was built with a case keeps that case, and a coordinator that was built
    without one keeps the default case, which asks the model once, and the facade may not replace either of them
    with the case of the demo (ADR-038).

    Why the run starts on the coordinator and not on the route: the route hands its own case to every run it
    starts, so only a run that starts on the coordinator itself shows the case the coordinator kept (ADR-038).
    """
    vault = CredentialVault()
    adapter = FakeProviderAdapter(provider="openai", api_key=harness.MARKER).script_answer("the answer of the provider")
    with_case = _coordinator(adapter, vault, executor=_the_case_of_the_coordinator)
    without_case = _coordinator(adapter, vault)

    for coordinator, expected in (
        (with_case, "the case of the coordinator"),
        (without_case, "the answer of the provider"),
    ):
        create_app(
            vault=vault,
            registry=harness.registry(),
            session_issuer=SessionIssuer(tmp_path / "demo-session.key"),
            runtime_dir=tmp_path / "runtime",
            adapter_factory=lambda _provider, _key: adapter,
            coordinator=coordinator,
            executor=_the_case_of_the_application,
        )
        handle = vault.accept(harness.MARKER, "openai", session_id=SESSION)

        coordinator.start(_plan(handle.handle))
        result = coordinator.wait(RUN_ID, timeout=20.0)

        assert result is not None
        assert result.status == "completed", result.error
        # The coordinator of the caller answers with its own case, and never with the case of the application.
        assert result.answer == expected


# --- the file of the ledger does not outlive a run -----------------------------------------------------


class _RefusingCoordinator(LiveRunCoordinator):
    """A coordinator whose start refuses the run and removes nothing: the facade has to clean up (ADR-038).

    Why a double and not the coordinator of the domain: the coordinator of the domain removes the file of the
    ledger itself when it refuses, and this double is the other half of the promise, the facade that removes the
    file of a coordinator that refuses without removing anything (ADR-038).
    """

    def start(self, plan: LiveRunPlan, *, case: Any = None) -> Any:
        """Refuses the run the way the coordinator refuses a model that is not in the allowlist."""
        raise ByokError("the coordinator of the test refuses this run")


def test_the_file_of_the_ledger_does_not_outlive_a_run_that_never_started(
    tmp_path: Path,
    ledger_db: Path,
) -> None:
    """ADR-038: a run that never starts leaves no file of the ledger behind, and no folder of the run.

    Why two ways of refusing: the coordinator of the first case refuses the model of the run itself, and the
    facade refuses whatever the coordinator refused, and the file of the ledger goes away in both (ADR-038).
    """
    the_ledger = _scoped_ledger_of_the_run(ledger_db, tmp_path / "ledger-of-the-run.db")
    vault = CredentialVault()
    adapter = FakeProviderAdapter(provider="openai", api_key=harness.MARKER)
    # The first coordinator does not hold the model of the run, so its start refuses the run.
    coordinators = (
        LiveRunCoordinator(
            registry=ProviderRegistry([]),
            vault=vault,
            adapter_factory=lambda _provider, _key: adapter,
        ),
        _RefusingCoordinator(
            registry=harness.registry(),
            vault=vault,
            adapter_factory=lambda _provider, _key: adapter,
        ),
    )

    for coordinator in coordinators:
        layer = FakeBranchLayer(source=the_ledger)
        with _live_app(
            tmp_path,
            branch_layer=layer,
            coordinator=coordinator,
            vault=vault,
            adapter=adapter,
        ) as (client, _vault, _adapter):
            handle = _credential(client)
            response = client.post("/v1/live-runs", json=_run_body(handle))

            assert response.status_code == 422, response.text
            assert layer.written, "the layer of the branch never wrote the file of the run"
            target = layer.targets[0]

        assert not target.exists(), "the file of the ledger of the run outlived a run that never started"
        assert not target.parent.exists(), "the folder of the run outlived a run that never started"


def test_a_refused_run_leaves_no_folder_behind(tmp_path: Path) -> None:
    """ADR-038: a run that the route refuses leaves no folder of the run in the runtime folder.

    Why the folder matters: the folder of a run holds the file of the ledger of the visitor, and a refused run
    never wrote one, so an empty folder is the leftover of nothing (ADR-038).
    """
    layer = FakeBranchLayer(refusal=BranchNotFound())

    with _live_app(tmp_path, branch_layer=layer) as (client, _vault, _adapter):
        handle = _credential(client)
        response = client.post("/v1/live-runs", json=_run_body(handle))

        assert response.status_code == 404

    runs = tmp_path / "runtime" / RUNS_FOLDER_NAME
    assert not runs.exists() or not any(runs.iterdir()), "the refused run left a folder behind"


# --- the owner of the removal of the file of the ledger -----------------------------------------------


class _BrokenCoordinator(LiveRunCoordinator):
    """A coordinator whose start breaks in a way the route does not know (ADR-038).

    Why a double and not the coordinator of the domain: the coordinator of the domain refuses a run with a refusal
    of its own family, and this double breaks with an error of nobody, so the route has to clean up after it
    (ADR-038).
    """

    def start(self, plan: LiveRunPlan, *, case: Any = None) -> Any:
        """Breaks the way a coordinator breaks when it meets something it does not expect."""
        raise RuntimeError("the coordinator of the test breaks in a way the route does not know")


def test_the_file_of_the_ledger_does_not_outlive_a_request_that_the_coordinator_refuses_with_an_error_it_does_not_know(
    tmp_path: Path,
    ledger_db: Path,
) -> None:
    """ADR-038: the route owns the removal of the file of the ledger, whatever the refusal of the coordinator is.

    Why a refusal the route does not know: the route cannot know every way a coordinator may refuse, and the rows
    of a visitor may not stay on the disk of the server for a run that never happened (ADR-038).
    """
    the_ledger = _scoped_ledger_of_the_run(ledger_db, tmp_path / "ledger-of-the-run.db")
    layer = FakeBranchLayer(source=the_ledger)
    vault = CredentialVault()
    adapter = FakeProviderAdapter(provider="openai", api_key=harness.MARKER)
    coordinator = _BrokenCoordinator(
        registry=harness.registry(),
        vault=vault,
        adapter_factory=lambda _provider, _key: adapter,
    )

    with _live_app(
        tmp_path,
        branch_layer=layer,
        coordinator=coordinator,
        vault=vault,
        adapter=adapter,
    ) as (client, _vault, _adapter):
        handle = _credential(client)
        with pytest.raises(RuntimeError):
            client.post("/v1/live-runs", json=_run_body(handle))
        assert layer.written, "the layer of the branch never wrote the file of the run"
        target = layer.targets[0]

    assert not target.exists(), "the file of the ledger outlived the request"
    assert not target.parent.exists(), "the folder of the run outlived the request"


def test_the_file_of_the_ledger_of_a_run_that_started_is_not_removed_by_the_route(
    tmp_path: Path,
    ledger_db: Path,
) -> None:
    """ADR-038: the route leaves the file of the ledger of a run that started, and the run removes it at its end.

    Why the case waits: the file of the ledger belongs to the run while the run runs, and the only proof that the
    route did not take it is that the file is there while the run is still running (ADR-038).
    """
    the_ledger = _scoped_ledger_of_the_run(ledger_db, tmp_path / "ledger-of-the-run.db")
    layer = FakeBranchLayer(source=the_ledger)
    vault = CredentialVault()
    adapter = FakeProviderAdapter(provider="openai", api_key=harness.MARKER)
    release = threading.Event()

    def case(caller: Any, plan: LiveRunPlan) -> str:
        """The case of the run, which waits until the test lets the run end."""
        release.wait(timeout=20.0)
        return "the answer of the run"

    coordinator = LiveRunCoordinator(
        registry=harness.registry(),
        vault=vault,
        adapter_factory=lambda _provider, _key: adapter,
        executor=case,
    )

    with _live_app(
        tmp_path,
        branch_layer=layer,
        coordinator=coordinator,
        vault=vault,
        adapter=adapter,
        executor=case,
    ) as (client, _vault, _adapter):
        handle = _credential(client)
        response = client.post("/v1/live-runs", json=_run_body(handle))
        assert response.status_code == 201, response.text
        run_id = response.json()["run_id"]
        target = layer.targets[0]
        # The run is running, so the file of the ledger is its own until the run ends.
        assert target.exists(), "the route removed the file of the ledger of a run that started"
        release.set()
        state = _wait_for_the_end(client, run_id)

    assert state["status"] == "completed", state
    assert not target.exists(), "the run did not remove the file of the ledger of its own run"


# --- the case forgets the run when the run ends -------------------------------------------------------


def test_the_case_forgets_the_run_when_the_run_ends(
    ledger_db: Path,
    index_root: Path,
    embeddings: Any,
    tmp_path: Path,
) -> None:
    """ADR-038: the case forgets the run when it ends, so it holds no context and no bridges of that run.

    Why the run is forgotten at its end: a case that keeps every run it ever served grows without end in a long
    lived process, one context and four bridges per run (ADR-038).
    """
    the_ledger = _scoped_ledger_of_the_run(ledger_db, tmp_path / "ledger-of-the-run.db")
    adapter = _scripted_adapter(SQL_OF_THE_ACCOUNT)
    vault = CredentialVault()
    case = _case(index_root, embeddings, tmp_path)
    coordinator = _coordinator(adapter, vault, executor=case)
    handle = vault.accept(harness.MARKER, "openai", session_id=SESSION)

    coordinator.start(_plan(handle.handle, ledger=_ledger_of_the_run(the_ledger)), case=case)
    result = coordinator.wait(RUN_ID, timeout=20.0)

    assert result is not None
    assert result.status == "completed", result.error
    # The run is over, so the case holds no context of it and no bridges of it.
    assert case.context_of(RUN_ID) is None
    assert case.bridges_of(RUN_ID) == {}


def test_the_maps_of_the_case_do_not_grow_with_the_runs(
    ledger_db: Path,
    index_root: Path,
    embeddings: Any,
    tmp_path: Path,
) -> None:
    """ADR-038: the maps of the case do not grow with the runs: every run that ended is forgotten.

    Why many runs: a map that grows with every run looks the same as a map that is empty after one run, and only
    the many runs tell the two apart (ADR-038).
    """
    vault = CredentialVault()
    case = _case(index_root, embeddings, tmp_path)
    coordinator = LiveRunCoordinator(
        registry=harness.registry(),
        vault=vault,
        adapter_factory=lambda _provider, _key: _scripted_adapter(SQL_OF_THE_ACCOUNT),
    )
    handle = vault.accept(harness.MARKER, "openai", session_id=SESSION)

    for index in range(RUNS_OF_THE_TEST):
        run_id = f"run-{index}"
        the_ledger = _scoped_ledger_of_the_run(ledger_db, tmp_path / f"ledger-of-the-run-{index}.db")
        coordinator.start(_plan(handle.handle, run_id=run_id, ledger=_ledger_of_the_run(the_ledger)), case=case)
        result = coordinator.wait(run_id, timeout=20.0)

        assert result is not None
        assert result.status == "completed", result.error

    # No run of the six is left in the case, so the two maps of the case are empty and do not grow.
    for index in range(RUNS_OF_THE_TEST):
        run_id = f"run-{index}"
        assert case.context_of(run_id) is None
        assert case.bridges_of(run_id) == {}


# --- a router without a case refuses the run ----------------------------------------------------------


def test_a_run_without_a_case_is_refused_with_a_readable_reason(
    tmp_path: Path,
    ledger_db: Path,
) -> None:
    """ADR-038: a router built without a case refuses the run, with a code and a readable reason.

    Why the refusal and not the case of the coordinator: the coordinator may carry the default case, which asks the
    model once with the question of the request, and a run that answers with it never reads the ledger of the
    visitor (ADR-038).

    Why no provider is called: the refusal happens before the branch of the visitor is read, so no money of the
    visitor is spent (ADR-038).
    """
    the_ledger = _scoped_ledger_of_the_run(ledger_db, tmp_path / "ledger-of-the-run.db")
    layer = FakeBranchLayer(source=the_ledger)
    vault = CredentialVault()
    adapter = FakeProviderAdapter(provider="openai", api_key=harness.MARKER)
    coordinator = LiveRunCoordinator(
        registry=harness.registry(),
        vault=vault,
        adapter_factory=lambda _provider, _key: adapter,
    )
    app = FastAPI()
    app.include_router(
        build_router(
            vault=vault,
            registry=harness.registry(),
            issuer=SessionIssuer(tmp_path / "demo-session.key"),
            coordinator=coordinator,
            branch_layer=layer,
            runtime_dir=tmp_path / "runtime",
        )
    )

    with TestClient(app) as client:
        client.post("/v1/sessions")
        handle = _credential(client)
        with pytest.raises(ContractError) as refusal:
            client.post("/v1/live-runs", json=_run_body(handle))

    assert refusal.value.code == byok_api.CODE_CASE_MISSING
    assert refusal.value.status_code == 503
    assert "case" in refusal.value.message.lower()
    # The refusal happened before the branch was read and before the provider was called.
    assert layer.calls == [], "the route read the branch of the visitor for a run it refuses"
    assert adapter.calls == []
