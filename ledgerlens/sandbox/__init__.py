"""The branch layer of the sandbox: the store, the base of a branch and the rules of a branch.

Why this package exists: the phase R2 gives every visitor a private working copy of a published case. The rules of
that copy live here, behind a store interface, so the persistence can be replaced without the rules changing.

The public names of the package are the ones a caller needs: the store and its rows, the base of a branch and the
layer that forks it.
"""

from ledgerlens.sandbox.branch import (
    BranchExpired,
    BranchLayer,
    ForkOutcome,
    SandboxBranch,
    new_branch_id,
)
from ledgerlens.sandbox.factory import build_branch_store
from ledgerlens.sandbox.postgres_store import PostgresBranchStore
from ledgerlens.sandbox.session import DemoSession, InvalidSession, SessionIssuer
from ledgerlens.sandbox.snapshot import BaseResolver, BaseSnapshot, UnknownScenario
from ledgerlens.sandbox.store import (
    BranchNotFound,
    BranchStore,
    FileBranchStore,
    SandboxBranchRow,
    SandboxEventRow,
)

__all__ = [
    "BaseResolver",
    "BaseSnapshot",
    "BranchExpired",
    "BranchLayer",
    "BranchNotFound",
    "BranchStore",
    "DemoSession",
    "FileBranchStore",
    "ForkOutcome",
    "InvalidSession",
    "PostgresBranchStore",
    "SandboxBranch",
    "SandboxBranchRow",
    "SandboxEventRow",
    "SessionIssuer",
    "UnknownScenario",
    "build_branch_store",
    "new_branch_id",
]
