---
type: adr
status: accepted
date: 2026-11-24
---

# ADR-096: The deterministic verdict is the gate of the training data

Status: accepted. Date: 2026-11-24.

## Context

The design package
[LL-V3-R20-01, verified feedback to evaluation and training](../design/advanced-specs/R20-01-verified-feedback-to-evaluation-and-training.md)
proposes a loop that turns a published failure into a reviewed regression and, where warranted, into a dataset
that a specialized model could be tuned against. The repository publishes two catalogs of recorded scenarios,
and [ADR-068](ADR-068-the-published-catalogue-holds-the-failures-and-not-only-the-cases-the-agent-resolves.md)
says that they hold the failures and not only the cases the agent resolves. The failures are read and nothing
else happens with them.

The milestone of [specs/021](../../specs/021-r20-verified-feedback-to-evaluation-and-training/spec.md) closes
that loop with one rule in front of it, and the rule is the red line of ADR-P007 expressed as a field of a
record: model output never becomes training data without the deterministic verdict as its gate. Without the
gate, the loop would be a machine that trains a model on the agreement of another model, and the number it
produced would measure nothing.

## Decision

**The verdict of a feedback record is the verdict of the deterministic verifier over the published evidence of
the bundle, the verdict of a model never fills that field and never promotes a record, the tier of a record and
the split of a dataset are two different axes, the held out set stays reserved, and no model is trained by this
milestone.**

1. **The verdict of a record is the verdict of the deterministic verifier over the published evidence of the
   bundle.** It is computed by `ledgerlens/verify/checks.py` over the evidence the bundle publishes, offline,
   with no model and no network, exactly as [ADR-073](ADR-073-the-published-bundle-carries-the-evidence-its-verdict-was-computed-on-and-it-is-reproducible.md)
   re-verifies a published bundle. The verdict of the NLI model never fills that field: when the NLI verdict
   disagrees with the deterministic one, the deterministic one is the one that is written down.
2. **The verdict of a model never promotes a record.** A record whose only support is an output of a model,
   whether the answer of the agent, the label of the NLI model or a correction proposed from a suggestion of
   the model, stays below the tier `gold` and never enters a training set.
3. **The tier of a record and the split of a dataset are two different axes.** The tier of a record is
   `gold`, `silver` or `unverified`, and it lives in the registry of the records. The split of a dataset is
   `tuning`, `validation` or `held_out`, and it lives in the manifest of the datasets under
   [ADR-052](ADR-052-the-manifest-of-the-eval-datasets.md) and
   [ADR-062](ADR-062-the-role-held-out-exists-and-the-sentence-of-adr-052-is-superseded.md). A `gold` record may land in
   a `tuning` dataset or in a `validation` dataset, and it never lands in a `held_out` dataset.
4. **The held out set stays reserved.** The reservation is by the content of the case and not by its
   identifier, under [ADR-065](ADR-065-the-reservation-of-the-held-out-set-follows-the-case-and-not-only-the-file.md), and the key
   of that set is never published in any form, including a hash.
5. **No model is trained by this milestone.** The milestone ships the loop and the measurement: the dataset is
   built, the comparison with the baseline runs over the holdout, the negative result is kept, and the
   promotion of a candidate is written down whatever it is. The training of a model waits for a dataset that a
   human has reviewed and goes behind the flag of ADR-P007, which is the only place where a specialist model
   is allowed to exist.

## Alternatives considered

- **To let the verdict of the NLI model fill the verdict of a record.** Refused. The verdict of a record is a
  decision of the code over the published evidence, and a verdict of a model is a proposal that the code may
  confirm or refuse.
- **To accept the agreement of a model with a correction as the promotion of a record.** Refused. A record is
  `gold` only when the deterministic verdict supports the correction and a second reader of the repository
  confirmed it, and the second reader is another person and not the same reader twice.
- **To mix the tier of a record with the split of a dataset.** Refused. The two axes answer two questions: the
  tier says how much the repository trusts a record, and the split says what a dataset may be used for.
- **To publish the key of the held out set in a form that only a machine reads.** Refused. A key that is
  public is not a key, and the reservation of the held out set is the reservation that makes a number over it
  a generalization.

## Consequences

- **The repository has the loop of the verified feedback**, in `ledgerlens/feedback/`: the record
  (`record.py`), the deterministic gate (`gate.py`), the tiers (`tiers.py`), the registry (`registry.py`), the
  training set (`training_set.py`), the contamination check (`contamination.py`), the promotion
  (`promotion.py`) and the archive (`archive.py`), with the tests in `tests/feedback/`.
- **The records live under `data/eval/feedback/` with their digests**, and the check of the registry reads the
  disk and writes nothing, next to the check of the datasets of the evaluation in the gate.
- **The feedback of a visitor stays in the session of the visitor**, under the sandbox, and the registry
  refuses a record whose source is a session of a visitor, because
  [ADR-P009](../design/adrs/ADR-P009-privacy-scope.md) is a safety invariant
  and not a preference.
- **The page of the loop is [the page of the verified feedback](../feedback.md)**, with the four stages, the
  three tiers and the reservation of the held out set.

## Links

- [ADR-052, the datasets of the evaluation carry a manifest](ADR-052-the-manifest-of-the-eval-datasets.md)
- [ADR-062, the role held out exists and the sentence of ADR-052 is superseded](ADR-062-the-role-held-out-exists-and-the-sentence-of-adr-052-is-superseded.md)
- [ADR-065, the reservation of the held out set is by the content](ADR-065-the-reservation-of-the-held-out-set-follows-the-case-and-not-only-the-file.md)
- [ADR-067, the tuning against the held out set is refused](ADR-067-the-measurement-of-the-held-out-set-is-published-without-its-answer-key.md)
- [ADR-073, a published bundle is re-verified offline](ADR-073-the-published-bundle-carries-the-evidence-its-verdict-was-computed-on-and-it-is-reproducible.md)
- [ADR-075, the catalogue of a real model says what it is](ADR-075-the-site-publishes-two-catalogs-and-each-bundle-declares-the-one-it-belongs-to.md)
- [the page of the verified feedback](../feedback.md)
- [the specification of the milestone](../../specs/021-r20-verified-feedback-to-evaluation-and-training/spec.md)
- [the design package](../design/advanced-specs/R20-01-verified-feedback-to-evaluation-and-training.md)
