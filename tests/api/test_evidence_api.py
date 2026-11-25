"""The standalone and wired routes that serve published evidence graphs.

What they guarantee, and why: (a) the graph of a run of another account is never served, because the scope of
the account is applied when the data is read; (b) the refusal discloses nothing about the run, because a refusal
that names the run is a refusal that confirms the run exists; (c) two reads of the same run return the same
bytes, because the graph is a read and a read is deterministic; (d) the route publishes the count of the nodes
it filtered, so a reader knows the graph was scoped.

Everything here runs offline, with no key and with no network: the `TestClient` calls the app in process, and
the runs are the published bundles of the repository.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from ledgerlens.api.evidence import create_app  # noqa: E402
from ledgerlens.api.wiring import build_wired_app  # noqa: E402
from ledgerlens.config import Settings  # noqa: E402
from ledgerlens.replay.bundle import EVENTS_FILE  # noqa: E402
from ledgerlens.sandbox.store import FileBranchStore  # noqa: E402
from ledgerlens.verify.graph import NODE_POLICY  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
BUNDLES = ROOT / "data" / "eval" / "replay"
ACCOUNT = "C-0412"


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(BUNDLES))


@pytest.fixture
def replay_with_changed_index(tmp_path: Path) -> Path:
    """Keep the recorded replay and change the digest in the current policy index."""
    moved = tmp_path / "data" / "eval" / "replay"
    shutil.copytree(BUNDLES, moved)
    index_meta = tmp_path / "data" / "index" / "policies_fastembed" / "index_meta.json"
    index_meta.parent.mkdir(parents=True)
    index_meta.write_text(json.dumps({"corpus_sha256": "f" * 64}), encoding="utf-8")
    return moved


def test_the_graph_of_a_run_is_served_with_the_scope_of_the_account(client: TestClient) -> None:
    """The graph of the run of the account is served, with the count of the nodes it filtered."""
    response = client.get("/evidence/replay-s01", params={"account": ACCOUNT})

    assert response.status_code == 200
    body = response.json()
    assert body["nodes"]
    assert body["edges"]
    assert body["filtered"] == 0
    assert body["snapshot_hash"]


def test_policy_nodes_carry_the_digest_from_the_published_graph(replay_with_changed_index: Path) -> None:
    """The current policy index can change without relabeling a recorded run."""
    published = json.loads((replay_with_changed_index / "graph" / "s01.json").read_text(encoding="utf-8"))
    with TestClient(create_app(replay_with_changed_index)) as client:
        response = client.get("/evidence/replay-s01", params={"account": ACCOUNT})

    assert response.status_code == 200
    assert published["corpus_digest"]
    assert {node["digest"] for node in response.json()["nodes"] if node["kind"] == NODE_POLICY} == {
        published["corpus_digest"]
    }


@pytest.mark.parametrize(
    "artifact_change",
    [
        pytest.param(None, id="missing-artifact"),
        pytest.param("{", id="invalid-json"),
        pytest.param([], id="invalid-artifact-shape"),
        pytest.param({"artifact": "other"}, id="other-artifact-kind"),
        pytest.param({"schema_version": "99"}, id="unknown-schema"),
        pytest.param({"run_id": "another-run"}, id="other-run"),
        pytest.param({"scenario": "OTHER"}, id="other-scenario"),
        pytest.param({"snapshot_hash": "0" * 64}, id="other-snapshot"),
        pytest.param({"bundle_digest": "0" * 64}, id="other-bundle"),
        pytest.param({"corpus_digest": None}, id="missing-corpus-digest"),
        pytest.param({"corpus_digest": "unrecorded"}, id="invalid-corpus-digest"),
    ],
)
def test_policy_digest_is_unknown_without_a_matching_artifact(
    replay_with_changed_index: Path, artifact_change: dict[str, str | None] | list[object] | str | None
) -> None:
    """A missing or mismatched artifact cannot lend a historical run a policy digest."""
    artifact_path = replay_with_changed_index / "graph" / "s01.json"
    if artifact_change is None:
        artifact_path.rename(artifact_path.with_suffix(".bak"))
    elif isinstance(artifact_change, str):
        artifact_path.write_text(artifact_change, encoding="utf-8")
    else:
        recorded = json.loads(artifact_path.read_text(encoding="utf-8"))
        changed = recorded | artifact_change if isinstance(artifact_change, dict) else artifact_change
        artifact_path.write_text(json.dumps(changed), encoding="utf-8")

    with TestClient(create_app(replay_with_changed_index)) as client:
        response = client.get("/evidence/replay-s01", params={"account": ACCOUNT})

    assert response.status_code == 200
    assert {node["digest"] for node in response.json()["nodes"] if node["kind"] == NODE_POLICY} == {""}


def test_missing_manifest_event_count_leaves_the_digest_unknown(replay_with_changed_index: Path) -> None:
    """Readable events still form a graph when the published manifest no longer matches."""
    path = replay_with_changed_index / "s01" / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    del manifest["events"]
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with TestClient(create_app(replay_with_changed_index)) as client:
        response = client.get("/evidence/replay-s01", params={"account": ACCOUNT})
    assert response.status_code == 200
    assert {node["digest"] for node in response.json()["nodes"] if node["kind"] == NODE_POLICY} == {""}


def test_policy_digest_is_unknown_when_the_bundle_files_change(replay_with_changed_index: Path) -> None:
    """The manifest hash still matches the artifact, but the bundle fails its file hash check."""
    events_path = replay_with_changed_index / "s01" / EVENTS_FILE
    events_path.write_bytes(events_path.read_bytes() + b"\n")

    with TestClient(create_app(replay_with_changed_index)) as client:
        response = client.get("/evidence/replay-s01", params={"account": ACCOUNT})

    assert response.status_code == 200
    assert {node["digest"] for node in response.json()["nodes"] if node["kind"] == NODE_POLICY} == {""}


def test_the_wired_app_serves_only_published_replay_evidence_without_a_session(tmp_path: Path) -> None:
    """A runtime replay cannot enter the public evidence route, even with a matching account."""
    runtime = tmp_path / "runtime"
    private_bundle = runtime / "replay" / "local"
    private_bundle.mkdir(parents=True)
    (private_bundle / "manifest.json").write_text(json.dumps({"run_id": "runtime-only"}), encoding="utf-8")
    private_ledger = private_bundle.parent / "ledger"
    private_ledger.mkdir()
    shutil.copyfile(BUNDLES / "ledger" / "s01.json", private_ledger / "local.json")
    app = build_wired_app(settings=Settings(), store=FileBranchStore(runtime / "sandbox"), runtime_dir=runtime)

    with TestClient(app) as client:
        published = client.get("/evidence/replay-s01", params={"account": ACCOUNT})
        wrong_account = client.get("/evidence/replay-s01", params={"account": "C-9999"})
        private = client.get("/evidence/runtime-only", params={"account": ACCOUNT})

    assert published.status_code == 200
    assert published.json()["nodes"]
    assert private.status_code == wrong_account.status_code == 404
    assert private.content == wrong_account.content


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


def test_an_evidence_that_names_a_record_of_another_account_is_filtered(tmp_path) -> None:
    """An evidence of the ledger that names a record of another account is out of the graph, and the count
    of the filtered nodes says so."""
    moved = tmp_path / "replay"
    shutil.copytree(BUNDLES, moved)
    ledger_path = moved / "ledger" / "s01.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    # The read of the account names a record of another account: the evidence of that read is out of scope.
    ledger["accounts"][0]["reads"][0]["records"] = ["TX-2048", "TX-9999"]
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")

    client = TestClient(create_app(moved))
    response = client.get("/evidence/replay-s01", params={"account": ACCOUNT})

    assert response.status_code == 200
    body = response.json()
    assert body["filtered"] == 1
    assert all(node["id"] != "sql:1" for node in body["nodes"])
