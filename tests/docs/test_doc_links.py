"""The links of the documentation must point to a file that is on the disk.

Why this file exists: a link that points to nothing is a promise the repository does not keep, and nothing else in
the gate saw it. The index of the documentation is built from the names of the files and not from the links inside
them, and the tests of the documentation read the content of a page and not where it points. The name of a record
of a decision changes when its title changes, so a link written by hand breaks with no visible change in the file
that carries it: two links of the routing pointed to a record that does not exist, and the whole repository was
green.

The tests here hold the contract of the script that checks them: the committed documentation has no broken link,
the check refuses with a readable reason and a non zero exit code when a link breaks, a link to the web is not a
file of the repository, a link to a folder of the repository is not broken, and the imported design package is left
alone.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_doc_links.py"
DOCS = ROOT / "docs"

sys.path.insert(0, str(ROOT))

from scripts.check_doc_links import check, links_of  # noqa: E402  (the path is set up before the import)


def _run(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """The script run against a root of the repository, with the text of the outcome."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments, "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


def _root_with_a_page(tmp_path: Path, body: str) -> Path:
    """A small repository of the test, with one page that carries the body."""
    root = tmp_path / "repository"
    (root / "docs" / "decisions").mkdir(parents=True)
    (root / "docs" / "README.md").write_text("# The index\n\nThe [decisions](decisions).\n", encoding="utf-8")
    (root / "docs" / "page.md").write_text(f"# A page\n\n{body}\n", encoding="utf-8")
    return root


def test_the_committed_documentation_has_no_broken_link() -> None:
    """Every link of the documentation of the repository points to a file that exists.

    Why it matters: the gate runs this check, and a broken link that reached the commit is a broken link that
    every reader of that page meets.
    """
    done = _run(ROOT)
    assert done.returncode == 0, done.stdout + done.stderr


def test_the_check_refuses_and_names_the_link_that_is_broken(tmp_path: Path) -> None:
    """A link that points to a file that does not exist stops the check and is named.

    Why the name matters: the person who reads the failure has to know which link to fix, and a refusal that only
    says that something is broken sends that person to hunt for it.
    """
    root = _root_with_a_page(tmp_path, "The link to [nothing](decisions/ADR-999-nothing.md).")
    done = _run(root)

    assert done.returncode != 0
    assert "ADR-999-nothing.md" in done.stdout + done.stderr


def test_a_link_to_the_web_is_not_a_link_of_the_repository(tmp_path: Path) -> None:
    """A link to a site outside the repository is not a broken link: the repository cannot see that file."""
    root = _root_with_a_page(
        tmp_path, "The link to [the site](https://example.invalid/page) and the [mail](mailto:someone@example.invalid)."
    )

    assert check(root) == []
    assert _run(root).returncode == 0


def test_a_link_to_a_folder_of_the_repository_is_not_broken(tmp_path: Path) -> None:
    """A link to a folder of the repository points to something that exists."""
    root = _root_with_a_page(tmp_path, "The link to [the decisions](decisions).")

    assert check(root) == []


def test_the_imported_design_package_is_left_alone(tmp_path: Path) -> None:
    """A broken link inside the imported package is a link of the package and not a promise of the repository.

    Why it matters: the package is imported as it is, and the repository does not own the pages of it. A check
    that refused on them would stop the gate of a repository whose own documentation did not change at all.
    """
    root = _root_with_a_page(tmp_path, "The link to [a file](README.md).")
    imported = root / "docs" / "v3"
    imported.mkdir(parents=True)
    (imported / "README.md").write_text(
        "# The package\n\nThe link to [a file of the package](docs/00-NOT-THERE.md).\n", encoding="utf-8"
    )

    assert check(root) == []


def test_the_links_of_a_page_are_read_without_their_fragment() -> None:
    """A link that names a section of a file points to the file, and the fragment is not a path."""
    found = links_of("The [page](routing.md#the-cascade) and the [other](https://example.invalid/x#y).")

    assert found == ["routing.md"]


def test_a_link_that_carries_a_title_is_read_without_the_title() -> None:
    """A link that carries a title between the address and the quote points to the address."""
    found = links_of('The [page](routing.md "The routing of the inference").')

    assert found == ["routing.md"]
