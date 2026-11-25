---
type: adr
status: accepted
date: 2026-11-25
---

# ADR-099: The truth of the policies and the money is the contract of Acme, and the rules of the world carry their source

Status: accepted. Date: 2026-11-25.

## Context

[ADR-061](ADR-061-the-corpus-of-the-policies-is-the-contract-of-a-fictional-company.md) decided that the
corpus of `data/policies/` is the contract of a fictional company, and it ordered the corrections of the
twelve gaps of the audit of the truth of the policies and of the money. The milestone of
[specs/006](../../specs/006-r4-the-truth-of-the-policies-and-the-money/spec.md) is those corrections, and
this record writes down the rule by rule decisions, the class of every rule of the corpus, the debts the
milestone does not pay and the fact that the held out set is never regenerated.

The four tests of the audit were written to fail first, and they did: a paragraph named the card network
without the source, the corpus said a negative net gets no payout while the simulator paid two, sixteen
refunds of merchants at exactly three percent reached over the flat ceiling, and the calculator refused nine
conversions that are inside the rounding band of four decimals.

## Decision

**The corpus is the contract of Acme, the rules of the world live in `docs/policies-of-acme.md` with the
source and the date of the reading, a paragraph of the corpus that names an external body carries the source
and the date, the corpus and the simulator state the same rule of the money, and the held out set is never
regenerated.**

### The rule by rule decisions of the twelve gaps

1. **The response deadline.** The window of ten to fourteen days is the deadline of Acme for the response of
   the merchant, and the window of the card network (thirty calendar days for the categories of Visa, the
   frames of Mastercard) is a fact of the world, in `docs/policies-of-acme.md` with the source and the date.
2. **The reason codes.** FRD, NRC, NAD, DUP and OTH are internal codes of Acme, and the mapping to the codes
   of the networks is a fact of the world, in the document with the source and the date.
3. **The negative net.** A settlement whose net is negative pays nothing: no payout is made, the settlement
   stays scheduled, and the negative balance is carried into the next settlement of the merchant, which the
   simulator implements (`carried_minor` in the settlements table). Paying the negative net and also carrying
   the balance would recover the same money twice, so the corpus and the simulator state the rule of the carry
   without the payout.
4. **The band of the applied rate.** The guard of the calculator accepts an applied rate above the reference
   inside the rounding band of four decimals, reported as a rounding effect, and keeps `SWAPPED_RATES` for a
   pair outside the band.
5. **The ceiling of the markup.** The ceiling of 3.0% is read with the rounding band of the same policy, and
   a merchant whose contractual markup is exactly three percent is not escalated for the rounding.
6. **The markup wording.** The merchant applies the markup below the reference rate, with one direction word,
   and the arithmetic of the corpus stands.
7. **The rounding mode.** The mode of the rounding is the choice of the platform, and the corpus says what
   the common commercial practice does with a tie. The scenario S14 plants a settlement with an exact half
   cent tie, so the rule is exercised.
8. **The refund floor.** The refund policy states the floor of fourteen days with the source of the law
   (Directive 2011/83/EU, Article 9(1)), and the window of the policy is a house rule that cannot be
   narrower than the right of withdrawal.
9. **The calendar of the internal cutoff.** The policy and the code name the same calendar: the settlement
   currency of the merchant, read from the ledger, because the merchant is the one who answers the dispute.
10. **The marker of the fiction.** Every chunk of the index and every result of the tool carries the marker
    that Acme Payments is a fictional company, so an excerpt says so even when it is read out of its file.
11. **The rule of the world as evidence.** A claim may cite a rule of the world, with the URL of the source
    and the date it was read, and the verifier names the conflict between a cited rule of the world and a
    cited policy instead of scoring a plain contradiction.
12. **The notice and the lock.** The NOTICE quotes the three conditions of the ECB for the use of the
    reference rates, it says that the cross rates of the recordings are computed through the euro by this
    project, and the lock of the sources says the same.

### The class of every rule of the corpus

Every rule of the corpus is a house rule of Acme or an invention of this project, and the rules of the world
live in `docs/policies-of-acme.md` with the source and the date of the reading. The document says, for every
rule of the corpus, which of the three it is.

### The debts the milestone does not pay

- The provision of the United Kingdom was not located, and the Brazilian right of regret of seven days,
  which is shorter than the fourteen of the Union and relevant to the merchants that trade in Brazil, was
  not verified. The caveats are next to the rules they belong to in `docs/policies-of-acme.md`.
- The refund rule of the card regulation was not verified.
- The measurement of the latency and of the cost with the provider is still the measurement that moves the
  cap of the wall clock of ADR-098, and it runs by hand with a key.

### The held out set is never regenerated

The held out set of the verification keeps the corpus of its generation: the excerpts of the cases are the
text of the corpus of the generation, and a correction of the corpus never regenerates the set. The set is
read once, its labels are published, and the number over it is a number over those cases and those excerpts.
The tuning sets follow the corrected corpus, because a tuning set that quoted a rule the correction moved
would teach the wrong rule.

## Consequences

- The corpus of the policies says what Acme says, and the rules of the world carry their source in
  `docs/policies-of-acme.md`.
- The simulator and the corpus state the same rule of the negative net, and the settlements table carries
  the `carried_minor` of the balance.
- The guard of the calculator accepts the rounding band of four decimals, and the ceiling of the markup is
  read with the band.
- The index of the policies carries the marker of the fiction in every chunk, and the tool carries it in
  every result.
- The evaluation set follows the corrected corpus, and the held out set keeps the corpus of its generation.
- The four tests of the audit pass, and the gate refuses a paragraph that names an external body without the
  source and the date.

## Links

- [ADR-061, the corpus of the policies is the contract of a fictional company](ADR-061-the-corpus-of-the-policies-is-the-contract-of-a-fictional-company.md)
- [the document of the truth of the policies](../policies-of-acme.md)
- [the specification of the milestone](../../specs/006-r4-the-truth-of-the-policies-and-the-money/spec.md)
