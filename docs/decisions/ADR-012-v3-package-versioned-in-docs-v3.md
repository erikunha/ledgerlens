---
type: adr
status: accepted
date: 2026-11-11
---

# ADR-012: The v3 package versioned in `docs/v3/`

Status: accepted. Date: 2026-11-11.

## Context

The v3 design package is a set of 125 files that drives the next cycle: the product requirements, the architecture, the
advanced specs, the contracts with their JSON Schemas, the screen registry, the capability atlas and the release train.
It arrives as a folder outside git.

Keeping it outside has two costs. Nobody can read the plan next to the code, and the code evolves without a versioned
plan: the plan says what the next slice should do, and nobody can check whether it still says that.

Importing it by hand does not work either. A hand copy cannot be checked, and it rots the first time the package
changes.

## Decision

The package is versioned in `docs/v3/`, imported by `scripts/import_v3_pack.py`.

The import is mechanical and declared, and it does exactly these things:

- an em dash (U+2014) and an en dash (U+2013) become a hyphen with spaces, except in a number range, which stays
  glued, for example `1-15`;
- the English word for evaluation criteria, and its plural, become `evaluation criteria`, because the context guard of
  the repository forbids that word;
- the cedilla of `facade` is dropped, because the repository guard reads a cedilla as a Portuguese letter;
- the two documents that exist only in Brazilian Portuguese are translated into English and renamed, because this
  repository is written in English. The translation lives in `scripts/v3_translations.py`, which is versioned, so the
  import stays reproducible.

Everything else is copied byte by byte. No claim of the package is corrected, expanded or deleted.

The script writes the provenance in `docs/v3/ORIGEM.md`: the date of the import, the number of files, the sha256 of the
source set, the sha256 of the converted tree, the exact commands to reimport and to check, the inventory of every file
with its size, and the list of what was converted and what was not.

The sha256 of the source set is calculated over the package: for each file, in path order, the relative path followed by
the bytes. The sha256 of the converted tree is the same calculation over the files that stayed versioned, so any clone
can check it.

`scripts/import_v3_pack.py --check` recomputes both digests and compares them with the record, and it also compares the
tree file by file. It returns an error when the package changed, which warns that the record has to be redone.

The import refuses to run when the package violates the context guard of the repository, and it refuses to run when git
would ignore one of the imported files, because a file that is ignored does not enter the versioning.

## Alternatives considered

- **Keep the package outside git and cite it in the README.** The plan would drift from the code, and a reader of the
  repository would have to guess what the next slice was supposed to do.
- **Copy the package by hand into `docs/`.** A hand copy cannot be checked, and the day the package changes, the
  repository would carry a plan that no longer matches the source.
- **Translate the whole package.** The package is already in English, and translating 125 files would put the work in
  the plan of the work. The two documents that exist only in Portuguese are translated, because this repository is in
  English and the guard reads Portuguese as a defect.
- **Store the package compressed.** A zip in git is not readable and not reviewable in a diff.

## Consequences

- The plan and the code are read in the same tree, and the plan is reviewable in a diff.
- The import is reproducible, and the check says whether the package moved.
- The converted tree is not byte identical to the package, and the record says exactly what changed and why.
- The package is third party material. It is in English and it stays in English.
- The two Portuguese documents arrive as translations, so they are a translation and not a copy. The record says so.
- The digest of the source set is a single number that identifies the package: `4bf1cb2402ac7b31d85244e9ec7e4970c1db5ab63f17361d43471e102a2cbad1`.
