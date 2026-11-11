"""The guard of the import is never weaker than the guard of the repository.

Why this file exists: the import script writes the design package into `docs/v3/`, and the repository guard scans
that folder afterwards. When the import guard misses a rule the repository guard has, the import lands material the
gate then refuses, and the failure appears one step too late. Here the import reuses the repository patterns
themselves, and these tests pin that: every category the repository refuses, the import refuses first.

The forbidden material is assembled from fragments, the same trick the repository guard uses, so this file does not
match its own rules.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from import_v3_pack import _guard_report  # noqa: E402


def _hits(name: str, text: str) -> list[str]:
    """The guard report of a one file package with the given content."""
    return _guard_report({name: text.encode("utf-8")})


def test_the_import_refuses_what_the_repository_guard_refuses():
    """Course words, the course acronym, machine paths, secrets and Portuguese never land in docs/v3/."""
    cases = [
        "kept a " + "note" + "book of the " + "al" + "uno",
        "the M" + "BA material",
        "recorded at /" + "Users" + "/someone/file.md",
        "the key sk-" + "fakefakefakefakefake1234 leaked",
        "O reem" + "bolso veio menor.",
        "prazo d" + "e 30 dias",
    ]
    for line in cases:
        assert _hits("docs/x.md", line + "\n"), line


def test_the_import_keeps_its_own_extra_rules():
    """The rules specific to the import stay: the ids and the name of the local plan, and its course wording."""
    cases = [
        "see task T" + "101",
        "recorded by Er" + "ik",
        "the g" + "mail thread",
        "one au" + "la of the course",
    ]
    for line in cases:
        assert _hits("docs/x.md", line + "\n"), line


def test_clean_english_passes_the_import_guard():
    """What the repository accepts, the import accepts: the guard does not block honest English."""
    assert not _hits("docs/x.md", "The refund came in lower than the payment, see the policy for details.\n")


def test_the_file_name_counts_like_a_line():
    """The repository guard scans file names too, and so does the import: a forbidden name never lands."""
    assert _hits("docs/the-" + "note" + "book.md", "clean english\n")


def test_the_id_exemption_is_only_for_the_prd():
    """The local plan ids are refused everywhere except in the PRD file that defines its own id space."""
    prd = "docs/02-PRD-AND-DEFINITION-OF-DONE.md"
    other = "docs/03-OTHER.md"
    line = "the task T" + "101 of the plan"
    assert not _hits(prd, line + "\n")
    assert _hits(other, line + "\n")
