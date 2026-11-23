"""The index of the documentation must never describe a disk that is not there.

Why this file exists: the documentation of the repository had no index, and a measurement of the audit of the
product found that around three quarters of the Markdown files of `docs/` were orphans: no document of the
repository linked to them. The index closes that gap, and the tests here hold the contract of the script that
writes it: no document is left out, every record of a decision shows its number, its title, its status and its
date, the same disk always produces the same bytes, the check mode refuses when the index drifts away from the
files it lists, and the text that the script copies never carries a dash the repository forbids.

The tests that write run the script on a copy of the documentation inside a temporary folder, so a test never
writes into the repository and the committed state of the repository stays the state that the gate reads.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build_docs_index.py"
DOCS = ROOT / "docs"
DOCS_INDEX = DOCS / "README.md"
DECISIONS_INDEX = DOCS / "decisions" / "README.md"

# The files of the documentation that the index leaves out on purpose. The index of the documentation leaves
# itself out, and the handoff of a cycle is local material that never reaches git, so a committed index cannot
# list a file that a clone of the repository does not have.
LOCAL_ONLY = ("README.md", "handoff-v3.md")

# The two dashes the repository forbids in any text of the repository.
EM_DASH = "\u2014"
EN_DASH = "\u2013"


def _run(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """The script run against a root of the repository, with the text of the outcome."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments, "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


def _copy_of_the_documentation(tmp_path: Path) -> Path:
    """A copy of the documentation in a temporary folder, so a test never writes into the repository."""
    root = tmp_path / "repository"
    root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(DOCS, root / "docs")
    return root


def _status_and_date(text: str) -> tuple[str, str]:
    """The status and the date that the front matter of a record declares, read here on its own.

    Why it is read here and not imported from the script: the test has to read the record the way a reader
    reads it, so that the script cannot define its own success.
    """
    status = "unknown"
    date = "unknown"
    found = re.search(r"^status:\s*(\S+)", text, re.MULTILINE)
    if found:
        status = found.group(1)
    found = re.search(r"\bdate:\s*(\d{4}-\d{2}-\d{2})", text)
    if found:
        date = found.group(1)
    return status, date


def _title_of(text: str, fallback: str) -> str:
    """The first level one heading of a document, or the fallback when the document has none."""
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def test_every_markdown_file_of_the_documentation_appears_in_the_index():
    """No document of `docs/` is an orphan of the index.

    Why it matters: the reader who wants to know which file holds a decision reads the index, and a document
    that the index does not name is a document that nobody finds.
    """
    index = DOCS_INDEX.read_text(encoding="utf-8")
    missing = []
    for path in sorted(DOCS.rglob("*.md")):
        relative = path.relative_to(DOCS).as_posix()
        if relative in LOCAL_ONLY:
            continue
        if f"]({relative})" not in index:
            missing.append(relative)
    assert not missing, missing


def test_every_decision_record_shows_its_number_its_title_its_status_and_its_date():
    """Every record of `docs/decisions/` is in the index of the records, with the four facts it holds.

    Why the four facts: the number says the order in which the decision was taken, the title says what it was
    about, the status says whether it still binds the work and the date says when it was taken. A record that
    the index shows with a fact missing is a record that a reader has to open to understand.
    """
    index = DECISIONS_INDEX.read_text(encoding="utf-8")
    missing = []
    for path in sorted((DOCS / "decisions").glob("ADR-*.md")):
        text = path.read_text(encoding="utf-8")
        number = path.name.split("-")[1]
        status, date = _status_and_date(text)
        title = _title_of(text, path.name)
        if f"| {number} |" not in index:
            missing.append(f"{path.name}: the number")
        if f"]({path.name})" not in index:
            missing.append(f"{path.name}: the link")
        if title not in index:
            missing.append(f"{path.name}: the title")
        if status not in index:
            missing.append(f"{path.name}: the status")
        if date not in index:
            missing.append(f"{path.name}: the date")
    assert not missing, missing


def test_the_records_are_listed_in_the_order_of_their_number():
    """The index of the records reads as a history, so the numbers go up.

    Why it matters: a reader who looks for the decision of last week reads the end of the list, and a list that
    jumps back and forth makes the reader hunt for the number instead of reading the decision.
    """
    index = DECISIONS_INDEX.read_text(encoding="utf-8")
    numbers = []
    for line in index.splitlines():
        if not line.startswith("|"):
            continue
        label = line.split("|")[1].strip()
        if label.isdigit():
            numbers.append(int(label))
    assert numbers == sorted(numbers), numbers


def test_the_script_writes_the_same_bytes_twice(tmp_path):
    """The same disk always produces the same two files.

    Why it matters: the index is committed, and the gate compares it with what the script would write. A script
    that puts a timestamp or a random order in its output would make the gate fail on every run for a reason
    that has nothing to do with the documentation.
    """
    root = _copy_of_the_documentation(tmp_path)
    assert _run(root).returncode == 0
    first = (root / "docs" / "README.md").read_bytes()
    second = (root / "docs" / "decisions" / "README.md").read_bytes()
    assert _run(root).returncode == 0
    assert (root / "docs" / "README.md").read_bytes() == first
    assert (root / "docs" / "decisions" / "README.md").read_bytes() == second


def test_the_check_fails_when_the_disk_holds_a_file_the_index_does_not_name(tmp_path):
    """The check mode refuses when a file of the disk is missing from the index, and it names the file.

    Why the name matters: the person who reads the failure must know which file to add to the index, and a
    refusal that only says that something is out of date sends that person to hunt for it.
    """
    root = _copy_of_the_documentation(tmp_path)
    assert _run(root, "--check").returncode == 0
    orphan = root / "docs" / "orphan.md"
    orphan.write_text("# A file that the index does not name\n\nThe body of the file.\n", encoding="utf-8")
    done = _run(root, "--check")
    assert done.returncode != 0
    assert "orphan.md" in done.stdout + done.stderr


def test_the_check_passes_on_the_committed_state_of_the_repository():
    """The committed index is the index of the files that are on the disk.

    Why it matters: the gate runs this check, and a committed index that no longer matches the disk would stop
    the gate of a repository whose documentation did not change at all.
    """
    done = _run(ROOT, "--check")
    assert done.returncode == 0, done.stdout + done.stderr


def test_the_generated_files_hold_no_forbidden_dash():
    """Neither of the two generated files carries an em dash or an en dash.

    Why it matters: the repository forbids the two dashes in any text, and a file that the script writes has to
    obey the same rule as a file that a person writes.
    """
    for path in (DOCS_INDEX, DECISIONS_INDEX):
        text = path.read_text(encoding="utf-8")
        assert EM_DASH not in text, path
        assert EN_DASH not in text, path


def test_the_script_never_writes_a_forbidden_dash(tmp_path):
    """A document that holds a forbidden dash does not carry it into the index.

    Why it matters: the title and the description of the index are copied from the documents, and a document
    that holds a dash would put it in a file the repository forbids, without anybody having written a word.
    """
    root = _copy_of_the_documentation(tmp_path)
    (root / "docs" / "dashes.md").write_text(
        "# A title with a dash \u2014 and an en dash \u2013\n\nA paragraph with a dash \u2014 here.\n",
        encoding="utf-8",
    )
    assert _run(root).returncode == 0
    for path in (root / "docs" / "README.md", root / "docs" / "decisions" / "README.md"):
        text = path.read_text(encoding="utf-8")
        assert EM_DASH not in text, path
        assert EN_DASH not in text, path
    index = (root / "docs" / "README.md").read_text(encoding="utf-8")
    assert "A title with a dash, and an en dash," in index
    assert "A paragraph with a dash, here." in index


def test_a_document_without_a_title_is_listed_with_its_file_name_and_a_note(tmp_path):
    """A document without a level one heading appears in the index with its file name and says that it has none.

    Why it matters: a document without a title is a finding about the repository, and the index shows the
    finding instead of hiding it behind a title that the document does not have.
    """
    root = _copy_of_the_documentation(tmp_path)
    (root / "docs" / "untitled.md").write_text("A paragraph with no heading at all.\n", encoding="utf-8")
    assert _run(root).returncode == 0
    index = (root / "docs" / "README.md").read_text(encoding="utf-8")
    assert "](untitled.md) (the file has no title)" in index


def test_a_document_without_a_paragraph_says_that_it_has_no_description(tmp_path):
    """A document with a title and no paragraph under it says in the index that it has no description.

    Why it matters: the line of the index says what the document holds, and a document that holds nothing but
    a title has no line to give. Saying so is better than filling the line with the title a second time.
    """
    root = _copy_of_the_documentation(tmp_path)
    (root / "docs" / "bare.md").write_text("# A title and nothing else\n", encoding="utf-8")
    assert _run(root).returncode == 0
    index = (root / "docs" / "README.md").read_text(encoding="utf-8")
    assert "](bare.md): the document has no description." in index


def test_a_record_without_front_matter_shows_that_its_shape_is_unknown(tmp_path):
    """A record without front matter appears in the index with the status and the date unknown.

    Why it matters: the record is a decision of the repository, and a reader has to see it. Saying that the
    shape of the record is unknown is better than leaving the record out of the index.
    """
    root = _copy_of_the_documentation(tmp_path)
    (root / "docs" / "decisions" / "ADR-999-example.md").write_text(
        "# ADR-999: Example\n\nThe body of the record.\n", encoding="utf-8"
    )
    assert _run(root).returncode == 0
    index = (root / "docs" / "decisions" / "README.md").read_text(encoding="utf-8")
    assert "| 999 | [ADR-999: Example](ADR-999-example.md) | unknown | unknown |" in index


def test_the_files_of_the_portuguese_folder_are_marked_as_the_edition_of_the_document_beside_them():
    """Every file of `docs/pt-BR/` is listed as the Portuguese edition of the document beside it.

    Why it matters: the edition is the same document in another language, and a reader who opens the index in
    English has to know that the file is the edition and not a document of its own.
    """
    index = DOCS_INDEX.read_text(encoding="utf-8")
    lines = index.splitlines()
    for path in sorted((DOCS / "pt-BR").rglob("*.md")):
        relative = path.relative_to(DOCS).as_posix()
        listed = [line for line in lines if f"]({relative})" in line]
        assert listed, relative
        assert "the Portuguese edition of" in listed[0], relative


def test_the_index_links_with_relative_paths_only():
    """The two indexes link with relative paths and never with an absolute path or with a wikilink.

    Why it matters: the index is read on the site of the repository and in a clone of it, and a link that points
    at the machine of the author or at a wiki that does not exist there is a link that leads nowhere.
    """
    for path in (DOCS_INDEX, DECISIONS_INDEX):
        text = path.read_text(encoding="utf-8")
        assert "](/" not in text, path
        assert "[[" not in text, path
        assert ROOT.as_posix() not in text, path
