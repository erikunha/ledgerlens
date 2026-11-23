# Implementation Plan: The truth of the policies and the truth of the money

**Branch**: `feature/v3` | **Date**: 2026-11-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/006-r4-the-truth-of-the-policies-and-the-money/spec.md`

## Summary

The milestone makes the corpus of `data/policies/` say what it is. The corpus is the contract of Acme Payments, a
fictional company, and not a description of payments as they are. Today the corpus says the second in its wording
and the first in its effect: the verifier judges every answer against it and the agent quotes it to merchants, so a
rule of a fiction is enforced as if it were a rule of the world.

The audit of the truth of the policies and of the money found twelve places where the corpus says something the
world does not say, or something the data of this repository contradicts: a window of ten to fourteen days called
the deadline of the card network, reason codes that no network uses, a corpus that says a negative net gets no
payout while the simulator pays two such settlements, a calculator that refuses nine rows of the ledger that are
inside the rounding band of four decimals, a ceiling of three percent read without the band that the same policy
defines, a sentence that says "over the reference rate" and then subtracts the markup, a tie rule of rounding
presented as a rule when it is a choice of the platform, a refund policy with no statutory floor, a policy and a
code that disagree about the calendar of the internal cutoff, a fiction that is not carried by the chunks of the
index, a claim that may cite only what is inside this repository, and a notice of the sources that states two
conditions where the source states three.

The milestone starts from
[ADR-061](../../docs/decisions/ADR-061-the-corpus-of-the-policies-is-the-contract-of-a-fictional-company.md),
which decides that the corpus is the contract of a fictional company, that the rules of the world live in
[docs/policies-of-acme.md](../../docs/policies-of-acme.md) with the source and the date of each, that a
contradiction with a policy may mean that the policy is wrong, and that the held out set freezes the corpus of its
generation. The order of the corrections is the order of that record: the wording first, the rules where the data
and the text disagree decided rule by rule, the floors that a house rule may not cross, the marker of the fiction in
the chunks of the index, and the notice and the lock of the sources. The four tests of the audit are written to
fail before the correction each one proves, because a test that passes before the correction would prove nothing.

The technical approach keeps the Python core as the authority. A correction of the corpus is a correction of a
Markdown file, and the test that holds it is a test that reads the Markdown file. The money stays in `Decimal`,
the calculator refuses nothing that the rounding band of the policy allows, and the verifier keeps its discipline:
the numbers come from the tool and the label comes from the evidence, and the verifier never picks a side.

## The audit that starts the milestone

The audit is the finding F10, the truth of the policies and of the money, read on 2026-11-22 and written on
2026-11-23. Its findings live in the research folder of the owner of the repository, out of git and not published,
because the repository is public. The audit was a read only pass: it opened the eight policies, the code that judges
and the code that computes, the
shipped ledger `data/runtime/sandbox-bases/ledger.db` in read only mode, and the sources of the world with their
dates.

The audit holds the twelve gaps in a table with, for each one, the file it touches, what is wrong with the evidence,
what the change would be, how one would know it worked, and whether it may be done now. It holds the arithmetic
that was recomputed with `Decimal`, and the sources with their URLs and the dates they were read. It also holds a
section named "What I did not check", and every one of those points is a debt that this milestone does not pay and
that the last section of this plan lists.

Two findings of the audit are not gaps and are recorded here so that nobody reopens them: the netting identity and
the fee formula hold on every row of the ledger, and the schema of the database carries the identity as a
constraint, and the charge conversion carries no markup on every charge row of the ledger.

## Technical Context

**Language/Version**: Python 3.12 for the core
**Primary Dependencies**: the existing `ledgerlens` core, `fastembed` for the embedding of the policies, and the
`holidays` library for the business day calendars
**Architecture**: the corpus of the policies is the contract of Acme and the rules of the world live in a document
apart from it; every correction of the corpus is a correction of a Markdown file with a test that reads it, and the
four tests of the audit read the corpus and the data together
**Storage**: the eight policies of `data/policies/`, the committed index of the policies under
`data/index/policies_fastembed/`, the document of the truth of the policies under `docs/`, and the lock of the
sources in `data/sources.lock.json`
**Testing**: pytest offline with `LEDGERLENS_OFFLINE=1`, and the scripted model for the agent
**Constraints**: no key and no network in the gate, money as `Decimal`, no change in `docs/v3/`, and no rewrite of
the simulator outside the tasks that say so

## The milestones of the release

| Milestone | What it delivers | State |
|---|---|---|
| M27 | The wording of the corpus, where it names the world where it names Acme | Next |
| M28 | The rules where the data and the text disagree, decided rule by rule | Later |
| M29 | The floors that a house rule may not cross | Later |
| M30 | The marker of the fiction in every chunk served | Later |
| M31 | The way to cite a rule of the world next to a policy | Later |
| M32 | The notice of the sources and the lock | Later |
| M33 | The document of the truth of the policies, with the test that it names every policy | Later |
| M34 | The four tests of the audit, each one written to fail before its correction | Later |
| M35 | The sentence about a policy that is wrong, and the held out set that is frozen | Later |
| M36 | The rebuild of what the corpus pins, and the record of the milestone | Later |

## The order, and why it is that order

The order is the order of ADR-061, and it is the order of the cost of a correction.

**The wording comes first.** The wording is the cheapest part of the milestone and it does not move the data: a
paragraph of `data/policies/chargeback-handling.md` that calls a window of ten to fourteen days the deadline of the
card network becomes the deadline of Acme, and the reason codes become internal codes with the mapping to the codes
of the networks in the document of the truth. The sentence that says "over the reference rate" says "below" and
keeps the arithmetic. The sentence about the tie of the rounding says that the mode is the choice of the platform.
None of these four corrections moves a row of the ledger, so none of them moves the digest of the index, and the
guard of the repository can stay green while they happen.

**The rules where the data and the text disagree come next.** The negative net, where the policy and the simulator
say opposite things; the band of the applied rate, where the code refuses nine rows that are inside the rounding
band; the ceiling of the markup, read with the band that the same policy defines; and the calendar of the internal
cutoff, where the policy and the code disagree about the currency. These four are decided rule by rule, because
they are not the same kind of question. The negative net is a question about the design of the world of the demo,
and ADR-061 refused to answer it in advance. The band of the applied rate and the ceiling of the markup are
arithmetic, and the arithmetic of the ledger decides them. The calendar of the internal cutoff is a reading of a
docstring that says in writing that it diverges from the policy.

**The floors come after the rules.** A floor is a limit that a house rule may not cross, and a floor that is
published changes what a house rule may say. The refund policy states the floor of fourteen days with its source,
and the window of the policy stays a house rule that cannot be narrower than the right of withdrawal. Publishing a
floor before the rules that the floor limits would give the corpus a limit it does not yet respect.

**The marker of the fiction comes after the text.** The marker travels in the metadata of every chunk of the index
and in the result of the tool, and the metadata of the chunk is built from the corpus. A marker that is written
before the text settles would be carried by chunks of a corpus that is about to change.

**The notice and the lock come last.** They are the cheapest of the twelve and they are the last because they name
what the corpus and the recordings are, and they should name the finished thing.

**The way to cite a rule of the world is the largest of the twelve and it needs the decision record first.** It
touches the evidence id scheme of the verifier, the envelope of the tools and the checks that turn a premise into
a label. It comes after the wording, because the wording decides what a policy may say about the world, and the
citation decides what an answer may say next to it.

**The document and the four tests come after the corrections, and the rebuild comes last.** The document names what
the corpus is, and it can only name it when the corpus says what it is. The four tests of the audit are written
before the corrections they prove, and they are read once the corrections are in. The rebuild of the index, the
refresh of the pin and the update of the manifest come last of all, because they describe a corpus that no longer
moves.

## The rules that apply to every milestone of this release

1. The corpus of the policies states the contract of Acme and never a claim about the world.
2. A rule of the world lives in `docs/policies-of-acme.md` with the source that supports it and the date it was
   read.
3. A paragraph of the corpus that names an external body carries that source and that date in the same paragraph.
4. A test of the audit is written to fail before the correction it proves.
5. The numbers come from the tool and the label comes from the evidence, and the verifier never picks a side.
6. A contradiction with a policy may mean that the policy is wrong, and the analyst is told so.
7. The held out set is never regenerated, and a correction of the corpus never changes its cases.
8. Every decision that restricts the future becomes an ADR in `docs/decisions/`.

## The risks

- **A correction that moves the corpus moves everything that is pinned to it.** Every correction moves the bytes of
  the corpus, so it moves the sha256 of the corpus that the index carries
  ([ADR-055](../../docs/decisions/ADR-055-the-policy-index-carries-the-hash-of-the-corpus.md)), the pin of the
  calibration
  ([ADR-007](../../docs/decisions/ADR-007-nli-verification.md)), and the sha256 of the datasets that the manifest
  of the datasets carries. The guard is the last task of the milestone: the index is rebuilt over the corrected
  corpus, the pin is refreshed and the manifest is updated, in one pass, and the check of the gate refuses the
  repository that was not updated.
- **A correction of the wording that changes the meaning instead of the claim.** The risk is the sentence about the
  markup, whose arithmetic is right and whose word is wrong. The guard is a test that reads the paragraph and
  asserts the direction, and a test that recomputes the worked example of the policy through the calculator of the
  repository.
- **A correction of the rules that decides the wrong way.** The negative net is the sharpest internal disagreement
  of the audit and the two negative controls of the held out set depend on it. The guard is a test that reads the
  settlements of the shipped ledger and asserts that a negative net either has no payout or is carried into the
  next settlement, and the choice is written down in the record of the milestone.
- **A floor that a house rule cannot live with.** Publishing the floor of the law may make a window of the corpus
  narrower than the law allows. The guard is the test of the floor and the check of the window of every merchant of
  the scenarios.
- **A marker of the fiction that is carried by the chunk and dropped by the tool.** The metadata of the chunk and
  the result of the tool are two different places. The guard is a test on every chunk of the index and a test on
  every result of `search_policies`.
- **A citation of a rule of the world that becomes a new claim of the repository.** The verifier must not start
  judging the world. The guard is that the new kind of evidence names the conflict and does not label the claim, and
  that the numbers still come from the tool.
- **A notice that promises more than the repository does.** The notice must state the three conditions of the ECB
  and say that the cross rates of the recordings are computed by this project. The guard is a test that reads the
  notice and the lock and refuses a licence string that the source does not publish.
- **A held out set that is regenerated by accident.** The set is the most expensive act of the milestone and it was
  read over the corpus of its generation. The guard is that no task of this milestone writes into
  `data/eval/heldout/` and that a test reads the excerpts of the cases and finds the text of the generation.

## The strategy for the validation

Every task ships its test before its code, and the gate of the Python side is the one that runs everywhere, including
in the continuous integration. The four tests of the audit are the heart of the validation: the test of the sources
in the same paragraph, the test of the corpus against the simulator, the test of the implied markup inside the band
and the test of the applied rate inside the rounding band of the same day. Each of them fails today, on the corpus
and on the data of today, and each of them passes after the corrections it proves. A test of the audit that passed
before the correction would have proved nothing, so the order of the work is the proof.

## What is out of scope

- The simulator is not rewritten in this milestone, except where a task says so. The only exception is the settlement
  with an exact half cent tie that the gap of the rounding mode asks for, and the negative net rule when the rule
  by rule decision is to correct the data instead of the text.
- The held out set is not regenerated and its labels are not read again.
- The frontend is not touched. The interface of the repository may show the corpus of the corrected policies, and no
  task of this milestone changes a page of `apps/web/`.
- The rules of the world are not verified beyond the sources that the audit read on 2026-11-22, and the document of
  the truth says so next to each rule.
- The licences of the BIN list and of Nager.Date are not audited, and the terms of the hosted service of Nager.Date
  are not read.
- The API layer, the replay harness and the export are not checked.

## The definition of done

1. The twelve gaps of the audit are closed, each one by a test that fails before the correction and passes after it.
2. The four tests of the audit are in the suite and are green.
3. The document of the truth of the policies exists, names every one of the eight policies and carries the source and
   the date of each rule of the world.
4. Every chunk of the index and every result of the policy tool carries the marker that the company is fictional.
5. A claim may cite a rule of the world next to a policy, and a conflict between the two is a named finding.
6. The escalation policy says that a contradiction with a policy may mean that the policy is wrong.
7. The index is rebuilt over the corrected corpus, the pin of the calibration is refreshed and the sha256 of the
   datasets of the manifest is updated, and the gate is green.

## The debt this milestone does not pay

Every item below is a debt that the audit named, in its own words. None of them is closed by a task of this
milestone, and the ones that are marked as an inference stay marked as an inference in the document of the truth.

- The exact 30 calendar day response window of Visa comes from two secondary sources, Verdikx and disputed.ai. The
  primary document that the audit read states that every step of the dispute has a strict deadline and that the
  acquirer decides the timeline, and it does not print the number. The document of the truth carries the number with
  that caveat.
- The provision of the United Kingdom was not located. The audit read a section of the Consumer Rights Act 2015 that
  is not the refund period provision, so the UK citation is unverified and is not cited.
- The refund rule of Regulation (EU) 2015/751, which governs the card side of the business, was not verified and is
  not cited by any finding.
- The Brazilian right of regret of seven days for online purchases, which is shorter than the fourteen of the Union
  and relevant to the merchants of the corpus that trade in Brazil, was not verified at all.
- The label that a sentence contradicting a policy excerpt would receive is an inference from the reading of the
  code path of the verifier and of the thresholds. The NLI model was not run on such a sentence.
- The statement that the policy should name the rounding mode as a choice of the platform is the judgement of the
  audit, and not a measurement. The measurement that the audit did make is that no row of the ledger exercises the
  tie.
- The dispute rate of the simulator is calibrated from the statistics of Pix, which is an instant payment with no
  chargeback, and the audit did not look for the threshold of the networks in that pass, so no figure is stated for
  it.
- The audit did not check the git history of the policies, so it does not know when each rule was written or whether
  any of them was ever checked against a source.
- The corpus never states the rate of disputes, so the cost of the calibration stays bounded and is not a gap.

## The questions the coordinator answered

- **Which of the two is the design, the text or the simulator, for the negative net.** The specification does not
  decide it, because ADR-061 refused to decide it in advance: it is a question about the world of the demo and not
  about the truth of a rule. The task of the gap decides it rule by rule, and the record of the milestone writes the
  decision down with the test that holds it.
- **Where the tests of the corpus live.** The folder `tests/policies/` is created, because the corpus is a domain
  area of the repository and the tests that read the eight files and the data together belong next to the corpus
  they protect. The tests of the code that the gaps touch stay where they are: `tests/tools/`, `tests/verify/` and
  `tests/eval/`.
- **How a rule of the world is cited.** With a new kind of evidence that carries the URL and the date of the source,
  next to a citation of a policy. The verifier names the conflict and does not label the claim, because a rule of
  the world is not a premise that the repository can decide.
- **The document of the truth of the policies.** It is `docs/policies-of-acme.md`, it is written in parallel with this
  milestone and it is a requirement of the specification with a test that checks that it exists and names every
  policy.
- **The name of the record of the milestone.** The decision that starts the milestone is ADR-061. The record of the
  corrections is the one that writes down the rule by rule decisions, and it is the next number of the folder
  `docs/decisions/`.
