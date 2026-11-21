---
type: adr
status: accepted
date: 2026-11-11
---

# ADR-016: English first, with a maintained Brazilian Portuguese translation layer

Status: accepted. Date: 2026-11-11.

## Context

The repository is written in English: prompts, docs, identifiers, docstrings, commit messages. The guard of the public
repository enforces it and refuses Portuguese text across the code, the data, the docs, the tests and the specs. That
rule made the R0 import simple and the repository readable for any reviewer.

Erik asked, on 2026-11-11, that the project stay initially in English but also carry a Brazilian Portuguese
translation: the audience of the demonstration is Brazilian, and the language of the repository should not be a wall
between the work and the people it was built for.

The two goals live together only if the translation is a derived layer with an explicit surface. A translation that
spreads through the tree fights the guard; a guard that simply stops looking fights the repository.

## Decision

- English is the source of truth. Documents, identifiers, tests, commit messages, code comments and file names are
  written in English, exactly as the guard demands today.
- The Brazilian Portuguese translation lives in a derived surface: `docs/pt-BR/` mirrors the path of the English
  document it translates (`docs/roadmap-v3.md` becomes `docs/pt-BR/roadmap-v3.md`), and the root gains
  `README.pt-BR.md` next to the English README.
- Documents are born in English. A translation is added when the document becomes part of what a Brazilian reader
  evaluates, and the first batch is the README and the roadmap.
- The guard is narrowed, not weakened: Portuguese is allowed only inside `docs/pt-BR/**` and `README.pt-BR.md`.
  Everywhere else the refusal stays exactly as it is, and a test keeps the allowance narrow.
- Parity is part of the definition of done: when an English document that has a translation changes, its translation
  changes in the same commit. A translation that lags behind its source is a defect, the same way a stale document is.
- When a translation and its source disagree, the English text wins and the translation is fixed. The translation is
  never the authority.
- Nothing under `docs/v3/` is translated: that tree is the imported design package, and the import check compares it
  against the package after the mechanical conversion of the import.
- The user-facing strings of the web surfaces become bilingual when the frontend phase opens, which is a paused
  decision recorded here so that it is not rediscovered later.

## Alternatives considered

- **Keep the repository English only.** It is the rule of the R0 and the cheapest path. It hides the work from the
  Brazilian audience it was built for, which is the reason the request exists.
- **Write both languages in one file.** It doubles every file, makes every diff noisy, and the guard would have to
  reason line by line instead of path by path.
- **Translate everything, including code comments.** It fights every rule of the repository, doubles the surface that
  can drift, and serves no reader: the code speaks to contributors, who read the repository language.

## Consequences

- The guard gains one narrow allowance, with a test that keeps it narrow, landing together with the first translated
  documents.
- `docs/pt-BR/` is a mirror, never an origin: a document that only exists there is a defect.
- Every commit that touches a translated document carries its translation update, which is a small, visible review
  step.
- The bilingual web strings arrive with the frontend phase, not before, and this decision is the place that says so.
