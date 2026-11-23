---
description: "Task list for the truth of the policies and the truth of the money"
---

# Tasks: The truth of the policies and the truth of the money

**Input**: Design documents from `specs/006-r4-the-truth-of-the-policies-and-the-money/`

**Prerequisites**: plan.md (required), spec.md (required), the decision that starts the milestone
(`docs/decisions/ADR-061-the-corpus-of-the-policies-is-the-contract-of-a-fictional-company.md`) and the audit of the
truth of the policies and of the money, whose findings live in the research folder of the owner of the repository, out
of git and not published: the finding that starts this milestone is F10, the truth of the policies and of the money

**Tests**: Every task that changes the behaviour of the repository ships its test before its code, and the gate of
the Python side is green before the commit. A task that is delivered says so, with **DELIVERED** and the evidence
of what it delivered. The four tests of the audit are written to FAIL before the correction they prove, because a
test that passes before the correction would prove nothing.

**Organization**: Tasks are grouped by the milestone that delivers them, and the tasks of a milestone touch disjoint
files so that they can be worked on in parallel. The ids follow the order of the twelve gaps of the audit and the
milestones follow the order of the corrections of ADR-061, so the ids of a milestone are not consecutive. The
folder `tests/policies/` is created by T151, and the tests of the code that the gaps touch stay where they are:
`tests/tools/`, `tests/verify/`, `tests/eval/` and `tests/docs/`.

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[DELIVERED]**: the task is done, and the sentence names what it delivered
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `ledgerlens/`, `tests/`, `scripts/`, `data/`, `docs/` at repository root
- Paths shown below assume single project

## Milestone 27, the wording of the corpus, where it names the world where it names Acme

**Purpose**: the cheapest of the corrections, and the one that does not move the data.

- [ ] T151 [P] Rewrite the paragraph of the response deadline of `data/policies/chargeback-handling.md:25` so that the
  window of ten to fourteen days is the deadline of Acme and not the deadline of the card network, put the window of
  the network, thirty calendar days for the categories of Visa and the frames of Mastercard, in
  `docs/policies-of-acme.md` with the source and the date it was read, and write the test in
  `tests/policies/test_gap_01_deadline.py`, which creates the folder `tests/policies/`, that fails while a window of
  ten to fourteen days is named the deadline of the card network
- [ ] T152 [P] Rewrite the paragraph of the reason codes of `data/policies/chargeback-handling.md:21` so that FRD, NRC,
  NAD, DUP and OTH are internal codes of Acme, put the mapping to the codes of Visa and of Mastercard in
  `docs/policies-of-acme.md` with the source and the date it was read, and write the test in
  `tests/policies/test_gap_02_reason_codes.py` that fails while a paragraph presents those five codes as the codes of
  a network
- [ ] T156 [P] Correct the direction word of `data/policies/cross-currency-refunds.md:29`, so that the merchant
  applies the markup below the reference rate, keep the arithmetic and the worked example of `:41`, and write the test
  in `tests/policies/test_gap_06_markup_wording.py` that reads the paragraph, expects one direction word and
  recomputes the worked example through the calculator of the repository
- [ ] T157 [P] Say in `data/policies/fees-and-pricing.md:29` and in `data/policies/cross-currency-refunds.md:45` that
  the mode of the rounding is the choice of the platform and what the common commercial practice does with a tie, add
  one settlement with an exact half cent tie to the simulator under `ledgerlens/sim/`, and write the test in
  `tests/policies/test_gap_07_rounding_mode.py` that finds the tie in the settlements of the shipped ledger and
  expects the corpus to name the mode as a choice of the platform

## Milestone 28, the rules where the data and the text disagree, decided rule by rule

**Purpose**: four rules where the corpus and the data of the repository say opposite things, decided one by one.

- [ ] T153 Decide the rule of the negative net and make the corpus and the simulator agree: either the paragraph of
  `data/policies/settlement-schedule.md:49` states that a negative net is paid and the balance is carried into the
  next settlement and `ledgerlens/sim/pipeline.py:707` carries the balance, or the paragraph states that there is no
  payout and the simulator withholds the payout, and write the test in `tests/policies/test_gap_03_negative_net.py`
  that reads the settlements of the shipped ledger and expects a negative net either to have no payout or to be
  carried, and that the corpus states the same rule
- [ ] T154 Accept an applied rate above the reference rate in `ledgerlens/tools/calculator.py:210` when the
  difference is inside the rounding band of four decimals, report it as a rounding effect instead of raising
  `SWAPPED_RATES`, keep the refusal for a pair outside the band, and write the test in
  `tests/tools/test_calculator.py` that expects no refusal over every conversion of the shipped ledger
- [ ] T155 Read the ceiling of the implied markup with the band that the same policy defines in
  `data/policies/fx-reference-rates.md:53`, so that the paragraph of `:49` does not escalate a merchant whose
  contractual markup is exactly three percent, and write the test in `tests/policies/test_gap_05_markup_ceiling.py`
  that compares the implied markup of every refund of a merchant of the markup plan with the ceiling read with the
  band
- [ ] T159 Make the policy and the code name the same calendar of the internal cutoff: either
  `data/policies/chargeback-handling.md:29` names the calendar of the dispute record, or
  `ledgerlens/verify/escalation.py:30` reads the settlement currency of the merchant and the docstring stops
  carrying the divergence from the policy, and write the test in `tests/verify/test_escalation.py` that counts the
  cutoff of a dispute whose currency is not the settlement currency of the merchant and expects the code and the
  policy to agree

## Milestone 29, the floors that a house rule may not cross

**Purpose**: the corpus states the floor of the law, so that an analyst can tell a statutory floor from a commercial
term.

- [ ] T158 State the floor of fourteen days with the source of the law in the paragraph of the time to pay of
  `data/policies/refund-policy.md:37`, say in the paragraph of the window at `:17` that the window is a house rule
  that cannot be narrower than the right of withdrawal, and write the test in
  `tests/policies/test_gap_08_refund_floor.py` that reads the paragraph and expects the floor and the source in it.
  The set of the held out cases keeps the excerpt of its generation, so the correction of the paragraph does not
  change the cases

## Milestone 30, the marker of the fiction in every chunk served

**Purpose**: an excerpt that is read out of its file still says that the company is fictional.

- [ ] T160 [P] Carry the marker that Acme Payments is a fictional company in the metadata of every chunk of the index
  in `ledgerlens/retrieval.py:96` and in the note of every result of the tool in `ledgerlens/tools/policies.py:70`,
  rebuild the committed index under `data/index/policies_fastembed/`, and write the test in
  `tests/policies/test_gap_10_fiction_marker.py` that reads the metadata of every chunk and the test in
  `tests/tools/test_policies.py` that reads every result of the tool

## Milestone 31, the way to cite a rule of the world next to a policy

**Purpose**: an answer that is right about the real world can be cited, and the conflict is named.

- [ ] T161 Add a kind of evidence for a rule of the world, with the URL of the source and the date it was read, to
  `ledgerlens/verify/claims.py:54` and to the envelope of `ledgerlens/tools/envelope.py`, make
  `ledgerlens/verify/checks.py` name the conflict between a cited rule of the world and a cited policy instead of
  scoring a plain contradiction, keep the discipline that the numbers come from the tool and the label comes from the
  evidence, and write the tests in `tests/verify/test_claims.py` and in `tests/verify/test_checks.py` that expect the
  new kind of evidence and a named conflict

## Milestone 32, the notice of the sources and the lock

**Purpose**: the conditions of the central bank are quoted and the derived recordings say so.

- [ ] T162 [P] Quote the three conditions of the European Central Bank in `NOTICE` and state there that the cross
  rates of the committed recordings are computed through the euro by this project, replace the string of the lock in
  `data/sources.lock.json` with the notice of the ECB, and write the test in `tests/test_notice_sources.py` that reads
  the notice and the lock and refuses a licence string that the ECB does not publish

## Milestone 33, the document of the truth of the policies

**Purpose**: one document that says what is real and what is a house rule of a fictional company.

- [ ] T163 [P] Write `docs/policies-of-acme.md` with one section for each one of the eight policies of
  `data/policies/`, saying for every rule whether it is a rule of the world, a house rule of Acme or an invention of
  this project, with the URL of the source and the date it was read, and with the caveats of the audit next to the
  rules it marked as unverified
- [ ] T164 [P] Write `tests/docs/test_policies_of_acme.py` that reads `docs/policies-of-acme.md`, expects every one of
  the eight policies to be named, expects a source and a date for every rule of the world, and expects the caveats of
  the audit next to the rules that it marked as unverified

## Milestone 34, the four tests of the audit

**Purpose**: four tests that hold the four findings of the audit that are a matter of the data and not of a wording.

- [ ] T165 [P] Write `tests/policies/test_corpus_sources.py` that reads the eight policies of `data/policies/` and
  fails while a paragraph names an external body, the card network, the central bank or the law, without the source
  and the date in the same paragraph. The test is written to FAIL before the corrections of the corpus, because a
  test that passes before the correction would prove nothing
- [ ] T166 [P] Write `tests/policies/test_corpus_against_simulator.py` that reads the manifest of the scenarios and
  the policies and fails while a policy states a rule of the world that the simulator contradicts, with the rule of
  the negative net as the first case. The test is written to FAIL before the correction of that rule, because a test
  that passes before the correction would prove nothing
- [ ] T167 [P] Write `tests/policies/test_corpus_markup_band.py` that reads the shipped ledger and fails while the
  implied markup of a refund of a merchant of the markup plan is outside the band that
  `data/policies/fx-reference-rates.md` defines, which today happens on sixteen of the two hundred and thirty refunds.
  The test is written to FAIL before the correction of the ceiling, because a test that passes before the correction
  would prove nothing
- [ ] T168 [P] Write `tests/policies/test_corpus_rate_band.py` that reads the shipped ledger and the table of the
  rates and fails while an applied rate is outside the rounding band of the reference of the same day, which today
  happens on nine of the two hundred and thirty refunds, and that expects the calculator of the repository to accept
  every pair that the ledger contains. The test is written to FAIL before the correction of the guard, because a test
  that passes before the correction would prove nothing

## Milestone 35, the sentence about a policy that is wrong and the set that is frozen

**Purpose**: the analyst is told that a contradiction may mean that the policy is wrong, and the held out set keeps
the corpus of its generation.

- [ ] T169 [P] Write the sentence in `data/policies/escalation-and-review.md` that says that a contradiction with a
  policy may mean that the policy is wrong, next to the paragraph of the contradicted claims of `:21`, and keep the
  sentence that the system does not resolve contradictions by picking a side, with the test in
  `tests/policies/test_escalation_wording.py` that expects the sentence in the corpus
- [ ] T170 Keep the held out set as the corpus of its generation: do not write into `data/eval/heldout/`, and write the
  test in `tests/eval/test_heldout_frozen_excerpts.py` that reads `data/eval/heldout/cases.jsonl` and expects the
  excerpt of every policy citation to be the text of the corpus of the generation and not the text of the corrected
  corpus
  - **DELIVERED**: the cases of the set exist in `data/eval/heldout/cases.jsonl` with 48 cases, each one carrying the
    text of its excerpt inside it, and the first reading of ADR-059 is in `data/eval/heldout/labels_reader_a.jsonl`
    with 48 labels. The excerpts inside the cases are the ones of the corpus of the generation, and a correction of
    the corpus does not change them

## Milestone 36, the rebuild of what the corpus pins and the record of the milestone

**Purpose**: everything that is pinned to the corpus is pinned to the corrected corpus, and the decisions of the
milestone are written down.

- [ ] T171 Rebuild the committed index of the policies over the corrected corpus with `scripts/build_index.py`,
  refresh the pin of the calibration with `scripts/pin_calibration.py`, update the sha256 of the datasets that the
  corpus touched in `data/eval/datasets.json`, and expect the digests of the disk in the check of the index of
  `scripts/gate.sh` and in `tests/verify/test_calibration_pin.py`
- [ ] T172 Write the record of the milestone in `docs/decisions/`, with the next number after ADR-061, which writes
  down the rule by rule decisions of the twelve gaps, the class of every rule of the corpus, the debts that the
  milestone does not pay and the fact that the held out set is never regenerated, and link it from
  `docs/decisions/README.md`
