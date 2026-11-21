---
type: adr
status: accepted
date: 2026-11-11
---

# ADR-014: The replay bundle has a manifest and a hash

Status: accepted. Date: 2026-11-11.

## Context

The R1 release repeats a recorded execution without calling any model. For that there has to be a trace on disk, in the
public contract format, that anyone can read, play in a browser and check by hash.

A file of events alone does not say what it is. The same bytes could be a live run, a sandbox run or a fixture, and a
reader would have to guess from the shape. That is exactly the failure the constitution calls out: a replay read as a
live run is the worst thing this repository can do.

## Decision

The bundle is two files in a folder: `events.jsonl`, with the public events one per line in sequence order, and
`manifest.json`, which declares what the bundle is.

The manifest carries the bundle schema version, the run identifier, the mode, the scenario, the number of events, the
creation date, a note in plain words, and the sha256 of each file of the bundle.

The note is not decoration. It says the execution is deterministic, with the scripted model and the recorded exchange
rate, that it is not a live execution and that it calls no model.

The manifest is written after the events, with the hash of each file, and it is what closes the package.

`load_bundle` refuses a bundle that does not hold up. It checks that every file the manifest cites is there, that the
hash of each one matches, that the number of events in the manifest is the number in the file, that the sequence has no
gap and no repetition, and that every event carries the mode the manifest declares. It also checks the redaction again:
if the text of the file changes with the redaction, there is a key inside it and the bundle does not open. It is the
same `redact` function the trace uses, so there is a single source of pattern.

`replay` repeats the bundle into a sink. It is not an execution: the events that come out are the recorded ones, with
the mode the manifest declares.

`bundle_digest` returns the sha256 of the manifest, which is the summary of the whole bundle. It is what a reader
cites as proof that the replay is the same one as always.

The canonical bundle is the one of the S01 scenario, captured by `scripts/capture_replay.py` from the offline path of
the product: the scripted model, the recorded exchange rate, no key and no network. It is 57 events.

## Alternatives considered

- **A single file with the events and the metadata at the end.** The last line would have to be skipped by every
  reader, and a truncated file would be read as a valid one.
- **Trust the mode of the events without a manifest.** Then a bundle with mixed modes would open, and the reader would
  have to check every event to find the inconsistency.
- **Hash the whole folder as one number only.** Then the bundle could not say which file changed, and a partial change
  would be indistinguishable from a full one.
- **Check the redaction only when the bundle is written.** The bundle would still be able to be tampered with after
  the write, which is the case the check on read exists for.

## Consequences

- A reader can tell what a bundle is without guessing, from the manifest alone.
- A tampered bundle does not open, and the reason is specific: a missing file, a hash that does not match, a count
  that does not match, a gap in the sequence or a mode that is not the declared one.
- A bundle with a secret inside does not open, even when the hash was redone to match.
- The bundle hash can be published and cited.
- The mode travels with the manifest and with every event, so there is a single source for the label.
- The capture is reproducible: running the script again produces the same content except for the timestamps and the
  execution identifiers.
