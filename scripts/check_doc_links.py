#!/usr/bin/env python3
"""Checks the links of the documentation against the files that are on the disk.

Why it exists: a link that points to a file that does not exist is a promise the repository does not keep, and
nothing else in the gate sees it: the index of the documentation is built from the names of the files and not
from the links inside them, and the tests of the documentation check the content of a page and not where it
points. A reader who follows a link of a decision record and finds nothing there stops trusting the record, and
the name of a decision record changes when its title changes, so a link written by hand breaks without any
visible change in the file that carries it.

What it does, and what it does not do:
- it reads the disk, prints one line per broken link and writes nothing;
- it follows the relative links of the Markdown of the repository and of the root of it, and it leaves the
  addresses of the web alone: a link to a site outside the repository is not a file of the repository;
- it ignores the fragments of a link, because a fragment names a section of a file and the sections are not
  checked by this script;
- it leaves the imported design package (`docs/design/`) alone, because the repository does not own the pages of
  the package and a link inside it is a link of the package, and the package is imported as it is.

Usage:

```bash
uv run python scripts/check_doc_links.py            # checks every page, writes nothing
```

Exit code 0 when every link points to a file of the repository, 1 when there is a broken link.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from pathlib import Path

from ledgerlens.config import PROJECT_ROOT

__all__ = ["check", "main", "links_of"]

# The link of Markdown: the text between brackets and the address between parentheses. The address of a link of
# an image is the same shape, and an image is a link to a file as well.
LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")

# The folders whose Markdown is checked. The root holds the two READMEs and the folders of the documentation.
ROOTS = ("README.md", "README.pt-BR.md", "docs", "specs")


def links_of(text: str) -> list[str]:
    """The addresses of the links of a page, without the fragments and without the addresses of the web.

    Why the addresses of the web are left alone: a link to a site outside the repository is not a file of the
    repository, and the repository cannot say that the file is there.
    """
    found: list[str] = []
    for address in LINK.findall(text):
        target = address.strip().split(" ", 1)[0]
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        found.append(target.split("#", 1)[0])
    return found


def check(root: Path | str) -> list[str]:
    """The broken links of the documentation, one sentence per broken link. Empty when every link resolves.

    Why the sentences and not only a count: the reader of the failure is a person writing a page, and a page
    with a broken link is fixed by knowing which link is broken and where it is.
    """
    base = Path(root)
    problems: list[str] = []
    for page in _pages(base):
        try:
            text = page.read_text(encoding="utf-8")
        except OSError as exc:  # pragma: no cover - a file that cannot be read is reported, not raised
            problems.append(f"the page {page} cannot be read: {exc}")
            continue
        for target in links_of(text):
            if not target:
                continue
            resolved = (page.parent / target).resolve()
            if not resolved.exists():
                problems.append(f"the page {page.relative_to(base)} points to '{target}', which is not on the disk")
    return problems


def _pages(base: Path) -> list[Path]:
    """Every page of the repository that the check reads, without the imported design package."""
    pages: list[Path] = []
    for name in ROOTS:
        path = base / name
        if path.is_file():
            pages.append(path)
        elif path.is_dir():
            pages.extend(page for page in sorted(path.rglob("*.md")) if not _is_imported(base, page))
    return pages


def _is_imported(base: Path, page: Path) -> bool:
    """Whether a page belongs to the imported design package, which the repository does not own.

    Why the package is left alone: the pages of the package are imported as they are, and a broken link inside
    them is a link of the package and not a promise of this repository.
    """
    try:
        relative = page.resolve().relative_to(base.resolve())
    except ValueError:  # pragma: no cover - a page outside the root is not imported
        return False
    return relative.parts[:2] == ("docs", "design")


def main(argv: Sequence[str] | None = None) -> int:
    """The entry point of the check. The exit code is the answer."""
    parser = argparse.ArgumentParser(description="Checks the links of the documentation against the files on the disk.")
    parser.add_argument("--root", default=str(PROJECT_ROOT), help="the root of the repository")
    args = parser.parse_args(argv)

    problems = check(args.root)
    if problems:
        for problem in problems:
            print(f"check_doc_links: {problem}", file=sys.stderr)
        print(f"check_doc_links: {len(problems)} broken link(s) found", file=sys.stderr)
        return 1
    print("every link of the documentation points to a file of the repository")
    return 0


if __name__ == "__main__":
    sys.exit(main())
