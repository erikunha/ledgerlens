# Feature Specification: Verified feedback to evaluation and training

**Feature Branch**: `feature/v3`

**Created**: 2026-11-23

**Status**: Draft

**Input**: Design documents: [R20-01, verified feedback to evaluation and training](../../docs/v3/advanced-specs/R20-01-verified-feedback-to-evaluation-and-training.md),
[ADR-052, the manifest of the eval datasets](../../docs/decisions/ADR-052-the-manifest-of-the-eval-datasets.md),
[ADR-059, the held out set is read by two blind machines and adjudicated](../../docs/decisions/ADR-059-the-held-out-set-is-read-by-two-blind-machines-and-adjudicated.md),
[ADR-062, the role held out exists](../../docs/decisions/ADR-062-the-role-held-out-exists-and-the-sentence-of-adr-052-is-superseded.md),
[ADR-065, the reservation follows the content of the case](../../docs/decisions/ADR-065-the-reservation-of-the-held-out-set-follows-the-case-and-not-only-the-file.md),
[ADR-067, the measurement of the held out set is published without its answer key](../../docs/decisions/ADR-067-the-measurement-of-the-held-out-set-is-published-without-its-answer-key.md),
[ADR-068, the published catalog holds the failures](../../docs/decisions/ADR-068-the-published-catalogue-holds-the-failures-and-not-only-the-cases-the-agent-resolves.md),
[ADR-073, the published bundle carries the evidence its verdict was computed on](../../docs/decisions/ADR-073-the-published-bundle-carries-the-evidence-its-verdict-was-computed-on-and-it-is-reproducible.md),
[ADR-075, the site publishes two catalogs](../../docs/decisions/ADR-075-the-site-publishes-two-catalogs-and-each-bundle-declares-the-one-it-belongs-to.md),
[ADR-077, the published bundle is verified against the answer the run verified](../../docs/decisions/ADR-077-the-published-bundle-is-verified-against-the-answer-the-run-verified.md),
[ADR-P007, one evidence-first agent by default](../../docs/v3/adrs/ADR-P007-no-multiagent-by-default.md),
[ADR-P009, the privacy scope of the public project](../../docs/v3/adrs/ADR-P009-privacy-scope.md) and
[the release train, the R20 contract](../../docs/v3/roadmap/RELEASE-TRAIN-2027-2030.md). User description: "The
repository publishes two catalogs of recorded scenarios. One of them holds the cases the agent resolves and the
cases it fails on. The failures are read, but nothing is done with them: they do not become a regression, they do
not become a dataset, and no model is trained on them. This specification closes that loop with one rule in front
of it: nothing that came out of a model becomes training data before the deterministic verifier of the repository
has judged it."

## The rule that decides the milestone

**Model output never becomes training data without the deterministic verdict as its gate.**

This is the red line of ADR-P007 and the rule this specification exists to enforce. The repository publishes two
catalogs of recorded scenarios, and every one of those recordings carries verdicts. Some of those verdicts come
from the NLI model, which is a model, and some come from the deterministic verifier of the repository, which is
code. A verdict of a model is a proposal. A verdict of the deterministic verifier is a decision. Only a decision
may open the door to a dataset.

So the rule has three parts, and the milestone is green when all three hold.

1. **A record carries the verdict of the deterministic verifier, and never the verdict of a model.** The verifier
   of `ledgerlens/verify/checks.py` re-verifies the published evidence of a bundle offline, with no model and no
   network, exactly as ADR-073 and ADR-075 require of the published catalogs. That verdict is the one the record
   carries.
2. **A record is promoted to `gold` only when that verdict supports the correction.** A record whose deterministic
   verdict is `contradicted` or `not_enough_evidence` stays `silver` at best, and a record with no published
   evidence stays `unverified` and never enters a training set.
3. **A training set is built only from `gold` records.** A `silver` record may be read by a person and it may be
   promoted by a review, but it never enters a dataset on its own. A `unverified` record never enters anything.

The rule applies to the three kinds of output that a model produces in this repository: the answer of the agent,
the label of the NLI model and the corrected value that a reviewer proposed from a suggestion of the model. None of
them becomes training data without the deterministic verdict as its gate.

## What exists today and what the package proposes

The package proposes a feedback record with a trust tier, a dataset registry with hashes, permissions and splits,
a contamination check, a promotion that compares on an untouched holdout and a rollback. It is a design note of the
frozen import and none of it exists.

What the repository has is the whole governance around it and none of the loop.

| What the package names | What the repository has | What is missing |
|---|---|---|
| the evidence of a failure | the two published catalogs, `data/eval/replay/` with the recordings of the scripted model and `data/eval/replay-real/` with the recordings of a real model, and ADR-068 that says the catalog holds the failures and not only the resolved cases | the record that links a failure, its claim, its evidence and its verdict |
| `gold/silver/unverified` | the roles of the manifest of the datasets, `tuning`, `validation` and `held_out`, under ADR-052 and ADR-062 | the tier of a record, which is a different axis from the split of a dataset |
| the dataset registry with hashes, permission and split | `data/eval/datasets.json`, the manifest that carries the digest of every dataset and its role, checked by `scripts/check_eval_datasets.py` | the registry of the feedback records and the permission that says what a record may be used for |
| the contamination check | the reservation of the held out set, which follows the case and not only the file, under ADR-065, and the guard of the tuning in `ledgerlens/eval/manifest.py` | the check that a case of the training set is not in the test set, including through an alias |
| the promotion that compares on an untouched holdout | the measurement of the held out set, published as an aggregate and with the predictions of the model, under ADR-067 | the promotion of a candidate and the comparison that justifies it |
| the rollback | the rollback of the thresholds, which is a file and a pin | the rollback of a trained artifact |
| no multiagent by default | ADR-P007, which keeps the runtime a single agent with a deterministic verifier and makes a specialist graph a controlled experiment | the paired comparison that would justify one |

Four adaptations the port makes.

1. **The feedback comes from the two published catalogs, and the record says which one.** ADR-075 says that each
   bundle declares the catalog it belongs to and that a folder with two modes has no honest name. A feedback record
   therefore names the catalog of its bundle, and the two are not the same kind of thing: a failure of the
   scripted catalog is reproducible byte for byte, and a failure of the real catalog is the failure of one run of a
   model and is not reproducible. A training set built from the second one has to say so.
2. **The tier of a record and the split of a dataset are different axes.** The manifest of ADR-052 carries the
   split, and the split of a dataset is `tuning`, `validation` or `held_out`. The tier of a record says how much
   the repository knows about it, and it is `gold`, `silver` or `unverified`. The two never mix, and the registry
   of the records carries the tier while the manifest of the datasets keeps carrying the split.
3. **The holdout stays reserved.** ADR-065 reserves the held out set by the content of the case and ADR-067
   reserves the published report of the measurement against tuning. A promotion therefore compares the candidate
   with the baseline on the holdout once, after the candidate is frozen, and the comparison is written down in a
   record. The set is never a tuning target and the key is never published, in any form, including a hash.
4. **No model is trained in this milestone.** The package says that a tuned reranker or intent model is optional
   and behind a research module. The milestone that ships first is the loop that produces a regression set and the
   measurement that says whether a change helped. The training itself waits for the loop to have produced a
   dataset that a human has reviewed, and it goes behind the flag that ADR-P007 describes.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Turn a published failure into a record with a verdict (Priority: P1)

A maintainer reads the catalog of the scripted model, finds a scenario whose published answer does not hold, and
opens the failure. The record that is created names the scenario, the bundle and its digest, the claim, the
evidence of the claim, the reading of a reviewer and the verdict of the deterministic verifier. The record can be
read without a key and without a network, and re-running the verifier over the published evidence gives the same
verdict.

**Why this priority**: the whole loop starts here. A failure that is not a record is a bug report, and a bug report
does not become a regression.

**Independent test**: take a scenario of `data/eval/replay/` whose answer the verifier marks as not supported,
create the record and assert that it names the bundle, the digest of the bundle, the claim, the evidence and the
verdict of the deterministic verifier, and assert that re-running the verifier over the published evidence of the
bundle gives the same verdict with no model and no network.

### User Story 2 - See a record that a model wants to promote and that the verifier refuses (Priority: P1)

A reviewer proposes a correction for a case and the NLI model of the repository agrees with the proposal. The
record stays `silver`, because the verdict of the deterministic verifier is `not_enough_evidence`, and the record
names the reason. The record never enters a training set, and a test proves it.

**Why this priority**: this is the case the red line exists for. A model that agrees with a proposal is not a
verification, and a loop that lets a proposal in on the agreement of a model is a loop that trains a model on its
own output.

**Independent test**: create a record whose proposed correction is supported by the NLI model and whose
deterministic verdict is `not_enough_evidence`, and assert that the tier is `silver`, that the record is not in the
training set and that the reason names the verdict of the verifier.

### User Story 3 - See a record promoted only when the verifier supports it (Priority: P1)

A reviewer proposes a correction, the deterministic verifier re-verifies the published evidence and answers
`supported`, and a second reader of the repository confirms the correction. The record becomes `gold` and it is
the only tier that a training set is built from.

**Why this priority**: the promotion is the door, and the door has to have one key.

**Independent test**: create the record of the story above with a deterministic verdict of `supported` and the
confirmation of a second reader, and assert that the tier is `gold` and that the record is in the training set
while a `silver` record is not.

### User Story 4 - See that a case of the training set is not in the test set, even under another name (Priority: P1)

The maintainer builds a training set and the contamination check finds that a case of the training set is in the
held out set under an alias: the same ledger, the same complaint and the same merchant with a different
identifier. The build is refused, with the name of the case and of the alias.

**Why this priority**: a case that is in both sets makes the number of the evaluation meaningless, and the
reservation of the held out set follows the content of the case and not only the file.

**Independent test**: build a training set that holds a case of the held out set under an alias and expect the
refusal with the name of the case, and expect that the guard of the tuning of `ledgerlens/eval/manifest.py` still
refuses a tuning against the held out set.

### User Story 5 - Compare a candidate with the baseline and see that a worse result stops the promotion (Priority: P1)

The maintainer changes something, builds the candidate, runs the baseline and the candidate over the same cases
and compares them over the holdout. The candidate is worse on the holdout, and the promotion does not happen. The
negative result is written down and kept, not deleted.

**Why this priority**: a loop that only records the wins is a loop that cannot be trusted, and a repository that
publishes negative results is a repository that can be read.

**Independent test**: compare a candidate that is worse than the baseline and expect that the promotion does not
happen, that the report of the comparison holds the negative result and that the report names the set, the
denominator and the role of the set.

### User Story 6 - Keep the feedback of a visitor out of the shared set (Priority: P1)

A visitor of the sandbox writes a comment about a case. The comment stays in the session of the visitor. It never
reaches the registry of the records, it never becomes a `gold` record and it never touches a training set.

**Why this priority**: ADR-P009 is a safety invariant, and a public laboratory whose shared training set a visitor
can write into is a laboratory that a visitor can poison.

**Independent test**: send a feedback comment through the sandbox of a visitor and assert that nothing was written
under the registry of the records, and assert that the registry refuses a record whose source is a session of a
visitor.

### User Story 7 - Keep the experiment reproducible after the archive (Priority: P2)

The maintainer archives an experiment: the dataset, its digests, the code, the commit and the report of the
comparison. Six months later the experiment can be run again and it gives the same numbers, or it refuses and says
that the set moved.

**Why this priority**: an experiment that cannot be reproduced is an anecdote, and the archives are the memory of
the loop.

**Independent test**: archive an experiment, read the archive and expect the digests of the dataset, the commit and
the report, and expect that a run over a dataset whose bytes moved is refused with a reason.

### Edge Cases

- A failure of the catalog of a real model: the record names the catalog and says that the recording is not
  reproducible byte for byte, and the record is never presented as a reproducible regression.
- A record whose evidence was never published: the tier is `unverified` and the record never enters a training
  set, whatever a reviewer says.
- A corrected value that is a money value: it is a `Decimal` and it is compared with `Decimal`, never with a
  float.
- A case of the held out set that a reviewer wants to add to the training set: refused, because the set is
  reserved and the key is never published.
- Two records for the same claim with different corrections: both are kept, the disagreement between them is
  named, and neither is promoted until it is resolved.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A feedback record is a typed record with the run, the bundle and its digest, the catalog the bundle
  belongs to, the claim, the verdict, the corrected value, the evidence references, the role of the reviewer and the
  tier of the record.
  - Test: `tests/feedback/test_record.py` expects the fields of the record and expects the refusal of a record
    that misses one of them.
- **FR-002**: The verdict of a record is the verdict of the deterministic verifier of `ledgerlens/verify/checks.py`
    over the published evidence of the bundle, computed offline with no model and no network. The verdict of the
    NLI model never fills the field.
  - Test: `tests/feedback/test_deterministic_gate.py` expects that the verdict of a record is the one the
    deterministic verifier gives for the published evidence of the bundle, and that a record whose NLI verdict
    disagrees with the deterministic one carries the deterministic one.
- **FR-003**: The tier of a record is `gold` only when the deterministic verdict supports the correction and a
    second reader of the repository confirmed it. A record with a deterministic verdict of `contradicted` or
    `not_enough_evidence` is at most `silver`, and a record with no published evidence is `unverified`.
  - Test: `tests/feedback/test_tiers.py` expects the tier of each of the three cases and expects that a record
    that no deterministic verdict supports is never `gold`.
- **FR-004**: A training set is built only from the records whose tier is `gold`. A `silver` record and a
    `unverified` record never enter it, whatever a reviewer says.
  - Test: `tests/feedback/test_training_set.py` builds a set from a mixture of the three tiers and expects only the
    `gold` records in it.
- **FR-005**: No output of a model ever becomes training data without the deterministic verdict as its gate. The
  answer of the agent, the label of the NLI model and a correction proposed from a suggestion of the model are all
  outputs of a model, and none of them promotes a record on its own.
  - Test: `tests/feedback/test_model_output_is_not_training_data.py` expects that a record whose only support is a
    model output stays below `gold` and that the training set of FR-004 does not carry it.
- **FR-006**: A record of a failure of the catalog of the scripted model names that catalog, and a record of a
  failure of the catalog of a real model names the other one and says that the recording is not reproducible byte
  for byte.
  - Test: `tests/feedback/test_catalog_of_the_origin.py` expects the catalog in the record and the statement of
    reproducibility, for one record of each catalog.
- **FR-007**: The registry of the records carries the digest of the source of every record, the permission that
  says what the record may be used for and the tier, and the registry is checked by a script that reads the disk.
  - Test: `tests/feedback/test_registry.py` expects the three fields of every entry and expects the refusal of an
    entry whose digest does not match the file it names.
- **FR-008**: The build of a training set is refused when a case of it is in another split, including under an
    alias. The check compares the content of the case and not only its identifier, under ADR-065.
  - Test: `tests/feedback/test_contamination.py` expects the refusal with the name of the case and of the alias.
- **FR-009**: The held out set stays reserved. The guard of the tuning of `ledgerlens/eval/manifest.py` still
    refuses a tuning against a dataset whose role is `held_out`, and the published report of the measurement stays
    refused as a tuning target by its path and by the digest of its bytes.
  - Test: `tests/eval/test_tuning_guard.py` expects the refusal for the held out set and for the published report.
- **FR-010**: A promotion compares the candidate with the baseline over the same cases and over the holdout, once,
    after the candidate is frozen. A candidate that is worse on the holdout is not promoted, and the negative result
    is kept.
  - Test: `tests/feedback/test_promotion.py` expects that a worse candidate is not promoted and that the report
    holds the negative result with the set, the denominator and the role of the set.
- **FR-011**: The report of a comparison names the set, the denominator, the role of the set and the digest of the
    dataset, and it publishes no number that was not measured.
  - Test: `tests/feedback/test_promotion.py` reads the report and expects the four names and expects that no
    number of the report is a number that the run did not produce.
- **FR-012**: The feedback of a visitor stays in the session of the visitor. The registry refuses a record whose
    source is a session of a visitor, and nothing of a visitor is written into the registry.
  - Test: `tests/feedback/test_visitor_feedback_is_sandbox_only.py` expects the refusal and expects that nothing
    was written under the registry.
- **FR-013**: The corrected value of a record is a `Decimal` when it is a money value, and it is compared with
    `Decimal`.
  - Test: `tests/feedback/test_record.py` expects the `Decimal` of a corrected amount and expects the comparison
    with the value of the ledger to be exact.
- **FR-014**: An experiment is archived with the dataset, its digests, the code, the commit and the report of the
    comparison, and a run over a dataset whose bytes moved is refused with a reason.
  - Test: `tests/feedback/test_archive.py` expects the fields of the archive and expects the refusal when the
    digest of the dataset does not match.
- **FR-015**: No model is trained in this milestone, and nothing of this milestone changes the runtime of the
    agent. ADR-P007 keeps the runtime a single agent with a deterministic verifier, and any specialist model is a
    controlled experiment behind a flag that is compared with the baseline over the holdout and over the cost.
  - Test: `tests/feedback/test_no_model_is_trained.py` expects that the folder of the feedback holds no weights and
    no model artifact, and that the modules of `ledgerlens/feedback/` import no training library.

### Key Entities

- **Feedback record**: the typed record of a failure, its bundle and its digest, its catalog, its claim, its
  corrected value, its evidence, the role of the reviewer and its tier.
- **Tier**: the named quality of a record: `gold`, `silver` or `unverified`. The tier is a property of the record
  and never of the split of a dataset.
- **Registry of the records**: the file that carries every record with its digest, its permission and its tier, and
  the script that reads it and checks it against the disk.
- **Training set**: the versioned dataset built only from the records of the tier `gold`, with the digests of its
  files and the split it belongs to.
- **Promotion**: the decision to adopt a candidate, taken after a comparison with the baseline over the holdout,
  and written down with the result, including when the result is negative.
- **Experiment archive**: the dataset, the digests, the code, the commit and the report of a comparison.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The verdict of every record is the verdict of the deterministic verifier over the published evidence
  of the bundle, computed with no model and no network.
- **SC-002**: A record whose only support is an output of a model is never `gold` and never enters a training set.
- **SC-003**: A training set holds only the records of the tier `gold`.
- **SC-004**: The record names the catalog of its bundle, and a record of the catalog of a real model says that
  the recording is not reproducible byte for byte.
- **SC-005**: The registry carries the digest, the permission and the tier of every record, and an entry whose
  digest does not match the disk is refused.
- **SC-006**: A training set that holds a case of another split under an alias is refused with the name of the
  case.
- **SC-007**: The guard of the tuning still refuses the held out set and the published report of the measurement.
- **SC-008**: A candidate that is worse on the holdout is not promoted and the negative result is kept.
- **SC-009**: The report of a comparison names the set, the denominator, the role of the set and the digest of the
  dataset.
- **SC-010**: The feedback of a visitor stays in the session of the visitor and the registry refuses it.
- **SC-011**: The corrected value of a money amount is a `Decimal` and the comparison with the ledger is exact.
- **SC-012**: An experiment that is archived can be read again, and a run over a dataset whose bytes moved is
  refused with a reason.
- **SC-013**: No model is trained, no weight is written and the runtime of the agent does not change.
- **SC-014**: The whole suite runs offline with `LEDGERLENS_OFFLINE=1`, with no key and no network.

## Assumptions

- The failures come from the two published catalogs, and ADR-068 says that the catalog holds the failures and not
  only the cases the agent resolves. A failure that is not published cannot be a record, because a record without
  published evidence has no deterministic verdict.
- The deterministic verdict is the one of ADR-073: the verifier of the repository rebuilds the result of the run
  out of the published events and hands it to the verifier. It runs offline and it needs no model.
- The reviewer of a record is a person of the repository, and the second reader is another person. A record is
  never confirmed by the same reader twice.
- The permission of a record says what it may be used for: a regression of the suite, an evaluation, or a training
  set. A record with the permission of an evaluation never enters a training set.
- The holdout stays reserved, and the comparison of a promotion is the one exception, taken once and written down.
- The cost of the loop is part of what a promotion compares, because ADR-P007 makes the cost one of the criteria
  against the gain.
- Nothing in this specification is built yet, and no model is trained by it.

## Out of scope

- The training of a model, of a reranker and of an intent model. The milestone produces the dataset and the
  measurement; the training waits for a reviewed dataset and goes behind the flag of ADR-P007.
- The multiagent topology. ADR-P007 makes it a controlled experiment and this milestone does not start it.
- The change of the prompts and of the thresholds. The loop of the thresholds exists and this milestone does not
  touch it.
- The publication of the answer key of the held out set, in any form, including a hash.
- The acceptance of a feedback from a visitor as a record of the repository.

## Design documents

- [R20-01, verified feedback to evaluation and training](../../docs/v3/advanced-specs/R20-01-verified-feedback-to-evaluation-and-training.md)
- [ADR-052, the manifest of the eval datasets](../../docs/decisions/ADR-052-the-manifest-of-the-eval-datasets.md)
- [ADR-059, the held out set is read by two blind machines and adjudicated](../../docs/decisions/ADR-059-the-held-out-set-is-read-by-two-blind-machines-and-adjudicated.md)
- [ADR-062, the role held out exists](../../docs/decisions/ADR-062-the-role-held-out-exists-and-the-sentence-of-adr-052-is-superseded.md)
- [ADR-065, the reservation follows the content of the case](../../docs/decisions/ADR-065-the-reservation-of-the-held-out-set-follows-the-case-and-not-only-the-file.md)
- [ADR-067, the measurement of the held out set is published without its answer key](../../docs/decisions/ADR-067-the-measurement-of-the-held-out-set-is-published-without-its-answer-key.md)
- [ADR-068, the published catalog holds the failures](../../docs/decisions/ADR-068-the-published-catalogue-holds-the-failures-and-not-only-the-cases-the-agent-resolves.md)
- [ADR-073, the published bundle carries the evidence its verdict was computed on](../../docs/decisions/ADR-073-the-published-bundle-carries-the-evidence-its-verdict-was-computed-on-and-it-is-reproducible.md)
- [ADR-075, the site publishes two catalogs](../../docs/decisions/ADR-075-the-site-publishes-two-catalogs-and-each-bundle-declares-the-one-it-belongs-to.md)
- [ADR-077, the published bundle is verified against the answer the run verified](../../docs/decisions/ADR-077-the-published-bundle-is-verified-against-the-answer-the-run-verified.md)
- [ADR-P007, one evidence-first agent by default](../../docs/v3/adrs/ADR-P007-no-multiagent-by-default.md)
- [ADR-P009, the privacy scope of the public project](../../docs/v3/adrs/ADR-P009-privacy-scope.md)
- [the release train, the R20 contract](../../docs/v3/roadmap/RELEASE-TRAIN-2027-2030.md)
- [the implementation plan of this specification](plan.md) and [its tasks](tasks.md)

## Status

Nothing in this specification is built. The repository holds the two published catalogs with their failures, the
manifest of the datasets with the roles, the guard of the tuning, the verifier that re-verifies a published bundle
offline and the record of the reservation of the held out set, and it holds none of the record of a feedback, of the
tier, of the registry, of the training set and of the promotion.

The decision this specification needs is written down before the first task: the deterministic verdict is the gate
of the training data, the tier of a record and the split of a dataset are two different axes, and the holdout
stays reserved. That record is the next free number of `docs/decisions/` (ADR-082 at the time of writing; check
[the index of the decisions](../../docs/decisions/README.md) before creating the file). It does not change any
accepted record.
