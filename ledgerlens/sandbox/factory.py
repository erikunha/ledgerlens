"""Builds the store of the branches from the configuration.

Why it exists: ADR-020 put the branch data of the deployment in Postgres and kept the file backed store as the
fallback, and that decision belongs to the configuration and not to a command that reads the disk of a working tree.
So the settings name the database and this module turns the name into the store.

The rule is one line: a database url in the configuration means the database store, and no url means the file backed
one. A machine without a database keeps working, and the record of the run says which half of the contract suite ran.
"""

from __future__ import annotations

from ledgerlens.config import Settings, get_settings
from ledgerlens.sandbox.postgres_store import PostgresBranchStore
from ledgerlens.sandbox.store import BranchStore, FileBranchStore


def build_branch_store(settings: Settings | None = None) -> BranchStore:
    """The store the configuration asks for.

    The database store when the setting of the database url is filled, and the file backed one otherwise. The folder
    of the file backed store is the runtime folder of the configuration, so it stays out of git with the rest of the
    runtime material.
    """
    settings = settings or get_settings()
    if settings.sandbox_database_url:
        return PostgresBranchStore(settings.sandbox_database_url)
    return FileBranchStore(settings.runtime_dir / "sandbox")


__all__ = ["build_branch_store"]
