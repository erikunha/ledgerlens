# Feature Specification: Portable proof of work

**Feature Branch**: `feature/v3`

**Created**: 2026-11-23

**Status**: Draft

**Input**: Design documents: [R22-01, portable proof of work artifact export](../../docs/design/advanced-specs/R22-01-portable-proof-of-work-artifact-export.md),
[ADR-013, the public trace is a versioned contract](../../docs/decisions/ADR-013-public-trace-as-a-versioned-contract.md),
[ADR-014, the replay bundle has a manifest and a hash](../../docs/decisions/ADR-014-replay-bundle-with-manifest-and-hash.md),
[ADR-017, the bundle declares its commit and the export publishes artifacts the interface accepts](../../docs/decisions/ADR-017-export-contract-and-provenance.md),
[ADR-036, the limitation of the zeroization of the key of a visitor](../../docs/decisions/ADR-036-the-limitation-of-the-zeroization.md),
[ADR-040, the live mode lives on the origin of the backend and the recorded demo stays a static export](../../docs/decisions/ADR-040-the-live-mode-on-the-origin-of-the-backend.md),
[ADR-042, the site of the demo serves the artifacts the repository publishes](../../docs/decisions/ADR-042-the-site-of-the-demo-serves-the-published-artifacts.md),
[ADR-073, the published bundle carries the evidence its verdict was computed on](../../docs/decisions/ADR-073-the-published-bundle-carries-the-evidence-its-verdict-was-computed-on-and-it-is-reproducible.md),
[ADR-075, the site publishes two catalogs](../../docs/decisions/ADR-075-the-site-publishes-two-catalogs-and-each-bundle-declares-the-one-it-belongs-to.md),
[ADR-076, the answer of the run is published whole](../../docs/decisions/ADR-076-the-answer-of-the-run-is-published-whole-because-the-claims-are-extracted-from-it.md),
[ADR-077, the published bundle is verified against the answer the run verified](../../docs/decisions/ADR-077-the-published-bundle-is-verified-against-the-answer-the-run-verified.md),
[ADR-P007, one evidence-first agent by default](../../docs/design/adrs/ADR-P007-no-multiagent-by-default.md),
[ADR-P009, the privacy scope of the public project](../../docs/design/adrs/ADR-P009-privacy-scope.md) and
[the release train, the R22 contract](../../docs/design/roadmap/RELEASE-TRAIN-2027-2030.md). User description: "The
repository publishes two catalogs of recorded scenarios with their digests, their commit and their provenance. A
reader can check a number in this repository. A reader cannot carry the check anywhere else, because there is no
artifact that says, in one place, what was done, which commit did it, what evidence it rests on and how to redo
it. This specification builds that artifact and publishes it."

## What exists today and what the package proposes

The package proposes a composed artifact, a route that serves it, a verified badge and a set of acceptance
scenarios about redaction and about missing evidence. It is a design note of the frozen import and none of it
exists.

What the repository has is the substance of the artifact and none of the composition.

| What the package names | What the repository has | What is missing |
|---|---|---|
| compose sanitized evidence from an immutable run | the bundle of `ledgerlens/replay/bundle.py` with its manifest, its digests, its commit, its snapshot digest and its provenance, and the export of `ledgerlens/replay/site_export.py` that publishes it to `site/replay/` and to `site/replay-real/` | the composition of a bundle, a report and a recipe into one artifact |
| the `portfolio-proof` schema v3 and the route `GET /proof/{id}` | the schema of the package at `docs/design/contracts/schemas/v3-portfolio-proof.schema.json` with its example, and a static site under `apps/web/` with the routes `/replay` and `/replay-real` | the artifact, the route and the validation of the artifact against the schema |
| the artifact is marked incomplete when the experiment hash is missing | the check of the export, `scripts/export_replay_site.py --check`, and the check of the digests, `scripts/verify_replay_digests.py` | the status of the artifact, `draft` or `verified`, and the rule that decides it |
| a secret-like string in the trace blocks the export | the redaction of the trace in `ledgerlens/observability/callbacks.py`, applied at the boundary before the file is written | a scan of the finished artifact, because the artifact carries prose and a report that the trace does not |
| the benchmark numbers come from the actual report | the reports of the evaluation under `data/eval/`, the report of the measurement of the held out set and the manifest of the datasets | the rule that a number of an artifact is read from a report and never written by hand |
| an accessible image or a video with a text transcript | the accessibility rules of `apps/web/` and the end to end checks of `apps/web/tests/e2e/a11y.spec.ts` | the artifact that would carry the media and the transcript |

Four adaptations the port makes, because the repository had already decided the neighbouring question.

1. **The artifact is a static export and not a runtime route.** The package proposes `GET /proof/{id}` with
   unguessable public identifiers and an access scope that has to be enforced for a private case. The repository
   publishes a static site under ADR-042 and ADR-040, and the published artifacts are files. So the artifact is
   built by the same export path that builds the two catalogs, it is published under `site/proof/`, and the route
   of the site is `/proof`. The identifier of an artifact is the digest of the bundle it was made from, which is
   unguessable by construction. The access scope is enforced where the artifact is built rather than where it is
   served: a private case never becomes an artifact, so there is no artifact whose access has to be checked at the
   moment of the request.
2. **The artifact attests to a claim about the repository and never about a person.** The package says that there
   must be no ability to forge employer proof. The repository does not issue proof of employment and does not
   publish anything about a person, an employer or a hiring decision. The artifact states a technical claim about
   the code of the repository, and the claim carries its evidence, its commit and its digests. A reader who wants
   to know what an engineer did reads the artifact and the code, not a badge.
3. **The provenance and the digest discipline of the published catalogs is the discipline of the artifact.** The
   artifact names the commit it was produced from, it carries the digest of every file of the bundle, the digest of
   the ledger snapshot, the digest of the dataset and the catalog the bundle belongs to, and it says that the
   bundle is re-verified offline by the deterministic verifier of the repository with no model and no network.
   That re-verification is the one of ADR-073 and ADR-077, and it is what earns the status of `verified`. An
   artifact whose evidence is missing is `draft` and it carries no verified badge.
4. **Nothing private is exported.** The private input of a visitor lives in the session and in the vault of the
   session, and ADR-036 says what the zeroization of the key does and does not achieve. The export of a proof reads
   the published catalogs and never a session, a key or a prompt of a visitor. The artifact of a case that a
   visitor made with their own key does not exist, because such a run is not published.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Open a proof and find everything needed to redo it (Priority: P1)

A reviewer opens the artifact of a scenario. The artifact names the commit of the code that produced it, the digest
of every file of the bundle, the digest of the ledger snapshot, the digest of the dataset and the catalog the
bundle belongs to. The reviewer copies the commit, checks out the repository and runs the verifier over the
published evidence, and the verdict they get is the verdict the artifact publishes.

**Why this priority**: the whole promise of the artifact is that a reader can check it without trusting anybody.
An artifact that names a claim without the commit and the digests is a claim.

**Independent test**: build the artifact of a scenario of `data/eval/replay/`, assert that it carries the commit,
the digest of every file of the bundle, the digest of the snapshot, the digest of the dataset and the catalog, and
assert that the offline re-verification of the published evidence gives the same verdict the artifact publishes.

### User Story 2 - Read a proof that is a draft when the evidence is missing (Priority: P1)

A reviewer opens an artifact whose bundle does not carry the digest of the dataset. The artifact is marked `draft`,
it says which evidence is missing, and it carries no verified badge. The export refuses to publish it as verified.

**Why this priority**: a badge that a missing digest does not remove is a badge that means nothing.

**Independent test**: build an artifact from a bundle with the digest of the dataset removed and expect the status
`draft`, the name of the missing evidence and the absence of the verified badge.

### User Story 3 - Find the export blocked by a secret-like string (Priority: P1)

The maintainer exports a proof whose report carries a string that looks like a key. The export refuses, names the
file and the reason, and writes nothing. A secret never reaches a published artifact.

**Why this priority**: the artifacts are public and permanent. A key in one of them is a key in the history of the
repository.

**Independent test**: build an artifact over a report that carries a string that looks like a key and expect the
export to refuse with the name of the file, and expect that the output directory holds no file.

### User Story 4 - Read numbers that come from a report (Priority: P1)

The reviewer reads the artifact of a scenario and every number in it is the number of a report on the disk, with the
path of the report and the digest of the report next to it. No number of the artifact was typed by a person.

**Why this priority**: the rule of the repository is that a published number is a measurement. A number that was
typed into an artifact is a claim, and it drifts from the report the day the report is regenerated.

**Independent test**: build an artifact and assert that every number of the artifact is present in the report that
the artifact names, with the digest of that report, and assert that the build fails when a number of the artifact
is not in the report.

### User Story 5 - Read the artifact without the media (Priority: P2)

The reviewer uses a screen reader and reads the artifact of a scenario that carries an image. The image is
optional and the artifact carries a text transcript of it, and the review reaches the same conclusion with and
without the picture.

**Why this priority**: the repository treats accessibility as a gate, and an artifact that only a sighted reader
can read is an artifact that a part of the audience cannot check.

**Independent test**: build the artifact of a scenario that carries media and assert that it carries a text
transcript, and expect the end to end accessibility check of `apps/web/tests/e2e/a11y.spec.ts` to pass over the
page of the proof.

### User Story 6 - Not find anything of a visitor in an artifact (Priority: P1)

The reviewer looks for the private input of a visitor in every published artifact and finds none. There is no key,
no prompt of a visitor, no private case and no path of the machine of a visitor.

**Why this priority**: ADR-P009 and ADR-036 are safety invariants, and an artifact that leaks one of them
compromises the live mode for every visitor.

**Independent test**: export every artifact of the two catalogs and assert that no artifact carries a key, a
session id or a path of a machine, and assert that the scan of the artifact refuses an artifact that carries one.

### Edge Cases

- A bundle of the catalog of a real model: the artifact says that the recording is not reproducible byte for byte,
  and the digests are the digests of that run.
- A bundle whose re-verification offline fails: the artifact is `draft` and says that the verification failed.
- A scenario with no report: the artifact carries no number at all and is `draft`.
- An artifact whose media is too big for the budget of the site: the media is dropped and the text transcript stays.
- Two artifacts of the same scenario from two commits: they have different identifiers and both are published, each
  with its own commit.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The artifact carries the provenance of the run: the commit of the code, the digest of every file of
  the bundle, the digest of the ledger snapshot, the digest of the dataset, the catalog the bundle belongs to, the
  model profiles when the run used more than one model and the capture kind.
  - Test: `tests/proof/test_provenance.py` expects every field of the provenance for a bundle of each catalog and
    expects the digest of every file to be the digest of the file on the disk.
- **FR-002**: The artifact carries the evidence of the claims it publishes, and the verdict of every claim. The
  artifact is re-verified offline by the deterministic verifier of the repository, with no model and no network.
  - Test: `tests/proof/test_offline_reverification.py` expects the verdict the artifact publishes to be the verdict
    the deterministic verifier gives for the published evidence of the bundle.
- **FR-003**: The status of an artifact is `draft` or `verified`. It is `verified` only when the bundle carries the
  digest of the dataset, the commit, the digests of every file and the offline re-verification passes. A `draft`
  artifact carries no verified badge and names the evidence that is missing.
  - Test: `tests/proof/test_status.py` expects `draft` and the name of the missing evidence for a bundle with the
    digest of the dataset removed, and expects `verified` for a complete bundle.
- **FR-004**: The identifier of an artifact is the digest of the bundle it was made from, and two artifacts of two
  commits have two identifiers.
  - Test: `tests/proof/test_identifier.py` expects the identifier to be the digest of the bundle and expects two
    identifiers for two commits.
- **FR-005**: The artifact is validated against the schema of the package,
    `docs/design/contracts/schemas/v3-portfolio-proof.schema.json`, and a build that does not satisfy it is refused.
  - Test: `tests/proof/test_schema.py` expects the validation of the artifact against the schema of the package, and
    expects the refusal of an artifact that breaks it.
- **FR-006**: The export refuses an artifact whose content carries a string that looks like a secret, and it writes
  nothing when it refuses.
  - Test: `tests/proof/test_redaction.py` expects the refusal with the name of the file and an output directory
    that holds no file, using the redaction of `ledgerlens/observability/callbacks.py`.
- **FR-007**: Every number of an artifact is read from a report on the disk, with the path of the report and the
  digest of the report next to it, and a number that is not in the report fails the build.
  - Test: `tests/proof/test_numbers_come_from_a_report.py` expects every number of the artifact to be in the report
    that it names, and expects the failure of the build when it is not.
- **FR-008**: The export reads the published catalogs and never a session, a key or a prompt of a visitor. The
  artifact carries no key, no session id and no path of a machine.
  - Test: `tests/proof/test_no_visitor_data.py` exports every artifact of the two catalogs and expects no key, no
    session id and no path of a machine in any of them.
- **FR-009**: The artifact carries a text transcript of every media it carries, and the media is optional. An
  artifact that would exceed the budget of the site drops the media and keeps the transcript.
  - Test: `tests/proof/test_accessibility.py` expects the transcript of every media and expects that an artifact over
    the budget keeps the transcript and drops the media.
- **FR-010**: The artifact states a claim about the code of the repository and never about a person, an employer
  or a hiring decision. No sentence of the artifact says what an employer should do.
  - Test: `tests/proof/test_claim_scope.py` reads the artifact and expects that it names the code, the commit and
    the digests, and expects no sentence about an employer or a hiring decision.
- **FR-011**: The artifact names the recipe that reproduces it, the command and the version of the code, and the
  links it carries point at paths of the commit it names.
  - Test: `tests/proof/test_links.py` expects every link of the artifact to resolve inside the commit that the
    artifact names, and expects the recipe to carry the command.
- **FR-012**: The export of the proofs is published under `site/proof/`, it is checked by the same discipline as
    the two catalogs, and a change of a published proof without a change of its bundle fails the gate.
  - Test: `tests/proof/test_published_proof.py` expects the export to match the bundle and expects the check to
    fail when a published proof does not match.
- **FR-013**: The export of the proofs never writes into `data/eval/replay/` and never into `data/eval/replay-real/`,
  and the export of the two catalogs keeps passing its check.
  - Test: `tests/proof/test_not_a_replay_bundle.py` expects the two catalogs to be untouched and the export of the
    site to pass `uv run python scripts/export_replay_site.py --check`.

### Key Entities

- **Proof artifact**: the composed document that carries a claim about the code of the repository, the evidence of
  the claim, its provenance, the recipe that reproduces it and the links to the commit it names.
- **Provenance of the artifact**: the commit, the digests of the files of the bundle, the digest of the snapshot,
  the digest of the dataset, the catalog, the capture kind and the model profiles.
- **Status of the artifact**: `draft` or `verified`. A `draft` artifact names the evidence that is missing.
- **Recipe**: the command that reproduces the run and the version of the code it used.
- **Transcript**: the text alternative of a media of the artifact.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The artifact carries the commit, the digest of every file of the bundle, the digest of the snapshot,
  the digest of the dataset and the catalog.
- **SC-002**: The offline re-verification of the published evidence gives the verdict the artifact publishes.
- **SC-003**: An artifact with a missing digest is `draft`, names the missing evidence and carries no verified
  badge.
- **SC-004**: The identifier of an artifact is the digest of the bundle, and two commits have two identifiers.
- **SC-005**: The artifact satisfies the schema of the package, and a build that breaks it is refused.
- **SC-006**: An export whose content carries a string that looks like a secret is refused and writes nothing.
- **SC-007**: Every number of the artifact is in the report that the artifact names, with the digest of the report.
- **SC-008**: No artifact carries a key, a session id or a path of a machine.
- **SC-009**: Every media of an artifact carries a transcript, and the transcript survives the budget of the site.
- **SC-010**: No sentence of the artifact is about an employer or a hiring decision.
- **SC-011**: Every link of the artifact resolves inside the commit that the artifact names.
- **SC-012**: The export of the proofs is published under `site/proof/` and the check of the gate refuses a
  published proof that does not match its bundle.
- **SC-013**: The two published catalogs are untouched by the export of the proofs and their own check still
  passes.
- **SC-014**: The whole suite runs offline with `LEDGERLENS_OFFLINE=1`, with no key and no network.

## Assumptions

- The artifact is published by the same export path as the two catalogs, under `site/proof/`, and the site serves
  it at `/proof`. The package proposes a runtime route and the repository publishes a static site.
- The content of an artifact comes from the published catalogs and from the reports of the evaluation. It is never
  typed by a person.
- The re-verification of a published bundle is the one of ADR-073 and ADR-077: the deterministic verifier of the
  repository rebuilds the result of the run out of the published events and hands it to the verifier, offline.
- The private input of a visitor never reaches an artifact, because a run of a visitor is not published.
- The artifact is a public document and it is permanent. The redaction is the last wall before the file is written.
- Nothing in this specification is built yet.

## Out of scope

- The proof of a person, of an employer or of a hiring decision. The repository issues no such thing.
- The publication of the answer key of the held out set, in any form, including a hash.
- The video and the image of a real product, or a recording that would carry the private input of a visitor.
- The change of the two catalogs and of their export. The proof reads them and never writes into them.
- The analytics of the visits to the proof. The package mentions the completion of a visitor, and the privacy
  scope of ADR-P009 says that the visits are not tracked by default.

## Design documents

- [R22-01, portable proof of work artifact export](../../docs/design/advanced-specs/R22-01-portable-proof-of-work-artifact-export.md)
- [ADR-013, the public trace is a versioned contract](../../docs/decisions/ADR-013-public-trace-as-a-versioned-contract.md)
- [ADR-014, the replay bundle has a manifest and a hash](../../docs/decisions/ADR-014-replay-bundle-with-manifest-and-hash.md)
- [ADR-017, the bundle declares its commit and the export publishes artifacts the interface accepts](../../docs/decisions/ADR-017-export-contract-and-provenance.md)
- [ADR-036, the limitation of the zeroization of the key of a visitor](../../docs/decisions/ADR-036-the-limitation-of-the-zeroization.md)
- [ADR-040, the live mode lives on the origin of the backend and the recorded demo stays a static export](../../docs/decisions/ADR-040-the-live-mode-on-the-origin-of-the-backend.md)
- [ADR-042, the site of the demo serves the artifacts the repository publishes](../../docs/decisions/ADR-042-the-site-of-the-demo-serves-the-published-artifacts.md)
- [ADR-073, the published bundle carries the evidence its verdict was computed on](../../docs/decisions/ADR-073-the-published-bundle-carries-the-evidence-its-verdict-was-computed-on-and-it-is-reproducible.md)
- [ADR-075, the site publishes two catalogs](../../docs/decisions/ADR-075-the-site-publishes-two-catalogs-and-each-bundle-declares-the-one-it-belongs-to.md)
- [ADR-076, the answer of the run is published whole](../../docs/decisions/ADR-076-the-answer-of-the-run-is-published-whole-because-the-claims-are-extracted-from-it.md)
- [ADR-077, the published bundle is verified against the answer the run verified](../../docs/decisions/ADR-077-the-published-bundle-is-verified-against-the-answer-the-run-verified.md)
- [ADR-P007, one evidence-first agent by default](../../docs/design/adrs/ADR-P007-no-multiagent-by-default.md)
- [ADR-P009, the privacy scope of the public project](../../docs/design/adrs/ADR-P009-privacy-scope.md)
- [the schema of the proof artifact in the package](../../docs/design/contracts/schemas/v3-portfolio-proof.schema.json)
  and [its example](../../docs/design/contracts/examples/v3-portfolio-proof.json)
- [the release train, the R22 contract](../../docs/design/roadmap/RELEASE-TRAIN-2027-2030.md)
- [the implementation plan of this specification](plan.md) and [its tasks](tasks.md)

## Status

Nothing in this specification is built. The repository holds the bundles, the two catalogs, the export that
publishes them, the check of the digests, the redaction of the trace and the accessibility gate, and it holds none
of the proof artifact, of its status, of the export that publishes it and of the route of the site.

The decision this specification needs is written down before the first task: the proof artifact carries the
provenance and the digest discipline of the published catalogs, it is a static export and not a runtime route, and
it attests to a claim about the code and never about a person. That record is the next free number of
`docs/decisions/` (ADR-083 at the time of writing; check
[the index of the decisions](../../docs/decisions/README.md) before creating the file). It does not change any
accepted record.
