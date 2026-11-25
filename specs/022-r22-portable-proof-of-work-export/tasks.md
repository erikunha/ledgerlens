---
description: "Task list for portable proof of work"
---

# Tasks: Portable proof of work

**Input**: Design documents from `specs/022-r22-portable-proof-of-work-export/`

**Prerequisites**: plan.md (required), spec.md (required), the design package of the release
(`docs/v3/advanced-specs/R22-01-portable-proof-of-work-artifact-export.md`), ADR-013, ADR-014, ADR-017, ADR-036,
ADR-040, ADR-042, ADR-073, ADR-075, ADR-076 and ADR-077 of `docs/decisions/`, ADR-P007 and ADR-P009 of
`docs/v3/adrs/`, and the code the artifact builds on: `ledgerlens/replay/bundle.py`, `ledgerlens/replay/site_export.py`,
`ledgerlens/observability/callbacks.py` for the redaction, `scripts/export_replay_site.py`,
`scripts/verify_replay_digests.py`, `scripts/check_export_pages.mjs`, `scripts/measure_replay_budget.py`, the
published catalogs `data/eval/replay/` and `data/eval/replay-real/`, the reports under `data/eval/` and the
accessibility checks of `apps/web/tests/e2e/a11y.spec.ts`

**Tests**: Every task that changes the behaviour of the repository ships its test before its code, and the gate of
the Python side and the gate of the frontend are green before the commit. The tests of the artifact live in
`tests/proof/`, the tests of the page in `apps/web/tests/unit/` and in `apps/web/tests/e2e/`, and everything runs
offline with `LEDGERLENS_OFFLINE=1`. Every test of this list is written to fail before the code of its task and to
pass after it. No task of this list writes into `data/eval/replay/` or into `data/eval/replay-real/`, and no
artifact of this list carries the input of a visitor

**Organization**: Tasks are grouped by the layer of the artifact that they build, from the decision that starts it
to the page that shows it. The ids of this list start at T1101 and are unique in the repository; the ids of the
specifications `001` to `006` end at T172, and the blocks of the lists that run in parallel are kept apart, so that
two people can work on this list and on another list at the same time. The tasks marked `[P]` touch disjoint files
and can run in parallel with each other.

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[DELIVERED]**: the task is done, and the sentence names what it delivered
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `ledgerlens/`, `tests/`, `scripts/`, `data/`, `docs/` at repository root
- Paths shown below assume single project

## The decision that starts the milestone

**Purpose**: the artifact carries the provenance and the digest discipline of the published catalogs, it is a
static export and not a runtime route, and it attests to a claim about the code and never about a person.

- [x] T1101 Write the record of the decision in
  `docs/decisions/ADR-083-the-proof-of-work-carries-the-provenance-and-the-digest-discipline-of-the-catalogs.md`,
  with the number the index shows as free at the time of writing, saying that the artifact is a static export under
  `site/proof/`, that its identifier is the digest of the bundle, that the status is `draft` until the digest of
  the dataset, the commit, the digests of the files and the offline re-verification are all there, that the
  numbers come from the reports of the repository, that the redaction is the last wall before the file is written
  and that the artifact says nothing about a person, an employer or a hiring decision. Run
  `uv run python scripts/build_docs_index.py` to regenerate `docs/decisions/README.md` and commit the result. The
  record does not change any accepted record

## The provenance of the artifact

**Purpose**: the artifact carries the commit and the digests of the run it describes.

  - **DELIVERED**: ADR-097 written and the decisions index regenerated with it; no accepted record changed.
- [x] T1102 Write `ledgerlens/proof/__init__.py` with the docstring of the package, which says that the package
  composes a claim about the code of the repository with its evidence, its provenance and the recipe that
  reproduces it
  - **DELIVERED**: `ledgerlens/proof/__init__.py` carries the docstring of the package: the artifact is a claim about the code with its evidence, its provenance and the recipe that reproduces it.
- [x] T1103 Write `tests/proof/test_provenance.py` first, expecting that the artifact of a bundle of each catalog
  carries the commit, the digest of every file of the bundle, the digest of the snapshot, the digest of the
  dataset, the catalog, the capture kind and the model profiles, and expecting that every digest is the digest of
  the file on the disk. Then write `ledgerlens/proof/provenance.py` with the reading of the manifest of the bundle
  and of the index of the catalog, with a docstring that says that the provenance of the artifact is the
  provenance of the bundle
  - **DELIVERED**: `tests/proof/test_provenance.py` and `ledgerlens/proof/provenance.py`: the commit, the digest of every file, the digest of the snapshot, the digest of the dataset, the catalog, the capture kind and the model profiles, every digest read from the disk.
- [x] T1104 Write `tests/proof/test_identifier.py` first, expecting that the identifier of the artifact is the
  digest of the bundle and that two artifacts of two commits have two identifiers. Then extend
  `ledgerlens/proof/provenance.py` with the identifier, with a docstring that says that the identifier is
  unguessable by construction and that no private artifact exists

## The offline re-verification and the status

**Purpose**: the artifact is `verified` only when the evidence is all there and the code says so.

  - **DELIVERED**: `tests/proof/test_identifier.py`: the identifier of the artifact is the digest of the bundle, and two artifacts of two bundles have two identifiers.
- [x] T1105 Write `tests/proof/test_offline_reverification.py` first, expecting that the verdict the artifact
  publishes is the verdict the deterministic verifier of `ledgerlens/verify/checks.py` gives for the published
  evidence of the bundle, with no model and no network, reusing the reading of `ledgerlens/replay/bundle.py`. Then
  write `ledgerlens/proof/verification.py` with the re-verification, with a docstring that says that the
  verification is the one of the published catalogs and that it needs nothing but the bundle
  - **DELIVERED**: `tests/proof/test_offline_reverification.py` and `ledgerlens/proof/verification.py`: the verdict the artifact publishes is the verdict of the deterministic verifier over the published evidence, with no model and no network.
- [x] T1106 Write `tests/proof/test_status.py` first, expecting that the status is `draft` with the name of the
  missing evidence when the digest of the dataset is removed, that a `draft` artifact carries no verified badge and
  that the status is `verified` for a complete bundle. Then write `ledgerlens/proof/status.py` with the rule, with
  a docstring that says that no person promotes an artifact by hand

## The composition

**Purpose**: the artifact is a document whose every part comes from a file of the repository.

  - **DELIVERED**: `tests/proof/test_status.py` and `ledgerlens/proof/status.py`: the status is draft with the name of the missing evidence, a draft carries no badge, and a complete bundle is verified.
- [x] T1107 Write `tests/proof/test_numbers_come_from_a_report.py` first, expecting that every number of the
  artifact is present in the report that the artifact names, with the path and the digest of that report, and
  expecting the failure of the build when a number is not in the report. Then write `ledgerlens/proof/numbers.py`
  with the reading of the reports, with a docstring that says that a number typed by a person is a claim and not a
  measurement
  - **DELIVERED**: `tests/proof/test_numbers_come_from_a_report.py` and `ledgerlens/proof/numbers.py`: every number is in the report it names, with the path and the digest, and a number that is not there fails the build.
- [x] T1108 Write `tests/proof/test_links.py` first, expecting that every link of the artifact resolves inside the
  commit that the artifact names and that the recipe carries the command that reproduces the run. Then write
  `ledgerlens/proof/artifact.py` with the composition of the sections and the recipe, with a docstring that says
  what an artifact is and why every section of it has a source
  - **DELIVERED**: `tests/proof/test_links.py` and `ledgerlens/proof/artifact.py`: every link resolves inside the commit the artifact names, and the recipe carries the command that reproduces the run.
- [x] T1109 Write `tests/proof/test_schema.py` first, expecting the validation of the artifact against
  `docs/v3/contracts/schemas/v3-portfolio-proof.schema.json` with `jsonschema` and expecting the refusal of an
  artifact that breaks it. The schema is versioned in the frozen package and it is read, never edited
  - **DELIVERED**: `tests/proof/test_schema.py`: the artifact of each catalog validates against the schema of the package with jsonschema, and an artifact that breaks it is refused.
- [x] T1110 Write `tests/proof/test_claim_scope.py` first, expecting that the artifact names the code, the commit
  and the digests and that no sentence of it is about an employer or a hiring decision. Then extend
  `ledgerlens/proof/artifact.py` with the wording of the claim, with a docstring that says that the artifact is a
  claim about the code and never about a person

## The redaction and the privacy

**Purpose**: nothing that looks like a secret reaches a published file.

  - **DELIVERED**: `tests/proof/test_claim_scope.py`: the artifact names the code, the commit and the digests, and no sentence of it is about an employer or a hiring decision.
- [x] T1111 Write `tests/proof/test_redaction.py` first, expecting that an export over a content that carries a
  string that looks like a key is refused with the name of the file and that the output directory holds no file,
  using the `redact` of `ledgerlens/observability/callbacks.py`. Then write `ledgerlens/proof/redact.py` with the
  scan of the finished artifact, with a docstring that says that the artifact carries prose that the trace does
  not carry and that the scan is the last wall before the write
  - **DELIVERED**: `tests/proof/test_redaction.py` and `ledgerlens/proof/redact.py`: an export whose content carries a secret like string is refused with the name of the file, and the output directory holds no file.
- [x] T1112 Write `tests/proof/test_no_visitor_data.py` first, exporting every artifact of the two catalogs and
  expecting that no artifact carries a key, a session id or a path of a machine. Then extend
  `ledgerlens/proof/export.py` so that it reads the published catalogs and never a session, with a docstring that
  says that a run of a visitor is not published and therefore has no artifact

## The accessibility of the artifact

**Purpose**: the artifact can be read without the media.

  - **DELIVERED**: `tests/proof/test_no_visitor_data.py` and `ledgerlens/proof/export.py`: every artifact of the two catalogs is exported, and no artifact carries a key, a session id or a path of a machine.
- [x] T1113 Write `tests/proof/test_accessibility.py` first, expecting the transcript of every media of the
  artifact and expecting that an artifact over the budget of the site keeps the transcript and drops the media,
  with the budget measured by `scripts/measure_replay_budget.py`. Then write `ledgerlens/proof/media.py` with the
  transcript and the budget, with a docstring that says that the media is optional and the text is not

## The export and the gate

**Purpose**: the artifact is published under `site/proof/` and the gate refuses a drift.

  - **DELIVERED**: `tests/proof/test_accessibility.py` and `ledgerlens/proof/media.py`: every media carries a transcript, and an artifact over the budget keeps the transcript and drops the media.
- [x] T1114 Write `tests/proof/test_published_proof.py` first, expecting that the export under `site/proof/`
  matches the bundle it was built from and that the check fails when a published proof does not match. Then write
  `scripts/export_proof_site.py` with the export and the `--check` mode, next to `scripts/export_replay_site.py`,
  and add the step to `scripts/gate.sh` with the same discipline: it writes nothing and fails with a readable
  reason
  - **DELIVERED**: `tests/proof/test_published_proof.py` and `scripts/export_proof_site.py`: the export under site/proof/ matches the bundle, the check fails on a drift, and the step runs in scripts/gate.sh.
- [x] T1115 Write `tests/proof/test_not_a_replay_bundle.py` first, expecting that the export of the proofs writes
  nothing under `data/eval/replay/` and nothing under `data/eval/replay-real/` and that
  `uv run python scripts/export_replay_site.py --check` still passes for the two catalogs. The two catalogs are
  read by this milestone and never written

## The page of the site

**Purpose**: a reader opens the proof and reads it.

  - **DELIVERED**: `tests/proof/test_not_a_replay_bundle.py`: the export of the proofs writes nothing under the two published catalogs, and the export of the replay site still passes its check.
- [x] T1116 [P] Write the page under `apps/web/app/(public)/proof/page.tsx` and the page of a single artifact
  under `apps/web/app/(public)/proof/[id]/page.tsx`, with the provenance, the claim, the evidence, the verdicts,
  the recipe and the links, and with the status of the artifact and the badge only when it is `verified`. Write
  the unit tests in `apps/web/tests/unit/features/proof-page.test.tsx` and the tests of the catalog in
  `apps/web/tests/unit/proof-catalog.test.tsx`
  - **DELIVERED**: The pages `apps/web/app/(public)/proof/page.tsx` and `apps/web/app/(public)/proof/[id]/page.tsx` with the provenance, the claim, the evidence, the verdicts, the recipe and the links, and the unit tests in `apps/web/tests/unit/proof-catalog.test.tsx` and `apps/web/tests/unit/features/proof-page.test.tsx`.
- [x] T1117 [P] Write the end to end test in `apps/web/tests/e2e/proof.spec.ts` that opens the proof, expects the
  provenance and the recipe, and expects the accessibility check of `apps/web/tests/e2e/a11y.spec.ts` to pass over
  the page of the proof

## The documentation that closes the milestone

**Purpose**: a reader of the artifact knows what it claims and what it does not.

  - **DELIVERED**: The end to end test `apps/web/tests/e2e/proof.spec.ts` opens the proof and expects the provenance and the recipe, and the page of the proof joined the pages the accessibility suite scans.
- [x] T1118 [P] Write `docs/proof.md` with the sections of the artifact and where each one comes from, the rule of
  the status, the rule that the numbers come from the reports, the redaction and the privacy of the export, the
  accessibility of the media, and the statement that the artifact is a claim about the code of the repository and
  never a proof of a person or of an employer. Link it from `docs/README.md` by running
  `uv run python scripts/build_docs_index.py`
  - **DELIVERED**: `docs/proof.md` written with the sections of the artifact, the rule of the status, the numbers, the redaction, the accessibility and the statement that the artifact is a claim about the code; the index regenerated.
