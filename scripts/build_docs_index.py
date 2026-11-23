#!/usr/bin/env python3
"""Builds the index of the documentation and the index of the decision records of the repository.

Why this script exists: `docs/` holds more than a hundred Markdown files and `docs/decisions/` holds more than
fifty decision records, and nothing told a reader which file holds which decision. A measurement of the audit
of the product found that around three quarters of the Markdown files of `docs/` were orphans: no document of
the repository linked to them. The two index files this script writes close that gap, and the check mode keeps
the index honest about the files that are on the disk.

Two modes, and the difference matters:

- without arguments it WRITES the two index files.
- `--check` writes NOTHING. It compares what would be written with what is on the disk, and it refuses with a
  readable message that names the file that is out of date and a non zero exit code, so the gate stops on the
  reason and not on a traceback.

The script is deterministic: the same disk always produces the same two files. There is no timestamp, no random
order and no absolute path in what it writes, so a diff of the index is a diff of the files it describes.

The rules of the content of the index live here and not in the documents, because the documents are never edited
by the index. The title of a document is its first level one heading, and a document without one is listed with
its file name and a note, because a document without a title is a finding about the repository and the index
shows it. The line that says what a document holds is the first paragraph after that heading, shortened to one
line. The text that is copied is sanitized, because the em dash (U+2014) and the en dash (U+2013) are forbidden
in this repository and a document that holds one would carry it into the index.

The files of `docs/pt-BR/` are the Portuguese edition of the documents beside them. The index lists them in a
group of their own and names the edition, and it does not copy the Portuguese prose of the file, because the
index is written in the language of the repository.

Usage:

```bash
uv run python scripts/build_docs_index.py           # writes the two indexes
uv run python scripts/build_docs_index.py --check   # writes nothing, refuses when the index drifted
```

Exit code 0 when the two modes agree with the disk, 1 when the check finds a difference.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
DECISIONS = DOCS / "decisions"
DOCS_INDEX = DOCS / "README.md"
DECISIONS_INDEX = DECISIONS / "README.md"

__all__ = [
    "build_decisions_index",
    "build_docs_index",
    "describe",
    "main",
    "sanitize",
    "shorten",
]

# The two dashes the repository forbids in any text of the repository.
EM_DASH = "\u2014"
EN_DASH = "\u2013"
# The longest line the index uses to say what a document holds.
MAX_DESCRIPTION = 160
# The sentence the index uses when a document does not say what it holds.
NO_DESCRIPTION = "the document has no description."
# The files under `docs/` that the index leaves out, and the reason of each one.
#
# The index of the documentation leaves itself out, because a file cannot describe its own listing. The handoff
# of a cycle leaves the scan too: it names the paths of the machine of its author, so it never reaches git, and a
# committed index cannot list a file that a clone of the repository does not have.
LOCAL_ONLY = frozenset({"README.md", "handoff-v3.md"})
# The folder that holds the Portuguese edition of the documents, and the prefix of the paths inside it.
PORTUGUESE_FOLDER = "pt-BR"

_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_LINK_TARGET = re.compile(r"\]\(([^)]+)\)")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC = re.compile(r"(?<![\w*])\*([^*\n]+)\*(?!\w)")
_UNDERLINE = re.compile(r"(?<![\w_])_([^_\n]+)_(?!\w)")
_STRIKE = re.compile(r"~~([^~]+)~~")
_FENCE = re.compile(r"^(```|~~~)")
_HORIZONTAL_RULE = re.compile(r"^[-*_]{3,}$")
_LIST_ITEM = re.compile(r"^([-*+]\s+|\d+[.)]\s+)")
_STATUS = re.compile(r"^status:\s*(\S+)", re.MULTILINE)
_DATE = re.compile(r"\bdate:\s*(\d{4}-\d{2}-\d{2})")
_NUMBER = re.compile(r"^ADR-(\d+)")


def sanitize(text: str) -> str:
    """The text without the dashes the repository forbids and without the spaces the change leaves behind.

    Why it exists: the title and the description of the index are copied from the documents, and a document that
    holds an em dash would carry it into the index, where the rule of the repository forbids it. The dash becomes
    a comma and the spaces that the change leaves are collapsed, so the line keeps a single space between the
    words and a single space after the comma.
    """
    cleaned = text.replace(EM_DASH, ",").replace(EN_DASH, ",")
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r" *, *", ", ", cleaned)
    return cleaned.strip()


def strip_markdown(text: str) -> str:
    """The plain prose of a line of Markdown, without the links, the emphasis markers and the code ticks.

    Why it exists: the index describes a document in one line of prose, and a line that carries the syntax of
    Markdown reads as broken text in a list of documents.
    """
    plain = _LINK.sub(r"\1", text)
    plain = plain.replace("`", "")
    plain = _BOLD.sub(r"\1", plain)
    plain = _ITALIC.sub(r"\1", plain)
    plain = _UNDERLINE.sub(r"\1", plain)
    plain = _STRIKE.sub(r"\1", plain)
    return plain.strip()


def shorten(text: str, limit: int = MAX_DESCRIPTION) -> str:
    """The text on one line, at most the limit characters, cut at the boundary of a word.

    Why the cut is at a word: a line that ends in the middle of a word reads as a mistake of the index and not
    as a summary of the document.
    """
    if len(text) <= limit:
        return text
    cut = text[: limit - 3]
    space = cut.rfind(" ")
    if space > 0:
        cut = cut[:space]
    return cut.rstrip(" ,;:.") + "..."


def first_heading(text: str) -> str | None:
    """The first level one heading of a document, or None when the document has none.

    Why the fence of a code block is tracked: a document can show the Markdown of a heading inside an example,
    and that line is not the title of the document.
    """
    fenced = False
    for line in text.splitlines():
        stripped = line.strip()
        if _FENCE.match(stripped):
            fenced = not fenced
            continue
        if fenced:
            continue
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return None


def first_paragraph(text: str) -> str | None:
    """The first paragraph after the first heading of a document, or None when there is none.

    Why the blocks that are not prose are skipped: a table, a quotation, a rule and a block of code are not a
    description of the document, and the index would carry a fragment of a table as if it were a sentence.
    """
    lines = text.splitlines()
    start = None
    fenced = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if _FENCE.match(stripped):
            fenced = not fenced
            continue
        if fenced:
            continue
        if stripped.startswith("# "):
            start = index + 1
            break
    if start is None:
        return None

    fenced = False
    block: list[str] = []
    index = start
    while index < len(lines):
        stripped = lines[index].strip()
        index += 1
        if _FENCE.match(stripped):
            fenced = not fenced
            continue
        if fenced:
            continue
        if not stripped:
            if block:
                break
            continue
        if stripped.startswith("#"):
            # A subheading is not the end of the search: the paragraph of the section it opens is still the first
            # paragraph that the document holds after its title.
            continue
        if stripped.startswith("|") or stripped.startswith(">"):
            continue
        if _HORIZONTAL_RULE.match(stripped):
            continue
        if stripped.startswith("<!--"):
            continue
        if _LIST_ITEM.match(stripped):
            # The first item of a list says what the document holds as well as a paragraph does.
            return _LIST_ITEM.sub("", stripped)
        block.append(stripped)
    if not block:
        return None
    return " ".join(block)


def describe(path: Path, text: str | None = None) -> tuple[str, str]:
    """The title of a document and the one line that says what it holds.

    Why the title is empty when the document has no heading: the caller shows the file name and says that the
    document has no title, and an empty title never becomes a link that points at nothing.

    Why the text may be given by the caller: a file that the script writes is described by the text that the
    script writes now, and not by the text that the previous run left on the disk.
    """
    if text is None:
        text = path.read_text(encoding="utf-8", errors="replace")
    heading = first_heading(text)
    title = sanitize(heading) if heading else ""
    paragraph = first_paragraph(text)
    description = shorten(sanitize(strip_markdown(paragraph))) if paragraph else ""
    if not description:
        description = NO_DESCRIPTION
    return title, description


def _front_matter(text: str) -> str:
    """The front matter of a document, or an empty string when the document has none.

    Why the closing marker is recognised in two shapes: one record of the repository closes the front matter and
    writes the date and the end of the block in the same line, and a block that never closes would swallow the
    whole document.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    block: list[str] = []
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            break
        block.append(line)
        if stripped.endswith("---"):
            break
    return "\n".join(block)


def _record(path: Path) -> tuple[int | None, str, str, str]:
    """The number, the title, the status and the date of one decision record.

    Why the status and the date fall back to the word unknown: a record without front matter is a finding about
    the repository, and saying that the shape is unknown is better than hiding the record.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    matter = _front_matter(text)
    status = "unknown"
    date = "unknown"
    found = _STATUS.search(matter)
    if found:
        status = found.group(1).strip().strip('"')
    found = _DATE.search(matter)
    if found:
        date = found.group(1)
    heading = first_heading(text)
    title = sanitize(heading) if heading else path.name
    number = None
    found = _NUMBER.match(path.name)
    if found:
        number = int(found.group(1))
    return number, title, status, date


def _entry(docs: Path, relative: str, generated: dict[str, str]) -> str:
    """The line of the index that describes one document."""
    path = docs / relative
    if relative.startswith(f"{PORTUGUESE_FOLDER}/"):
        return _portuguese_entry(docs, relative)
    title, description = describe(path, generated.get(relative))
    if not title:
        return f"- [{path.name}]({relative}) (the file has no title): {description}"
    return f"- [{title}]({relative}): {description}"


def _portuguese_entry(docs: Path, relative: str) -> str:
    """The line of the index that describes the Portuguese edition of a document.

    Why the file name names the edition: the title of the edition is written in Portuguese, and the index of the
    documentation is written in the language of the repository. The file name points at the file and the English
    document beside it says what the edition holds.
    """
    path = docs / relative
    counterpart = relative[len(PORTUGUESE_FOLDER) + 1 :]
    if not (docs / counterpart).is_file():
        return f"- [{path.name}]({relative}): the Portuguese edition of a document that has no English counterpart."
    return (
        f"- [{path.name}]({relative}): the Portuguese edition of [{Path(counterpart).name}]({counterpart}); "
        f"its own title is in Portuguese, so the file name names it here."
    )


def build_docs_index(root: Path = ROOT, generated: dict[str, str] | None = None) -> str:
    """The text of the index of the documentation, built from the files that are on the disk.

    Why the groups are the folders of the tree: a reader who looks for the record of a decision needs the folder
    that holds it, and the order is alphabetical inside every group, so a diff of the index is a diff of the
    files that it describes.
    """
    docs = root / "docs"
    virtual = generated or {}
    groups: dict[str, list[str]] = {}
    for relative in _documents_of_the_disk(docs):
        folder = Path(relative).parent.as_posix()
        groups.setdefault(folder, []).append(relative)

    lines = [
        "# Documentation of LedgerLens",
        "",
        "This index is generated by `scripts/build_docs_index.py` from the files that are on the disk. Do not edit it",
        "by hand: run `uv run python scripts/build_docs_index.py` and commit the result.",
        "",
        "It lists every Markdown file under `docs/`, grouped by the folder that holds it, with the title of the file",
        "and one line that says what the file holds.",
        "",
    ]
    for folder in sorted(groups):
        lines.append(f"## docs/{folder}" if folder != "." else "## docs")
        lines.append("")
        for relative in groups[folder]:
            lines.append(_entry(docs, relative, virtual))
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def build_decisions_index(root: Path = ROOT) -> str:
    """The text of the index of the decision records, in the order of the number of each record."""
    decisions = root / "docs" / "decisions"
    records: list[tuple[int | None, str, str, str, str]] = []
    for path in sorted(decisions.glob("*.md")):
        if path.name == "README.md":
            continue
        number, title, status, date = _record(path)
        records.append((number, path.name, title, status, date))
    records.sort(key=lambda item: (item[0] is None, item[0] or 0, item[1]))

    lines = [
        "# Decision records",
        "",
        "Every decision that restricts the future of the work is a record in this folder, and this index lists them",
        "in the order of their number, with their status and their date.",
        "",
        "This file is generated by `scripts/build_docs_index.py` from the files that are on the disk. Do not edit it",
        "by hand: run `uv run python scripts/build_docs_index.py` and commit the result.",
        "",
        "| ADR | Title | Status | Date |",
        "| --- | --- | --- | --- |",
    ]
    for number, name, title, status, date in records:
        label = f"{number:03d}" if number is not None else "unknown"
        # The pipe of the title is escaped, because a pipe inside a cell of the table would open a new column.
        cell = title.replace("|", "\\|")
        lines.append(f"| {label} | [{cell}]({name}) | {status} | {date} |")
    lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def _documents_of_the_disk(docs: Path) -> list[str]:
    """The paths of the Markdown files of the documentation, relative to the folder of the documentation.

    Why the index of the documentation leaves two files out: it leaves itself out, and it leaves the handoff of
    a cycle out, because that file names the paths of the machine of its author and never reaches git.
    """
    return [
        path.relative_to(docs).as_posix()
        for path in sorted(docs.rglob("*.md"))
        if path.relative_to(docs).as_posix() not in LOCAL_ONLY
    ]


def _the_two_indexes(root: Path) -> dict[Path, str]:
    """The two index files of the repository, with the index of the documentation built last.

    Why the order matters: the index of the documentation describes the index of the records, and the
    description has to come from the text that the script writes now. Reading that text from the disk instead
    would make the index depend on the state of the previous run, and the check would refuse on a repository
    whose documentation never changed.
    """
    decisions = build_decisions_index(root)
    docs = build_docs_index(root, generated={"decisions/README.md": decisions})
    return {
        root / "docs" / "README.md": docs,
        root / "docs" / "decisions" / "README.md": decisions,
    }


def _check(root: Path) -> int:
    """The check mode: compare the index with the disk, write nothing and name the file that drifted."""
    wanted = _the_two_indexes(root)
    problems = []
    for path in sorted(wanted):
        text = wanted[path]
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current == text:
            continue
        name = path.relative_to(root).as_posix()
        if current is None:
            problems.append(f"build_docs_index: {name} does not exist on the disk")
        else:
            problems.append(
                f"build_docs_index: {name} is out of date: the file on the disk is not what the script writes"
            )
    index_path = root / "docs" / "README.md"
    index_on_disk = index_path.read_text(encoding="utf-8") if index_path.is_file() else ""
    problems.extend(_documents_left_out(root, index_on_disk))
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        print("build_docs_index: run 'uv run python scripts/build_docs_index.py' to write the index", file=sys.stderr)
        return 1
    print("the index of the documentation matches the files that are on the disk")
    return 0


def _documents_left_out(root: Path, current: str | None) -> list[str]:
    """The documents of the disk that the index on the disk does not name.

    Why the names of the documents come before the verdict: the person who reads the failure has to know which
    file to add to the index, and a refusal that only says that the index is out of date sends that person to
    hunt for it.
    """
    if current is None:
        return []
    docs = root / "docs"
    listed = set(_LINK_TARGET.findall(current))
    return [
        f"build_docs_index: docs/{relative} is on the disk and the index does not name it"
        for relative in _documents_of_the_disk(docs)
        if relative not in listed
    ]


def _write(root: Path) -> int:
    """The write mode: write the two index files."""
    wanted = _the_two_indexes(root)
    for path in sorted(wanted):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(wanted[path], encoding="utf-8")
        print(f"the index was written: {path.relative_to(root).as_posix()}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """The entry point of the script. The exit code is the answer."""
    parser = argparse.ArgumentParser(description="Builds the index of the documentation and of the decision records.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="writes nothing and refuses when the index on the disk is not what the script would write",
    )
    parser.add_argument("--root", default=str(ROOT), help="the root of the repository")
    args = parser.parse_args(argv)
    try:
        root = Path(args.root).resolve()
    except (OSError, RuntimeError, ValueError) as error:
        print(f"build_docs_index: the root {args.root} cannot be resolved: {error}", file=sys.stderr)
        return 1
    if not (root / "docs").is_dir():
        print(f"build_docs_index: the root {root} holds no folder of documentation", file=sys.stderr)
        return 1
    if args.check:
        return _check(root)
    return _write(root)


if __name__ == "__main__":
    sys.exit(main())
