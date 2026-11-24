---
type: adr
status: accepted
date: 2026-11-23
---

# ADR-061: The corpus of the policies is the contract of a fictional company, and the held out set freezes it

Status: accepted. Date: 2026-11-23.

## Context

The audit of the truth of the policies and of the money found twelve places where the corpus of `data/policies/`
says something the world does not say, or something the data of this repository contradicts. The audit did not
leave a list of sentences to fix. It left one question, and the answer to that question decides the other
eleven:

> Is the corpus of `data/policies/` a set of rules that describe payments as they are, or the contract of a
> fictional company that the agent treats as the contract of that company?

Today the corpus is the second in its claims and the first in its effect. In its claims, because it names the
card network, the central bank and the law, and it gives a window of ten to fourteen days as the window of the
network, a set of reason codes that no network uses, and a ceiling of three percent as if it were a fact of the
market. In its effect, because the verifier judges every answer against this corpus and the agent quotes it to
merchants, so a rule of a fiction is enforced as if it were a rule of the world.

The two cannot stand at once, and the repository already decided the general matter: ADR-001 and ADR-009
decided what is real data and what is simulated. What was never decided is what a policy of a demo is. The
simulator pays a settlement with a negative net, and the corpus says that a negative net gets no payout and the
balance is carried to the next settlement; the corpus is right about the design and the simulator is wrong, or
the other way round, and nobody wrote down which.

### The twelve gaps, in one line each

| # | The place | What is wrong |
| --- | --- | --- |
| 1 | `data/policies/chargeback-handling.md:25` | calls a window of ten to fourteen days the deadline of the card network, and no source read gives a window that short |
| 2 | `data/policies/chargeback-handling.md:21` | the reason codes FRD, NRC, NAD, DUP and OTH are internal to the company and no network uses them |
| 3 | `data/policies/settlement-schedule.md:49` | says that a negative net gets no payout, and the simulator pays two such settlements |
| 4 | `ledgerlens/tools/calculator.py:210` | refuses an applied rate above the reference, and nine rows of the ledger are inside the rounding band of four decimals |
| 5 | `data/policies/fx-reference-rates.md:49` | escalates above three percent, and sixteen refunds of merchants at exactly three percent reach three and a quarter |
| 6 | `data/policies/cross-currency-refunds.md:29` | says "up to 3.0% over the reference rate" and then subtracts the markup |
| 7 | `data/policies/fees-and-pricing.md:29` | states a tie rule of half to even and presents it as a rule, when it is a choice of the platform |
| 8 | `data/policies/refund-policy.md:37` | states the time to pay a refund and never the statutory floor of fourteen days |
| 9 | `data/policies/chargeback-handling.md:29` and `ledgerlens/verify/escalation.py:30` | the policy names the calendar of the settlement currency and the code uses the calendar of the dispute record |
| 10 | `ledgerlens/retrieval.py:96` | the fiction is stated in one policy of eight and in no chunk of the index, so a served excerpt reads as a rule of a real company |
| 11 | `ledgerlens/verify/claims.py:54` | a claim may cite only what is inside this repository, so an answer that is right about the real world can only be contradicted or not enough evidence |
| 12 | `NOTICE` and `data/sources.lock.json` | the ECB sets three conditions and the NOTICE states two, and the cross rates of the recordings are derived and the NOTICE does not say so |

### The reading of the held out set was about to happen over a corpus that was about to move

Two of the three negative controls of the held out set, `ho-013` and `ho-035`, cite the rule
`settlement-schedule#negative-net`, the rule that the simulator breaks. The control is built on the
contradiction: the row of the settlement says a payout was made for a period whose net is negative, and the
excerpt of the policy says that such a period gets no payout, so the evidence contradicts itself and the label
is `not_enough_evidence` without anybody having to decide which of the two is true.

The audit recommended that the corpus be corrected before the reading, so that the set is not frozen against a
rule that is about to change. The question had to be answered before the reading, because the reading is the
most expensive act of the milestone and it cannot be done twice.

## Decision

### The corpus is the contract of Acme, and never a claim about the world

Every rule of `data/policies/` is either a house rule of Acme, which is a commercial choice of a fictional
company, or an invention of this project, which is a simplification made for the sake of a demo. A rule of the
corpus never states what a card network, a central bank or a law requires. The rules that the world does have
live in `docs/policies-of-acme.md`, with the source of each and the date it was read, and that document is the
context in which an analyst may answer a merchant who asks what the network really does.

This is the same kind of decision as ADR-009, which already separated the real data from the simulated one.
A policy of the corpus is simulated data with teeth: the verifier enforces it, so the fiction has to be honest
about being a fiction.

### The corrections come in this order, and each one names its test

1. **The wording that names the world where it names Acme**: the window of ten to fourteen days becomes the
   deadline of Acme and the window of thirty calendar days of the network becomes a fact of the world, in the
   document and not in the contract; the reason codes become internal to Acme and the mapping to the codes of
   the networks goes to the document; the sentence that says "over the reference rate" says "below" and keeps
   the arithmetic; the sentence about the tie of the rounding says that the mode is the choice of the platform.
2. **The rules where the data and the text disagree**, decided rule by rule: the negative net, where the text
   and the simulator say opposite things; the band of the applied rate, where the code refuses nine rows that
   are inside the rounding band; the ceiling of the markup, read with the band that the same policy defines;
   the calendar of the internal cutoff, where the policy and the code disagree about the currency.
3. **The floors that a house rule may not cross**: the refund policy states the floor of fourteen days with
   its source, and the window of the policy is a house rule that cannot be narrower than the right of
   withdrawal.
4. **The marker of the fiction in every chunk served**: the metadata of every chunk of the index carries it,
   and so does the result of the tool, so that an excerpt says that the company is fictional even when it is
   read out of its file.
5. **The notice and the lock of the sources**: the three conditions of the ECB are quoted, and the notice says
   that the cross rates of the recordings are computed through the euro by this project.

The tasks live in `specs/006-r4-the-truth-of-the-policies-and-the-money/`, one per gap, each with the test that
would hold it. The four tests of the audit are written to fail first: a test that fails is the proof that the
gap is real, and a test that passes before the correction would prove nothing.

### The held out set freezes the corpus of its generation, and a correction never regenerates it

The reading was done blind over the corpus as it stood, and the cases carry the text of the excerpts inside
them, so the correction of the corpus does not change the cases and does not oblige a second reading. A
correction of the corpus never regenerates the set: the set is read once, its labels are published, and the
number over it is a number over those cases and those excerpts.

The consequence is named here so that nobody has to guess it: after the corrections, the held out set still
measures the verifier over the excerpts of the corpus of its generation, and the two negative controls still
depend on a rule that the correction may change. That is the price of a frozen benchmark, and the price is
smaller than the price of a set that is regenerated every time the corpus moves, because a regenerated set has
no provenance and no published labels.

The blind reading of the set was two independent machine readings with an adjudication
([ADR-059](ADR-059-the-held-out-set-is-read-by-two-blind-machines-and-adjudicated.md)), and it was done before
the corpus was corrected and before this record existed. The recipes of the generator were not in the public
tree while the reading happened, so the reading was blind in the only sense that a procedure can be blind.

### A contradiction with a policy may mean that the policy is wrong

The verifier keeps its discipline: the numbers come from the tool and the label comes from the evidence, and
the verifier never picks a side. The gap is in what the analyst, the merchant and the reader are told. A
sentence in `escalation-and-review.md` that says a contradiction with a policy may mean that the policy is
wrong, and a way to cite a rule of the world next to a policy, are part of the work of `specs/006`. The
alternative, an agent that answers "the policy says this" when the policy says something the world does not,
is a product that repeats its own fiction as a fact.

## Consequences

- The corpus of the policies keeps saying what it says until the tasks of `specs/006` are done. This record
  decides what it is going to say and in what order, and it does not rewrite eight files by hand in the same
  breath as the decision.
- Every correction moves the corpus, so it moves the hash that the index carries
  ([ADR-055](ADR-055-the-policy-index-carries-the-hash-of-the-corpus.md)) and the pin of the calibration
  ([ADR-007](ADR-007-nli-verification.md)), and the guard that refuses a tuning script that reads a set that
  was not meant for it keeps working over the datasets that move.
- `docs/policies-of-acme.md` becomes the document that a reader of the public repository needs first, because
  it is the one that says what is real and what is a house rule of a fictional company.
- The gaps that the audit did not check stay gaps: the provision of the United Kingdom was not located, the
  refund rule of the card regulation was not verified, and the Brazilian right of regret of seven days, which
  is shorter than the fourteen of the Union and relevant to the merchants that trade in Brazil, was not
  verified at all.

## Alternatives that were refused

- **Correct the corpus before the reading.** Refused. The cases carry the text of the excerpts, so the
  correction does not change the cases; and the reading is the expensive act of the milestone, and doing it
  twice over a corpus that is about to move would have frozen a set against a rule that no longer exists.
- **Leave the corpus as it is and publish it as a description of the world.** Refused. The verifier judges
  every answer against this corpus and the agent quotes it to merchants: a rule of a fiction that is presented
  as a rule of the world is a claim the product cannot keep.
- **Delete the policies and let the agent answer with the world.** Refused. The contract of the company is
  what makes the demo legible: a merchant asks what the company will do, and the company has to have an
  answer.
- **Make the house rules realistic by copying the text of a network.** Refused. A house rule written with the
  words of a network is a claim about the network, and it is the exact confusion this record exists to end.
- **Let the simulator keep paying a negative net and change the corpus to match.** Refused for now. Which of
  the two is the design is a question about the world of the demo and not about the truth of a rule, and the
  task of `specs/006` decides it rule by rule, with the test that holds it.

## Links

- [the document of the truth of the policies](../policies-of-acme.md)
- [the tasks of the correction](../../specs/006-r4-the-truth-of-the-policies-and-the-money/tasks.md)
- [the blind reading of the held out set](ADR-059-the-held-out-set-is-read-by-two-blind-machines-and-adjudicated.md)
- [the evaluation of the verifier](ADR-052-the-manifest-of-the-eval-datasets.md)
