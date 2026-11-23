---
type: adr
status: accepted
date: 2026-11-24
---

# ADR-070: The script that writes the pin reads the commit of the weights from the file it writes

Status: accepted. Date: 2026-11-24.

## Context

ADR-067 decided that the loader of the model asks for the commit of the weights that the calibration recorded, and
that it reads that commit from `ledgerlens/verify/thresholds.json` at run time instead of holding a second copy of it.
The loader was changed. The script that writes the pin was not: `scripts/pin_calibration.py` held the commit of the
weights in a constant of its own, `NLI_REVISION`, and wrote that constant into the file.

Two copies of a value drift, and this copy drifted in the quiet way. The file of the thresholds records the commit
that the calibration was measured with, and the loader asks for that commit, so the file is the source of the truth.
The constant of the script was the value the script wrote, so every run of the script made the file agree with the
constant, and the reader of the file could not tell whether the file or the constant was the original. A pin written
with a stale constant would have left the loader asking for the weights of one day while the file claimed the
calibration of the weights of another, and the number of that day would not have been a number that another day could
reproduce.

The review of this branch also found that the value of the constant was never checked by anything: the pin of the
calibration was tested against the manifest of the disk and against the datasets of the tuning, and the commit of the
weights was only tested for being there.

## Decision

**The script that writes the pin takes the commit of the weights from the file of the thresholds, or from an argument
the caller gives, and refuses to write anything when neither is known.**

The file of the thresholds is the single source: the script reads the commit that the file already records, writes it
back unchanged, and never holds a copy of its own. The argument `--nli-revision` is how the coordinator pins a
calibration that was measured over another commit, without a second copy of the value appearing in the script. When
the file records no commit and the argument is not given, the script says so and writes nothing: a commit that nobody
gave is not a value the script may invent, and a pin written with an invented commit would claim a calibration over
weights that were never used.

## Alternatives considered

- **To keep the constant and to check it against the file.** Refused. A check that fails is a script that has to be
  run before every commit, and a check that is not run is the drift that this record exists to close. One source and
  no second copy cannot drift.
- **To write the commit of the weights by hand, as the rest of the file of the thresholds is written.** Refused. The
  pin is written by a script, and a script that writes half of the file and leaves the other half to a human is a
  file whose two halves disagree without anybody noticing.
- **To let the script write a commit that it makes up when the file has none.** Refused. A commit that nobody gave
  names weights that were never used, and the file would claim a calibration over them.

## Consequences

- **The file of the thresholds is the only place where the commit of the weights lives**, and the loader and the
  script that writes the pin read it from there.
- **A pin that names a commit nobody gave is not written**, and the script says why.
- **The pin of the calibration follows the manifest of the disk**, and a manifest that moves makes the pin that has
  to move with it, exactly as before.
- **The pin of the weights is checked by a test**: the script writes the commit that the file records, it refuses
  when the file records none, and it writes the commit that the argument gives.

## Links

- [ADR-007, the verification with the NLI model](../ADR-007-nli-verification.md)
- [ADR-067, the measurement of the held out set is published without its answer key](ADR-067-the-measurement-of-the-held-out-set-is-published-without-its-answer-key.md)
- [the script of the pin](../../scripts/pin_calibration.py)
- [the file of the thresholds](../../ledgerlens/verify/thresholds.json)
