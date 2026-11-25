"""The route that serves the evidence graph of a run.

What they guarantee, and why: (a) the graph of a run of another account is never served, because the scope of
the account is applied when the data is read; (b) the refusal discloses nothing about the run, because a refusal
that names the run is a refusal that confirms the run exists; (c) two reads of the same run return the same
bytes, because the graph is a read and a read is deterministic; (d) the route publishes the count of the nodes
it filtered, so a reader knows the graph was scoped.

Everything here runs offline, with no key and with no network: the `TestClient` calls the app in process, and
the runs are the published bundles of the repository.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from ledgerlens.api.evidence import create_app  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
BUNDLES = ROOT / "data" / "eval" / "replay"
ACCOUNT = "C-0412"


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(BUNDLES))


def test_the_graph_of_a_run_is_served_with_the_scope_of_the_account(client: TestClient) -> None:
    """The graph of the run of the account is served, with the count of the nodes it filtered."""
    response = client.get("/evidence/replay-s01", params={"account": ACCOUNT})

    assert response.status_code == 200
    body = response.json()
    assert body["nodes"]
    assert body["edges"]
    assert body["filtered"] == 0
    assert body["snapshot_hash"]


def test_the_graph_of_a_run_of_another_account_is_never_served(client: TestClient) -> None:
    """The scope of the account is applied when the data is read, and a run of another account is refused."""
    response = client.get("/evidence/replay-s01", params={"account": "C-9999"})

    assert response.status_code == 404


def test_the_refusal_discloses_nothing_about_the_run(client: TestClient) -> None:
    """A refusal that names the run is a refusal that confirms the run exists."""
    response = client.get("/evidence/replay-s01", params={"account": "C-9999"})

    assert response.status_code == 404
    body = response.text
    assert "replay-s01" not in body
    assert "C-0412" not in body
    assert "C-9999" not in body
    assert "s01" not in body.lower()


def test_two_reads_of_the_same_run_return_the_same_bytes(client: TestClient) -> None:
    """The graph is a read, and a read is deterministic."""
    first = client.get("/evidence/replay-s01", params={"account": ACCOUNT})
    second = client.get("/evidence/replay-s01", params={"account": ACCOUNT})

    assert first.status_code == 200
    assert first.content == second.content
