"""The suite of the facade of the live mode: the routes of the credential, of the catalog and of the run.

What they guarantee, and why: (a) the answer of the credential route never carries the key of the visitor and
carries the handle, the provider and the expiry (FR-004, FR-005); (b) the answer carries the headers that say that
nothing is stored, that the memory of the machine cannot be guaranteed to be erased and that the provider may charge
the visitor (FR-003, FR-008, FR-021); (c) the "forget key" action is always there and takes effect at once (FR-014);
(d) the catalog shows only the models that were tested, with their status and their capabilities (FR-016, FR-030);
(e) the price of a model comes with its provenance, and a model whose price was never verified shows no amount at
all and never claims a verification (FR-011, FR-031); (f) the live mode is refused while the product runs offline,
with an answer that names the reason, and the rest of the demo keeps working (FR-001, FR-029); (g) the route of the
run refuses a model outside the allowlist, refuses a body that carries a raw key, refuses a body the published
contract forbids and refuses the mode of the sandbox (FR-027, FR-007, FR-025); (h) the cost report shows the observed
cost and the estimated cost apart (FR-010); (i) the end of a session drops the credentials of that session, from the
live mode and from the sandbox (FR-022); (j) the caps of the request are the caps of the run, cap by cap (FR-025);
(k) the cap of the calls of the models stops the run at the attempt that would break it, for every cap the contract
allows (FR-009); (l) a run that is over is never told that it was cancelled (FR-019); (m) a session that may not run
the live mode never runs it (FR-024); (n) the route of the run resolves the branch of the visitor before the run
starts, and it refuses a branch of another session, an expired branch, a branch that cannot prove its own state, an
account that is not the account of the branch and a revision that moved, with a readable reason and without
calling any provider (ADR-038); (o) the trace of the run names the branch, the revision and the hash of the state
that was read, and the run reads the ledger of that branch and not the ledger of the configuration (ADR-038);
(p) the run carries the case of the application and the coordinator of the caller is never rewritten, so a
coordinator keeps the case it was built with (ADR-038); (q) the API never accepts an endpoint, so a
body that carries one is refused, and a deployment that points the adapter at a link-local endpoint
is refused before any provider is called, with the code of the rule (FR-017);
(r) a refusal of the live mode carries the headers it was given, the way the refusals of the sandbox do (ADR-047).

Everything offline, with no key and no network: the provider is the fake adapter of the domain and the tests never
open a socket. The application of the tests is wired the way a deployment wires it: one session issuer over one key
file, one store of the branches and one branch layer over the resolver of the base (ADR-038).
"""

from __future__ import annotations

import json
import sys
import threading
import time
import tomllib
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402
from jsonschema import Draft202012Validator  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from ledgerlens.api import byok as byok_api  # noqa: E402
from ledgerlens.api.byok import LiveRunRequest, RunLimits, create_app  # noqa: E402
from ledgerlens.api.live_run import LiveRunCoordinator, LiveRunPlan, ModelCaller  # noqa: E402
from ledgerlens.api.sandbox import SESSION_COOKIE, ContractError  # noqa: E402
from ledgerlens.byok.adapter import (  # noqa: E402
    ENDPOINT_LINK_LOCAL,
    EndpointRefused,
    FakeProviderAdapter,
    ProviderRequest,
    build_adapter,
)
from ledgerlens.byok.registry import ModelNotAllowed, ModelProfile, Pricing, ProviderRegistry  # noqa: E402
from ledgerlens.byok.vault import DEFAULT_TTL_SECONDS, CredentialHandle, CredentialVault  # noqa: E402
from ledgerlens.config import Settings  # noqa: E402
from ledgerlens.run_context import RunBudget  # noqa: E402
from ledgerlens.sandbox.branch import BranchLayer  # noqa: E402
from ledgerlens.sandbox.factory import build_branch_store  # noqa: E402
from ledgerlens.sandbox.session import SessionIssuer  # noqa: E402
from ledgerlens.sandbox.snapshot import BaseResolver  # noqa: E402

# The marker of the credential of the visitor: a shape that no known pattern of the repository matches, so only the
# vault and the adapter of the run can scrub it.
MARKER = "ledgerlens-marker-" + "4f3a9c2b7e1d"

# The marker of a value that the vault never accepted. It is the value that a refusal must not repeat: the scrub of
# the vault knows the credentials it holds and the shapes the repository knows, and this marker is neither.
UNKNOWN_MARKER = "ledgerlens-unknown-" + "9b2c4e7a1f30"

# A marker with the shape of a key of a provider, so the generic redaction of the repository matches it.
SHAPED_MARKER = "sk-" + "test-marker-0123456789abcdef"

# The answer of the triage of the agent of the demo: a plan with the only tool the run needs, so the agent is not
# asked for a second time.
TRIAGE_ANSWER = json.dumps(
    {
        "intent": "status_lookup",
        "entities": {"transaction_ids": ["TX-2048"]},
        "urgency": "normal",
        "plan": [{"id": "S1", "goal": "read the ledger", "tool": "query_ledger", "depends_on": []}],
        "needs_clarification": False,
        "clarification_question": None,
    }
)
# The SQL of the ledger: one read-only statement over an allowed table, about the transaction of the account of the
# branch of the visitor.
SQL_ANSWER = "SELECT id, status, amount_minor, currency FROM transactions WHERE id = 'TX-2048'"
# The answer of the agent of the demo, the last thing the provider says.
FINAL_ANSWER = "The payment of TX-2048 was captured and the refund is on its way."

PROFILE_ID = "openai-gpt-4.1-mini"
MODEL_ID = "gpt-4.1-mini"
UNPRICED_ID = "openai-mystery"

# The scenario of the visitor and the account of that scenario. The branch of the visitor is a branch of that
# scenario, and the account of the request has to be the account of the branch (ADR-038).
SCENARIO_ID = "S01"
ACCOUNT_ID = "C-0412"
# The account of another customer of the same published ledger. A request that names it is refused, because the rows
# of that customer are not the rows of the visitor.
ANOTHER_ACCOUNT_ID = "C-0001"

# The endpoint of a provider that reaches the machine itself: the address of the metadata of a cloud machine. The
# public demo refuses it before it opens a socket, because a request that goes there reads the credentials of the
# machine instead of the answer of the provider (FR-017).
LINK_LOCAL_ENDPOINT = "http://169.254.169.254/latest/meta-data"

PRICED = ModelProfile(
    profile_id=PROFILE_ID,
    provider="openai",
    model_id=MODEL_ID,
    display_name="GPT-4.1 mini",
    capabilities=("chat", "tool_calling"),
    status="tested",
    enabled_in_public_demo=True,
    pricing=Pricing(
        source="manual",
        last_verified=date(2026, 11, 8),
        input_per_1m_usd=Decimal("0.40"),
        output_per_1m_usd=Decimal("1.60"),
    ),
)
UNPRICED = ModelProfile(
    profile_id=UNPRICED_ID,
    provider="openai",
    model_id="gpt-mystery",
    display_name="Mystery",
    capabilities=("chat", "tool_calling"),
    status="tested",
    enabled_in_public_demo=True,
    pricing=Pricing(source="unknown", last_verified=None, input_per_1m_usd=None, output_per_1m_usd=None),
)
WITHOUT_TOOLS = ModelProfile(
    profile_id="openai-chat-only",
    provider="openai",
    model_id="gpt-chat-only",
    display_name="Chat only",
    capabilities=("chat",),
    status="tested",
    enabled_in_public_demo=True,
    pricing=Pricing(source="unknown", last_verified=None, input_per_1m_usd=None, output_per_1m_usd=None),
)


def _registry() -> ProviderRegistry:
    """The allowlist of the tests: a model with a price, one without and one without tool calling."""
    return ProviderRegistry([PRICED, UNPRICED, WITHOUT_TOOLS])


def _adapter() -> FakeProviderAdapter:
    """The fake provider of the tests, with the marker of the credential of the visitor inside it."""
    return FakeProviderAdapter(provider="openai", api_key=MARKER).script_answer(
        "the refund is lower than the payment", input_tokens=120, output_tokens=30
    )


@pytest.fixture
def online(monkeypatch: pytest.MonkeyPatch) -> None:
    """The product is online for the tests of the live mode."""
    monkeypatch.setenv("LEDGERLENS_OFFLINE", "0")


@pytest.fixture
def vault() -> CredentialVault:
    """A vault of the test, given to the application of the test.

    Why the vault is given and not taken from a global: the facade of the live mode never reaches for a global, so a
    test that builds an application says which vault it uses (ADR-035).
    """
    the_vault = CredentialVault()
    yield the_vault


@pytest.fixture
def issuer(tmp_path: Path) -> SessionIssuer:
    """The issuer of the sessions of the test.

    Why the issuer is given to the applications: the two facades of the demo are the same visitor when they are
    given the same issuer, and they are two visitors when they are not (ADR-035).
    """
    return SessionIssuer(tmp_path / "demo-session.key")


@pytest.fixture(scope="module")
def branch_layer(tmp_path_factory: pytest.TempPathFactory) -> BranchLayer:
    """The branch layer of the sandbox, wired the way a deployment wires it.

    Why one store and one layer for the module: the deployment gives the two facades the same layer, and the layer
    holds the resolver of the base, which builds the base of a scenario once and keeps it. A layer per test would
    build the same base again and again for nothing (ADR-038).

    Why the store comes from the factory: the factory is what turns the configuration into a store, and the tests
    use the file backed one, in a temporary folder, so the suite never touches the database of the machine (ADR-020).
    """
    root = tmp_path_factory.mktemp("sandbox")
    settings = Settings(runtime_dir=root / "runtime")
    return BranchLayer(build_branch_store(settings), BaseResolver(root / "bases"))


def _the_branch_of(layer: BranchLayer, session_id: str) -> str:
    """The branch of the visitor for the scenario, forked for the session of that visitor.

    Why the branch is forked and not made up: the run reads the ledger of the branch of the visitor, and the layer
    refuses a branch that belongs to nobody, so a body that names an invented identifier never starts a run
    (ADR-038).
    """
    return layer.fork(session_id, SCENARIO_ID).branch.branch_id


def _branch_of(client: TestClient) -> str:
    """The identifier of the branch of the visitor of this client.

    Why the client carries it: the fixture forks the branch once the session of the visitor exists, and the body of
    the run has to name that branch (ADR-038).
    """
    return str(cast(Any, client).branch_id)


def _the_light_case(caller: ModelCaller, plan: LiveRunPlan) -> str:
    """The case of the tests of the facade: one call of the model of the run and the answer of the provider.

    Why the case is light and not the case of the demo: the tests of this file are about the facade, and the agent of
    the demo has a file of its own. The route resolves the branch of the visitor either way, so the ledger of the
    visitor is read by the run whatever the case does with it (ADR-038).
    """
    response = caller.complete(
        ProviderRequest(model_id=MODEL_ID, messages=({"role": "user", "content": plan.question},))
    )
    return str(response.content)


@pytest.fixture
def client(
    online: None, vault: CredentialVault, issuer: SessionIssuer, branch_layer: BranchLayer, tmp_path: Path
) -> TestClient:
    """The client of the live mode, over the fake provider and with a session and a branch of the visitor.

    Why the application is given the branch layer and the issuer of the deployment: the live run reads the ledger of
    the branch of the visitor, and the two facades are the same visitor when they are given the same issuer
    (ADR-035, ADR-038).

    Why the runtime folder is a temporary one: the file of the ledger of a run lives in it, and the run removes it
    when it ends (ADR-038).
    """
    adapter = _adapter()
    app = create_app(
        vault=vault,
        registry=_registry(),
        session_issuer=issuer,
        adapter_factory=lambda _provider, _key: adapter,
        branch_layer=branch_layer,
        executor=_the_light_case,
        runtime_dir=tmp_path / "runtime",
    )
    with TestClient(app) as the_client:
        session = the_client.post("/v1/sessions").json()
        cast(Any, the_client).branch_id = _the_branch_of(branch_layer, str(session["id"]))
        yield the_client


def _credential(client: TestClient, provider: str = "openai") -> str:
    """The handle of a credential of the visitor."""
    response = client.post("/v1/credentials", json={"provider": provider, "api_key": MARKER})
    assert response.status_code == 201, response.text
    return str(response.json()["handle"])


def _run_body(client: TestClient, handle: str, **overrides: object) -> dict[str, object]:
    """The body of the route of the live run, as the contract of the request.

    Why the body names the branch of the visitor: the run reads the ledger of the branch the visitor forked, and a
    body that names a branch of nobody is refused before the run starts (ADR-038).
    """
    body: dict[str, object] = {
        "mode": "live_agent",
        "scenario_id": SCENARIO_ID,
        "sandbox_id": _branch_of(client),
        "expected_revision": 0,
        "account_id": ACCOUNT_ID,
        "question": "What happened to the refund of TX-2048?",
        "variant": "B",
        "model_profile_id": PROFILE_ID,
        "credential_handle": handle,
        "limits": {
            "max_model_calls": 2,
            "max_tool_calls": 4,
            "max_wall_seconds": 30,
            "max_output_tokens": 512,
        },
    }
    body.update(overrides)
    return body


def _wait_for_the_end(client: TestClient, run_id: str, timeout: float = 5.0) -> dict[str, object]:
    """Waits for the end of a run and answers the state of it."""
    deadline = time.monotonic() + timeout
    state: dict[str, object] = {}
    while time.monotonic() < deadline:
        response = client.get(f"/v1/live-runs/{run_id}")
        assert response.status_code == 200, response.text
        state = dict(response.json())
        if state["status"] != "running":
            return state
        time.sleep(0.01)
    return state


# --- the credential --------------------------------------------------------------------------------


def test_the_credential_route_never_returns_the_secret(client: TestClient) -> None:
    """FR-004: the answer of the credential route carries the handle and never the key."""
    response = client.post("/v1/credentials", json={"provider": "openai", "api_key": MARKER})

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"handle", "provider", "created_at", "expires_at"}
    assert body["provider"] == "openai"
    assert MARKER not in response.text
    assert MARKER not in repr(body)


def test_the_credential_route_says_that_nothing_is_stored(client: TestClient) -> None:
    """FR-003, FR-008: the answer carries the headers of nothing stored and the disclosure of the billing."""
    response = client.post("/v1/credentials", json={"provider": "openai", "api_key": MARKER})

    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert "not stored" in response.headers[byok_api.KEY_STORAGE_HEADER]
    assert "charge" in response.headers[byok_api.BILLING_DISCLOSURE_HEADER]


def test_the_credential_route_refuses_a_provider_that_the_server_does_not_publish(client: TestClient) -> None:
    """FR-016: the server publishes the providers of the live mode and refuses the others."""
    response = client.post("/v1/credentials", json={"provider": "nowhere", "api_key": MARKER})

    assert response.status_code == 422
    assert response.json()["code"] == byok_api.CODE_UNKNOWN_PROVIDER


def test_the_forget_route_drops_the_key_at_once(client: TestClient) -> None:
    """FR-014: the action of forgetting the key takes effect immediately."""
    handle = _credential(client)

    response = client.post("/v1/credentials/forget", json={"handle": handle})

    assert response.status_code == 200
    assert response.json()["forgotten"] is True
    assert "gone" in response.json()["message"]
    again = client.post("/v1/credentials/forget", json={"handle": handle})
    assert again.json()["forgotten"] is False


def test_the_forget_route_always_answers(client: TestClient) -> None:
    """FR-014: the action is always there, even when there was no key to forget."""
    response = client.post("/v1/credentials/forget", json={"handle": "a-handle-that-never-existed"})

    assert response.status_code == 200
    assert response.json()["forgotten"] is False


# --- the catalog ---------------------------------------------------------------------------------


def test_the_catalog_lists_only_the_models_that_were_tested(client: TestClient) -> None:
    """FR-016, FR-030: the catalog shows the tested models, with their status and their capabilities."""
    response = client.get("/v1/models")

    assert response.status_code == 200
    models = response.json()["models"]
    identifiers = [model["profile_id"] for model in models]
    assert PROFILE_ID in identifiers
    assert WITHOUT_TOOLS.profile_id not in identifiers
    for model in models:
        assert model["status"] == "tested"
        assert "tool_calling" in model["capabilities"]


def test_the_price_route_shows_the_provenance_and_the_day(client: TestClient) -> None:
    """FR-031: the price of a model comes with its provenance and the day it was verified."""
    response = client.get(f"/v1/models/{PROFILE_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["price_known"] is True
    assert body["model"]["pricing"]["last_verified"] == "2026-11-08"
    assert body["model"]["pricing"]["source"] == "manual"
    assert body["model"]["pricing"]["input_per_1m_usd"] == "0.40"


def test_the_price_route_says_that_the_price_is_unknown(client: TestClient) -> None:
    """FR-011: a model whose price was never verified shows no amount at all.

    Why the note may not claim a verification: the note of a model whose price is unknown says that the price is
    unknown, and a note that says that the price was verified would tell the visitor that the server knows a price
    it does not know (FR-031).
    """
    response = client.get(f"/v1/models/{UNPRICED_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["price_known"] is False
    assert "unknown" in body["price_note"]
    assert "verified" not in body["price_note"]
    assert body["model"]["pricing"]["input_per_1m_usd"] is None
    assert body["model"]["pricing"]["output_per_1m_usd"] is None


def test_the_price_route_refuses_a_model_outside_the_allowlist(client: TestClient) -> None:
    """FR-027: the server does not price a model it does not publish."""
    response = client.get("/v1/models/gpt-9-turbo")

    assert response.status_code == 404


# --- the live mode is opt-in -----------------------------------------------------------------------


def test_the_live_mode_is_refused_while_the_product_is_offline(
    online: None, vault: CredentialVault, issuer: SessionIssuer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-001, FR-029: the live mode is refused with a readable answer that names the reason."""
    monkeypatch.setenv("LEDGERLENS_OFFLINE", "1")
    app = create_app(
        vault=vault,
        registry=_registry(),
        session_issuer=issuer,
        adapter_factory=lambda _p, _k: _adapter(),
    )
    with TestClient(app) as client:
        client.post("/v1/sessions")
        response = client.post("/v1/credentials", json={"provider": "openai", "api_key": MARKER})

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == byok_api.CODE_LIVE_MODE_OFFLINE
    assert "offline" in body["message"]
    assert "replay and the sandbox keep working" in body["message"]


def test_the_rest_of_the_demo_keeps_working_while_the_product_is_offline(
    online: None, vault: CredentialVault, issuer: SessionIssuer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-001: the refusal of the live mode does not touch the rest of the demo."""
    monkeypatch.setenv("LEDGERLENS_OFFLINE", "1")
    app = create_app(
        vault=vault,
        registry=_registry(),
        session_issuer=issuer,
        adapter_factory=lambda _p, _k: _adapter(),
    )
    with TestClient(app) as client:
        assert client.get("/v1/models").status_code == 200
        assert client.post("/v1/sessions").status_code == 201


def test_the_forget_route_answers_while_the_product_is_offline(
    online: None, vault: CredentialVault, issuer: SessionIssuer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-014: the action of forgetting the key is always there."""
    monkeypatch.setenv("LEDGERLENS_OFFLINE", "1")
    app = create_app(
        vault=vault,
        registry=_registry(),
        session_issuer=issuer,
        adapter_factory=lambda _p, _k: _adapter(),
    )
    with TestClient(app) as client:
        client.post("/v1/sessions")
        response = client.post("/v1/credentials/forget", json={"handle": "a-handle-that-never-existed"})

    assert response.status_code == 200


# --- the run ---------------------------------------------------------------------------------------


def test_the_run_route_refuses_a_model_outside_the_allowlist(client: TestClient) -> None:
    """FR-027: the server refuses the model of a run that is not in the allowlist."""
    handle = _credential(client)

    response = client.post("/v1/live-runs", json=_run_body(client, handle, model_profile_id="gpt-9-turbo"))

    assert response.status_code == 422
    assert response.json()["code"] == byok_api.CODE_MODEL_NOT_ALLOWED


def test_the_run_route_refuses_a_model_without_the_capability_of_the_variant(client: TestClient) -> None:
    """FR-015: the refusal names the capability that is missing."""
    handle = _credential(client)

    response = client.post("/v1/live-runs", json=_run_body(client, handle, model_profile_id=WITHOUT_TOOLS.profile_id))

    assert response.status_code == 422
    assert response.json()["code"] == byok_api.CODE_CAPABILITY_MISSING
    assert "tool_calling" in response.json()["message"]


def test_the_run_route_never_accepts_a_raw_key(client: TestClient) -> None:
    """FR-007: the body of the route of the run accepts no field that the contract does not have."""
    handle = _credential(client)
    body = _run_body(client, handle)
    body["api_key"] = MARKER

    response = client.post("/v1/live-runs", json=body)

    assert response.status_code == 422
    assert MARKER not in response.text


def test_the_run_answers_with_the_run_and_never_with_the_key(client: TestClient) -> None:
    """FR-004, FR-024: the answer of the run carries the identifier of the run and no key."""
    handle = _credential(client)

    response = client.post("/v1/live-runs", json=_run_body(client, handle))

    assert response.status_code == 201
    body = response.json()
    assert body["run_id"].startswith("run_")
    assert body["mode"] == "live_agent"
    assert MARKER not in response.text
    assert handle not in response.text


def test_the_run_ends_with_a_terminal_event_and_the_mode_live_agent(client: TestClient) -> None:
    """FR-020, FR-024: the trace of the run ends with a terminal event and every event is live."""
    handle = _credential(client)
    run_id = client.post("/v1/live-runs", json=_run_body(client, handle)).json()["run_id"]

    state = _wait_for_the_end(client, run_id)
    assert state["status"] == "completed"

    stream = client.get(f"/v1/live-runs/{run_id}/events")
    assert stream.status_code == 200
    assert "run.completed" in stream.text
    assert "recorded_replay" not in stream.text


def test_the_cost_route_shows_the_observed_and_the_estimated_apart(client: TestClient) -> None:
    """FR-010: the observed cost and the estimated cost are two numbers and never one."""
    handle = _credential(client)
    run_id = client.post("/v1/live-runs", json=_run_body(client, handle)).json()["run_id"]
    _wait_for_the_end(client, run_id)

    response = client.get(f"/v1/live-runs/{run_id}/cost")

    assert response.status_code == 200
    body = response.json()
    assert body["model_calls"] == 1
    assert body["input_tokens"] == 120
    assert body["output_tokens"] == 30
    assert body["observed_cost_usd"] is not None
    assert body["estimated_cost_usd"] is not None
    assert body["observed_cost_usd"] != body["estimated_cost_usd"]
    assert body["price_known"] is True


def test_the_cost_route_shows_no_amount_when_the_price_is_unknown(client: TestClient) -> None:
    """FR-011: a run whose model has no verified price shows no dollar amount at all."""
    handle = _credential(client)
    body = _run_body(client, handle, model_profile_id=UNPRICED_ID)
    run_id = client.post("/v1/live-runs", json=body).json()["run_id"]
    _wait_for_the_end(client, run_id)

    response = client.get(f"/v1/live-runs/{run_id}/cost")

    assert response.status_code == 200
    answer = response.json()
    assert answer["price_known"] is False
    assert answer["observed_cost_usd"] is None
    assert answer["estimated_cost_usd"] is None
    assert "unknown" in answer["note"]


def test_a_run_of_another_session_is_not_readable(client: TestClient) -> None:
    """FR-006, SC-002: the run of a visitor is invisible to another one."""
    handle = _credential(client)
    run_id = client.post("/v1/live-runs", json=_run_body(client, handle)).json()["run_id"]

    with TestClient(client.app) as other:
        other.post("/v1/sessions")
        response = other.get(f"/v1/live-runs/{run_id}")

    assert response.status_code == 404


def test_a_handle_of_another_session_never_runs(client: TestClient, branch_layer: BranchLayer) -> None:
    """FR-006, SC-002: the handle of another session is refused and the run calls no provider.

    Why the other visitor forks a branch of its own: a branch belongs to exactly one session, so the other visitor
    cannot run with the branch of the first one, and the refusal of the branch would hide the refusal of the handle
    that this test is about (ADR-038).
    """
    handle = _credential(client)
    run_id = client.post("/v1/live-runs", json=_run_body(client, handle)).json()["run_id"]
    _wait_for_the_end(client, run_id)

    with TestClient(client.app) as other:
        session = other.post("/v1/sessions").json()
        cast(Any, other).branch_id = _the_branch_of(branch_layer, str(session["id"]))
        response = other.post("/v1/live-runs", json=_run_body(other, handle))
        assert response.status_code == 201
        other_run = response.json()["run_id"]
        state = _wait_for_the_end(other, other_run)

    assert state["status"] == "failed"
    assert "unknown" in str(state["error"])


def test_the_cancel_route_ends_the_run_and_says_that_the_cancellation_is_a_best_effort(
    online: None, vault: CredentialVault, issuer: SessionIssuer, branch_layer: BranchLayer, tmp_path: Path
) -> None:
    """FR-019: the cancellation stops the run and says that a call in flight is a best effort."""
    entered = threading.Event()
    release = threading.Event()

    class Blocking(FakeProviderAdapter):
        def complete(self, request: object) -> object:
            entered.set()
            release.wait(5.0)
            return super().complete(request)

    adapter = Blocking(provider="openai", api_key=MARKER).script_answer("the answer")
    app = create_app(
        vault=vault,
        registry=_registry(),
        session_issuer=issuer,
        adapter_factory=lambda _provider, _key: adapter,
        branch_layer=branch_layer,
        executor=_the_light_case,
        runtime_dir=tmp_path / "runtime",
    )
    with TestClient(app) as client:
        session = client.post("/v1/sessions").json()
        cast(Any, client).branch_id = _the_branch_of(branch_layer, str(session["id"]))
        handle = _credential(client)
        run_id = client.post("/v1/live-runs", json=_run_body(client, handle)).json()["run_id"]
        assert entered.wait(5.0)

        responses = client.get("/openapi.json").json()["paths"]["/v1/sessions/current"]["delete"]["responses"]
        assert "RUN_RUNNING (retryable)" in responses["409"]["description"]
        schema = responses["409"]["content"]["application/json"]["schema"]
        assert schema["$ref"].endswith("/ContractErrorBody")
        refused = client.delete("/v1/sessions/current")
        assert refused.status_code == 409
        assert refused.json()["code"] == "RUN_RUNNING"
        assert len(vault) == 1

        answer = client.post(f"/v1/live-runs/{run_id}/cancel").json()

        assert answer["status"] == "cancelling"
        assert answer["best_effort"] is True
        assert "best effort" in str(answer["message"])

        # The provider answers and the run stops: the run ends as cancelled and the trace stays visible.
        release.set()
        assert _wait_for_the_end(client, run_id)["status"] == "cancelled"


# --- the endpoint of the provider -----------------------------------------------------------------------


def test_the_credential_route_refuses_a_body_that_carries_an_endpoint(client: TestClient) -> None:
    """FR-017: the API never takes an endpoint, so a body that carries one is refused.

    Why this is the first line of defence: the visitor never chooses the endpoint of the provider,
    and the contract of the credential has exactly two fields. A body that carries an endpoint, a
    link-local one included, is a body the contract does not have, and the facade refuses it before
    it reads anything of it (FR-007, FR-027).

    Why the refusal names the contract and not the field: the facade answers every body that does
    not match the contract with the same answer, so a refusal cannot be used to guess what the
    server reads.
    """
    response = client.post(
        "/v1/credentials",
        json={"provider": "openai", "api_key": MARKER, "endpoint": LINK_LOCAL_ENDPOINT},
    )

    assert response.status_code == 422
    assert response.json()["code"] == byok_api.CODE_INVALID_REQUEST
    assert "does not match the contract" in response.json()["message"]


def test_the_run_route_refuses_a_body_that_carries_a_link_local_endpoint(client: TestClient) -> None:
    """FR-017: the body of the run carries no endpoint either, so a link-local one never reaches the server.

    Why the run matters as much as the credential: the run is the request that spends the money of
    the visitor, and a body that named an endpoint would be a body that could point the server at
    the machine itself. The request is the published contract, and the published contract has no
    endpoint (FR-017, FR-027).
    """
    handle = _credential(client)
    body = _run_body(client, handle)
    body["endpoint"] = LINK_LOCAL_ENDPOINT

    response = client.post("/v1/live-runs", json=body)

    assert response.status_code == 422
    assert response.json()["code"] == byok_api.CODE_INVALID_REQUEST
    assert "does not match the contract" in response.json()["message"]
    # The refusal never carries the value of the visitor.
    assert MARKER not in response.text


def test_a_link_local_provider_endpoint_is_refused_before_any_provider_call(
    online: None, vault: CredentialVault, issuer: SessionIssuer, branch_layer: BranchLayer, tmp_path: Path
) -> None:
    """FR-017: a link-local endpoint is refused, and no provider is ever called.

    Why the adapter factory of the test points at the link-local address: the API refuses every
    body that names an endpoint, so the only way an endpoint reaches the server is a deployment
    that points the adapter at an endpoint of its own. This test is that deployment, and the
    refusal it gets is the refusal of the product and not a refusal of the test.
    """
    app = create_app(
        vault=vault,
        registry=_registry(),
        session_issuer=issuer,
        adapter_factory=lambda _provider, key: build_adapter("openai", key, endpoint=LINK_LOCAL_ENDPOINT),
        branch_layer=branch_layer,
        executor=_the_light_case,
        runtime_dir=tmp_path / "runtime",
    )
    with TestClient(app) as client:
        session = client.post("/v1/sessions").json()
        cast(Any, client).branch_id = _the_branch_of(branch_layer, str(session["id"]))
        handle = _credential(client)
        run_id = client.post("/v1/live-runs", json=_run_body(client, handle)).json()["run_id"]
        state = _wait_for_the_end(client, run_id)
        cost = client.get(f"/v1/live-runs/{run_id}/cost").json()

    # The run ends with the reason of the refusal, and the reason names the family of the address.
    assert state["status"] == "failed"
    assert "link-local" in str(state["error"])

    # The refusal came before the provider was called: the run spent nothing and shows no amount of money.
    assert cost["model_calls"] == 0
    assert cost["observed_cost_usd"] is None
    assert cost["estimated_cost_usd"] is None


def test_the_refusal_of_a_link_local_endpoint_carries_the_code_of_the_rule() -> None:
    """FR-017: the refusal of a link-local endpoint is machine readable, and the code names the rule."""
    with pytest.raises(EndpointRefused) as refused:
        build_adapter("openai", MARKER, endpoint=LINK_LOCAL_ENDPOINT)

    assert refused.value.code == ENDPOINT_LINK_LOCAL
    assert "link-local" in str(refused.value)


# --- the branch of the visitor ------------------------------------------------------------------------


def test_the_run_route_refuses_a_branch_of_another_session(client: TestClient, branch_layer: BranchLayer) -> None:
    """ADR-038: a branch of another session is refused with the generic answer, and no run starts.

    Why the branch of the other visitor is used: the branch of the visitor of the test belongs to its own session, and
    the other branch belongs to another one, so the layer refuses it exactly like a branch that does not exist.
    """
    handle = _credential(client)
    other = TestClient(client.app)
    other_session = other.post("/v1/sessions").json()
    other_branch = _the_branch_of(branch_layer, str(other_session["id"]))
    body = _run_body(client, handle, sandbox_id=other_branch)

    response = client.post("/v1/live-runs", json=body)

    assert response.status_code == 404
    assert response.json()["code"] == byok_api.CODE_NOT_FOUND
    assert other_branch not in response.text


def test_the_run_route_refuses_an_account_that_is_not_the_account_of_the_branch(client: TestClient) -> None:
    """ADR-038: the account of the request has to be the account of the branch, and a mismatch is refused.

    Why the refusal is a 422 and not a 404: the body of the visitor is the wrong one, and a status that blames it
    sends the visitor to look in the wrong place.
    """
    handle = _credential(client)

    response = client.post("/v1/live-runs", json=_run_body(client, handle, account_id=ANOTHER_ACCOUNT_ID))

    assert response.status_code == 422
    assert response.json()["code"] == byok_api.CODE_ACCOUNT_MISMATCH
    # The refusal names the reason and never the account that the visitor sent (FR-018, SC-001).
    assert ANOTHER_ACCOUNT_ID not in response.text


def test_the_run_route_refuses_a_revision_that_moved(client: TestClient) -> None:
    """ADR-038: the revision the request expected has to be the revision the branch is at.

    Why the revision matters: a run that answers about a state the visitor never saw answers a question nobody
    asked.
    """
    handle = _credential(client)

    response = client.post("/v1/live-runs", json=_run_body(client, handle, expected_revision=7))

    assert response.status_code == 409
    assert response.json()["code"] == byok_api.CODE_REVISION_MOVED


def test_a_live_application_without_a_branch_layer_refuses_the_run(
    online: None, vault: CredentialVault, issuer: SessionIssuer, branch_layer: BranchLayer, tmp_path: Path
) -> None:
    """ADR-038: an application without a branch layer refuses the run instead of reading the ledger of the
    configuration.

    Why the refusal is a 503 and not a 422: the body of the visitor is fine, and the deployment is what is missing.

    Why the visitor still forks a branch: the body of the run names the branch of the visitor, and the deployment
    that cannot resolve it is the one that is broken, not the body (ADR-038).
    """
    app = create_app(
        vault=vault,
        registry=_registry(),
        session_issuer=issuer,
        adapter_factory=lambda _provider, _key: _adapter(),
        executor=_the_light_case,
        runtime_dir=tmp_path / "runtime",
    )
    with TestClient(app) as client:
        session = client.post("/v1/sessions").json()
        cast(Any, client).branch_id = _the_branch_of(branch_layer, str(session["id"]))
        handle = _credential(client)
        body = _run_body(client, handle)

        response = client.post("/v1/live-runs", json=body)

    assert response.status_code == 503
    assert response.json()["code"] == byok_api.CODE_BRANCH_LAYER_MISSING


def test_the_trace_of_the_run_names_the_branch_that_was_read(client: TestClient) -> None:
    """ADR-038: the trace says which ledger the run read, with the branch, the revision and the hash of the state.

    Why the trace says it: a reader of a run has to know which state answered the question.
    """
    handle = _credential(client)
    run_id = client.post("/v1/live-runs", json=_run_body(client, handle)).json()["run_id"]
    _wait_for_the_end(client, run_id)

    stream = client.get(f"/v1/live-runs/{run_id}/events")

    assert stream.status_code == 200
    started = _the_event_of_the_stream(stream.text, "run.started")
    assert started["payload"]["branch_id"] == _branch_of(client)
    assert started["payload"]["branch_revision"] == 0
    assert started["payload"]["canonical_hash"]


def _the_event_of_the_stream(text: str, event_type: str) -> dict[str, Any]:
    """The event of the given type of the stream of the trace of a run."""
    for line in text.splitlines():
        if not line.startswith("data: "):
            continue
        event = json.loads(line[len("data: ") :])
        if event.get("event_type") == event_type:
            return dict(event)
    raise AssertionError(f"the stream of the run carries no event of the type {event_type}")


def test_the_run_of_the_demo_answers_about_the_ledger_of_the_branch_of_the_visitor(
    online: None, vault: CredentialVault, issuer: SessionIssuer, branch_layer: BranchLayer, tmp_path: Path
) -> None:
    """ADR-038: the agent of the demo reads the ledger of the branch of the visitor, and not the ledger of the
    configuration.

    Why the case of the demo is used here and not the light one: this is the test that says which ledger the tools of
    the agent read, and only the agent of the demo reads a ledger at all (ADR-038).

    Why the row of the transaction of the account of the branch is the proof: the ledger of the branch holds the rows
    of that account and of no other one, and the ledger of the configuration holds the rows of every account of the
    repository. A row that came back is a row of the ledger of the branch (ADR-038).
    """
    adapter = FakeProviderAdapter(provider="openai", api_key=MARKER)
    adapter.script_answer(TRIAGE_ANSWER)
    adapter.script_tool_call("query_ledger", json.dumps({"question": "the status of TX-2048"}), call_id="call_sql")
    adapter.script_answer(SQL_ANSWER)
    adapter.script_answer(FINAL_ANSWER)
    app = create_app(
        vault=vault,
        registry=_registry(),
        session_issuer=issuer,
        adapter_factory=lambda _provider, _key: adapter,
        branch_layer=branch_layer,
        runtime_dir=tmp_path / "runtime",
    )
    # The case of the demo asks the model four times, so the caps of the request have to allow them.
    limits = {"max_model_calls": 8, "max_tool_calls": 4, "max_wall_seconds": 30, "max_output_tokens": 512}
    with TestClient(app) as client:
        session = client.post("/v1/sessions").json()
        cast(Any, client).branch_id = _the_branch_of(branch_layer, str(session["id"]))
        handle = _credential(client)
        run_id = client.post("/v1/live-runs", json=_run_body(client, handle, limits=limits)).json()["run_id"]
        state = _wait_for_the_end(client, run_id)

    assert state["status"] == "completed", state
    assert state["answer"] == (
        "Human review required. Verification found 0 supported, 0 contradicted, 1 with insufficient evidence.\n\n"
        + FINAL_ANSWER
    )
    # The tool of the agent read the ledger of the branch: the row of the transaction of the account came back.
    answers_of_the_tools = [
        message.content for call in adapter.calls for message in call.messages if message.role == "tool"
    ]
    assert answers_of_the_tools
    assert "TX-2048" in answers_of_the_tools[0]


# --- the end of the session ------------------------------------------------------------------------


def test_the_end_of_the_session_drops_the_credentials_of_the_session(
    client: TestClient, vault: CredentialVault
) -> None:
    """FR-022: the key of a visitor dies with the session of the visitor."""
    _credential(client)
    assert len(vault) == 1

    response = client.delete("/v1/sessions/current")

    assert response.status_code == 204
    assert len(vault) == 0


def test_the_sandbox_drops_the_credentials_of_the_session_that_ends(
    client: TestClient, vault: CredentialVault, issuer: SessionIssuer, tmp_path: Path
) -> None:
    """FR-022: the route that ends the session in the sandbox drops the credentials too.

    Why the sandbox is given the vault and the issuer: the purge of a session drops from the vault of the
    application it belongs to, and the two facades are the same visitor when they are given the same issuer
    (ADR-035).
    """
    from ledgerlens.api.sandbox import create_app as create_sandbox_app
    from ledgerlens.sandbox.snapshot import BaseResolver
    from ledgerlens.sandbox.store import FileBranchStore

    _credential(client)
    assert len(vault) == 1

    sandbox = create_sandbox_app(
        store=FileBranchStore(tmp_path / "sandbox"),
        base_resolver=BaseResolver(tmp_path / "bases"),
        session_issuer=issuer,
        credential_vault=vault,
    )
    with TestClient(sandbox) as other:
        other.cookies.set(SESSION_COOKIE, client.cookies[SESSION_COOKIE])
        response = other.delete("/v1/sessions/current")

    assert response.status_code == 204
    assert len(vault) == 0


def test_the_sandbox_refuses_the_cookie_of_a_live_mode_with_a_issuer_of_its_own(
    client: TestClient, vault: CredentialVault, tmp_path: Path
) -> None:
    """ADR-035: the two facades share the session when they are given the same issuer, and not by accident."""
    from ledgerlens.api.sandbox import create_app as create_sandbox_app
    from ledgerlens.sandbox.snapshot import BaseResolver
    from ledgerlens.sandbox.store import FileBranchStore

    _credential(client)
    sandbox = create_sandbox_app(
        store=FileBranchStore(tmp_path / "sandbox"),
        base_resolver=BaseResolver(tmp_path / "bases"),
        session_issuer=SessionIssuer(tmp_path / "other-session.key"),
        credential_vault=vault,
    )
    with TestClient(sandbox) as other:
        other.cookies.set(SESSION_COOKIE, client.cookies[SESSION_COOKIE])
        response = other.delete("/v1/sessions/current")

    assert response.status_code == 401
    assert len(vault) == 1


# --- the contract of the request ----------------------------------------------------------------------


def test_the_run_route_refuses_the_mode_of_the_sandbox(client: TestClient) -> None:
    """FR-024: this route runs the live mode, and the deterministic sandbox has its own route."""
    handle = _credential(client)
    body = _run_body(client, handle)
    body["mode"] = "deterministic_sandbox"

    response = client.post("/v1/live-runs", json=body)

    assert response.status_code == 422
    assert response.json()["code"] == byok_api.CODE_WRONG_MODE


def test_the_run_route_refuses_a_body_that_the_published_contract_forbids(client: TestClient) -> None:
    """FR-025: the body of the request is the published contract, and the server keeps it.

    Why the negative money and the cap as a text: the contract says that the cap of money is never negative and
    that the counts are integers. A server that accepts a body the contract forbids breaks the contract (FR-007).
    """
    handle = _credential(client)

    negative_money = _run_body(client, handle)
    negative_money["limits"] = {**negative_money["limits"], "max_estimated_usd": -1}
    money = client.post("/v1/live-runs", json=negative_money)

    text_cap = _run_body(client, handle)
    text_cap["limits"] = {**text_cap["limits"], "max_model_calls": "4"}
    calls = client.post("/v1/live-runs", json=text_cap)

    assert money.status_code == 422
    assert money.json()["code"] == byok_api.CODE_INVALID_REQUEST
    # The refusal names what the contract refused, so the answer says which rule of the contract stopped the run.
    assert "minimum" in money.json()["message"]
    assert calls.status_code == 422
    assert calls.json()["code"] == byok_api.CODE_INVALID_REQUEST


def test_the_request_model_and_the_published_contract_cannot_drift() -> None:
    """FR-025: the model of the request and the schema of the contract accept and refuse the same bodies.

    Why the test compares the two instead of trusting one of them: the contract is what a client is written against,
    and a model that drifts away from it breaks the contract without anybody noticing (FR-007).
    """
    schema = json.loads(byok_api.RUN_REQUEST_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)

    # The caps of the request are the caps of the contract, and the request accepts no other field.
    published_limits = schema["properties"]["limits"]
    model_limits = RunLimits.model_json_schema()
    assert set(published_limits["required"]) == set(model_limits["required"])
    assert published_limits["additionalProperties"] is False
    assert model_limits["additionalProperties"] is False
    assert set(published_limits["properties"]) == set(model_limits["properties"])

    # The body of a run is accepted and refused exactly like the contract accepts and refuses it.
    for name, value, refused in _CONTRACT_CASES:
        body = _valid_body()
        body["limits"][name] = value
        assert bool(list(validator.iter_errors(body))) is refused, (name, value)
        with pytest.raises(ValidationError) if refused else _no_error():
            LiveRunRequest.model_validate(body)

    # The cases where the model is stricter than the contract are named, and the model is stricter on purpose.
    for (name, value), why in _DOCUMENTED_DIFFERENCES.items():
        body = _valid_body()
        body["limits"][name] = value
        assert not list(validator.iter_errors(body)), (name, value)
        with pytest.raises(ValidationError):
            LiveRunRequest.model_validate(body)
        assert why


class _no_error:
    """The context of a body the model accepts: the model raises when it refuses, and does nothing otherwise."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, kind: object, value: object, traceback: object) -> bool:
        return True


# The caps of the request, with the values the published contract accepts and the values it refuses.
_CONTRACT_CASES: list[tuple[str, object, bool]] = [
    ("max_model_calls", 0, True),
    ("max_model_calls", 1, False),
    ("max_model_calls", 20, False),
    ("max_model_calls", 21, True),
    ("max_model_calls", "4", True),
    ("max_model_calls", 4.5, True),
    ("max_tool_calls", 0, True),
    ("max_tool_calls", 1, False),
    ("max_tool_calls", 40, False),
    ("max_tool_calls", 41, True),
    ("max_wall_seconds", 4, True),
    ("max_wall_seconds", 5, False),
    ("max_wall_seconds", 180, False),
    ("max_wall_seconds", 181, True),
    ("max_output_tokens", 127, True),
    ("max_output_tokens", 128, False),
    ("max_output_tokens", 16000, False),
    ("max_output_tokens", 16001, True),
    ("max_input_tokens", 0, True),
    ("max_input_tokens", 1, False),
    ("max_input_tokens", None, False),
    ("max_estimated_usd", -1, True),
    ("max_estimated_usd", 0, False),
    ("max_estimated_usd", 0.25, False),
    ("max_estimated_usd", "0.25", False),
]

# The cases where the model of the request is stricter than the published contract, and why.
_DOCUMENTED_DIFFERENCES: dict[tuple[str, object], str] = {
    ("max_estimated_usd", "-0.5"): "the contract applies the minimum to the numbers only",
    ("max_estimated_usd", "abc"): "the contract accepts any text for the money and the model parses it",
}


def _valid_body() -> dict[str, object]:
    """A body of a run that the published contract accepts."""
    return {
        "mode": "live_agent",
        "scenario_id": "S01",
        "sandbox_id": "br_0123456789abcdef01234567",
        "expected_revision": 0,
        "account_id": "C-0412",
        "question": "What happened to the refund of TX-2048?",
        "variant": "B",
        "model_profile_id": PROFILE_ID,
        "credential_handle": "a-handle-of-a-credential",
        "limits": {
            "max_model_calls": 2,
            "max_tool_calls": 4,
            "max_wall_seconds": 30,
            "max_output_tokens": 512,
        },
    }


# --- the caps of the request -------------------------------------------------------------------------


def test_the_caps_of_the_request_are_the_caps_of_the_run(
    online: None, vault: CredentialVault, issuer: SessionIssuer, branch_layer: BranchLayer, tmp_path: Path
) -> None:
    """FR-025: every cap of the request is the cap of the budget of the run, and none of them is swapped.

    Why the test goes through the facade: the wiring from the request to the `RunBudget` is the only place where a
    cap can be raised, dropped or swapped, and a test that builds the budget by hand would not see it (FR-025).
    """
    coordinator = LiveRunCoordinator(
        registry=_registry(),
        vault=vault,
        adapter_factory=lambda _provider, _key: _adapter(),
    )
    app = create_app(
        vault=vault,
        registry=_registry(),
        session_issuer=issuer,
        coordinator=coordinator,
        adapter_factory=lambda _provider, _key: _adapter(),
        branch_layer=branch_layer,
        executor=_the_light_case,
        runtime_dir=tmp_path / "runtime",
    )
    limits = {
        "max_model_calls": 3,
        "max_tool_calls": 7,
        "max_wall_seconds": 45,
        "max_output_tokens": 900,
        "max_input_tokens": 5000,
        "max_estimated_usd": "0.25",
    }
    with TestClient(app) as client:
        session = client.post("/v1/sessions").json()
        cast(Any, client).branch_id = _the_branch_of(branch_layer, str(session["id"]))
        handle = _credential(client)
        run_id = client.post("/v1/live-runs", json=_run_body(client, handle, limits=limits)).json()["run_id"]
        _wait_for_the_end(client, run_id)
        result = coordinator.result(run_id)

    assert result is not None
    assert result.context.budget == RunBudget(
        max_model_calls=3,
        max_tool_calls=7,
        max_input_tokens=5000,
        max_output_tokens=900,
        max_estimated_usd=Decimal("0.25"),
        max_wall_seconds=45.0,
    )


def test_the_run_stops_at_the_attempt_that_would_break_the_cap_of_the_model_calls(
    online: None, vault: CredentialVault, issuer: SessionIssuer, branch_layer: BranchLayer, tmp_path: Path
) -> None:
    """FR-009, FR-025: the cap of the calls of the models stops the run, for every cap of the contract.

    Why every cap of the output tokens: the size of the answer is not known before the call, so the cap of the
    output tokens may not preempt the cap of the calls. The run has to reach the fourth call and stop at the fifth
    attempt, whatever the cap of the output tokens is (FR-009).
    """
    for output_cap in (128, 512, 16000):
        adapter = FakeProviderAdapter(provider="openai", api_key=MARKER)
        for index in range(5):
            adapter.script_answer(f"the answer {index}", input_tokens=10, output_tokens=5)
        coordinator = LiveRunCoordinator(
            registry=_registry(),
            vault=vault,
            adapter_factory=lambda _provider, _key, the_adapter=adapter: the_adapter,
            executor=_five_calls,
        )
        app = create_app(
            vault=vault,
            registry=_registry(),
            session_issuer=issuer,
            coordinator=coordinator,
            adapter_factory=lambda _provider, _key, the_adapter=adapter: the_adapter,
            branch_layer=branch_layer,
            executor=_five_calls,
            runtime_dir=tmp_path / "runtime",
        )
        limits = {
            "max_model_calls": 4,
            "max_tool_calls": 4,
            "max_wall_seconds": 30,
            "max_output_tokens": output_cap,
        }
        with TestClient(app) as client:
            session = client.post("/v1/sessions").json()
            cast(Any, client).branch_id = _the_branch_of(branch_layer, str(session["id"]))
            handle = _credential(client)
            run_id = client.post("/v1/live-runs", json=_run_body(client, handle, limits=limits)).json()["run_id"]
            state = _wait_for_the_end(client, run_id)
            cost = client.get(f"/v1/live-runs/{run_id}/cost").json()

        assert state["status"] == "failed", output_cap
        assert "max_model_calls" in str(state["error"]), output_cap
        assert cost["cut_by"] == "max_model_calls", output_cap
        assert cost["model_calls"] == 4, output_cap
        assert len(adapter.calls) == 4, output_cap


def _five_calls(caller: object, plan: object) -> str:
    """A case that asks the model five times, one after the other."""
    for _ in range(5):
        caller.complete(ProviderRequest(model_id=MODEL_ID, messages=({"role": "user", "content": "?"},)))
    return "done"


def test_the_cap_of_the_tools_stops_the_run_and_names_the_cap(
    online: None, vault: CredentialVault, issuer: SessionIssuer, branch_layer: BranchLayer, tmp_path: Path
) -> None:
    """FR-009, FR-012: every call of a tool reserves one, and the cap of the tools stops the run.

    Why the seam has to reach the tools: the agent of the demo uses them, and a cap of the tools that no call ever
    reserves is a cap that holds nothing (FR-009).
    """
    calls: list[str] = []

    def the_tool() -> str:
        """The tool of the test: it says that it ran."""
        calls.append("ledger.search")
        return "the tool answered"

    def the_case(caller: object, plan: object) -> str:
        """A case that uses the tool three times."""
        for _ in range(3):
            caller.call_tool("ledger.search", the_tool)
        return "done"

    coordinator = LiveRunCoordinator(
        registry=_registry(),
        vault=vault,
        adapter_factory=lambda _provider, _key: _adapter(),
        executor=the_case,
    )
    app = create_app(
        vault=vault,
        registry=_registry(),
        session_issuer=issuer,
        coordinator=coordinator,
        adapter_factory=lambda _provider, _key: _adapter(),
        branch_layer=branch_layer,
        executor=the_case,
        runtime_dir=tmp_path / "runtime",
    )
    limits = {
        "max_model_calls": 2,
        "max_tool_calls": 1,
        "max_wall_seconds": 30,
        "max_output_tokens": 512,
    }
    with TestClient(app) as client:
        session = client.post("/v1/sessions").json()
        cast(Any, client).branch_id = _the_branch_of(branch_layer, str(session["id"]))
        handle = _credential(client)
        run_id = client.post("/v1/live-runs", json=_run_body(client, handle, limits=limits)).json()["run_id"]
        state = _wait_for_the_end(client, run_id)
        cost = client.get(f"/v1/live-runs/{run_id}/cost").json()

    assert state["status"] == "failed"
    assert "max_tool_calls" in str(state["error"])
    assert cost["cut_by"] == "max_tool_calls"
    assert cost["tool_calls"] == 1
    assert calls == ["ledger.search"]


# --- the refusals of the facade ------------------------------------------------------------------------


def test_the_cancel_route_does_not_say_that_a_finished_run_was_cancelled(client: TestClient) -> None:
    """FR-019: a run that is over was not cancelled, and the answer says what really happened."""
    handle = _credential(client)
    run_id = client.post("/v1/live-runs", json=_run_body(client, handle)).json()["run_id"]
    assert _wait_for_the_end(client, run_id)["status"] == "completed"

    answer = client.post(f"/v1/live-runs/{run_id}/cancel").json()

    assert answer["status"] == "completed"
    assert "cancelled" not in str(answer["message"])
    assert "already over" in str(answer["message"])


def test_a_session_that_may_not_run_the_live_mode_never_runs_it(
    online: None, vault: CredentialVault, branch_layer: BranchLayer, tmp_path: Path
) -> None:
    """FR-024: a session of the sandbox may not run the live mode, and it never does.

    Why the rule is proved with a session the live mode did not issue: the modes of a session are declared when the
    session is issued, and the session of the sandbox is a session of the sandbox (ADR-035).

    Why the application is given the branch layer: the refusal of the mode happens before the branch of the visitor is
    resolved, and a body that names no branch at all would prove nothing about the order of the two (ADR-038).
    """
    app = create_app(
        vault=vault,
        registry=_registry(),
        session_issuer=SessionIssuer(tmp_path / "session.key"),
        adapter_factory=lambda _provider, _key: _adapter(),
        branch_layer=branch_layer,
    )
    with TestClient(app) as client:
        # A session that the live mode did not issue: the cookie of the sandbox, signed with the same key.
        session = client.post("/v1/sessions").json()
        assert "live_agent" in session["mode_capabilities"]
        cast(Any, client).branch_id = _the_branch_of(branch_layer, str(session["id"]))
        handle = _credential(client)
        # The jar of the client holds the cookie of the live session, and the cookie of the sandbox replaces it.
        client.cookies.clear()
        client.cookies.set(SESSION_COOKIE, _the_cookie_of_a_session_of_the_sandbox(tmp_path))

        response = client.post("/v1/live-runs", json=_run_body(client, handle))

    assert response.status_code == 403
    assert response.json()["code"] == byok_api.CODE_MODE_NOT_ALLOWED


def _the_cookie_of_a_session_of_the_sandbox(tmp_path: Path) -> str:
    """The cookie of a session that the sandbox issued, signed with the same key of the deployment."""
    issuer = SessionIssuer(tmp_path / "session.key")
    session = issuer.issue()
    return issuer.cookie_value(session)


def test_the_credential_route_carries_the_disclaimer_of_the_erasure(client: TestClient) -> None:
    """FR-021: the answer says that the memory of the machine cannot be guaranteed to be erased."""
    response = client.post("/v1/credentials", json={"provider": "openai", "api_key": MARKER})

    assert "cannot be guaranteed to be erased" in response.headers[byok_api.KEY_ERASURE_HEADER]
    assert "erase" not in response.headers[byok_api.KEY_STORAGE_HEADER]


def test_the_refusal_of_the_facade_never_carries_a_key(client: TestClient) -> None:
    """FR-018: the facade scrubs what it writes, and the refusal is what it writes.

    Why the answer is checked as a whole: the key must never travel in any part of the answer, and a body that says
    that the value was redacted still says where the value was (SC-001).
    """
    body = _run_body(client, "a-handle-of-a-credential")
    body["limits"] = {**body["limits"], "max_model_calls": SHAPED_MARKER}

    response = client.post("/v1/live-runs", json=body)

    assert response.status_code == 422
    assert SHAPED_MARKER not in response.text
    assert SHAPED_MARKER not in response.json()["message"]


def test_the_refusal_of_the_facade_never_carries_the_key_of_a_credential(client: TestClient) -> None:
    """FR-018: the scrub of the vault is the layer of the texts that the facade writes outside a run.

    Why the key of a credential is the marker: the shape of the key of the visitor is one the generic redaction
    never matches, and only the vault knows the exact text of the key it holds (FR-018).
    """
    handle = _credential(client)
    body = _run_body(client, handle)
    body["limits"] = {**body["limits"], "max_model_calls": MARKER}

    response = client.post("/v1/live-runs", json=body)

    assert response.status_code == 422
    assert MARKER not in response.text


# --- the value of the visitor never comes back ------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("mode", UNKNOWN_MARKER),
        ("scenario_id", UNKNOWN_MARKER),
        ("variant", UNKNOWN_MARKER),
        ("account_id", UNKNOWN_MARKER),
        ("limits.max_model_calls", UNKNOWN_MARKER),
    ],
)
def test_the_refusal_of_the_contract_never_quotes_the_value_of_the_visitor(
    client: TestClient, field: str, value: str
) -> None:
    """FR-018, SC-001: the refusal names the field that the contract refused and never the value of the field.

    Why the marker was never accepted by the vault: the scrub of the vault knows the credentials it holds and the
    shapes the repository knows, so a value it never saw is the value that a refusal has to refuse to quote. The
    message of the validator of the contract quotes that value, and the answer of the facade must not.
    """
    body = _run_body(client, "a-handle-of-a-credential")
    if field.startswith("limits."):
        body["limits"] = {**body["limits"], "max_model_calls": value}
    else:
        body[field] = value

    response = client.post("/v1/live-runs", json=body)

    assert response.status_code == 422
    assert response.json()["code"] == byok_api.CODE_INVALID_REQUEST
    assert value not in response.text
    assert value not in response.json()["message"]
    assert f"'{field}'" in response.json()["message"]


def test_the_refusal_of_the_other_routes_never_carries_the_value_of_the_visitor(client: TestClient) -> None:
    """FR-018: a refusal of any route of the facade carries no value that the visitor sent.

    Why the marker was never accepted by the vault: the scrub knows the credentials it holds and the shapes the
    repository knows, so a value it never saw is the value that a route must not repeat in its answer.
    """
    credential = client.post("/v1/credentials", json={"provider": UNKNOWN_MARKER, "api_key": MARKER})
    assert credential.status_code == 422
    assert credential.json()["code"] == byok_api.CODE_UNKNOWN_PROVIDER

    answers = [
        credential,
        client.post("/v1/credentials/forget", json={"handle": UNKNOWN_MARKER}),
        client.get(f"/v1/models/{UNKNOWN_MARKER}"),
        client.get(f"/v1/live-runs/{UNKNOWN_MARKER}"),
        client.get(f"/v1/live-runs/{UNKNOWN_MARKER}/cost"),
        client.post(f"/v1/live-runs/{UNKNOWN_MARKER}/cancel"),
    ]
    for answer in answers:
        assert UNKNOWN_MARKER not in answer.text, answer.text

    # The route of the session: a cookie that no issuer signed is refused, and the refusal does not quote it.
    client.cookies.clear()
    client.cookies.set(SESSION_COOKIE, UNKNOWN_MARKER)
    answer = client.delete("/v1/sessions/current")
    assert answer.status_code == 401
    assert UNKNOWN_MARKER not in answer.text


def _a_body_with_the_marker(client: TestClient, field: str, marker: str) -> dict[str, object]:
    """The body of a live run with the marker in one field and a valid body in every other field."""
    body = _run_body(client, "a-handle-of-a-credential")
    if field.startswith("limits."):
        body["limits"] = {**body["limits"], field.split(".", 1)[1]: marker}
    else:
        body[field] = marker
    return body


# Every field of the contract of the request of a run. The body of a visitor is untrusted, and every field of it may
# hold the key of the visitor, so every field of it has to be checked (FR-018, SC-001).
_THE_FIELDS_OF_THE_REQUEST = (
    "mode",
    "scenario_id",
    "sandbox_id",
    "expected_revision",
    "account_id",
    "question",
    "variant",
    "model_profile_id",
    "credential_handle",
    "limits.max_model_calls",
    "limits.max_tool_calls",
    "limits.max_wall_seconds",
    "limits.max_output_tokens",
    "limits.max_input_tokens",
    "limits.max_estimated_usd",
)


@pytest.mark.parametrize("field", _THE_FIELDS_OF_THE_REQUEST)
def test_no_field_of_the_request_of_a_run_carries_the_value_of_the_visitor_back(client: TestClient, field: str) -> None:
    """FR-018, SC-001: the answer of the route of the run carries no value that the visitor sent.

    Why the marker was never accepted by the vault: the scrub knows the credentials it holds and the shapes the
    repository knows, so a value it never saw is the value that an answer has to refuse to quote.
    """
    response = client.post("/v1/live-runs", json=_a_body_with_the_marker(client, field, UNKNOWN_MARKER))

    assert UNKNOWN_MARKER not in response.text, response.text


# Every route of the facade that takes a value of the visitor, and the way it takes it.
_THE_ROUTES_THAT_TAKE_A_VALUE: tuple[tuple[str, Callable[[TestClient, str], Any]], ...] = (
    (
        "the provider of the credential",
        lambda client, value: client.post("/v1/credentials", json={"provider": value, "api_key": MARKER}),
    ),
    (
        "the key of the credential",
        lambda client, value: client.post("/v1/credentials", json={"provider": "openai", "api_key": value}),
    ),
    (
        "the handle of the forgetting",
        lambda client, value: client.post("/v1/credentials/forget", json={"handle": value}),
    ),
    ("the model of the price", lambda client, value: client.get(f"/v1/models/{value}")),
    ("the run of the state", lambda client, value: client.get(f"/v1/live-runs/{value}")),
    ("the run of the cost", lambda client, value: client.get(f"/v1/live-runs/{value}/cost")),
    ("the run of the cancellation", lambda client, value: client.post(f"/v1/live-runs/{value}/cancel")),
    ("the run of the events", lambda client, value: client.get(f"/v1/live-runs/{value}/events")),
)


@pytest.mark.parametrize(
    ("route", "call"),
    _THE_ROUTES_THAT_TAKE_A_VALUE,
    ids=[name for name, _call in _THE_ROUTES_THAT_TAKE_A_VALUE],
)
def test_no_route_of_the_facade_carries_the_value_of_the_visitor_back(
    client: TestClient, route: str, call: Callable[[TestClient, str], Any]
) -> None:
    """FR-018, SC-001: no answer of any route of the facade quotes a value that the visitor sent.

    Why the marker was never accepted by the vault: the scrub knows the credentials it holds and the shapes the
    repository knows, so a value it never saw is the value that a route has to refuse to repeat.
    """
    answer = call(client, UNKNOWN_MARKER)

    assert UNKNOWN_MARKER not in answer.text, f"{route}: {answer.text}"


class _AnAllowlistThatRefusesWithAValue(ProviderRegistry):
    """An allowlist whose refusal quotes the value of the visitor, to prove that the handler scrubs what it writes."""

    def require(self, identifier: str) -> ModelProfile:
        raise ModelNotAllowed(f"the model '{MARKER}' is not in the allowlist of the server, so the run is refused")


def test_the_handler_of_the_refusals_scrubs_what_it_writes(
    online: None, vault: CredentialVault, issuer: SessionIssuer, branch_layer: BranchLayer
) -> None:
    """FR-018, SC-001: the handler scrubs the refusal it writes, whatever the refusal says.

    Why the allowlist of the test quotes a value: the refusal that the facade writes is not the refusal that the
    domain built, and the handler cannot trust the domain to leave the value out. The marker is the key that the
    vault holds, and only the vault knows its text: the generic redaction of the repository never matches it.

    Why the application is given the branch layer: the refusal of the model happens before the branch of the visitor
    is resolved, and the body of the run has to name a real branch for the refusal to be about the model (ADR-038).
    """
    app = create_app(
        vault=vault,
        registry=_AnAllowlistThatRefusesWithAValue(),
        session_issuer=issuer,
        adapter_factory=lambda _provider, _key: _adapter(),
        branch_layer=branch_layer,
    )
    with TestClient(app) as client:
        session = client.post("/v1/sessions").json()
        cast(Any, client).branch_id = _the_branch_of(branch_layer, str(session["id"]))
        client.post("/v1/credentials", json={"provider": "openai", "api_key": MARKER})

        response = client.post("/v1/live-runs", json=_run_body(client, "a-handle-of-a-credential"))

    assert response.status_code == 422
    assert MARKER not in response.text


class _AReaderOfTheLifeOfTheVault:
    """A reader that watches the life of the vault while the acceptances happen.

    Why the reader exists: the life of the vault is a property of the vault, and a reader that is not the acceptance
    has to see the same life before, during and after it. A design that writes the life of the vault for the moment
    of the acceptance shows a foreign life to this reader, and a reader is what tells the two designs apart.
    """

    def __init__(self, vault: CredentialVault) -> None:
        self._vault = vault
        self.seen: list[int] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._watch, name="reader-of-the-life", daemon=True)
        self._thread.start()

    def _watch(self) -> None:
        """Reads the life of the vault again and again, until the reader is stopped."""
        while not self._stop.is_set():
            self.seen.append(self._vault.ttl_seconds)
            time.sleep(0.005)

    def stop(self) -> list[int]:
        """Stops the reader and answers the lives that it saw."""
        self._stop.set()
        self._thread.join(timeout=2.0)
        return self.seen


def _widen_the_acceptance(vault: CredentialVault) -> None:
    """Widens the moment of the acceptance, so that a reader can see what happens inside it.

    Why the window is widened: the life of a credential is decided before the acceptance, and a test that does not
    widen that window cannot tell a design that hands the life to the vault from a design that writes the life on the
    vault and takes it back. The sleep is inside the acceptance, so the two acceptances of the test really meet.

    Why the life is optional in the wrapper: the wrapper has to work with a vault that takes a life and with a vault
    that does not, because the test has to tell the two designs apart and not fail on the shape of the call.
    """
    original = vault.accept

    def slow_accept(secret: str, provider: str, *, session_id: str, ttl_seconds: int | None = None) -> CredentialHandle:
        time.sleep(0.2)
        if ttl_seconds is None:
            return original(secret, provider, session_id=session_id)
        return original(secret, provider, session_id=session_id, ttl_seconds=ttl_seconds)

    vault.accept = slow_accept  # type: ignore[method-assign]


def _the_life_of_the_credential(answer: dict[str, Any]) -> float:
    """The life of the credential of an answer, in seconds."""
    created = datetime.fromisoformat(str(answer["created_at"]))
    expires = datetime.fromisoformat(str(answer["expires_at"]))
    return (expires - created).total_seconds()


def test_the_credential_never_outlives_the_session_that_holds_it(
    online: None, vault: CredentialVault, tmp_path: Path
) -> None:
    """FR-022: a credential dies with the session that holds it, and never later.

    Why the issuer of the test lives sixty seconds: the default of the repository hides the rule, because the life of
    a session is longer than the life of a credential, and the rule only shows with an issuer that lives less than
    the credential would.
    """
    issuer = SessionIssuer(tmp_path / "short-session.key", ttl_seconds=60)
    app = create_app(
        vault=vault,
        registry=_registry(),
        session_issuer=issuer,
        adapter_factory=lambda _provider, _key: _adapter(),
    )
    with TestClient(app) as client:
        session = client.post("/v1/sessions")
        credential = client.post("/v1/credentials", json={"provider": "openai", "api_key": MARKER})

    assert credential.status_code == 201, credential.text
    session_expiry = datetime.fromisoformat(session.json()["expires_at"])
    credential_expiry = datetime.fromisoformat(credential.json()["expires_at"])
    assert credential_expiry <= session_expiry, f"the credential lives {credential_expiry - session_expiry} longer"


def test_two_acceptances_at_the_same_time_each_take_the_life_of_their_own_session(
    online: None, vault: CredentialVault, tmp_path: Path
) -> None:
    """FR-022: two acceptances that meet never swap the life of their sessions.

    Why the two acceptances meet: the two applications share one vault and their sessions live a different number of
    seconds, and the window of the acceptance is widened so that the two really meet inside the vault.

    Why the reader watches: the life of the vault is a property of the vault, and a reader that is not the acceptance
    has to see the same life while the acceptances happen. A design that writes the life on the vault for the moment
    of the acceptance fails here, and so does a design that lets two acceptances swap their lives.
    """
    short = SessionIssuer(tmp_path / "short-session.key", ttl_seconds=60)
    long = SessionIssuer(tmp_path / "long-session.key", ttl_seconds=3000)
    app_short = create_app(
        vault=vault,
        registry=_registry(),
        session_issuer=short,
        adapter_factory=lambda _provider, _key: _adapter(),
    )
    app_long = create_app(
        vault=vault,
        registry=_registry(),
        session_issuer=long,
        adapter_factory=lambda _provider, _key: _adapter(),
    )
    _widen_the_acceptance(vault)
    reader = _AReaderOfTheLifeOfTheVault(vault)
    answers: dict[str, dict[str, Any]] = {}
    statuses: dict[str, int] = {}
    barrier = threading.Barrier(2)

    def accept(app: Any, name: str) -> None:
        """Accepts a key of a session of its own, at the same time as the other acceptance."""
        with TestClient(app) as client:
            client.post("/v1/sessions")
            barrier.wait()
            answer = client.post("/v1/credentials", json={"provider": "openai", "api_key": MARKER})
            statuses[name] = answer.status_code
            answers[name] = answer.json()

    threads = [
        threading.Thread(target=accept, args=(app_short, "short")),
        threading.Thread(target=accept, args=(app_long, "long")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    seen = reader.stop()

    assert statuses == {"short": 201, "long": 201}
    life_of_short = _the_life_of_the_credential(answers["short"])
    life_of_long = _the_life_of_the_credential(answers["long"])
    assert 50 <= life_of_short <= 60, f"the credential of the short session lives {life_of_short} seconds"
    assert 2900 <= life_of_long <= 3000, f"the credential of the long session lives {life_of_long} seconds"
    assert life_of_short < life_of_long
    # The life of the vault never changed, so no reader of the vault ever saw a foreign life.
    assert set(seen) == {DEFAULT_TTL_SECONDS}


def test_the_life_of_the_vault_is_never_changed_by_the_route(
    online: None, vault: CredentialVault, tmp_path: Path
) -> None:
    """FR-022: the route never changes the life of the vault, not even for the moment of the acceptance.

    Why the reader watches: the life of the vault is a property of the vault, and the route that accepts a key has to
    leave it as it was. A design that writes the life on the vault for the moment of the acceptance and takes it
    back shows a foreign life to every reader of the vault while the acceptance happens.

    Why the refusal is part of the test: a route that refuses a key has to leave the life of the vault as it was as
    well, and a refusal is a moment where the life of the vault could be left behind.

    Why the session of the test lives sixty seconds: the life of the credential has to be different from the life of
    the vault, because a life that was left behind and that happens to be the life of the vault anyway would not be
    seen by anybody.
    """
    issuer = SessionIssuer(tmp_path / "short-session.key", ttl_seconds=60)
    app = create_app(
        vault=vault,
        registry=_registry(),
        session_issuer=issuer,
        adapter_factory=lambda _provider, _key: _adapter(),
    )
    _widen_the_acceptance(vault)
    reader = _AReaderOfTheLifeOfTheVault(vault)
    with TestClient(app) as client:
        client.post("/v1/sessions")
        accepted = client.post("/v1/credentials", json={"provider": "openai", "api_key": MARKER})
        refused = client.post("/v1/credentials", json={"provider": "no-such-provider", "api_key": MARKER})
    seen = reader.stop()

    assert accepted.status_code == 201, accepted.text
    assert refused.status_code == 422, refused.text
    assert vault.ttl_seconds == DEFAULT_TTL_SECONDS
    assert set(seen) == {DEFAULT_TTL_SECONDS}


class _AnErrorOfTheContract:
    """An error of the contract with a path of its own."""

    def __init__(self, path: list[Any], validator: str = "type") -> None:
        self.path = path
        self.absolute_path = path
        self.validator = validator


class _AValidatorWithPathsOfAnotherType:
    """A validator whose errors carry paths of different types, as a contract that carries an array would."""

    def __init__(self, errors: list[_AnErrorOfTheContract]) -> None:
        self._errors = errors

    def iter_errors(self, _body: object) -> list[_AnErrorOfTheContract]:
        return self._errors


def test_a_body_with_errors_of_different_path_types_never_answers_500(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-025: the order of the errors of the contract cannot raise, so the route never answers 500.

    Why the validator of the test: the published contract carries no array today, so the path of an error holds no
    index in it, and two errors of different path types cannot happen yet. The rule still has to hold, because a
    contract with an array is a contract of the future, and a route that raises answers 500 to a body of the visitor.
    """
    errors = [
        _AnErrorOfTheContract(["limits", 0]),
        _AnErrorOfTheContract(["limits", "max_model_calls"]),
    ]
    monkeypatch.setattr(byok_api, "_validator_of_the_request", lambda: _AValidatorWithPathsOfAnotherType(errors))

    response = client.post("/v1/live-runs", json=_run_body(client, "a-handle-of-a-credential"))

    assert response.status_code == 422
    assert UNKNOWN_MARKER not in response.text


def test_the_session_answer_carries_the_disclaimer_of_the_erasure(client: TestClient) -> None:
    """FR-021: the answer of the session says that the memory of the machine cannot be guaranteed to be erased."""
    response = client.post("/v1/sessions")

    assert response.status_code == 201
    assert "cannot be guaranteed to be erased" in response.headers[byok_api.KEY_ERASURE_HEADER]


def test_the_answer_of_the_run_carries_the_disclaimer_of_the_erasure(client: TestClient) -> None:
    """FR-021: the answer of the run says that the memory of the machine cannot be guaranteed to be erased."""
    handle = _credential(client)

    response = client.post("/v1/live-runs", json=_run_body(client, handle))

    assert response.status_code == 201, response.text
    assert "cannot be guaranteed to be erased" in response.headers[byok_api.KEY_ERASURE_HEADER]


def test_the_state_of_a_run_carries_the_disclaimer_of_the_erasure(client: TestClient) -> None:
    """FR-021: the answer that describes a run carries the disclaimer of the erasure."""
    handle = _credential(client)
    run_id = client.post("/v1/live-runs", json=_run_body(client, handle)).json()["run_id"]
    _wait_for_the_end(client, run_id)

    response = client.get(f"/v1/live-runs/{run_id}")

    assert response.status_code == 200
    assert "cannot be guaranteed to be erased" in response.headers[byok_api.KEY_ERASURE_HEADER]


def test_the_events_of_a_run_carry_the_disclaimer_of_the_erasure(client: TestClient) -> None:
    """FR-021: the stream of the trace of a run carries the disclaimer of the erasure."""
    handle = _credential(client)
    run_id = client.post("/v1/live-runs", json=_run_body(client, handle)).json()["run_id"]
    _wait_for_the_end(client, run_id)

    response = client.get(f"/v1/live-runs/{run_id}/events")

    assert response.status_code == 200
    assert "cannot be guaranteed to be erased" in response.headers[byok_api.KEY_ERASURE_HEADER]


def test_the_cancel_route_carries_the_disclaimer_of_the_erasure(client: TestClient) -> None:
    """FR-021: the answer of the cancellation carries the disclaimer of the erasure."""
    handle = _credential(client)
    run_id = client.post("/v1/live-runs", json=_run_body(client, handle)).json()["run_id"]
    _wait_for_the_end(client, run_id)

    response = client.post(f"/v1/live-runs/{run_id}/cancel")

    assert response.status_code == 200
    assert "cannot be guaranteed to be erased" in response.headers[byok_api.KEY_ERASURE_HEADER]


def test_the_cost_route_carries_the_disclaimer_of_the_erasure(client: TestClient) -> None:
    """FR-021: the answer of the cost of a run carries the disclaimer of the erasure."""
    handle = _credential(client)
    run_id = client.post("/v1/live-runs", json=_run_body(client, handle)).json()["run_id"]
    _wait_for_the_end(client, run_id)

    response = client.get(f"/v1/live-runs/{run_id}/cost")

    assert response.status_code == 200
    assert "cannot be guaranteed to be erased" in response.headers[byok_api.KEY_ERASURE_HEADER]


def test_the_routes_that_hold_no_key_answer_normally(client: TestClient) -> None:
    """FR-021: the disclosure is uniform, and the answers that describe no run carry none.

    Why the absence matters: the disclaimer of the erasure is about the key of the visitor, and a route that holds
    no key and spends nothing has nothing to disclose.
    """
    catalog = client.get("/v1/models")
    price = client.get(f"/v1/models/{PROFILE_ID}")
    forgotten = client.post("/v1/credentials/forget", json={"handle": "a-handle-that-never-existed"})

    assert catalog.status_code == 200
    assert price.status_code == 200
    assert forgotten.status_code == 200
    assert forgotten.json()["forgotten"] is False
    for answer in (catalog, price, forgotten):
        assert byok_api.KEY_ERASURE_HEADER not in answer.headers


# --- the deployment of the live mode ----------------------------------------------------------------------


def test_the_refusal_when_jsonschema_is_absent_names_the_api_extra(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The route of the run needs jsonschema, and a deployment without it cannot serve the route.

    Why the status is not the one of a bad body: the body of the visitor is fine, and a status that blames it sends
    the visitor to look in the wrong place.
    """
    handle = _credential(client)
    monkeypatch.setitem(sys.modules, "jsonschema", None)

    response = client.post("/v1/live-runs", json=_run_body(client, handle))

    assert response.status_code == 503
    assert response.json()["code"] == byok_api.CODE_CONTRACT_UNAVAILABLE
    assert "jsonschema" in response.json()["message"]
    assert "api extra" in response.json()["message"]
    assert "dev extra" in response.json()["message"]
    assert "not the reason" in response.json()["message"]


def test_the_api_extra_installs_jsonschema() -> None:
    """The live mode belongs to the api extra, so the dependency of the route of the run belongs to it too.

    Why the dev extra installs it as well: the suite of the repository imports it, and a contributor who syncs only
    the extra of the development has to keep the suite working.
    """
    pyproject = tomllib.loads((Path(__file__).resolve().parents[2] / "pyproject.toml").read_text(encoding="utf-8"))
    extras = pyproject["project"]["optional-dependencies"]

    assert any(requirement.startswith("jsonschema") for requirement in extras["api"])
    assert any(requirement.startswith("jsonschema") for requirement in extras["dev"])


# --- the refusals of the live mode ----------------------------------------------------------------------


def test_a_refusal_of_the_live_facade_carries_the_headers_it_was_given(
    online: None, vault: CredentialVault, issuer: SessionIssuer
) -> None:
    """ADR-047: the headers of a refusal of the live mode reach the answer of the facade.

    Why this test exists: the handler of the wired application merges the headers of the refusal into the answer and
    the handler of the live facade wrote the header of the version of the schema alone, so a refusal of the live mode
    that carried a header would have lost it on the way out.

    Why the refusal is raised by a route of the test: no refusal of the live mode carries a header today, and the
    defect is the handler and not a route, so the test raises the refusal that the handler has to answer.
    """
    app = create_app(vault=vault, registry=_registry(), session_issuer=issuer)

    @app.get("/v1/a-refusal-that-carries-a-header")
    def a_refusal() -> None:
        raise ContractError(
            429,
            byok_api.CODE_RUN_RUNNING,
            "the run is still running",
            headers={"Retry-After": "7"},
        )

    with TestClient(app) as client:
        response = client.get("/v1/a-refusal-that-carries-a-header")

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "7"
    # The version of the schema is still there: the header of the refusal is merged into the answer, not over it.
    assert response.headers[byok_api.SCHEMA_VERSION_HEADER] == byok_api.SCHEMA_VERSION


def test_a_refusal_of_the_live_facade_without_headers_carries_only_the_version_of_the_schema(
    online: None, vault: CredentialVault, issuer: SessionIssuer
) -> None:
    """A refusal that carries no header carries no other header than the version of the schema.

    Why this test exists: the merge of the headers of the refusal must not invent one, or every refusal of the live
    mode would answer with a header that the refusal never asked for.
    """
    app = create_app(vault=vault, registry=_registry(), session_issuer=issuer)

    @app.get("/v1/a-refusal-without-a-header")
    def a_refusal() -> None:
        raise ContractError(404, byok_api.CODE_NOT_FOUND, "no such model in the allowlist of the server")

    with TestClient(app) as client:
        response = client.get("/v1/a-refusal-without-a-header")

    assert response.status_code == 404
    assert "Retry-After" not in response.headers
    assert response.headers[byok_api.SCHEMA_VERSION_HEADER] == byok_api.SCHEMA_VERSION


def test_the_docstring_of_the_facade_does_not_claim_a_cookie_in_common() -> None:
    """The docstring of the facade says what is true about the cookie of the live mode.

    Why the docstring is under test: a docstring that says that the two facades are the same visitor wires a
    deployment that nobody decided, and the wiring is a decision of the deployment (ADR-035).
    """
    docstring = byok_api.__doc__ or ""

    assert "reads the same cookie of the demo" not in docstring
    assert "session issuer" in docstring
    assert "decision of the deployment" in docstring
