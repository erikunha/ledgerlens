# Feature Specification: The truth of the policies and the truth of the money

**Feature Branch**: `feature/v3`

**Created**: 2026-11-23

**Status**: Draft

**Input**: Design documents: `docs/decisions/ADR-061-the-corpus-of-the-policies-is-the-contract-of-a-fictional-company.md`,
`docs/decisions/ADR-055-the-policy-index-carries-the-hash-of-the-corpus.md`, `docs/decisions/ADR-007-nli-verification.md`
and `docs/decisions/ADR-059-the-held-out-set-is-read-by-two-blind-machines-and-adjudicated.md`. The audit of the truth of
the policies and of the money, read on 2026-11-22 and written on 2026-11-23, whose findings live in the research folder
of the owner of the repository, out of git and not published: the finding that starts this milestone is F10, the truth of
the policies and of the money. User
description: "The corpus of `data/policies/` is the contract of Acme Payments, a company that does not exist, and it
is written as if it described payments as they are. The milestone closes the twelve gaps of the audit, states the
truth of the policies in a document of its own, and writes the four tests that hold them."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read a policy excerpt and know the company is fictional (Priority: P1)

The analyst asks a question about a rule and the tool serves a passage of the corpus. The passage says that Acme
Payments is a fictional company, and the marker is in the metadata of the excerpt and in the result of the tool, so
it travels even when the excerpt is read out of its file.

**Why this priority**: the fiction is stated in one policy of eight and in no chunk of the index, so today a served
excerpt reads as the operating rule of a real company.

**Independent test**: load the index of the policies and read the metadata of every chunk, then call the policy tool
and read every result. The marker is in the metadata of every chunk and in the note of every result.

### User Story 2 - Answer what the network really does, with the source (Priority: P1)

A merchant asks whether the deadline in the dispute record is the deadline of the card network. The analyst answers
that it is the deadline of Acme, that the window of the network is thirty calendar days for the categories of Visa
and the frames of Mastercard, and that the window of the network, the reason codes of the networks and the floor of
the law live in `docs/policies-of-acme.md`, with the source of each and the date it was read.

**Why this priority**: the corpus is the contract of a fictional company, and a reader needs one document that says
what is real and what is a house rule.

**Independent test**: read the document of the truth of the policies and check that it names the eight policies, that
every rule it states as a rule of the world carries a source and a date, and that the caveats the audit marked as
unverified are marked there too.

### User Story 3 - Cite a rule of the world next to a policy and name the conflict (Priority: P1)

The agent cites the law of the Union with its URL and the date it was read, next to the citation of the policy of the
refunds of Acme, and states that the consumer has the right to be reimbursed within fourteen days. The verifier names
the conflict between the two and does not label the claim, because a rule of the world is not a premise that the
repository can decide.

**Why this priority**: without a way to cite the world, an answer that is right about the real world can only be
contradicted or marked as not enough evidence, and both send a correct answer to a person for the wrong reason.

**Independent test**: build a claim that cites the law of the Union next to a passage of the corpus that says
otherwise, and run the checks. The result carries a named conflict and not a plain contradiction.

### User Story 4 - Compute the gap of a refund that the calculator used to refuse (Priority: P1)

The analyst asks for the breakdown of the difference of a refund of pounds sterling whose applied rate is 0.8590 and
whose reference of the same day is 0.85898. The calculator does not refuse the pair: the difference is inside the
rounding band of four decimals, so the tool answers and says that the difference is a rounding effect.

**Why this priority**: a guard that fires on nine real rows of the repository takes the answer away from the
analyst for the rows that the data really has.

**Independent test**: run the breakdown of the difference over every conversion of the shipped ledger and expect no
refusal, and run it over a pair that is outside the band and expect the refusal.

### User Story 5 - Explain a merchant at the ceiling of the markup without escalating (Priority: P1)

The analyst asks whether the implied markup of a refund is over the limit of the plan. The answer reads the ceiling
of three percent with the band of five hundredths of a point that the same policy defines four lines below it, so the
sixteen refunds of the merchants at exactly three percent are inside the band.

**Why this priority**: the policy has the answer four lines below the rule that fires, and a compliant merchant is
escalated sixteen times in the data of the repository.

**Independent test**: read the ledger, compute the implied markup of every refund of a merchant of the markup plan
and compare it with the ceiling read with the band. Every row is inside.

### User Story 6 - Explain a settlement with a negative net with the rule the data follows (Priority: P2)

The merchant asks why a settlement whose net is negative was paid. The analyst answers with the rule of Acme, and the
rule it quotes is the rule that the simulator of the repository performs, because the corpus and the data say opposite
things today.

**Why this priority**: this is the sharpest internal disagreement of the audit, and the two negative controls of the
held out set are built on it.

**Independent test**: read the settlements of the shipped ledger and assert that a settlement with a negative net
either has no payout or carries the balance into the next settlement, and assert that the corpus states the same
rule.

### Edge Cases

- A rule of the corpus that names an external body and states no source: the paragraph fails the test of the
  sources, and the correction is to say that the rule is a house rule of Acme.
- A rule of the world that the audit marked as unverified: the document carries it with the caveat of the audit, in
  the same words, and the caveat is part of the rule.
- A merchant at exactly the ceiling of the markup whose implied markup is above the ceiling by the rounding of the
  fourth decimal: the case is inside the band and is not escalated.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** (gap 1 of the audit): The corpus states the deadline of Acme and not the deadline of the card network,
  and the window of the network is a rule of the world that lives in the document of the truth, with its source and
  its date.
  - Test: `tests/policies/test_gap_01_deadline.py` fails while a window of ten to fourteen days is named the
    deadline of the card network.
- **FR-002** (gap 2 of the audit): The reason codes FRD, NRC, NAD, DUP and OTH are internal to Acme, and the mapping
  to the codes of the networks is in the document of the truth, with its source and its date.
  - Test: `tests/policies/test_gap_02_reason_codes.py` fails while a paragraph presents those five codes as the
    codes of a network.
- **FR-003** (gap 3 of the audit): The corpus states one rule of the negative net and the simulator performs that
  same rule, so that a negative net either has no payout or is carried into the next settlement, and the decision
  of which one is the design is written down in the record of the milestone.
  - Test: `tests/policies/test_gap_03_negative_net.py` expects the rule of the data and the rule of the corpus to
    be the same.
- **FR-004** (gap 4 of the audit): The calculator accepts an applied rate above the reference rate when the
  difference is inside the rounding band of four decimals, and it reports the difference as a rounding effect
  instead of refusing the pair.
  - Test: `tests/tools/test_calculator.py` expects no refusal over every conversion of the shipped ledger, and
    expects the refusal for a pair outside the band.
- **FR-005** (gap 5 of the audit): The ceiling of the implied markup is read with the band that the same policy
  defines, and a merchant whose contractual markup is at the ceiling is not escalated for an effect of the rounding.
  - Test: `tests/policies/test_gap_05_markup_ceiling.py` expects every implied markup of a merchant of the markup
    plan to be inside the band.
- **FR-006** (gap 6 of the audit): The cross currency policy says that the merchant applies the markup below the
  reference rate, and the arithmetic of the paragraph and of the worked example stays the one it is.
  - Test: `tests/policies/test_gap_06_markup_wording.py` asserts one direction word and recomputes the worked
    example through the calculator of the repository.
- **FR-007** (gap 7 of the audit): The corpus says that the mode of the rounding is a choice of the platform and
  what the common commercial practice does with a tie, and the data holds one settlement with an exact half cent tie.
  - Test: `tests/policies/test_gap_07_rounding_mode.py` finds the tie in the settlements of the shipped ledger and
    expects the corpus to name the mode as a choice of the platform.
- **FR-008** (gap 8 of the audit): The refund policy states the floor of fourteen days with its source, and says
  that the window of the policy is a house rule that cannot be narrower than the right of withdrawal.
  - Test: `tests/policies/test_gap_08_refund_floor.py` reads the paragraph of the time to pay and expects the floor
    and its source in it.
- **FR-009** (gap 9 of the audit): The policy and the code name the same calendar of the internal cutoff, and the
  docstring of the code carries no divergence from the policy.
  - Test: `tests/verify/test_escalation.py` counts the cutoff of a dispute whose currency is not the settlement
    currency and expects the code and the policy to agree.
- **FR-010** (gap 10 of the audit): Every chunk of the index of the policies carries the marker that the company is
  fictional, and so does every result of the policy tool.
  - Test: `tests/policies/test_gap_10_fiction_marker.py` reads the metadata of every chunk and
    `tests/tools/test_policies.py` reads every result of the tool.
- **FR-011** (gap 11 of the audit): A claim may cite a rule of the world next to a policy, with the URL of the source
  and the date it was read, and a conflict between the two is a named finding and not a plain contradiction.
  - Test: `tests/verify/test_claims.py` accepts the new kind of evidence and `tests/verify/test_checks.py` expects
    a named conflict for a claim that cites a rule of the world next to a policy that says the opposite.
- **FR-012** (gap 12 of the audit): The notice of the sources quotes the three conditions of the ECB and states that
  the cross rates of the committed recordings are computed through the euro by this project, and the lock holds the
  notice of the ECB.
  - Test: `tests/test_notice_sources.py` reads the notice and the lock and refuses a licence string that the ECB
    does not publish.
- **FR-013** (item 4 of the audit): The document of the truth of the policies exists, names the eight policies, and
  says for each rule whether it is a rule of the world, a house rule of Acme or an invention of this project, with
  the source and the date.
  - Test: `tests/docs/test_policies_of_acme.py` expects the eight policies and the caveat of each rule that the
    audit marked as unverified.
- **FR-014** (item 5 of the audit, first test): No paragraph of the corpus states a rule of an external body without
  the source that supports it and the date it was read in the same paragraph.
  - Test: `tests/policies/test_corpus_sources.py` fails while a paragraph names the card network, the central bank
    or the law without its source and its date.
- **FR-015** (item 5 of the audit, second test): No policy states a rule of the world that the simulator of the
  repository contradicts.
  - Test: `tests/policies/test_corpus_against_simulator.py` reads the manifest of the scenarios and the policies
    and expects no rule of the corpus that the data of the simulator contradicts.
- **FR-016** (item 5 of the audit, third test): Every implied markup of a merchant of the markup plan is inside the
  band that the policy of the reference rates defines.
  - Test: `tests/policies/test_corpus_markup_band.py` reads the shipped ledger and expects every implied markup of
    a merchant of the markup plan to be inside the band.
- **FR-017** (item 5 of the audit, fourth test): Every applied rate of the shipped ledger is inside the rounding
  band of the reference of the same day, and the calculator accepts every pair that the ledger contains.
  - Test: `tests/policies/test_corpus_rate_band.py` reads the shipped ledger and the table of the rates and expects
    every applied rate inside the band and no refusal of the calculator over the pairs of the ledger.
- **FR-018** (the open question 3 of the audit and ADR-061): The escalation and review policy says that a
  contradiction with a policy may mean that the policy is wrong, and the verifier still never picks a side.
  - Test: `tests/policies/test_escalation_wording.py` expects the sentence and `tests/verify/test_checks.py` expects
    that the verifier does not resolve a contradiction by picking a side.
- **FR-019** (ADR-061): The held out set is never regenerated by a correction of the corpus, its cases keep the
  excerpts of the corpus of their generation, and the two negative controls keep depending on that rule.
  - Test: `tests/eval/test_heldout_frozen_excerpts.py` expects the excerpts of the generation, and no task of this
    milestone writes into the folder of the set.
- **FR-020** (ADR-055, ADR-007 and the manifest of the datasets): Every correction of the corpus is followed by a
  rebuild of the index, a refresh of the pin of the calibration and an update of the sha256 of the datasets of the
  manifest, and the gate refuses a repository that was not updated.
  - Test: `tests/verify/test_calibration_pin.py` and the check of the index of `scripts/gate.sh` expect the digests
    of the disk.

### Key Entities

- **Acme contract**: one of the eight documents of `data/policies/`, which states the rules of a fictional company
  and never a rule of the world.
- **Rule of the world**: a rule with a source and the date it was read, published in the document of the truth.
- **Document of the truth of the policies**: `docs/policies-of-acme.md`, which names every policy and source.
- **Marker of the fiction**: the statement that Acme Payments is fictional, carried by the metadata of every chunk of
  the index and by the note of every result of the policy tool.
- **Rounding band**: the band of four decimals of a rate and the band of five hundredths of a point of an implied
  markup, both defined by the policies of the corpus.
- **Conflict**: the finding that names a cited rule of the world that disagrees with a cited policy, and not a label
  of the claim.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The phrase that names a window of ten to fourteen days the deadline of the card network is not in the
  corpus, and no paragraph presents the five reason codes of Acme as the codes of a network.
- **SC-002**: Every settlement of the shipped ledger with a negative net either has no payout or carries the balance
  into the next settlement, and the corpus states that rule.
- **SC-003**: The calculator answers the breakdown of the difference for every conversion of the shipped ledger.
- **SC-004**: No refund of a merchant of the markup plan is escalated for an implied markup that is inside the band
  that the policy defines, and the paragraph of the markup states one direction.
- **SC-005**: The corpus names the mode of the rounding as a choice of the platform, and the data holds one
  settlement with an exact half cent tie.
- **SC-006**: The paragraph of the time to pay a refund carries the floor of fourteen days and its source.
- **SC-007**: The policy and the code count the internal cutoff on the same calendar, and the docstring of the code
  carries no divergence from the policy.
- **SC-008**: Every chunk of the index and every result of the policy tool carries the marker of the fiction.
- **SC-009**: A claim may cite a rule of the world with its URL and its date, and a conflict between the two is a
  named finding and not a plain contradiction.
- **SC-010**: The notice of the sources carries the three conditions of the ECB and the statement that the cross
  rates of the recordings are computed by this project, and the lock carries the notice of the ECB.
- **SC-011**: The document of the truth of the policies names the eight policies and the source of every rule of
  the world.
- **SC-012**: The four tests of the audit are green, and each of them was seen failing before its correction.
- **SC-013**: The held out set keeps the excerpts of the corpus of its generation and is not regenerated.
- **SC-014**: The index is rebuilt over the corrected corpus, the pin of the calibration is refreshed and the sha256
  of the datasets of the manifest is updated.
- **SC-015**: The whole suite runs offline with `LEDGERLENS_OFFLINE=1`, with no key and no network.

## Assumptions

- The audit of the truth of the policies and of the money is the evidence of this milestone, and it is a read only
  pass of 2026-11-22 over the eight policies, the code that judges, the code that computes and the shipped ledger
  `data/runtime/sandbox-bases/ledger.db`. It modified nothing in the repository and it did not run the test suite,
  the gate or the build, so every statement of the audit about what passes is a statement about what the code says.
- The exact 30 calendar day response window of Visa comes from two secondary sources, and the primary document that
  the audit read states that the deadlines exist without printing the number, so the document of the truth carries the
  number with that caveat.
- The provision of the United Kingdom was not located, so the citation of the United Kingdom is unverified and is not
  cited. The refund rule of Regulation (EU) 2015/751 and the Brazilian right of regret of seven days were not
  verified, and neither is cited.
- The label that a sentence contradicting a policy excerpt would receive is an inference from the code path of the
  verifier and of the thresholds, because the NLI model was not run on such a sentence.
- The statement that the mode of the rounding should be named as a choice of the platform is the judgement of the
  audit and not a measurement. The measurement is that no row of the ledger exercises the tie.
- Which of the two is the design for the negative net, the text or the simulator, is not decided by this
  specification: ADR-061 refused to decide it in advance and the task of the gap decides it rule by rule.
- The document of the truth of the policies is written in parallel with this milestone, and the specification names
  it as a requirement with a test that checks that it exists and names every policy.

## Out of scope

- The simulator is not rewritten in this milestone, except where a task says so: the settlement with the half cent
  tie, and the negative net rule when the decision is to correct the data instead of the text.
- The held out set is not regenerated and its labels are not read again, and the frontend is not touched.
- The rules of the world are not verified beyond the sources that the audit read on 2026-11-22, the licences of the
  BIN list and of Nager.Date are not audited, and the API layer, the replay harness and the export are not checked.
