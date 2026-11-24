# Portable proof of work

The repository publishes two catalogs of recorded scenarios, and every bundle names the commit it was produced
from, carries the digest of every file, and is re-verified offline by the deterministic verifier with no model
and no network. The proof of work composes that check into a single artifact that a reader can carry anywhere:
what was done, which commit did it, what evidence it rests on and how to redo it. The decision is recorded in
[ADR-097](decisions/ADR-097-the-proof-of-work-carries-the-provenance-and-the-digest-discipline-of-the-catalogs.md).

An artifact is a claim about the code of the repository, and it says nothing about a person, an employer or a
hiring decision. The repository does not issue proof of employment and publishes nothing about a person.

## The sections of the artifact and where each one comes from

| Section | Where it comes from | What it may not do |
|---|---|---|
| the claim | the name of the scenario and the question of the bundle | state a result that no claim of the run carries |
| the evidence | the events of the bundle and the evidence of the claims | cut the fields of a record, under ADR-073 |
| the verdicts | the verdicts of the deterministic verifier, re-verified offline | carry a verdict of the NLI model as if the code had given it |
| the provenance | the manifest of the bundle and the index of the catalog | drop the digest of the dataset or the commit |
| the numbers | the reports under `data/eval/` | carry a number that is not in the report it names |
| the recipe | the command of the capture and the commit | name a command that does not reproduce the run |
| the links | the paths of the commit that the artifact names | point at a path of another commit |
| the transcript | the text of every media | be dropped when the media is dropped for the budget |

The artifact validates against the schema of the package,
`docs/v3/contracts/schemas/v3-portfolio-proof.schema.json`, which is frozen and is read, never edited. The
schema pins the source commit to sixty four hexadecimal characters, so the artifact carries the sha256 of the
git commit of the bundle, and the page of the proof names the commit itself.

## The rule of the status

The status of the artifact is `draft` or `verified`. It is `verified` only when the digest of the dataset is
there, the commit is there, the digest of every file matches the disk and the offline re-verification passes.
A missing evidence makes a `draft` that names what is missing and carries no verified badge, because a badge
that a missing digest does not remove means nothing. No person promotes an artifact by hand.

## The identifier of the artifact

The identifier of the artifact is the digest of the bundle it was built from. The identifier is unguessable by
construction, and no private artifact exists: every artifact is built from a published bundle of the two
catalogs, and a run of a visitor is not published and therefore has no artifact.

## The numbers come from a report

Every number of the artifact is read from the report it names, with the path and the digest of the report
written next to it. A number that is not in the report fails the build, because a number typed by a person is
a claim and not a measurement.

## The redaction and the privacy of the export

The trace is redacted when it is written, and the finished artifact is scanned again with the `redact` of
`ledgerlens/observability/callbacks.py`, because the artifact carries prose and a report that the trace does
not carry. An export whose content carries a secret like string is refused with the name of the file, and
nothing is written. No artifact carries a key, a session id or a path of a machine.

## The accessibility of the artifact

Every media of the artifact carries a transcript, and the transcript survives the budget of the site: an
artifact over the budget keeps the transcript and drops the media, because the media is optional and the text
is not. The page of the proof is scanned by the accessibility suite of the site like every other page.

## The export and the gate

The artifacts are published under `site/proof/`, one JSON per artifact with the projection of the schema, and
the index of the catalog for the page. The export lives in `scripts/export_proof_site.py`, next to
`scripts/export_replay_site.py`, and the gate of the repository runs its `--check` mode: a published proof
that does not match its bundle fails the gate. The two catalogs are read and never written, and the export of
the replay site still passes its own check.

The page of the proof lives under `apps/web/app/(public)/proof/`: the catalog of the artifacts, and the page
of every artifact with the provenance, the claim, the evidence, the verdicts, the recipe and the links.
