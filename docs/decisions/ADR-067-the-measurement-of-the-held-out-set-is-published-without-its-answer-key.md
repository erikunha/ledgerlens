---
type: adr
status: accepted
date: 2026-11-23
---

# ADR-067: The measurement of the held out set is published without its answer key

Status: accepted. Date: 2026-11-23.

## Context

The number over the held out set is 24 of the 48 cases, 0.500, and it is the only number of this repository that is
not a measurement of the fit. It is also the least checkable number the repository publishes.

The report of the measurement is `data/eval/report_heldout.md`, and the report is written by
`scripts/measure_heldout.py`. The script needs the recipes of the generator, `data/eval/heldout/recipes.jsonl`,
because the template of a case is in the recipe and not in the labelled file, and because the report says how many
cases the reading disagreed with the recipes. That file is gitignored (`.gitignore:16`), on purpose: it is the answer
key of the generator that wrote the set. The consequence is that a reader of the public repository cannot run the
measurement at all, because the script refuses to run when the labelled set and the recipes do not cover the same
cases (`scripts/measure_heldout.py:856-871`), and cannot check the 24, the confusion matrix or the table
by template.

The weights were not pinned either. The calibration of the thresholds records the model and the commit of the
weights it used, `ledgerlens/verify/thresholds.json` under `calibration.nli_model`, and `scripts/pin_calibration.py:63`
repeats the commit. The loader of `ledgerlens/verify/nli.py` asked the hub for the `main` branch of the model, so the
weights of the measurement of one day and the weights of the measurement of another day were two different sets of
weights, and the number of one day was not a number that another day could reproduce.

The obvious fix is to publish a file with the verdict of every case, so that the matrix and the 24 can be recomputed by
a reader. The obvious fix publishes the answer key. The expected label of a case is the label the generator expected,
and it is what the verifier is measured against, so a file that carries it carries the key of the set. A published key
ends the property that ADR-052, ADR-062 and ADR-065 defend: the set stays reserved so that a future change, a new
prompt or a new model can still be measured against data that no decision was taken against.

A hash of the expected label does not help. There are three labels, so a hash of the expected label of a case is
brute forceable in three tries, and a file that carries the hash of the expected label publishes the key as badly as
the key itself.

The tree already says where the protection of the set comes from, and it is not a secret. The generator is public and
deterministic, so anybody can rebuild the key (`data/eval/heldout/README.md:112-125`), and the labels of the reading
are published in the labelled file and in the table of the report. What keeps the set usable is the guard of the
tuning, the procedure of the reading and the review of this repository (ADR-059, ADR-062, ADR-065).

## Decision

**The measurement of the held out set is published as an aggregate and with the predictions of the model, and the
expected label of a case is not published and will not be published, in any form, including a hash.**

### What is published

`scripts/measure_heldout.py` writes, next to the Markdown report, the machine readable report
`data/eval/report_heldout.json`:

| what | what it is |
| --- | --- |
| the dataset | the id of the set, the path of the labelled file, the role `held_out` and the count of the cases |
| the denominator | the number of the cases that the accuracy was measured over, next to the accuracy itself |
| the confusion matrix | the counts of the reader and the verifier in the vocabulary of the Markdown report |
| the table by template | the cases of each template, the counts of the reading and the cases that were right |
| the predictions | the id of every case, the label that the model predicted and the method that decided it |
| the disagreements | the identifiers of the cases where the reading disagreed with the recipes, and their count |
| the limitations | the contamination policy of the set and the caveat of it, both read from the manifest of the datasets |
| the command | the command that produced the file and the version of the measurement |

The predictions are the output of the model and not the truth of a case. With the predictions and the matrix, a reader
checks that the predictions are consistent with the aggregate that is published, that the count of the cases is the one
the set holds, that the denominator is right and that the number did not change.

### What is not published

The expected label of a case. Never, in any form, including a hash, and the file says so in its own
`not_published` field, so that a reader of the file does not have to guess what a field that is not there means. The
label of the reading of a case is not published in the JSON either: the only label of a case that the file carries is
the label the model predicted.

The identifiers of the two cases where the reading disagreed with the recipes are published, because that count is
the noise a label of this set carries and a reader has to be able to see which cases carry it. The label of neither
of them is published.

### The sentences that limit the number come from one place

The contamination policy of the set and the caveat of it live in the manifest of the datasets,
`data/eval/datasets.json`, and both reports read them there at run time. The Markdown report and the JSON report
therefore never drift apart, and neither of them drifts from the manifest. A report that copied the sentences by hand
would drift from them on the day the manifest changed.

### The weights are pinned

The loader of `ledgerlens/verify/nli.py` asks for the commit of the weights that the calibration recorded, and it
reads the commit from `ledgerlens/verify/thresholds.json` at run time instead of holding a second copy of it. The
measurement of one day and the measurement of another day are the same measurement, and the published report names
the commit that produced it.

### The published report is reserved for the tuning

The published report carries the predictions of the model over the cases of the held out set, and a script that
tunes a threshold against the predictions is tuning against the held out set. The file is therefore reserved by the
guard of the tuning, the way the set and its sources are reserved: by its path, whatever role the manifest gives it,
and by the digest of its bytes, so that a copy of it under another name is refused as well.

The published report is written byte for byte the same by every run of the same measurement: it carries no clock and
no path of the machine that wrote it. That is what lets the digest of its bytes be reserved, the way the digest of
the set is reserved.

## Alternatives considered

- **To publish the expected label of every case, so that the 24 can be recomputed.** Refused. The expected label of
  a case is the answer key of the generator, and a published key ends the reservation of the set for every change that
  comes after. The whole purpose of the reservation is that a future prompt or a future model is measured against
  data that no decision was taken against.
- **To publish the hash of the expected label of every case.** Refused, and it is worse than it looks: there are
  three labels, so the hash is brute forceable in three tries. A hash of the expected label publishes the key.
- **To publish the label of the reading, which the labelled file already publishes.** Refused for the JSON. The label
  of the reading is the truth of the case for 46 of the 48 cases, and the file that a reader checks the aggregate
  against should carry the output of the model and nothing else. The label of the reading is where it already is, in
  the labelled file and in the table of the Markdown report.
- **To publish nothing new and to leave the number as it was.** Refused. The number stayed the least checkable number
  of the repository, and a reader who cannot check a number cannot decide whether to trust it.
- **To publish the aggregate without the predictions.** Refused. With the aggregate alone a reader can check nothing
  but the sum of the matrix; with the predictions the reader can check that the predictions are consistent with the
  matrix, that the count of the cases is the one the set holds and that the number did not change.
- **To publish the predictions and the label of the reading together, so that the matrix can be rebuilt row by
  row.** Refused, for the same reason the expected label is not published: the row of the matrix is the truth of the
  cases of the row.
- **To leave the weights on the branch of the hub.** Refused. A number measured with the weights of one day and the
  same number measured with the weights of another day are two measurements, and this repository publishes numbers.
- **To write the revision of the weights as a literal in the loader.** Refused. A literal is a second copy of a
  value that the calibration chose, and two copies drift. The loader reads the commit from the file that records it.

## Consequences

- **The number over the held out set does not change.** It stays 24 of 48, 0.500, and it is still the only number of
  the repository that is not a measurement of the fit.
- **A reader can check the aggregate and the predictions, and cannot recompute the 24 without the key.** That is the
  price of keeping the set usable, and the price is paid on purpose: a set that a reader can score case by case is a
  set that a future change was scored against.
- **The measurement of one day and the measurement of another day are the same measurement**, because the weights are
  pinned to the commit that the calibration recorded and the report names that commit.
- **The published report is refused as a tuning target**, by its path and by the digest of its bytes, so that the
  predictions of the held out set cannot become the material of a threshold.
- **The two reports of the measurement cannot drift.** The limitations come from the manifest of the datasets and the
  numbers come from the same measurement, and a test reads the two files and checks that they agree.
- **The debt of this record is the debt of ADR-059 and ADR-062.** The reading was made by machines, the repository
  cannot prove that they were blind, and the blindness of the reading is a procedure and not a secret. What this
  record adds is that the number is checkable and that the key is not published with it.

## Links

- [ADR-052, the manifest of the eval datasets](ADR-052-the-manifest-of-the-eval-datasets.md)
- [ADR-059, the held out set is read by two blind machines and adjudicated](ADR-059-the-held-out-set-is-read-by-two-blind-machines-and-adjudicated.md)
- [ADR-062, the role held out exists](ADR-062-the-role-held-out-exists-and-the-sentence-of-adr-052-is-superseded.md)
- [ADR-065, the reservation of the held out set follows the case and not only the file](ADR-065-the-reservation-of-the-held-out-set-follows-the-case-and-not-only-the-file.md)
- [the script of the measurement](../../scripts/measure_heldout.py)
- [the published report](../../data/eval/report_heldout.md) and [its machine readable form](../../data/eval/report_heldout.json)
- [the guard of the tuning](../../ledgerlens/eval/manifest.py)
