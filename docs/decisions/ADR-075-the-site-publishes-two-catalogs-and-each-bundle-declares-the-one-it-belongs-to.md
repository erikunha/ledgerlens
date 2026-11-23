---
type: adr
status: accepted
date: 2026-11-24
---

# ADR-075: The site publishes two catalogs, and each bundle declares the one it belongs to

Status: accepted. Date: 2026-11-24.

## Context

The published catalog of the site holds nine recordings of the same nine scenarios, and every one of them was made
the same way: the scripted model of the repository, the recorded exchange rate, no key and no network. That is a
strong promise, because the recording is a formula and anybody can run it again and get the same bytes. It is also
a narrow promise, because the agent of those recordings is a fixture. The product that a visitor of the live mode
meets is an agent that reads the ledger, asks the reference source and writes its own answer, and no recording of
that product existed in the repository.

The contract of the design package already admitted what the repository did not: the schema of the trace event
accepts the mode `live_agent`, and the bundle contract of the package names the kind of capture
`real_model_recorded`. The code of the repository refused both. `write_bundle` refused a set of events that carry
the mode `live_agent`, `site_export` published only the mode `deterministic_sandbox`, and the browser refused a
bundle that declared a live run. The refusal had a reason: a bundle published under the label of the sandbox would
be a lie, and a lie in a manifest is worse than a missing file.

What the phase needs is not a bundle with a different label. It needs a second catalog, distinct from the first in
every part that a reader can check, and honest about the part that a reader cannot check.

## Decision

**The site publishes two catalogs, each with one mode, and each bundle declares the catalog it belongs to.**

1. **A live recording becomes a bundle only when the capture kind admits it.** The kind `real_model_recorded` is the
   only one that admits events with the mode `live_agent`, and the refusal stays for every other kind, including
   the absence of a kind. The read path applies the same rule, so a bundle assembled by hand on the disk cannot
   declare a live mode with the kind of a fixture and be opened.
2. **A catalog is one mode.** The sandbox catalog holds the recordings of the scripted model and the real catalog
   holds the recordings of a real model. The export refuses a bundle whose mode does not match its kind, and refuses
   a set of bundles that mixes two modes, because a folder with two modes has no honest name. The catalogue that
   the site serves is two folders, two indexes and two routes: `/replay` and `/replay-real`.
3. **The judge of the verdicts is the same in the two catalogs.** The verdicts of a real recording are computed by
   the deterministic verifier of the repository, the same one that computes the verdicts of the sandbox catalog. The
   reason is the verifier that ADR-073 published: it re-verifies a bundle offline, with no model and no network, so
   a bundle whose verdicts came from the model of the NLI could not be re-verified by the code of the repository.
   The real NLI and the deterministic one do not always agree: on the scenario S01 the real NLI answers
   `not_enough_evidence` for the claim of the plan of the merchant, where the deterministic one answers
   `supported`. A catalogue whose verdicts a third party cannot reproduce is a catalogue of claims. The note of the
   manifest of a real bundle says which judge computed its verdicts.
4. **The key never travels with the recording.** The name of the model, the moment of the capture and the commit of
   the code travel in the provenance of the bundle; the key stays in the file of the environment of the machine that
   made the recording, and the redaction of the trace is the last wall before the file is written.

A real recording is not reproducible the way a deterministic one is: the same question asked twice of a real model
does not give the same answer. The digests of the real catalogue are therefore the digests of that run and not the
digests of a formula, and the panel of the provenance of the site says so in words.

## Alternatives considered

- **To publish the real recording under the label of the deterministic sandbox.** Refused. The mode and the kind of
  the capture are the first thing a reader checks, and a recording labelled as a fixture is a lie with a digest
  that proves it is a lie.
- **To replace the deterministic catalogue with the real one.** Refused. The deterministic catalogue is the proof
  that the product does what it says, and it is the only one a third party can run again without a key. The two
  catalogues answer two different questions: what the product does when it is scripted, and what the product does
  when a real model answers.
- **To compute the verdicts of the real catalogue with the real NLI.** Refused, for the reason of the third point:
  the verifier that the repository publishes re-verifies offline, and a verdict that only a model can give is a
  verdict the repository cannot stand behind. The judge is named in the note of the bundle, so a reader who wants
  the other judge can run it and see the difference.
- **To keep the real recording in the repository and not publish it.** Refused. A recording nobody can see proves
  nothing to a visitor, and the phase exists to publish.
- **To put the two catalogues in one folder.** Refused. The index of a folder with two modes has no honest title,
  and the browser would have to guess which mode a card belongs to. Two folders, two indexes and two routes say it
  in the place where a reader looks.

## Consequences

- **The repository holds a second set of bundles**, in `data/eval/replay-real/`, and a second export, in
  `site/replay-real/`, with the same four files per scenario and its own index.
- **The write path of the bundle changes**: `write_bundle` accepts the mode `live_agent` when the kind says
  `real_model_recorded`, and refuses it otherwise. The refusal of the old version stays for every other kind.
- **The export and the browser change**: the export publishes two catalogs and the browser reads two roots, and the
  panel of the provenance labels the real recording as a recording of a real model and not as a live run.
- **The capture of the real catalogue needs a key and the network**, and it refuses to run offline, because an offline
  machine runs the scripted model and its recording would carry a label that is not true.
- **The nine recordings of the real catalogue are not reproducible byte for byte.** The digests of the catalogue are
  the digests of that run, and the catalogue says so.

## Links

- [ADR-042, the site of the demo serves the artifacts the repository publishes](ADR-042-the-site-of-the-demo-serves-the-published-artifacts.md)
- [ADR-043, the public site of the design package is complete](ADR-043-the-public-site-of-the-design-package-is-complete.md)
- [ADR-073, the published bundle carries the evidence its verdict was computed on and it is reproducible](ADR-073-the-published-bundle-carries-the-evidence-its-verdict-was-computed-on-and-it-is-reproducible.md)
- [ADR-074, a case ends in a decision and the decision belongs to the code](ADR-074-a-case-ends-in-a-decision-and-the-decision-belongs-to-the-code.md)
- [the bundle contract](../../ledgerlens/replay/bundle.py)
- [the export of the site](../../ledgerlens/replay/site_export.py)
- [the capture of a real recording](../../scripts/capture_live_replay.py)
