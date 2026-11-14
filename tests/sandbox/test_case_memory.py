"""The case memory of a sandbox session: the folder of the session that owns the branch, and nothing shared.

What they guarantee, and why: (a) the memory folder of a branch is the folder of the session that owns it, because
the sandbox and the run context ask the same rule for the folder and the two cannot drift; (b) that folder is never
the global runtime folder of the configuration, so the memory of an anonymous visitor never reaches the memory of the
product; (c) the context of a branch carries the identity of the branch, its revision and its base hash, so every
trace and every answer says which branch it was (FR-042); (d) the isolation is proven in the data and not only in the
path, with the real case memory: a case written in the session of one branch is not read by another session (FR-027);
(e) the memory of a session dies with the session, so the memory of an anonymous visitor does not lie around under an
identifier nobody can reach again (ADR-030); (f) the purge refuses a folder that leaves the folder of the sessions and
a folder that carries the name of another session, because the one would delete what lives outside and the other would
delete the memory of another visitor; (g) the sandbox asks the run context for the folder and never computes it, and
an injected runtime folder holds the base of the scenarios too, so nothing of the sandbox lands in the runtime folder
of the machine.

Everything offline, with no key and no model: the scripted model answers what is needed, and every folder a test
touches is a temporary one, never the runtime folder of the repository.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from ledgerlens.agents.integrator import build_integrator  # noqa: E402
from ledgerlens.api.sandbox import create_app  # noqa: E402
from ledgerlens.config import get_settings  # noqa: E402
from ledgerlens.memory.long_term import CaseMemory  # noqa: E402
from ledgerlens.offline import ScriptedChatModel  # noqa: E402
from ledgerlens.run_context import RunContext, canonical_session_id  # noqa: E402
from ledgerlens.sandbox.branch import BranchLayer  # noqa: E402
from ledgerlens.sandbox.memory import (  # noqa: E402
    branch_run_context,
    purge_session_memory,
    session_memory_dir,
)
from ledgerlens.sandbox.snapshot import BaseResolver  # noqa: E402
from ledgerlens.sandbox.store import BranchStore  # noqa: E402
from ledgerlens.schemas import Coherence, InvestigationResult, Verdict  # noqa: E402


@pytest.fixture
def memory_layer(file_store: BranchStore, base_resolver: BaseResolver, clock) -> BranchLayer:
    """The branch layer over the file backed store, so the memory tests never touch the database."""
    return BranchLayer(file_store, base_resolver, clock=clock)


def _supported_result(session_id: str) -> InvestigationResult:
    """A result whose verdicts are all supported, which is what the memory accepts."""
    return InvestigationResult(
        session_id=session_id,
        question="the refund came in lower than the payment",
        answer="The difference is the refund fee.",
        claims=[],
        evidence=[],
        verdicts=[Verdict(claim_id="CL1", label="supported", method="rule")],
        coherence=Coherence(passed=True),
        recommended_action="explain_to_customer",
        requires_human_review=False,
    )


# --- the folder of a branch is the folder of its session -------------------------------------------


def test_the_memory_folder_of_a_branch_is_the_folder_of_the_session_that_owns_it(
    memory_layer: BranchLayer, session_id: str, scenario_id: str, tmp_path: Path
) -> None:
    """The branch writes in the folder of the session that owns it, and in no other."""
    branch = memory_layer.fork(session_id, scenario_id).branch
    context = branch_run_context(branch, runtime_dir=tmp_path)

    expected = tmp_path / "sessions" / canonical_session_id(session_id)
    assert context.resolve_memory_dir() == expected
    assert branch.owner_session == canonical_session_id(session_id)


def test_the_memory_folder_of_a_branch_is_never_the_global_runtime_folder(
    memory_layer: BranchLayer, session_id: str, scenario_id: str, tmp_path: Path
) -> None:
    """The global runtime folder of the configuration is never the memory of a sandbox session."""
    branch = memory_layer.fork(session_id, scenario_id).branch
    context = branch_run_context(branch, runtime_dir=tmp_path)

    assert context.resolve_memory_dir() != get_settings().runtime_dir
    assert context.resolve_memory_dir() != tmp_path


def test_the_folder_of_the_sandbox_and_the_folder_of_the_context_are_the_same_folder(
    memory_layer: BranchLayer, session_id: str, scenario_id: str, tmp_path: Path
) -> None:
    """The rule lives in one place: the sandbox asks the run context, so the two folders cannot drift."""
    branch = memory_layer.fork(session_id, scenario_id).branch
    context = branch_run_context(branch, runtime_dir=tmp_path)

    assert session_memory_dir(branch.owner_session, tmp_path) == context.resolve_memory_dir()


def test_the_sandbox_asks_the_run_context_for_the_folder_and_never_computes_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The folder is the one the run context answers, and not a folder the sandbox computes on its own.

    The two rules agree today, so a copy of the rule inside the sandbox would pass every other test. The run
    context is asked here, and the answer is the folder, so the sandbox has no rule of its own to drift.
    """
    answered = tmp_path / "answered-by-the-run-context"

    def answer(_self: RunContext, runtime_dir: Path | None = None) -> Path:
        return answered

    monkeypatch.setattr(RunContext, "resolve_memory_dir", answer)

    assert session_memory_dir("sess-a", tmp_path) == answered


def test_the_two_sessions_of_the_two_branches_have_two_different_folders(
    memory_layer: BranchLayer, session_id: str, other_session_id: str, scenario_id: str, tmp_path: Path
) -> None:
    """Two visitors never share the folder of the memory."""
    mine = branch_run_context(memory_layer.fork(session_id, scenario_id).branch, runtime_dir=tmp_path)
    theirs = branch_run_context(memory_layer.fork(other_session_id, scenario_id).branch, runtime_dir=tmp_path)

    assert mine.resolve_memory_dir() != theirs.resolve_memory_dir()


# --- the identity of the branch travels in the context ---------------------------------------------


def test_the_context_of_a_branch_carries_the_branch_id_the_revision_and_the_base_hash(
    memory_layer: BranchLayer, session_id: str, scenario_id: str, tmp_path: Path
) -> None:
    """The context says which branch the execution runs inside (FR-042)."""
    branch = memory_layer.fork(session_id, scenario_id).branch
    context = branch_run_context(branch, runtime_dir=tmp_path)

    assert context.branch_id == branch.branch_id
    assert context.branch_revision == branch.revision
    assert context.snapshot_sha256 == branch.base_canonical_hash


def test_the_identity_of_the_context_reports_the_revision_of_the_branch(
    memory_layer: BranchLayer, session_id: str, scenario_id: str, tmp_path: Path
) -> None:
    """The revision travels with the identity, as the decimal text of the integer."""
    branch = memory_layer.fork(session_id, scenario_id).branch
    context = branch_run_context(branch, runtime_dir=tmp_path)

    identity = context.identity()
    assert identity["branch_id"] == branch.branch_id
    assert identity["branch_revision"] == str(branch.revision)
    assert identity["snapshot_sha256"] == branch.base_canonical_hash


def test_the_context_of_a_branch_names_the_run_after_the_branch_when_the_caller_gives_none(
    memory_layer: BranchLayer, session_id: str, scenario_id: str, tmp_path: Path
) -> None:
    """Without a run identifier of its own, the branch is the scope of the execution."""
    branch = memory_layer.fork(session_id, scenario_id).branch

    assert branch_run_context(branch, runtime_dir=tmp_path).run_id == f"run-{branch.branch_id}"
    assert branch_run_context(branch, run_id="run-42", runtime_dir=tmp_path).run_id == "run-42"


# --- the isolation, proven in the data --------------------------------------------------------------


def test_a_case_written_in_the_session_of_a_branch_is_not_read_by_another_session(
    memory_layer: BranchLayer, session_id: str, other_session_id: str, scenario_id: str, tmp_path: Path
) -> None:
    """What a session writes is private: the other session does not read it.

    The seeded cases are shared and read-only by design, so both sessions see them. The proof is about what a
    session writes, exactly like the proof of the run context.
    """
    mine = branch_run_context(memory_layer.fork(session_id, scenario_id).branch, runtime_dir=tmp_path)
    theirs = branch_run_context(memory_layer.fork(other_session_id, scenario_id).branch, runtime_dir=tmp_path)

    memory_mine = CaseMemory(mine.resolve_memory_dir())
    memory_theirs = CaseMemory(theirs.resolve_memory_dir())

    written = memory_mine.write_case(_supported_result(session_id))
    assert written["written"] is True, written
    case_id = written["case_id"]

    ids_mine = {record["case_id"] for record in memory_mine.records()}
    ids_theirs = {record["case_id"] for record in memory_theirs.records()}

    assert case_id in ids_mine
    assert case_id not in ids_theirs
    assert not memory_theirs.runtime_file.exists()


def test_an_integrator_built_with_the_context_of_a_branch_writes_its_memory_in_the_session_folder(
    memory_layer: BranchLayer, session_id: str, scenario_id: str, tmp_path: Path
) -> None:
    """With the context of a branch, the integrator writes the memory in the session folder."""
    branch = memory_layer.fork(session_id, scenario_id).branch
    context = branch_run_context(branch, runtime_dir=tmp_path)

    agent = build_integrator(ScriptedChatModel(script=[]), run_context=context)
    assert agent.case_memory.runtime_dir == context.resolve_memory_dir()
    assert agent.case_memory.runtime_dir != get_settings().runtime_dir


def test_the_context_of_a_branch_is_accepted_by_the_run_context(
    memory_layer: BranchLayer, session_id: str, scenario_id: str, tmp_path: Path
) -> None:
    """The owner of a branch is stored in the canonical form, and the context accepts that form."""
    branch = memory_layer.fork(session_id, scenario_id).branch
    context = branch_run_context(branch, runtime_dir=tmp_path)

    assert context.session_id == branch.owner_session
    assert RunContext(run_id="r1", session_id=branch.owner_session).canonical_session_id == branch.owner_session


# --- the end of the session kills the memory ---------------------------------------------------------


def test_the_end_of_the_session_purges_the_memory_folder_of_the_session(
    file_store: BranchStore, base_resolver: BaseResolver, clock, tmp_path: Path
) -> None:
    """The memory of an anonymous visitor does not lie around under an identifier nobody can reach again."""
    runtime = tmp_path / "runtime"
    app = create_app(store=file_store, base_resolver=base_resolver, clock=clock, runtime_dir=runtime)
    client = TestClient(app)

    session_id = client.post("/v1/sessions").json()["id"]
    folder = session_memory_dir(session_id, runtime)
    folder.mkdir(parents=True)
    (folder / "cases.jsonl").write_text("{}\n", encoding="utf-8")

    response = client.delete("/v1/sessions/current")
    assert response.status_code == 204
    assert not folder.exists()


def test_the_end_of_the_session_leaves_the_memory_of_another_session_alone(
    file_store: BranchStore, base_resolver: BaseResolver, clock, tmp_path: Path
) -> None:
    """The purge of one session never touches the folder of another one."""
    runtime = tmp_path / "runtime"
    app = create_app(store=file_store, base_resolver=base_resolver, clock=clock, runtime_dir=runtime)
    client = TestClient(app)

    client.post("/v1/sessions")
    other = session_memory_dir("sess-another-visitor", runtime)
    other.mkdir(parents=True)
    (other / "cases.jsonl").write_text("{}\n", encoding="utf-8")

    assert client.delete("/v1/sessions/current").status_code == 204
    assert other.exists()


def test_the_purge_of_one_session_leaves_the_memory_of_another_session_alone(tmp_path: Path) -> None:
    """The purge removes the folder of the session it is given, and only that one."""
    first = session_memory_dir("sess-a", tmp_path)
    second = session_memory_dir("sess-b", tmp_path)
    first.mkdir(parents=True)
    second.mkdir(parents=True)

    assert purge_session_memory("sess-a", tmp_path) is True
    assert not first.exists()
    assert second.exists()


def test_the_purge_of_a_session_that_wrote_nothing_is_not_an_error(tmp_path: Path) -> None:
    """A missing folder is not a failure: the session that never wrote anything has nothing to purge."""
    assert purge_session_memory("sess-never-wrote", tmp_path) is False


def test_the_purge_refuses_a_session_id_that_is_not_an_identifier(tmp_path: Path) -> None:
    """An identifier that is not one removes nothing: the purge never follows a path out of the sessions."""
    outsider = tmp_path / "not-a-session"
    outsider.mkdir()
    (outsider / "cases.jsonl").write_text("{}\n", encoding="utf-8")

    assert purge_session_memory("../not-a-session", tmp_path) is False
    assert outsider.exists()


def test_the_purge_refuses_a_session_folder_that_points_outside_the_sessions(tmp_path: Path) -> None:
    """The folder of the session is the one inside the folder of the sessions, and nothing else."""
    sessions = tmp_path / "sessions"
    sessions.mkdir(parents=True)
    outsider = tmp_path / "elsewhere"
    outsider.mkdir()
    (outsider / "cases.jsonl").write_text("{}\n", encoding="utf-8")
    (sessions / "sess-link").symlink_to(outsider, target_is_directory=True)

    assert purge_session_memory("sess-link", tmp_path) is False
    assert outsider.exists()


def test_the_purge_refuses_a_session_folder_that_points_outside_the_sessions_under_the_same_name(
    tmp_path: Path,
) -> None:
    """The name of the folder is not enough to be the folder of the session: it also has to live inside.

    The link carries the name of the session, so only the guard of the place refuses it. Without that guard the
    purge removes a folder that lives outside the folder of the sessions.
    """
    sessions = tmp_path / "sessions"
    sessions.mkdir(parents=True)
    outsider = tmp_path / "elsewhere" / "sess-link"
    outsider.parent.mkdir(parents=True)
    outsider.mkdir()
    (outsider / "cases.jsonl").write_text("{}\n", encoding="utf-8")
    (sessions / "sess-link").symlink_to(outsider, target_is_directory=True)

    assert purge_session_memory("sess-link", tmp_path) is False
    assert outsider.exists()


def test_the_purge_refuses_a_session_folder_that_points_to_the_folder_of_another_session(tmp_path: Path) -> None:
    """The place of the folder is not enough to be the folder of the session: it also has to carry its name.

    The link lives inside the folder of the sessions, so only the guard of the name refuses it. Without that guard
    the purge removes the memory of another session.
    """
    sessions = tmp_path / "sessions"
    sessions.mkdir(parents=True)
    other = sessions / "sess-other"
    other.mkdir()
    (other / "cases.jsonl").write_text("{}\n", encoding="utf-8")
    (sessions / "sess-link").symlink_to(other, target_is_directory=True)

    assert purge_session_memory("sess-link", tmp_path) is False
    assert other.exists()


def test_the_purge_that_cannot_remove_the_folder_reports_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A folder that cannot be removed is reported as not removed, and the folder stays where it is."""
    folder = session_memory_dir("sess-a", tmp_path)
    folder.mkdir(parents=True)

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise OSError("the disk said no")

    monkeypatch.setattr("ledgerlens.sandbox.memory.shutil.rmtree", refuse)
    assert purge_session_memory("sess-a", tmp_path) is False
    assert folder.exists()


def test_the_end_of_the_session_answers_even_when_the_purge_of_the_memory_fails(
    file_store: BranchStore, base_resolver: BaseResolver, clock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The end of a session never fails over a folder of the disk: the failure is logged and the route answers."""

    def refuse(*_args: object, **_kwargs: object) -> bool:
        raise OSError("the disk said no")

    runtime = tmp_path / "runtime"
    app = create_app(store=file_store, base_resolver=base_resolver, clock=clock, runtime_dir=runtime)
    client = TestClient(app)
    client.post("/v1/sessions")

    monkeypatch.setattr("ledgerlens.api.sandbox.purge_session_memory", refuse)
    assert client.delete("/v1/sessions/current").status_code == 204


# --- the injected runtime folder scopes the whole sandbox --------------------------------------------


def test_the_base_of_a_facade_with_an_injected_runtime_folder_lands_inside_it(
    file_store: BranchStore, clock, tmp_path: Path, offline_environment: Path
) -> None:
    """The injected folder holds the base of the scenarios too, so nothing lands in the runtime of the machine.

    The injected folder is not the runtime folder of the configuration, so the proof says where the base really
    landed and not only that a folder appeared.
    """
    runtime = tmp_path / "injected-runtime"
    app = create_app(store=file_store, clock=clock, runtime_dir=runtime)
    client = TestClient(app)

    assert client.post("/v1/sessions").status_code == 201
    assert client.post("/v1/sandboxes", json={"scenario_id": "S01"}).status_code == 201

    base = runtime / "sandbox-bases" / "S01"
    assert base.is_dir()
    assert base.is_relative_to(runtime)
    assert not (offline_environment / "sandbox-bases" / "S01").exists()


def test_the_base_of_a_facade_without_an_injected_runtime_folder_stays_in_the_runtime_of_the_configuration(
    file_store: BranchStore, clock, offline_environment: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without an injected folder the base is built where it always was: in the runtime of the configuration."""
    built: list[Path] = []

    class RecordingResolver(BaseResolver):
        """The resolver of the base, which remembers the folder it was given."""

        def __init__(self, work_dir: Path | str | None = None) -> None:
            super().__init__(work_dir)
            built.append(self.work_dir)

    monkeypatch.setattr("ledgerlens.api.sandbox.BaseResolver", RecordingResolver)

    create_app(store=file_store, clock=clock)

    assert built == [offline_environment / "sandbox-bases"]
