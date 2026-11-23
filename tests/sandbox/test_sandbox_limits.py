"""The limits of the facade: the cap of the live branches of a session and the rate of the requests of a session.

Why this file exists: ADR-047 decides the two limits of the facade, the tecto of branches (decision 4) and the rate
per request (decision 5). The two limits answer with the same status, the same code and a different flag, so a test
that only looked at the status would not tell them apart, and this file holds both of them.

What the tests hold:

* the three settings of the limits exist, with the names and the defaults of the decision, and they are read from the
  environment by the mechanism of the repository;
* the header `Retry-After` is named among the headers the browser may read, because a browser cannot read a header
  that the CORS does not expose;
* the refusal carries the headers it was given, and the body of the refusal is the resource `Error` of the contract
  field for field, with no header inside it;
* the sixth live branch of a session is refused with `429`, the code `RESOURCE_LIMIT_EXCEEDED` and the flag
  `retryable` at false, and the five first ones pass;
* the reuse of a scenario the session already holds comes BEFORE the cap, so it answers `200` and is never refused;
* a branch that is already dead does not count, even before the sweep of the cleanup deletes its row, and the rule of
  the life is the one of `ledgerlens/sandbox/ttl.py`;
* the request over the rate is refused with `429`, the code `RESOURCE_LIMIT_EXCEEDED`, the flag `retryable` at true and
  the header `Retry-After` with the number of seconds until the oldest request of the window falls out of it;
* the route that issues the session is not counted, because a visitor that asks for a session has no session yet;
* the window slides, so a request that fell out of the window does not count anymore;
* the two limits are told apart by the flag and not by the code.

Why the clock is the one of the suite: the rate and the expiry are decided by the server and never by the visitor
(FR-031), and a test that waits for a minute proves nothing. The clock of the suite is the `FakeClock` of the
conftest of the sandbox, and the facade is built with it.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from ledgerlens.api.cors import EXPOSED_HEADERS  # noqa: E402
from ledgerlens.api.sandbox import ContractError, create_app  # noqa: E402
from ledgerlens.config import get_settings  # noqa: E402
from ledgerlens.sandbox.rate_limit import RateLimiter  # noqa: E402
from ledgerlens.sandbox.snapshot import BaseResolver  # noqa: E402
from ledgerlens.sandbox.store import BranchStore  # noqa: E402
from ledgerlens.sandbox.ttl import is_expired  # noqa: E402
from tests.sandbox.conftest import FakeClock  # noqa: E402

# The code of the two limits, the one that already exists in the domain (ADR-031).
CODE_RESOURCE_LIMIT = "RESOURCE_LIMIT_EXCEEDED"
# The scenarios of the published sample. Five of them are the branches that a session may hold, and the sixth one is
# the fork that the cap refuses. The scenario `S04` is not one of them: it is the case of the sample with no account,
# and the facade refuses it with `404` before the cap is ever read.
LIVE_SCENARIOS = ("S01", "S02", "S03", "S05", "S07")
THE_SIXTH_SCENARIO = "S06"
# The names of the settings of the limits, as the decision names them.
BRANCH_CAP_ENV = "LEDGERLENS_SANDBOX_SESSION_BRANCH_CAP"
RATE_REQUESTS_ENV = "LEDGERLENS_SANDBOX_RATE_LIMIT_REQUESTS"
RATE_WINDOW_ENV = "LEDGERLENS_SANDBOX_RATE_LIMIT_WINDOW_SECONDS"
# The idle deadline of a branch, the one the setting of the configuration names by default.
IDLE_TTL_SECONDS = 3600


@pytest.fixture
def app(store: BranchStore, base_resolver: BaseResolver, clock: FakeClock):
    """The facade of the sandbox, over the store of the suite and the clock of the suite."""
    return create_app(store=store, base_resolver=base_resolver, clock=clock)


@pytest.fixture
def client(app) -> TestClient:
    """The client of the facade. It calls the application in process, so no test opens a port."""
    return TestClient(app)


@pytest.fixture
def visitor(client: TestClient) -> tuple[TestClient, str]:
    """A client that holds the cookie of a session, and the identifier of that session.

    Why the two together: the identifier names the owner of the branches in the store, and a test that counts the
    branches of the session needs it.
    """
    response = client.post("/v1/sessions")
    assert response.status_code == 201
    return client, str(response.json()["id"])


@pytest.fixture
def a_client_with_a_rate(
    monkeypatch: pytest.MonkeyPatch,
    store: BranchStore,
    base_resolver: BaseResolver,
    clock: FakeClock,
):
    """A factory of clients whose facade answers with the rate of the environment.

    Why the rate comes from the environment and not from an argument: the rate of the deployment is a setting, and a
    test that builds the facade the way a deployment builds it proves that the setting is the way the rate is chosen.
    """

    def build(requests: str, window: str = "60") -> TestClient:
        monkeypatch.setenv(RATE_REQUESTS_ENV, requests)
        monkeypatch.setenv(RATE_WINDOW_ENV, window)
        return TestClient(create_app(store=store, base_resolver=base_resolver, clock=clock))

    return build


# --- the settings of the limits -----------------------------------------------------------------------


def test_the_cap_of_the_branches_of_a_session_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(BRANCH_CAP_ENV, "3")
    assert get_settings().sandbox_session_branch_cap == 3


def test_the_rate_of_the_requests_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(RATE_REQUESTS_ENV, "7")
    monkeypatch.setenv(RATE_WINDOW_ENV, "9")
    settings = get_settings()
    assert settings.sandbox_rate_limit_requests == 7
    assert settings.sandbox_rate_limit_window_seconds == 9


def test_the_defaults_are_five_branches_and_one_hundred_and_twenty_requests_a_minute() -> None:
    settings = get_settings()
    assert settings.sandbox_session_branch_cap == 5
    assert settings.sandbox_rate_limit_requests == 120
    assert settings.sandbox_rate_limit_window_seconds == 60


# --- the header of the wait ----------------------------------------------------------------------------


def test_the_retry_after_is_among_the_headers_the_browser_may_read() -> None:
    assert "Retry-After" in EXPOSED_HEADERS


def test_the_refusal_carries_the_headers_it_was_given() -> None:
    error = ContractError(
        429,
        CODE_RESOURCE_LIMIT,
        "the session is over the rate",
        retryable=True,
        headers={"Retry-After": "12"},
    )
    assert error.headers == {"Retry-After": "12"}


def test_the_body_of_the_refusal_carries_no_header() -> None:
    """The body of the refusal is the resource `Error` of the contract, field for field.

    Why: the header is a header of the answer and not a field of the body, and a body that grows a field breaks the
    contract of the design package (ADR-023).
    """
    error = ContractError(429, CODE_RESOURCE_LIMIT, "the session is over the rate", headers={"Retry-After": "12"})
    assert set(error.body()) == {"code", "message", "retryable", "request_id"}


def test_a_refusal_without_headers_has_none() -> None:
    assert ContractError(404, "NOT_FOUND", "no sandbox").headers == {}


# --- the cap of the live branches of a session ---------------------------------------------------------


def test_the_five_first_branches_of_the_session_pass_and_the_sixth_one_is_refused(visitor) -> None:
    client, _ = visitor
    for scenario_id in LIVE_SCENARIOS:
        response = client.post("/v1/sandboxes", json={"scenario_id": scenario_id})
        assert response.status_code == 201, response.text

    refused = client.post("/v1/sandboxes", json={"scenario_id": THE_SIXTH_SCENARIO})

    assert refused.status_code == 429
    body = refused.json()
    assert body["code"] == CODE_RESOURCE_LIMIT
    # The flag is false: the branches of the session are alive, and a retry would be refused again.
    assert body["retryable"] is False


def test_the_refusal_of_the_cap_leaves_nothing_behind(visitor, store: BranchStore) -> None:
    """The check of the cap only reads: the refusal happens before the branch is created."""
    client, session_id = visitor
    for scenario_id in LIVE_SCENARIOS:
        assert client.post("/v1/sandboxes", json={"scenario_id": scenario_id}).status_code == 201

    refused = client.post("/v1/sandboxes", json={"scenario_id": THE_SIXTH_SCENARIO})

    assert refused.status_code == 429
    assert len(store.list_branches(session_id)) == len(LIVE_SCENARIOS)


def test_the_reuse_of_a_scenario_of_the_session_comes_before_the_cap(visitor) -> None:
    """A fork of a scenario the session already holds creates no branch, so the cap cannot refuse it."""
    client, _ = visitor
    for scenario_id in LIVE_SCENARIOS:
        assert client.post("/v1/sandboxes", json={"scenario_id": scenario_id}).status_code == 201

    reused = client.post("/v1/sandboxes", json={"scenario_id": LIVE_SCENARIOS[0]})

    assert reused.status_code == 200, reused.text


def test_a_branch_that_is_already_dead_does_not_count(visitor, store: BranchStore, clock: FakeClock) -> None:
    """A branch whose expiry has passed is dead, and it does not count even before the sweep deletes its row.

    Why the sweep is not run here: the sweep of the cleanup runs every thirty seconds, and a visitor must not be
    refused for the branches that are already dead (ADR-047, ADR-029).
    """
    client, session_id = visitor
    assert client.post("/v1/sandboxes", json={"scenario_id": LIVE_SCENARIOS[0]}).status_code == 201
    # The first branch outlives its idle deadline, and the four that follow are alive.
    clock.advance(timedelta(seconds=IDLE_TTL_SECONDS + 1))
    for scenario_id in LIVE_SCENARIOS[1:]:
        assert client.post("/v1/sandboxes", json={"scenario_id": scenario_id}).status_code == 201

    rows = store.list_branches(session_id)
    assert len(rows) == len(LIVE_SCENARIOS)
    assert any(is_expired(row, clock.now) for row in rows)

    # The fork of a new scenario passes, because only the four live branches count.
    assert client.post("/v1/sandboxes", json={"scenario_id": THE_SIXTH_SCENARIO}).status_code == 201


def test_the_rule_of_the_life_is_the_one_of_the_ttl(visitor, store: BranchStore, clock: FakeClock) -> None:
    """The count of the branches follows the check of the expiry of the module of the time to live."""
    client, session_id = visitor
    for scenario_id in LIVE_SCENARIOS:
        assert client.post("/v1/sandboxes", json={"scenario_id": scenario_id}).status_code == 201

    rows = store.list_branches(session_id)
    live = [row for row in rows if not is_expired(row, clock.now)]

    assert len(live) == len(LIVE_SCENARIOS)


# --- the rate of the requests of a session --------------------------------------------------------------


def test_the_request_over_the_rate_is_refused_with_the_wait(a_client_with_a_rate) -> None:
    client = a_client_with_a_rate("2")
    assert client.post("/v1/sessions").status_code == 201
    created = client.post("/v1/sandboxes", json={"scenario_id": "S01"})
    assert created.status_code == 201
    branch_id = created.json()["id"]

    assert client.get(f"/v1/sandboxes/{branch_id}").status_code == 200
    refused = client.get(f"/v1/sandboxes/{branch_id}")

    assert refused.status_code == 429
    body = refused.json()
    assert body["code"] == CODE_RESOURCE_LIMIT
    # The flag is true: the same request, later, is expected to answer.
    assert body["retryable"] is True
    # The wait is the number of seconds until the oldest request of the window falls out of it.
    assert int(refused.headers["Retry-After"]) == 60


def test_the_route_that_issues_the_session_is_not_counted(a_client_with_a_rate) -> None:
    """A visitor that asks for a session has no session yet, so the route spends no quota of one."""
    client = a_client_with_a_rate("1")
    assert client.post("/v1/sessions").status_code == 201

    # The quota of the session is one request, and the fork is the first request of the session.
    assert client.post("/v1/sandboxes", json={"scenario_id": "S01"}).status_code == 201

    # The quota of the session is spent by now, and the route that issues a session is not counted, so it answers.
    assert client.post("/v1/sessions").status_code == 201


def test_the_window_slides_and_the_request_that_fell_out_of_it_does_not_count(
    a_client_with_a_rate, clock: FakeClock
) -> None:
    client = a_client_with_a_rate("2")
    assert client.post("/v1/sessions").status_code == 201
    created = client.post("/v1/sandboxes", json={"scenario_id": "S01"})
    branch_id = created.json()["id"]
    assert client.get(f"/v1/sandboxes/{branch_id}").status_code == 200
    assert client.get(f"/v1/sandboxes/{branch_id}").status_code == 429

    # The window slides: the requests of the first minute fell out of it.
    clock.advance(timedelta(seconds=61))

    assert client.get(f"/v1/sandboxes/{branch_id}").status_code == 200


def test_the_counter_of_the_rate_slides_with_the_clock_of_the_server() -> None:
    """The counter holds the moments of the requests and drops the ones that fell out of the window."""
    clock = FakeClock()
    limiter = RateLimiter(limit=2, window_seconds=60, clock=clock)

    assert limiter.acquire("sess_one").allowed
    assert limiter.acquire("sess_one").allowed
    refused = limiter.acquire("sess_one")
    assert not refused.allowed
    assert refused.retry_after_seconds == 60

    clock.advance(timedelta(seconds=61))

    assert limiter.acquire("sess_one").allowed


def test_the_counter_of_the_rate_keeps_the_sessions_apart() -> None:
    limiter = RateLimiter(limit=1, window_seconds=60, clock=FakeClock())

    assert limiter.acquire("sess_one").allowed
    assert not limiter.acquire("sess_one").allowed
    # The quota of one session is not the quota of another one.
    assert limiter.acquire("sess_two").allowed


def test_the_session_that_asks_once_and_never_again_dies_with_its_window() -> None:
    """The memory of a visitor dies with the visitor: a session that says nothing for a minute leaves no key.

    Why the sweep happens on the request of another session: the counter has no timer of its own, and the request of
    another session is the moment where the dead keys are found and dropped (ADR-030).
    """
    clock = FakeClock()
    limiter = RateLimiter(limit=5, window_seconds=60, clock=clock)

    assert limiter.acquire("sess_gone").allowed
    assert "sess_gone" in limiter._moments

    clock.advance(timedelta(seconds=61))
    # Another session asks, and the window sweeps the sessions that said nothing for a minute.
    assert limiter.acquire("sess_alive").allowed

    assert "sess_gone" not in limiter._moments
    assert "sess_alive" in limiter._moments


# --- the two limits -------------------------------------------------------------------------------------


def test_the_two_limits_answer_with_the_same_code_and_a_different_flag(a_client_with_a_rate) -> None:
    """The code is the one of the family of the domain, and the flag is what tells the two limits apart."""
    client = a_client_with_a_rate("8")
    assert client.post("/v1/sessions").status_code == 201
    branch_id = ""
    for scenario_id in LIVE_SCENARIOS:
        created = client.post("/v1/sandboxes", json={"scenario_id": scenario_id})
        assert created.status_code == 201
        branch_id = str(created.json()["id"])

    capped = client.post("/v1/sandboxes", json={"scenario_id": THE_SIXTH_SCENARIO})
    assert capped.status_code == 429

    # The rate is spent by now, so the next request of the session is refused by the rate.
    rate_refused = None
    for _ in range(8):
        response = client.get(f"/v1/sandboxes/{branch_id}")
        if response.status_code == 429:
            rate_refused = response
            break

    assert rate_refused is not None
    assert capped.json()["code"] == rate_refused.json()["code"] == CODE_RESOURCE_LIMIT
    assert capped.json()["retryable"] is False
    assert rate_refused.json()["retryable"] is True
