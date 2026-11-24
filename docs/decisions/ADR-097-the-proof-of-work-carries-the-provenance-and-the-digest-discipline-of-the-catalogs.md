---
type: adr
status: accepted
date: 2026-11-24
---

# ADR-097: The proof of work carries the provenance and the digest discipline of the catalogs

Status: accepted. Date: 2026-11-24.

## Context

The design package
[LL-V3-R22-01, portable proof of work artifact export](../v3/advanced-specs/R22-01-portable-proof-of-work-artifact-export.md)
proposes a single artifact that says what was done, which commit did it, what evidence it rests on and how to
redo it. The repository publishes two catalogs of recorded scenarios, and every bundle names the commit it was
produced from, carries the digest of every file, and is re-verified offline by the deterministic verifier with
no model and no network. What a reader cannot do is carry that check anywhere.

The milestone of [specs/022](../../specs/022-r22-portable-proof-of-work-export/spec.md) composes that artifact
and publishes it, with the discipline of the two catalogs and not less. The package proposes a runtime route
with unguessable identifiers and an access scope to enforce; the repository publishes a static site, so the
decision has to say where the artifact lives and what its status means.

## Decision

**The artifact is a static export under `site/proof/`, its identifier is the digest of the bundle, the status
is `draft` until the digest of the dataset, the commit, the digests of the files and the offline re-verification
are all there, the numbers come from the reports of the repository, the redaction is the last wall before the
file is written, and the artifact says nothing about a person, an employer or a hiring decision.**

1. **The artifact is a static export under `site/proof/`, and not a runtime route.** The site is a static
   export, so the artifact is a file built by the same export path as the catalogs, and the access scope of the
   package moves to the moment of the build: a private case never becomes an artifact, so there is no artifact
   whose access has to be checked when it is served.
2. **The identifier of the artifact is the digest of the bundle.** The identifier is unguessable by
   construction, because the digest of the bundle is, and no private artifact exists: every artifact is built
   from a published bundle of the two catalogs.
3. **The status is `draft` until the evidence is all there.** The status is `verified` only when the digest of
   the dataset is there, the commit is there, the digest of every file matches the disk and the offline
   re-verification passes. A missing evidence makes a `draft` that names what is missing and carries no
   verified badge, because a badge that a missing digest does not remove means nothing. No person promotes an
   artifact by hand.
4. **The numbers come from the reports of the repository.** The build reads the report, takes the number and
   writes the path and the digest of the report next to it, and a number that is not in the report fails the
   build. A number typed by a person is a claim and not a measurement.
5. **The redaction is the last wall before the file is written.** The trace is redacted when it is written,
   and the finished artifact is scanned again with the `redact` of `ledgerlens/observability/callbacks.py`,
   because the artifact carries prose and a report that the trace does not carry. An export whose content
   carries a secret like string is refused, and nothing is written.
6. **The artifact says nothing about a person, an employer or a hiring decision.** The artifact is a claim
   about the code of the repository: it names the code, the commit and the digests, and it attests to a claim
   about the code and never about a person. The repository does not issue proof of employment and publishes
   nothing about a person.

## Alternatives considered

- **To serve the artifact from a runtime route with an access scope.** Refused. The site is a static export,
  and a runtime route would be a second way to serve the same bytes, with a second discipline to keep. The
  access scope moves to the moment of the build, and a private case never becomes an artifact.
- **To let a person mark an artifact as verified.** Refused. The status is decided by the presence of the
  evidence and by the offline re-verification, and nothing else, because a badge that a person can grant is a
  badge that means nothing.
- **To carry a number that a person typed into the artifact.** Refused. Every number of the artifact is read
  from the report it names, with the path and the digest of the report, and a number that is not in the report
  fails the build.
- **To publish proof of a person or of an employer.** Refused. The artifact states a technical claim about the
  code, and a reader who wants to know what an engineer did reads the artifact and the code.

## Consequences

- **The repository has the composition of the proof of work**, in `ledgerlens/proof/`: the provenance
  (`provenance.py`), the offline re-verification (`verification.py`), the status (`status.py`), the numbers
  (`numbers.py`), the composition (`artifact.py`), the redaction (`redact.py`), the media (`media.py`) and the
  export (`export.py`), with the tests in `tests/proof/`.
- **The export lives in `scripts/export_proof_site.py`**, next to `scripts/export_replay_site.py`, with the
  same discipline: it writes nothing in the check mode, and the gate refuses a published proof that does not
  match its bundle.
- **The page of the proof lives under `apps/web/app/(public)/proof/`**, with the provenance, the claim, the
  evidence, the verdicts, the recipe and the links, and with the badge only when the status is `verified`.
- **The two catalogs are read and never written**, and the export of the proofs writes only under
  `site/proof/`.
- **The page of the proof of work is [the page of the proof](../proof.md)**, with the sections of the artifact
  and the rule of the status.

## Links

- [ADR-073, the published bundle carries the evidence its verdict was computed on](ADR-073-the-published-bundle-carries-the-evidence-its-verdict-was-computed-on-and-it-is-reproducible.md)
- [ADR-075, the site publishes two catalogs](ADR-075-the-site-publishes-two-catalogs-and-each-bundle-declares-the-one-it-belongs-to.md)
- [the page of the proof](../proof.md)
- [the specification of the milestone](../../specs/022-r22-portable-proof-of-work-export/spec.md)
- [the design package](../v3/advanced-specs/R22-01-portable-proof-of-work-artifact-export.md)
