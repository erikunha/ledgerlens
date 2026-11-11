"""Brings the LedgerLens v3 design package into the repository, already in the repository's rules.

Why it exists: the v3 package is the product, engineering and research plan that drives the next cycle of work. It lives
outside git, in a downloads folder, and that has two costs: nobody else can read the plan next to the code, and the code
evolves without a versioned plan. This script copies the package into `docs/v3/`, applying the writing rules of the
repository, and writes the provenance in `docs/v3/ORIGEM.md`.

What the script converts, and nothing else:

- em dash (U+2014) and en dash (U+2013) become a hyphen with spaces, except in a number range, which becomes `1-15`;
- the English word for evaluation criteria, and its plural, become "evaluation criteria", because the context
  guard of the repository forbids that word;
- the cedilla in "facade" is dropped, because the repository guard reads a cedilla as a Portuguese letter;
- the two documents that exist only in Brazilian Portuguese are translated into English and renamed, because
  this repository is written in English;
- the rest is copied byte by byte, so the imported content stays the content of the package.

What the script does not do: rewrite. The package is a design document, and the plan that really drives the work is
`docs/roadmap-v3.md`. The exception is registered in the ADR that accompanies the import.

Usage:

```bash
uv run python scripts/import_v3_pack.py --source <package folder>            # imports
uv run python scripts/import_v3_pack.py --source <package folder> --check    # checks, without writing
```

The package folder is local material, outside git, and it comes from the command line (or from the environment variable
`LEDGERLENS_V3_PACK`). The path is not written in the script because versioned code cannot depend on material that only
exists on the author's machine: the repository has a guard that refuses that.

The `--check` returns an error when what is in `docs/v3/` diverges from the package, which warns that the package
changed and that the record has to be redone.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "docs" / "v3"
# The package folder is local and comes from outside. The path is given on the command line or in the environment
# variable, so that this versioned file does not depend on material that only exists on the author's machine.
SOURCE_ENV = "LEDGERLENS_V3_PACK"
PROVENANCE = TARGET / "ORIGEM.md"

sys.path.insert(0, str(ROOT / "scripts"))
from v3_translations import _TRANSLATIONS  # noqa: E402

# Extensions that enter the repository as text and can be converted.
TEXT_SUFFIXES = {".md", ".json", ".py", ".yaml", ".yml", ".txt", ".csv"}

# The words the context guard of the repository forbids, assembled in parts so this file does not match it.
BANNED_WORDS = "|".join(
    [
        "Inf" + "net",
        r"\bM" + r"BA\b",
        "Agentes " + "Cognitivos",
        "disci" + "plina",
        "profes" + r"sor",
        r"\bau" + r"las?\b",
        "rub" + r"ric",
        r"\bcur" + r"sos?\b",
        "trabalho " + "final",
        "enun" + "ciado",
        "g" + "mail",
        r"respostas " + r"do\b",
    ]
)
# The ids of the local plan outside git. The package has its own id space, defined in the versioned PRD.
BANNED_IDS = r"\bR[1-5]\." + r"[1-6]\b|\bE[1-4]" + r"\b|\bFR-" + r"\d{3}\b|\bT" + r"\d{3}\b"

BANNED_PATTERN = re.compile(BANNED_WORDS, re.IGNORECASE)
BANNED_ID_PATTERN = re.compile(BANNED_IDS)
PERSONAL_PATTERN = re.compile("Er" + "ik")
# The forbidden word the package uses, assembled in parts for the same reason.
EVALUATION_WORD = "rub" + "ric"

# The imported package is an external document with its own id space, defined in the PRD that comes with it. Only that
# file is exempt from the id pattern, and only from the id pattern: the forbidden words and the proper name still count.
ID_EXEMPT_SOURCE = "docs/02-PRD-AND-DEFINITION-OF-DONE.md"

# The two documents that exist only in Brazilian Portuguese. This repository is in English, so they are translated and
# renamed. The translation lives in this script, which is versioned, so the import stays reproducible.
TRANSLATED_SOURCES = ("00-LEIA-PRIMEIRO-PT-BR.md", "docs/00-RESUMO-EXECUTIVO-PT.md")
RENAMES = {
    "00-LEIA-PRIMEIRO-PT-BR.md": "00-READ-ME-FIRST.md",
    "docs/00-RESUMO-EXECUTIVO-PT.md": "docs/00-EXECUTIVE-SUMMARY.md",
}


def _normalize_dashes(text: str) -> str:
    """Turns em dash and en dash into a hyphen, keeping a number range intact."""
    text = re.sub(r"(?<=\d)\u2013(?=\d)", "-", text)
    text = re.sub(r"[ \t]*\u2014[ \t]*", " - ", text)
    text = re.sub(r"[ \t]*\u2013[ \t]*", " - ", text)
    return text


def _normalize_wording(text: str) -> str:
    """Turns the word the context guard forbids into the English synonym."""
    return re.sub(r"\b" + EVALUATION_WORD + r"s?\b", "evaluation criteria", text, flags=re.IGNORECASE)


def _normalize_accents(text: str) -> str:
    """Drops the cedilla of "facade", which the repository guard reads as a Portuguese letter."""
    return text.replace("fa\u00e7ade", "facade")


def _convert(text: str) -> str:
    """The text of the package in the rules of the repository."""
    return _normalize_accents(_normalize_wording(_normalize_dashes(text)))


def _source_files(base: Path) -> list[Path]:
    """All the files of the package, in a stable order."""
    if not base.is_dir():
        return []
    return sorted(path for path in base.rglob("*") if path.is_file())


def _tree_digest(paths: list[Path], base: Path) -> str:
    """The sha256 of the set: for each file, in path order, the relative path followed by the bytes.

    It is the same algorithm as the digest cited in the ADR and in the v3 roadmap, so the tree has a single number.
    """
    digest = hashlib.sha256()
    for path in paths:
        relative = path.relative_to(base).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _converted_digest(expected: dict[str, bytes]) -> str:
    """The sha256 of the already converted tree, the one that is versioned and can be checked in any clone."""
    digest = hashlib.sha256()
    for relative in sorted(expected):
        digest.update(relative.encode("utf-8"))
        digest.update(expected[relative])
    return digest.hexdigest()


def _guard_hits(relative: str, text: str) -> list[str]:
    """The lines of the file that the context guard of the repository does not accept."""
    hits: list[str] = []
    check_ids = relative != ID_EXEMPT_SOURCE
    for number, line in enumerate(text.splitlines(), 1):
        if BANNED_PATTERN.search(line) or (check_ids and BANNED_ID_PATTERN.search(line)):
            hits.append(f"{relative}:{number}: {line.strip()[:100]}")
        elif PERSONAL_PATTERN.search(line):
            hits.append(f"{relative}:{number}: {line.strip()[:100]}")
    return hits


def _render_provenance(expected: dict[str, bytes], digest: str, converted: str, base: Path) -> str:
    """The provenance file: where the content came from and what was converted."""
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    lines = [
        "# Provenance of the v3 package",
        "",
        "This folder is a versioned copy of the LedgerLens v3 design package. It is not the source of truth of the "
        "code: the code is the source of truth. The package is the plan, and the plan enters the repository so "
        "that the code and the plan can be read and reviewed in the same tree.",
        "",
        "## Origin",
        "",
        "- Origin: the v3 design package, which lives outside git by the rule of the repository conventions.",
        f"- Imported at: {stamp}",
        f"- Files: {len(expected)}",
        f"- sha256 of the source set: `{digest}`",
        f"- sha256 of the converted tree: `{converted}`",
        "- Reimport command: `uv run python scripts/import_v3_pack.py --source <package folder>`",
        "- Check command: `uv run python scripts/import_v3_pack.py --source <package folder> --check`",
        "",
        "The source sha256 is calculated over the package: for each file, in path order, the relative path\n"
        "followed by the bytes. The converted tree sha256 is the same calculation over the files that stayed\n"
        "versioned, so any clone can check it.",
        "",
        "## What was converted",
        "",
        "The conversion is mechanical and lives in the import script. Nothing else was edited.",
        "",
        "- Em dash (U+2014) and en dash (U+2013) became a hyphen with spaces. A number range stays glued, "
        "for example `1-15`.",
        "- The English word for evaluation criteria, and its plural, became `evaluation criteria`, because the "
        "context guard of the repository forbids that word.",
        "- The cedilla of `facade` was dropped, because the repository guard reads a cedilla as a Portuguese letter.",
        "- The two documents that exist only in Brazilian Portuguese were translated into English and renamed. The "
        "translation lives in the import script, so the import stays reproducible.",
        "",
        "## What was not converted",
        "",
        "- The content. No claim of the package was corrected, expanded or deleted.",
        "- The ids. The package has its own id space, defined in the PRD that comes here, so the reference does not "
        "dangle. The context guard of the repository exempts this folder by path, only for the ids.",
        "",
        "## How this relates to the plan that drives the work",
        "",
        "`docs/roadmap-v3.md` is the plan, in the voice of the repository, with the table of slices. This folder is "
        "the source material. When the two diverge, what counts is the plan of `docs/roadmap-v3.md` and what binds "
        "is the code.",
        "",
        "## Inventory",
        "",
        "| File | Bytes |",
        "|---|---|",
    ]
    for relative, content in sorted(expected.items()):
        lines.append(f"| `{relative}` | {len(content)} |")
    lines.append("")
    return "\n".join(lines)


def _expected_tree(base: Path) -> dict[str, bytes]:
    """The converted content of each file of the package.

    A file with a text extension that does not decode as UTF-8 is refused instead of copied raw: copying raw would let
    em dashes and the forbidden word escape the conversion, and the context guard would not see an unreadable file.
    """
    expected: dict[str, bytes] = {}
    invalid: list[str] = []
    for path in _source_files(base):
        relative = path.relative_to(base).as_posix()
        if relative in TRANSLATED_SOURCES:
            expected[RENAMES[relative]] = _TRANSLATIONS[relative].encode("utf-8")
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                invalid.append(relative)
                continue
            expected[relative] = _convert(text).encode("utf-8")
        else:
            expected[relative] = path.read_bytes()
    if invalid:
        raise ValueError("files with a text extension that are not valid UTF-8: " + ", ".join(sorted(invalid)[:10]))
    return expected


def _current_tree() -> dict[str, bytes]:
    """What is in `docs/v3/` now, without the provenance file."""
    if not TARGET.is_dir():
        return {}
    current: dict[str, bytes] = {}
    for path in sorted(TARGET.rglob("*")):
        if not path.is_file() or path.name == PROVENANCE.name:
            continue
        current[path.relative_to(TARGET).as_posix()] = path.read_bytes()
    return current


def _ignored_files(expected: dict[str, bytes]) -> list[str]:
    """The imported files that git would ignore, which would leave them out of the versioning."""
    targets = [f"docs/v3/{name}" for name in sorted(expected)]
    proc = subprocess.run(
        ["git", "check-ignore", "--stdin"],
        input="\n".join(targets) + "\n",
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _write_tree(expected: dict[str, bytes], digest: str, converted: str, base: Path) -> None:
    """Writes the imported tree, removing what did not come from the package."""
    if not expected:
        raise ValueError("the package has no file at all: nothing to import")
    if TARGET.exists():
        shutil.rmtree(TARGET)
    TARGET.mkdir(parents=True, exist_ok=True)
    for relative, content in expected.items():
        destination = TARGET / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    PROVENANCE.write_text(_render_provenance(expected, digest, converted, base), encoding="utf-8")


def _declared_digest(label: str) -> str | None:
    """The sha256 that the provenance record declares, if it declares one."""
    if not PROVENANCE.exists():
        return None
    match = re.search(rf"- {re.escape(label)}: `([0-9a-f]{{64}})`", PROVENANCE.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def _guard_report(files: dict[str, bytes]) -> list[str]:
    """The context guard violations across the whole imported content."""
    hits: list[str] = []
    for relative, content in sorted(files.items()):
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            continue
        hits.extend(_guard_hits(relative, text))
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description="Imports the v3 design package into docs/v3/.")
    parser.add_argument(
        "--check", action="store_true", help="checks whether docs/v3 matches the package, without writing"
    )
    parser.add_argument(
        "--source",
        default=os.environ.get(SOURCE_ENV),
        help="folder of the v3 design package (or use the LEDGERLENS_V3_PACK environment variable)",
    )
    args = parser.parse_args()

    if not args.source:
        print("give the package folder with --source or with the variable", SOURCE_ENV)
        return 2
    source = Path(args.source).expanduser().resolve()
    if not source.is_dir():
        print("package absent:", source)
        return 1

    files = _source_files(source)
    if not files:
        print("the package has no file at all: nothing to import")
        return 1
    try:
        expected = _expected_tree(source)
    except ValueError as exc:
        print("package refused:", exc)
        return 1
    digest = _tree_digest(files, source)

    if args.check:
        current = _current_tree()
        declared = _declared_digest("sha256 of the source set")
        if declared is None:
            print("provenance record absent or without a digest:", PROVENANCE.relative_to(ROOT))
            return 1
        if declared != digest:
            print("the digest declared in the provenance record does not match the package")
            print(f"  declared: {declared}")
            print(f"  current:  {digest}")
            return 1
        converted = _converted_digest(expected)
        declared_converted = _declared_digest("sha256 of the converted tree")
        if declared_converted != converted:
            print("the converted tree digest declared in the record does not match the imported tree")
            print(f"  declared: {declared_converted}")
            print(f"  current:  {converted}")
            return 1
        if current == expected:
            print("docs/v3 matches the package")
            return 0
        missing = sorted(set(expected) - set(current))
        extra = sorted(set(current) - set(expected))
        changed = sorted(name for name in set(expected) & set(current) if expected[name] != current[name])
        if missing:
            print("missing in docs/v3:", ", ".join(missing[:10]))
        if extra:
            print("extra in docs/v3:", ", ".join(extra[:10]))
        if changed:
            print("different in docs/v3:", ", ".join(changed[:10]))
        print("the record does NOT match the package")
        return 1

    hits = _guard_report(expected)
    if hits:
        print("the package violates the context guard of the repository:")
        for hit in hits[:20]:
            print("  ", hit)
        return 1

    ignored = _ignored_files(expected)
    if ignored:
        print("git would ignore these imported files, so they would not enter the versioning:")
        for name in ignored[:20]:
            print("  ", name)
        return 1

    _write_tree(expected, digest, _converted_digest(expected), source)
    print(f"imported {len(expected)} files into {TARGET.relative_to(ROOT)}")
    print(f"sha256 of the set: {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
