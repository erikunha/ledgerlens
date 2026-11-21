---
type: adr
status: accepted
date: 2026-11-14
---

# ADR-017: The bundle declares its commit and the export publishes artifacts the interface accepts

Status: accepted. Date: 2026-11-14.

## Context

The R1 release publishes a recorded investigation as static artifacts that anybody can read without a key and
without a server. The export that produces them was written but never reviewed, and the review found that the
artifacts did not carry the promises the R1 specification asks for.

The specification of the feature requires two things that the artifacts did not have. FR-009 requires the
provenance to show the captured mode, the capture timestamp, the model profile, the code commit hash, the
snapshot hash, the prompt hash, the policy version and the digest of the bundle files, each one only when the
bundle declares it. FR-045 requires every artifact to be validated against a published schema before it is
rendered. The bundle contract of the design package requires a `code_sha`, and the manifest of the core has no
place to put one.

The shapes themselves were also wrong. The export wrote a `manifest.json` with a `schema_version` field, while the
manifest of the core and the transcription of the interface use `bundle_schema_version`. The catalog wrote a
`scenario` field and a `data_origin` object, while the interface reads an `id` and a `data_origin` string. The
provenance used names of its own, which the interface does not read.

The acceptance list of the cycle asks for a provenance that says, for each artifact, which commit and which
bundle produced it, and for an export that is deterministic: the same bundle always produces the same bytes.

## Decision

**The bundle declares its own provenance.** The manifest of the core gains the optional fields of the contract:
`capture_kind`, `recorded_at`, `model_profile`, `code_sha`, `prompt_hash`, `policy_version` and
`redaction_version`. The capture script fills the ones it can state honestly: the capture kind
`scripted_fixture`, the moment of the capture, the model profile `scripted-fixture`, the policy version and the
code commit. A field that cannot be computed stays absent, because FR-009 asks for a field only when the bundle
declares it.

**The commit comes from the capture, not from the export.** `code_sha` is the commit of the repository state the
capture ran from, and the capture refuses to run on a dirty tree, so the claim it writes is true. The export
never reads the state of the repository. This is what keeps the export a pure function: the same bundle always
produces the same bytes, and the published artifacts stay valid across commits, so the check in the continuous
integration keeps passing without regenerating anything.

**The artifacts follow the shape the interface already reads.** The exported `manifest.json` is the manifest of
the core: `bundle_schema_version`, `run_id`, `mode`, `scenario`, `events`, `files`, `snapshot_sha256`,
`created_at` and `note`, plus the provenance fields the bundle declares. The exported `provenance.json` carries
the fields the interface reads for the provenance panel (`mode`, `capture_kind`, `recorded_at`,
`model_profile`, `code_sha`, `snapshot_sha256`, `policy_version`, `files`, `created_at`, `note`) and the
export level extras under names of their own (`bundle_digest`, `artifacts`, `dataset_sha256`). The exported
`index.json` holds one card per scenario with `id`, `name`, `question`, `concepts`, `data_origin` as a string,
`status`, `capture_kind` and `bundle_path`, plus the export level extras of the card (`data_origin_detail`,
`bundle_digest`, `provenance_sha256` and `code_sha`). The shapes come from the versioned contracts of the
design package and from the entity of the specification; the interface transcribes them.

**The digests form a chain, and the chain is what covers the artifacts.** Each artifact is covered by the digest
that the next one carries: the provenance cites the digest of the events and of the manifest, and the card of the
catalog cites the digest of the provenance and the digest of the bundle. A file cannot carry its own digest, and
the catalog cannot carry the digest of itself, so the last link of the chain is the check of the export, which
compares the catalog on the disk with the catalog the bundle produces, byte for byte.

**The artifacts are published in the repository.** They live in `site/replay/`, one folder per scenario plus the
catalog at the root. The default output of the export script is that folder, and the gate runs the check of the
export, so the published artifacts can never drift away from the bundle they claim to show. The frontend tree
stays untouched: it is paused, and the artifacts it will read are generated into it when it opens.

**The export refuses what it cannot prove.** Every recorded line is validated against the versioned trace event
schema, the moment of the event is checked against the ISO 8601 shape the interface expects, and a bundle that
does not hold up is refused before anything is written. A bundle whose scenario is not in the shape of the
contract is refused too, so the exported manifest is never one the interface would reject. The write also removes
the files of the scenarios that left the set, so what is published is exactly what was exported, and a dotfile is
exempt from both the write and the check, because the desktop writes Finder metadata into folders and that is not
content of the export.

## Alternatives considered

- **The export reads the commit of the repository at the moment of the export.** The bundle would not have to
  change, but the bytes of the artifacts would change with every commit, the check in the continuous integration
  would only pass right after an export, and the export would depend on a state it does not receive as an
  argument.
- **The commit arrives as an argument of the export.** The export would stay pure, but every caller would have to
  know the commit and would have to keep it in step with the bundle. The commit belongs to the recording.
- **The artifacts stay out of the repository.** The export would still work, but the check would have nothing to
  compare against in the continuous integration, and the first public vertical slice would not exist in the
  public repository.
- **A new JSON Schema for the shapes of the export.** The design package is imported verbatim and the import
  check compares it with the package, so a contract that was decided after the import cannot live there. The
  shapes follow the contracts that already exist.

## Consequences

- The provenance of a published artifact names the commit that produced the recording, the bundle it came from,
  the digest of every bundle file and the digest of the artifacts it describes, and nothing is invented.
- The canonical bundle is captured again, so its digest changes and its snapshot hash stays the same, because the
  ledger the run reads is deterministic. The numbers frozen in the handoff are regenerated in the same commit, as
  the handoff itself requires.
- The capture refuses to run on a dirty tracked tree. The capture code has to be committed before the recording,
  because the recording names the commit it was made from. The untracked material of the repository, such as the
  paused frontend and the local handoff, does not block the capture.
- The published artifacts are part of the repository and are covered by the gate, and the continuous integration
  runs the gate on the branch of the cycle.
- A bundle that declares no commit yields a provenance without a commit, and the interface shows that field as
  unavailable, exactly as FR-009 asks.
