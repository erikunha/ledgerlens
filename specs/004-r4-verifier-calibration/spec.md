# Feature Specification: Verifier calibration and benchmark integrity

**Feature Branch**: `feature/v3`

**Created**: 2026-11-22

**Status**: Draft

**Input**: Design document: `docs/v3/specs/LL-R4-03-verifier-eval-reconciliation.md`. User description: "The
repository publishes an accuracy of the verifier and a correctness of the agent, and a reader of those numbers
cannot tell over which dataset they were measured, whether the decisions of the repository were taken against that
dataset, or how wide the uncertainty is. The release makes every number name its dataset and its restriction, pins
the calibration to the bytes it was measured over, holds out a set that no tuning script may read, and shows which
cases failed instead of publishing an aggregate that hides them."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Know the dataset behind every published number (Priority: P1)

A reader of the README, of `docs/verification_sets.md` or of a report asks what the number 1.0 over the 30 text
cases of the verification set means. The answer names the file the 30 cases live in, says that the sweep of ADR-007
chose the thresholds over exactly those cases, and says that an accuracy over a set the thresholds were chosen on is
a measure of the fit and not a measure of the behavior on unseen data. The reader also learns that no dataset of the
repository is held out today, and that this is a property of the repository and not a caveat that a report forgot.

**Why this priority**: this is the honesty of every number the repository publishes. A number that cannot be read
as more than it is worth exactly what the measurement behind it is worth.

**Independent test**: give the repository to a reader who has never seen the calibration and ask them what the
accuracy of the verifier is measured over. The answer has to name the dataset and the restriction, without opening
the source code.

### User Story 2 - Know that the calibration was measured over specific bytes (Priority: P1)

The reader of `ledgerlens/verify/thresholds.json` wants to know whether the thresholds in that file were chosen
against the files that are on the disk today. The calibration names the sha256 of the manifest of the datasets it
was measured over, the version of the NLI model, and the sweep that chose the thresholds, and a script that recomputes
the sweep refuses to run when the manifest at the moment of the run is not the one the calibration names.

**Why this priority**: an accuracy that does not name the bytes it was measured over is a number over a file that
may have moved under it.

**Independent test**: change one byte of a dataset, run the sweep, and the run refuses with the two hashes that
disagree.

### User Story 3 - Hold out a set that no tuning script can read (Priority: P1)

The repository has a set of verification cases that no threshold, prompt or hyperparameter was ever chosen against,
with different case templates, different text and different source structures from the sets of the tuning, labelled
by a person reading the evidence. A script that tunes refuses to read it, and the refusal is a sentence and not a
traceback. The cases that a tuning script may not read are declared in the manifest with the role that says so.

**Why this priority**: without a held out set, the repository can report the fit and never the generalization, and
no amount of care in the reports changes that.

**Independent test**: a script of the tuning that names the held out dataset exits with a non zero code and a
readable reason, and the same script over a tuning dataset runs.

### User Story 4 - See which cases failed, and why (Priority: P2)

A reader of the evaluation wants to know which cases the verifier got wrong, with the claim, the evidence and the
verdict of each one side by side. The report of the evaluation answers that, per case, and the aggregate number
sits next to the per case list instead of replacing it. A case that failed because the answer had no evidence at all
appears in the list even when the aggregate correctness went up.

**Why this priority**: an aggregate that hides the failures is the same kind of lie as a number without its dataset.

**Independent test**: remove one case from the set of the evaluation and the per case report shows the case that
failed, with the claim and the evidence, and the aggregate changes by exactly that case.

### User Story 5 - Read the limitations of the evaluation where the numbers are (Priority: P2)

A reader of the interface sees, next to every accuracy and every correctness, the dataset it comes from and the
restriction that applies to that dataset. The Eval Lab shows the cases that failed, with the claim and the
evidence, and says plainly when the NLI model is not loaded: an unavailable verification is not a pass.

**Why this priority**: the interface is where most of the readers of this repository meet it, and a limitation that
lives only in a document is a limitation that most readers never see.

**Independent test**: a page of the Eval Lab that shows a number shows, in the same view, the dataset and the
restriction.

### User Story 6 - Tell the correctness of the agent apart from the accuracy of the verifier (Priority: P3)

A reader compares two numbers of the repository, the correctness of the agent over the cases of the evaluation and
the accuracy of the verifier over the cases of the verification. They measure different things over different sets,
and the reports say so in the same sentence, so that a reader never adds them, averages them or quotes one as the
other.

**Why this priority**: the two numbers are both published today and a reader can easily read one as the other.

**Independent test**: every place that publishes one of the two numbers names the other as a different measure
over a different set.

### Edge Cases

- A dataset of `data/eval/` that no entry of the manifest declares: the gate refuses with the name of the file.
- A dataset that moved and whose manifest did not: the gate refuses with the two hashes that disagree.
- A manifest entry whose path leaves the repository, or is absolute: the manifest is refused and the check says why.
- A role of a dataset changed by hand: the manifest file is not protected by the gate, and the ADR says so, and the
  write says out loud when it could not compare the roles with the commit.
- A calibration whose manifest hash does not match the manifest of the disk: the sweep refuses and does not publish
  a number.
- An NLI model that is not loaded: the verification status is `unavailable`, and a case with no verdict is not a
  case that passed.
- A report of a previous run: it stays readable under its own versioned id, and it is never rewritten in place.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every dataset under `data/eval/` has an entry in the manifest with its sha256, its record count, its
  source, its labeling version, its split role, its scenario seed and the contamination policy.
- **FR-002**: The check of the manifest is a step of the gate, and a dataset that moves without the manifest moving
  breaks the build.
- **FR-003**: The role of a dataset is decided by evidence, and the conservative role wins when the evidence is not
  clean.
- **FR-004**: The calibration names the sha256 of the manifest it was measured over, the version of the NLI model
  and the sweep that chose the thresholds.
- **FR-005**: A script that tunes the thresholds refuses to read a dataset whose role is not `tuning`, and refuses
  to run when the manifest of the disk is not the one the calibration names.
- **FR-006**: The held out set has cases with different templates, different text and different source structures
  from the sets of the tuning, and their labels come from a person reading the evidence.
- **FR-007**: The evaluation report answers per case: the claim, the evidence, the expected verdict and the
  verdict that came out, and the aggregate sits next to the list.
- **FR-008**: A case that has no evidence, or whose evidence contradicts itself, or that is a benign claim the
  evidence does not support, appears in the per case report.
- **FR-009**: The interface shows the dataset and the restriction next to every number it publishes.
- **FR-010**: The correctness of the agent and the accuracy of the verifier are never published as if they were the
  same measure.
- **FR-011**: A missing NLI model produces `verification_status = unavailable`, and that is not a pass.
- **FR-012**: The exact money rules are decided by code, and the NLI never overrules a deterministic contradiction.
- **FR-013**: A report of a previous run is kept under its own versioned id, and a change of the extraction or of
  the prompt is reported as a change of the extraction, and never as a rewrite of the past.

### Key Entities

- **EvalDatasetManifest**: one dataset of `data/eval/`, pinned by the file it names and the role it plays.
- **Held out case**: one claim with its evidence and the label a person gave it, in a set that no decision of the
  repository was taken against.
- **Calibration pin**: the sha256 of the manifest, the version of the NLI model and the sweep, as the three things
  that say what a calibration was measured over.
- **Per case result**: one case of the evaluation with the claim, the evidence, the expected verdict, the verdict
  and the reason of the disagreement.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every number that the README, `docs/verification_sets.md` and the reports publish names the dataset
  it comes from and the restriction that applies to it, checked by a test that reads the documents.
- **SC-002**: A dataset of `data/eval/` that moves without the manifest moving fails the gate with a sentence that
  names the dataset, the file and the two values that disagree.
- **SC-003**: The manifest records the 43 records of `data/eval/verification_set.jsonl` and the exact sha256 of
  the file, checked against the disk.
- **SC-004**: A script that tunes the thresholds refuses to read a held out dataset, with a non zero exit code and
  a readable reason, and the refusal is covered by a test.
- **SC-005**: The calibration of `ledgerlens/verify/thresholds.json` names the sha256 of the manifest it was
  measured over, and the sweep refuses to run when the manifest of the disk is not that one.
- **SC-006**: The per case report of the evaluation shows every case that failed, with the claim and the evidence,
  and the aggregate sits next to the list.
- **SC-007**: A case with no evidence, a self contradicting evidence and an unsupported benign claim appear in the
  per case report, even when the aggregate correctness rises.
- **SC-008**: The confusion matrix of the verifier is per case and per label, and the report of the verifier
  distinguishes the false supported, the false contradicted and the case without a verdict.
- **SC-009**: No public metric of the repository states an accuracy of the verifier without naming the dataset and
  the restriction that applies to it.
- **SC-010**: The correctness of the agent and the accuracy of the verifier are published as two measures over two
  different sets, and no document presents one as the other.
- **SC-011**: The whole suite runs offline with `LEDGERLENS_OFFLINE=1`, with no key and no network, and the check of
  the manifest is a step of the gate of the continuous integration.
- **SC-012**: A change of the prompt parser, with the model output unchanged, is reported as a change of the
  extraction, and the reports of the past are not rewritten.

## Assumptions

- The design package of the release is `docs/v3/specs/LL-R4-03-verifier-eval-reconciliation.md`, and the decision
  that carries the first step of it is `docs/decisions/ADR-052-the-manifest-of-the-eval-datasets.md`.
- The numbers of the calibration do not change in this release. What changes is what they can be read as, and the
  data they were measured over is pinned.
- The labels of a held out set are read by a person. An agent that writes a case and labels it produces a
  tautology, so the writing and the labeling are two different acts by two different readers.
- The interface of the release lives in `apps/web/`, and the gate of the frontend is a job of its own in the
  continuous integration.
