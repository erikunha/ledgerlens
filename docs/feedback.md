# Verified feedback to evaluation and training

The repository publishes two catalogs of recorded scenarios, and the catalogs hold the failures and not only
the cases the agent resolves. The verified feedback loop turns a published failure into a reviewed regression
and, where warranted, into a dataset that a specialized model could be tuned against. The decision is recorded
in [ADR-096](decisions/ADR-096-the-deterministic-verdict-is-the-gate-of-the-training-data.md).

One rule stands in front of the loop: **no output of a model becomes training data without the deterministic
verdict as its gate.** The verdict of a feedback record is the verdict of the deterministic verifier of
`ledgerlens/verify/checks.py` over the published evidence of the bundle, computed offline, with no model and
no network. The verdict of the NLI model never fills that field, and when it disagrees with the deterministic
one, the deterministic one is the one that is written down.

## The four stages of the loop

1. **The record.** A published failure becomes a feedback record (`ledgerlens/feedback/record.py`): the
   bundle, the digest of the bundle, the catalog of the bundle, the claim, the failure, the corrected value,
   the evidence and the reviewer. A corrected amount is a `Decimal`, and the comparison with the value of the
   ledger is exact.
2. **The gate.** The deterministic verifier re-verifies the bundle of the record
   (`ledgerlens/feedback/gate.py`), exactly as a published bundle is re-verified offline under ADR-073. The
   gate is the only door to the tier `gold`.
3. **The tier and the registry.** The record is tiered (`ledgerlens/feedback/tiers.py`) and registered
   (`ledgerlens/feedback/registry.py`) with its digest, its permission and its tier. The check of the registry
   reads the disk and writes nothing, and it runs in the gate of the repository.
4. **The set, the comparison and the archive.** The training set holds only the records of the tier `gold`
   whose permission is training (`ledgerlens/feedback/training_set.py`). The contamination check refuses a set
   that holds a case of another split under an alias (`ledgerlens/feedback/contamination.py`). The candidate
   is compared with the baseline once, over the holdout, and the result is written down whatever it is
   (`ledgerlens/feedback/promotion.py`). The experiment is archived with the digests of the dataset, the
   commit and the report (`ledgerlens/feedback/archive.py`).

## The three tiers of a record

| Tier | Rule |
|---|---|
| `gold` | the deterministic verdict supports the correction, and a second reader of the repository confirmed it |
| `silver` | the verdict is `contradicted` or `not_enough_evidence`, or the second reader did not confirm |
| `unverified` | the record has no published evidence |

The second reader is another person and not the same reader twice. A record whose only support is an output of
a model, whether the answer of the agent, the label of the NLI model or a correction proposed from a
suggestion of the model, stays below the tier `gold` and never enters a training set.

## The tier of a record and the split of a dataset are two axes

The tier of a record says how much the repository trusts the record, and it lives in the registry of the
records. The split of a dataset says what the dataset may be used for, and it lives in the manifest of the
datasets under ADR-052 and ADR-062: `tuning`, `validation` or `held_out`. A `gold` record may land in a
`tuning` dataset or in a `validation` dataset, and it never lands in a `held_out` dataset.

## The two catalogs are not the same kind of thing

The catalog of the scripted model is reproducible byte for byte. The catalog of a real model is the recording
of one run of one model, and it is not reproducible byte for byte, under ADR-075. A record names the catalog
of its bundle and carries the statement of reproducibility of that catalog, so a reader knows what kind of
failure the record describes: a reproducible failure of the scripted model, or the failure of one run of a
real model.

## The held out set stays reserved

The reservation of the held out set is by the content of the case and not by its identifier, under ADR-065,
and the contamination check compares the content of the case, so a case of the held out set under an alias is
refused with the name of the case and of the alias. The guard of the tuning of `ledgerlens/eval/manifest.py`
still refuses a tuning against a dataset whose role is `held_out` and refuses the published report of the
measurement. The key of the held out set is never published in any form, including a hash.

## The feedback of a visitor stays in the session of the visitor

A comment sent through the sandbox of a visitor is written under the runtime of the sandbox, keyed by the
session of the visitor, and nothing of it is written under `data/eval/feedback/`. The registry refuses a
record whose source is a session of a visitor, because ADR-P009 is a safety invariant and not a preference.

## No model is trained by this milestone

The milestone ships the loop and the measurement: the dataset is built, the comparison with the baseline runs
over the holdout, the negative result is kept, and the promotion of a candidate is written down whatever it
is. No weight is written, the modules of the loop import no training library, and the runtime of the agent
does not change. The training of a model waits for a dataset that a human has reviewed and goes behind the
flag of ADR-P007, which is the only place where a specialist model is allowed to exist.
