"""The ledger of ONE visitor, materialized in a file that the tools of the agent can read.

Why this module exists: the projection of a branch lives in an in-memory SQLite connection
(`ledgerlens/sandbox/projector.py`), while the tools of the agent take the path of a database file
(`ledgerlens/tools/sql.py`). The live run of the visitor needs the state of the branch in a file, and it needs
that file to hold the rows of the account of the branch and the counterparties of the transactions of that account,
and no row of another account (ADR-038).

Why the view is a value object and not a path: a run has to be able to name the ledger it read, and the name is
the branch, the revision it was read at and the canonical hash of the state. The trace of the run carries those
three, so a reader of the trace knows which state answered the question.

Why the refusals live here and not in the branch module: the branch layer refuses a branch that does not exist,
one that expired and one that cannot prove its own state. These two are refusals of the READER of the ledger: the
account of the request is not the account of the branch, and the revision the request expected is not the revision
the branch is at. The layer of the branch keeps its own vocabulary.

Why the materialization lives here and not in the branch layer: the file of the run is an artifact of the run, and the
rule that builds it (a copy of the projected state, never a statement written by hand) belongs with the value object
the run carries. The branch layer asks for it only after every check passed.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from ledgerlens.sandbox.projector import ProjectedState

# The codes of the two refusals of the reader of the ledger. They are the codes the live facade already publishes for
# the same two cases, so the domain and the facade cannot disagree about what a refusal is, and they carry the shape
# of the other refusals of the sandbox, which have a code and a message.
CODE_ACCOUNT_MISMATCH = "ACCOUNT_MISMATCH"
CODE_REVISION_MOVED = "REVISION_MOVED"

__all__ = [
    "CODE_ACCOUNT_MISMATCH",
    "CODE_REVISION_MOVED",
    "LedgerAccountMismatch",
    "LedgerRevisionMoved",
    "LedgerView",
    "materialize",
]


class LedgerAccountMismatch(Exception):
    """The account of the request is not the account of the branch.

    Why the refusal exists: the branch holds the rows of one account and the counterparties of its transactions, and a
    request that names another account is a request about records the visitor does not own. The layer of the sandbox
    answers the same case with `BranchNotFound`, but the live facade has to tell the visitor that the request is wrong
    (ADR-038).

    Why the refusal carries a code and a message: every other refusal of the sandbox carries them, so a caller can
    answer a refusal of the reader of the ledger the way it answers the others.
    """

    code = CODE_ACCOUNT_MISMATCH

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class LedgerRevisionMoved(Exception):
    """The revision of the branch moved away from the revision the request expected.

    Why the refusal exists: the request carries the revision the visitor was looking at. A run that answers about a
    state the visitor never saw is a run that answers a question nobody asked.

    Why the refusal carries a code and a message: every other refusal of the sandbox carries them, so a caller can
    answer a refusal of the reader of the ledger the way it answers the others.
    """

    code = CODE_REVISION_MOVED

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class LedgerView:
    """The ledger of ONE visitor, materialized in a file the tools of the agent can read.

    Why the fields are here and not only the path: the run has to name the ledger it read. The branch says which
    branch, the revision says at which state and the canonical hash proves which state it was.
    """

    path: Path
    account_id: str
    branch_id: str
    revision: int
    canonical_hash: str


def materialize(state: ProjectedState, target: Path | str) -> Path:
    """The projected state of a branch written in the file of the target, and the path of that file.

    Why the copy is made with the backup of SQLite: the rows of the projection are written by the interpreter of the
    vocabulary of the sandbox, and rebuilding them with statements written by hand would be a second implementation
    of the projection, free to disagree with the first one. The backup copies the pages as they are, so the file holds
    exactly the state the branch holds (ADR-038).

    Why the file is written under a temporary name and renamed: the tools of the agent open the file while the run
    writes it, and a file that is half written is a ledger that answers about half of a branch.

    Why the base is never touched: the source of the copy is the projection, which is a copy of the base in memory.
    The file of the base is only ever read, and the file of the view holds the rows of the account of the branch
    because the base is already the account scoped copy. The file also holds the counterparties of the transactions
    of the account, because a transaction names the merchant it is with and the counterparty of the transaction of
    the visitor is part of the story the run reads. The name of that merchant is on the disk of the server for the
    length of the run, and the decision says so out loud (ADR-038).
    """
    out = Path(target)
    out.parent.mkdir(parents=True, exist_ok=True)
    temporary = out.with_name(out.name + ".tmp")
    for suffix in ("", "-journal", "-wal", "-shm"):
        # A temporary file of an earlier run would be the seed of a wrong file, so it is dropped first.
        Path(str(temporary) + suffix).unlink(missing_ok=True)
    # The projection holds the changes of the events in an open transaction, and the backup of SQLite copies the
    # committed state, so the transaction is closed here and never on the file of the base.
    state.conn.commit()
    with closing(sqlite3.connect(temporary)) as destination:
        state.conn.backup(destination)
        destination.commit()
    temporary.replace(out)
    return out
