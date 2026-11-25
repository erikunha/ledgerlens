"""No artifact carries a key, a session id or a path of a machine.

What they guarantee, and why: every artifact of the two catalogs is exported, and no artifact carries a key,
a session id or a path of a machine, because the export reads the published catalogs and never a session, and
a run of a visitor is not published and therefore has no artifact.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import re

from ledgerlens.observability.callbacks import redact
from ledgerlens.proof.export import build_proof_export

SESSION_ID = re.compile(r"\bsess[-_][a-z0-9]{6,}\b", re.IGNORECASE)
MACHINE_PATH = "/" + "Users" + "/"


def test_no_artifact_carries_a_key_a_session_id_or_a_path_of_a_machine(root) -> None:
    """The export of every artifact of the two catalogs, scanned for the three shapes."""
    files = build_proof_export(root)

    assert files
    for name, content in files.items():
        text = content.decode("utf-8")
        assert redact(text) == text, f"the artifact {name} carries a string that looks like a key"
        assert not SESSION_ID.search(text), f"the artifact {name} carries a session id"
        assert MACHINE_PATH not in text, f"the artifact {name} carries a path of a machine"
