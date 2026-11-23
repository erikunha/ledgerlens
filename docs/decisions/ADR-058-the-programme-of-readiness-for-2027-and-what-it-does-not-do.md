---
type: adr
status: proposed
date: 2026-11-22
---

# ADR-058: The programme of readiness for 2027 and what it does not do

Status: proposed. Date: 2026-11-22.

## Context

The question this record answers is not what the repository should build. It is what the repository has to be, and what
it has to prove, for a reader in 2027 to believe that the number it publishes is a fact about a payment investigation
and not a story. Three debaters argued three stances about it and a judge decides; the cases are on the board of the
milestone and are not repeated here. The evidence they used is the repository, quoted with the file and the line.

- No dataset carries the role `held_out` today, so no result may be presented as a generalization to unseen data
  (`data/eval/datasets.json:4`), and all five carry the role `tuning` (`data/eval/datasets.json:13`, `:25`, `:37`,
  `:49`, `:61`).
- The blind reading of the 48 cases of the held out set is happening now: the instrument is `scripts/label_heldout.py`,
  the blind file exists (`data/eval/heldout/cases.jsonl`), the labelled file does not exist yet
  (`data/eval/verification_heldout.jsonl` is absent from the tree), and the measurement script of milestone 21 is
  written (`scripts/measure_heldout.py`).
- The reports publish the harmless error and hide the costly one: `verification_summary` returns the
  `false_positive_rate` (`ledgerlens/eval/evaluators.py:247`), the renderer prints it (`ledgerlens/eval/run.py:784`),
  and the false `supported` is computed by the sweep (`ledgerlens/verify/sweep.py:210`) and published nowhere, although
  ADR-007 calls it the costly error (`docs/decisions/ADR-007-nli-verification.md:106`).
- The loop that ships has no ceiling (no `recursion_limit` in `ledgerlens/`, `ledgerlens/agents/integrator.py:261`),
  the index can answer from a corpus that moved under it (the meta carries no digest of the corpus,
  `ledgerlens/retrieval.py:151-159`), and the gate has no step that touches the index (`scripts/gate.sh`).
- The trace of a live run dies with the process (the sink is in memory, `ledgerlens/api/live_run.py:696`, although the
  file sink is written and tested, `ledgerlens/observability/trace_event.py:301`), and the schema declares
  `evidence.added` and `claim.verdict` that no module emits (`ledgerlens/observability/trace_event.py:63-64`).
- The model has a clock: `gpt-4.1-mini` is the default of the registry (`ledgerlens/byok/registry.py:304-313`) and
  every published online number names it (`data/eval/report_online.md:7`), and its provider has announced the shutdown
  of the model for 14 January 2027. The repository has 53 accepted ADRs, a public site with one recorded scenario, 188
  tracked Markdown files, and no index of the documentation, no `SECURITY.md`, no `CONTRIBUTING.md` and no `CODEOWNERS`.

ADR-054, ADR-055 and ADR-056 are already written and are `proposed`, and their tasks are carried verbatim by
`specs/005-r4-runtime-latency-and-cost-per-case/tasks.md` with the ids T115 to T140. This record does not restate them
and does not renumber them. It decides where they sit in the cycle and what the cycle owes to the reader.

## Decision

### 1. What the programme is

**The next cycle of LedgerLens is a programme of enforcement and measurement, and not a programme of construction.**

The reason is the state of the repository and not a taste. The shape of the system is already decided and sound where
it decides the answer; what a reader in 2027 cannot check is that the decisions hold, because nothing enforces them,
and what the repository has never produced is a number over data that no decision of the repository was taken against.
Both gaps are gaps of enforcement and of measurement, both are cheaper than any component that could be added in the
same attention, and a component added now would compete with the reading that is happening today. A number over a set
nobody tuned on is the only thing that changes the status of every other number, and it is produced by reading, not by
coding.

**D1, the conservative case: ACCEPTED.** Its sentence is the sentence above and its order is the spine of the ordering
below. It is accepted because it is the only case that puts the reading of the held out set first and refuses every
component whose justification is a number that does not exist yet, and the repository is short of exactly that number.
The one change this record makes to it is the discoverability: D1 would put the surface last and accepts that risk only
if the cycle were long enough, and this record decides the cycle is not that long, so the reader path is inside the
cycle and the vector protocol is last, as D1 itself says it should be.

**D2, the product case: ACCEPTED WITH A CHANGE.** Its items land, because a number no reader can find is not published
in any sense that matters, and because the manifest, the contamination policy and the calibration pin live in a 398
line ADR, an orphan spec line and a JSON file, with the page that explains them linked from nowhere. The change is in
two places. The items land as reachability and not as design: the index of the documentation, the links from the README
to the public site and to the evaluation page, the parity of the Portuguese README and the disclosure of the AI, and
none of them is a redesign. And the analytics counter does not land, because the repository has no address and no
deployment workflow, so a counter would count the owner's own runs; the second published scenario becomes a failure
scenario rather than a second happy path, because the published proof is one scenario deep and the interesting case is
the one that escalates.

**D3, the law and the envelope case: REJECTED as a posture, and two of its items are taken.** The reason is that this
repository must not publish a claim it cannot hold. The conformity assessment, the marking, the registration, the
internal audit and the management review belong to a deployer, and the classification page asks for a legal conclusion
whose answer flips on a fact the repository does not state, namely whether a deploying organisation uses the answer to
decide a refund forgiveness or a chargeback waiver. The design package already refuses the first of these in its own
words: "Do not build multi-user billing, bank-grade compliance certification, real payment operations"
(`docs/v3/docs/15-RISKS-AND-OPEN-DECISIONS.md:26`). And the envelope D3 asks for has a shelf life shorter than the
cycle, because the model it would measure is the one being retired. Two of its items are taken and land inside the
programme as the honesty of the repository and not as compliance: the one line disclosure of the AI on every surface
that answers a person, and the incident path with a severity, an owner and a clock. The classification page becomes a
debt of this record and a decision of the owner.

### 2. The ordering, with the reason of each step

Four precedences are forced by the state of the world and this record has no freedom to move them: the reading of the
held out set comes before any number over it; the ceiling of the loop comes before the latency measurement, because a
measurement over a loop that can run for ever measures nothing; the digest of the corpus comes before the protocol of
the vectors, because a clean interface over a stale index hides the staleness; and the model of the registry has to be
pinned before any number that names it is published as a fact. A fifth precedence is added here: the reader path comes
before the vector protocol, because the vector protocol is the only item of the cycle that is about a future swap and
not about the truth of a number, and the reader path is the only item that makes the truth of a number reachable.

1. **The blind reading of the 48 cases, and the declaration of the role `held_out`.** A number over an unlabelled set is
   the exact failure the set exists to prevent, and the reading is the precondition of the only measurement that changes
   the status of every other number. It is also the one item with no engineering in it, so it is the one most easily
   displaced, and it is named first.
2. **The ceiling of the loop in every path that reaches a provider** (ADR-054, T115 to T120). The ceiling comes before
   the latency and before the cost per case, because a latency measured over a loop that can run for ever is not a
   latency.
3. **The digest of the corpus in the index, and the gate check that refuses a stale index** (ADR-055, T121 to T125).
   The digest comes before the protocol of the vectors, and the retrieval numbers come before any publication about the
   retrieval. A stale index is the one failure the gate can detect for the price of one field and one comparison.
4. **The pin of the model of the registry** (ADR-057), with the rule that a change of model re-measures against the
   declared thresholds before any number is republished. Every published online number was produced by the model that
   is being removed on 14 January 2027, and the pin comes before the reports are republished because republishing is
   the moment the model is named.
5. **The costly error in the two reports, the role of their set, and a quality step in the gate.** The report is the
   public face of the repository, and until it publishes the false `supported` rate with its denominator and names the
   role of its set, everything else is decoration. It is also where the reader looks for the answer to the question of
   this debate, and today the answer there is a fit that reads as a rate.
6. **The number over the held out set, with its denominator, its template table and the count of the disagreements of
   the reader with the recipes.** This is the fact the programme exists to produce, and ADR-053 decides that it may
   only be published with those three things (`docs/decisions/ADR-053-the-held-out-set-and-the-blind-labelling.md:144-146`).
   It comes after the pin and after the reports name their role, so the first number of the cycle is published by a
   report that already says what a role is.
7. **The trace that outlives the process, the usage on the result, and the cost of a case.** A number that dies with the
   process cannot be checked by anybody, and the cost of a case cannot be computed without the usage of the case.
8. **The latency and the cost per investigation** (T132 to T140). It comes after the ceiling by the rule of step 2 and
   after the usage on the result by the rule of step 7, and it is the only measurement of the cycle about the envelope
   of the system and not about the truth of a number.
9. **The reader path: the index of the documentation, the links from the README, the parity of the Portuguese README,
   the disclosure of the AI and the incident path.** It comes before the vector protocol by the fifth precedence, and it
   is the item that makes the number of step 6 reachable by a stranger who is not the author. The disclosure is already
   late and lands in this cycle whatever else is cut, because it is one constant and one test.
10. **The vector protocol** (ADR-056, T126 to T131). It is last because it is a promise about a future swap and not
    about the truth of a number, and a promise kept late costs less than a number published over an index nobody can
    prove is fresh.

### 3. What lands in this cycle, and what does not

The first table is the work that lands in this cycle. Every item is held by a test or by a check the gate runs, because
a thing that cannot be measured does not land in this cycle.

| # | the work | the file it touches | the test that holds it |
| --- | --- | --- | --- |
| 1 | the blind reading, the labelled file, the role `held_out` | `data/eval/verification_heldout.jsonl`, `data/eval/datasets.json` | `tests/eval/test_label_heldout.py`, `scripts/check_eval_datasets.py` (the gate, `scripts/gate.sh:21`) |
| 2 | the number over the held out set, with its denominator and its disagreement count | `scripts/measure_heldout.py` and its report | `tests/verify/test_measure_heldout.py`, the test that the number names its set |
| 3 | the false `supported` rate, the role of the set in the reports, a gate step against the pinned baseline | `ledgerlens/eval/evaluators.py:247`, `ledgerlens/eval/run.py:784`, the two reports, `scripts/gate.sh` | a new test in `tests/eval/`, `tests/eval/test_dataset_documentation.py`, the check of `scripts/baseline.py` |
| 4 | the ceiling of the loop in every path that reaches a provider | ADR-054 accepted, T115 to T120 | the scripted model test of the integrator under `tests/agents/` |
| 5 | the digest of the corpus in the index, and the gate check | ADR-055 accepted, T121 to T125 | `scripts/check_policy_index.py`, a step of the gate |
| 6 | the pin of the model of the registry, and the rule that a change of model re-measures | ADR-057 accepted, `ledgerlens/byok/registry.py` | a test that the model a published number names is the model the pin names |
| 7 | the trace that outlives the process, the usage on the result, the latency and the cost per case | ADR-054 decision six, T119, T132 to T140 | `tests/eval/test_runtime_numbers_documentation.py` (T140), a test that a finished run writes the file |
| 8 | the disclosure of the AI on every surface that answers a person, and the incident path | the disclosure constant of both surfaces, `README.md`, `README.pt-BR.md` | a test that asserts the sentence is in the DOM, `tests/test_public_clean.py` |
| 9 | the index of the documentation, the links from the README, the parity of the Portuguese README, `SECURITY.md` | `docs/README.md`, `docs/decisions/README.md`, the two READMEs, `SECURITY.md` | `tests/eval/test_readme_parity.py`, `tests/test_public_clean.py`, a test that the table of the ADRs is generated |
| 10 | the vector protocol | ADR-056 accepted, T126 to T131 | `tests/retrieval/test_vectorstore_boundary.py` (T129) |

The second table is the work that becomes a debt, and it is deliberately short: an item belongs here when nothing the
repository publishes today changes because of it.

| the debt | the owner | the milestone | why it can wait |
| --- | --- | --- | --- |
| the truth of the policies and of the money | the maintainer and a reader of payment operations | 22 | no number of this cycle is over the content of a policy |
| the second reader of the labels | a second reader | 22 | the disagreement count published next to the number already shows the noise of the reader |
| the methodology of the evaluation of the agent | the maintainer | 23 | the agent numbers keep the restriction they carry today (`data/eval/report_online.md:3`) |
| the classification of the system under the Act, and the question of who the provider is | the owner | 22 | the answer changes nothing a laboratory publishes |
| the inventory of what runs, and the bill of materials as a checked file | the maintainer | 22 | the artifacts that decide an answer are already pinned, and the chat model cannot be pinned by this repository at all |
| the continuity of the project | the owner | 22 | nothing published changes, but this debt decides whether there is a next cycle |

### 4. The statements the programme publishes

Not one of these sentences can be said about the repository today. They are the output of the programme, written here so
that the cycle can be checked against them.

1. **[a number with a denominator]** "On 48 cases that no decision of this repository was taken against, the verifier
   reproduced the verdict of the blind reader on a number of the 48, and the blind reader disagreed with the recipes of
   the generator on another number of the 48."
2. **[a number with a denominator]** "At the calibrated thresholds the false `supported` rate of the verifier over those
   48 cases is a number, and that is the error that lets a sentence with no backing through."
3. **[a statement about the code]** "Every number this repository publishes names the dataset it was measured over and
   the restriction that applies to that dataset, and the gate refuses a dataset that moved without the manifest moving."
4. **[a statement about the code]** "No investigation can make more provider calls than the ceiling that ADR-054
   declares, in every path that reaches a provider."
5. **[a statement about the code]** "The policy index the agent answers from carries the digest of the corpus it was
   built from, and the gate refuses an index that does not match the policies on the disk."
6. **[a statement about the code]** "The model that produced every published number is named in ADR-057 with the date
   it was verified, and a change of model re-measures against the declared thresholds before any number is republished."
7. **[a number with a denominator]** "The p50 and the p95 of a turn, and the cost of an investigation, are published
   with the thirty case denominator and the role that set carries."
8. **[a statement about the code]** "The trace of a finished run outlives the process, and it carries the evidence and
   the verdict of every claim."
9. **[a statement about the code]** "The answer you are reading was produced by an AI system, and every surface that
   answers a person says so."
10. **[a statement about the code]** "This repository publishes no certification, no conformity assessment and no
    deployment, and it says so in its own words."

### 5. What this programme does not do

These are refusals, and the repository already refuses most of them in its own words. This record collects them.

- **No certification, no conformity assessment, no registration, no marking, no internal audit and no management
  review.** The design package refuses the first in its own words
  (`docs/v3/docs/15-RISKS-AND-OPEN-DECISIONS.md:26`).
- **No claim of alignment with any framework**, and no management system of any kind. The frameworks of this decade
  delegate the criteria to the organisation, and this repository is not going to be an organisation that certifies.
- **No deployment of anything public.** It needs the decision of the security and the legal audits, and the owner did
  not ask for it.
- **No rewrite of the runtime.** The shape was decided in ADR-010 and in the proposed ADR-P007 of the v3 package
  (`docs/v3/adrs/ADR-P007-no-multiagent-by-default.md:5`).
- **No redesign of the interface.** The owner reserved it for the end of the cycle, and the measurement of the surface
  comes before the redesign.
- **No number over a set that nobody labelled.** The role is declared over the complete labelled file and never over an
  unread one (`docs/decisions/ADR-053-the-held-out-set-and-the-blind-labelling.md:159-161`).
- **No claim that a number generalises.** The repository refuses this in its own words
  (`docs/decisions/ADR-052-the-manifest-of-the-eval-datasets.md:394`); this cycle changes the sentence that says no
  dataset carries the role and not the refusal.
- **No switch to the replacement of the retired model.** The replacement behaves differently, and that difference has
  to be measured, not assumed.
- **No analytics counter and no address for the public site.** There is no public URL and no deployment workflow, so a
  counter would count the owner's own runs.
- **No new component in this cycle** unless a number that does not exist today justifies it.
- **No publication of a result over the held out set** before the labels exist and the role is declared.

### 6. The measurement of the programme itself

A programme that cannot be measured is a plan. These are the indicators, each with its denominator, and anybody,
including the owner, can read them in a year.

| # | the indicator | the denominator | today | the target |
| --- | --- | --- | --- | --- |
| 1 | the datasets that carry the role `held_out` in `data/eval/datasets.json` | the count of datasets of the manifest | 0 of 5 | 1 of 6 |
| 2 | the published numbers that do not name, in the same block of text, the dataset and its restriction | the published numbers in the two READMEs, the two reports, `docs/verification_sets.md` and `docs/evaluation.md` | not zero | 0 |
| 3 | the steps of `scripts/gate.sh` that hold a property of the quality of the system | the count of steps of the gate | 0 of 6 (`scripts/gate.sh:10-38`) | 2 of 8 |
| 4 | the changes of the model profile in `ledgerlens/byok/registry.py` not followed by a re-measurement | the changes of the profile since the date of ADR-057 | not applicable | 0 |
| 5 | the items of the first table of this record that landed without a test that holds them | the count of items of that table | not applicable | 0 |
| 6 | the age in days of the published number over the held out set | no denominator, this is a duration | the number does not exist yet | it is republished with the same denominator whenever the manifest moves or the model changes |

The failure mode is stated here, because a programme that names only its successes cannot be judged. The failure mode is
that the programme succeeds in every indicator above and the reader in 2027 learns nothing new: the gate holds, the
reports name their sets, the documentation has an index, the disclosure is in the DOM, and the one new number is over 48
cases, where the honest answer is still a fit over 48 cases, with an interval that does not separate it from the tuning
numbers. That is enforcement without a fact, and it is the outcome this record is most likely to produce, because it is
the outcome that requires the least of the one engineer. The second failure mode is the opposite one: a check that
guards a file nobody moves is a check that has never fired, and a discipline held by a convention is a discipline the
next commit breaks.

The one sentence test of the programme: **a reader, in a year, can quote one number of this repository that was measured
over data that no decision of the repository was taken against, and the gate refuses to let that number drift away from
its denominator.**

## Consequences

- **The attention of one engineer.** The reading is about three hours of one sitting
  (`docs/decisions/ADR-053-the-held-out-set-and-the-blind-labelling.md:153-158`), and that engineer is also the only
  reader of the held out set. If that person is unavailable, the order stops at step 1 and nothing else in this record
  matters. The rest of the cycle is the same engineer, and there is no second pair of hands.
- **The risk that the programme produces nothing a stranger notices.** The tree carries 188 tracked Markdown files and
  no map of them, and the reader path is one commit of the cycle. If the cycle is cut after the measurement steps, the
  reader arrives at a repository whose numbers are honest and whose documentation is still a map of nowhere. This
  record accepts that risk, because the alternative, a beautiful surface over numbers that are still a fit, is worse.
- **The risk that the compliance shaped work becomes theatre.** The refusals of section 5 exist to prevent this, and a
  refusal in a record is a sentence, while an inventory, a bill of materials and a classification page are exactly the
  files that look like compliance and that nobody but an auditor will ever open. The rule carried forward is that a
  file whose only reader is an auditor who will never open it does not land.
- **The risk that a programme of enforcement delays the one thing that would change the status of the numbers.** The
  reading can fall back: ADR-053 decides that if the reading time is not available, the labels are written by the rule
  and audited on twelve cases, and the milestone then publishes the set and no number at all
  (`docs/decisions/ADR-053-the-held-out-set-and-the-blind-labelling.md:155-158`). That fallback is the worst outcome of
  this programme and it is a real possibility, because the reading is one person and one session. The risk has a second
  form: the switch to the replacement of the retired model waits for a measurement this programme does not produce, so
  the published numbers may name a model that no longer answers on the day a reader checks them.
- **The cost of publishing the costly error.** The false `supported` rate may lower the number a reader remembers, and
  a verifier that publishes its own worst error is harder to sell than one that publishes a false positive rate of
  zero. The repository has chosen the first, and the choice is not reversible without a worse reason.
- **The cost of the strictness of the corpus.** One edit of one policy file makes the index stale and the gate red, and
  the rebuild is a manual step. That is the price of an index that stops answering instead of hiding that it answers from
  an old corpus. Nothing here adds a component, a dependency, a service or a person.

## The debt of this record

The debt of ADR-052 was the held out set, and ADR-053 paid it. The debt of ADR-053 is the held out set of the
retrieval, and that debt is not paid here either: it belongs to the milestone that owns the retrieval, and this record
only names it in the ordering, where the protocol of the vectors comes after the digest of the corpus. The debts of
this record are the six of the second table of section 3, written out with the same precision that ADR-052 and ADR-053
use.

1. **The truth of the policies and of the money.** Owner: the maintainer, with a second reader who works in payment
   operations. Milestone: 22. The corpus of `data/policies/` is the ground truth of the verifier: it is the premise a
   claim is judged against, so a deadline that is wrong makes the verifier right about a wrong thing and every number over
   it a fact about the fiction. No audit of this repository has looked at the content of those eight files, because every
   audit so far asked what the system does and not what it is talking about. The next record has to decide how the corpus
   is audited, by whom, and what a policy that the audit finds wrong does to the numbers already published over it.
2. **The second reader of the labels.** Owner: a second reader. Milestone: 22. One labeling pass has been made and the
   repository has no mechanism to version a second one (`data/eval/datasets.json:43`). The published count of the
   disagreements with the recipes is the first honest measure of a label, and a second blind pass over a subset turns it
   into an error rate. Until then, every number over the held out set carries an uncertainty that is visible but not
   quantified.
3. **The methodology of the evaluation of the agent.** Owner: the maintainer. Milestone: 23. The repository measures the
   verifier with a held out set and a calibration, and the agent with thirty cases, three runs each, an LLM judge for the
   explanation and a hand written count for the correctness. What a trajectory match means, what pass at k means for a
   system that has to be right every time, whether thirty cases and three runs can separate two variants, and what the
   judge is worth, are unmeasured. This record does not touch them, because the numbers they cover keep the restriction
   they carry today.
4. **The classification of the system, and the question of who the provider is.** Owner: the owner. Milestone: 22. The
   answer is not a legal opinion the repository can avoid, and it is not a conclusion the repository can reach either: it
   depends on the intended purpose and on what a deploying organisation does with the answer. The next record has to
   decide whether the repository states a purpose and a boundary with three open facts, or stays silent on the question of
   the provider, and the second option is legitimate for a public laboratory.
5. **The inventory and the bill of materials as a checked file.** Owner: the maintainer. Milestone: 22. The pins exist and
   they are real, and the inventory of what runs, what it reaches, what it may do and who owns it does not. The file has
   to say, for every artifact, its immutable reference, its role, its licence and the date it was verified, and it has to
   say plainly that the chat model cannot be pinned by this repository at all, so that the entry of the model that
   produced every published number is a reference and a date and not a hash.
6. **The continuity of the project.** Owner: the owner. Milestone: 22. One maintainer, a public repository, a cycle that
   has to end, and a handover that is a local file the git ignores. The next record has to decide what a handover
   contains, because the cost of this cycle is the attention of the person who is also its only reader, and that reader is
   a single point of failure with no measured error rate.
