---
type: adr
status: accepted
date: 2026-11-24
---

# ADR-072: A currency the reference source does not publish is missing data, and the case goes to a person

Status: accepted. Date: 2026-11-24.

## Context

ADR-068 published the scenario S10 as the failure of the currency: the reference source does not publish the currency
of the payment, the amount cannot be converted, and the case goes to a person. The review of this branch read the
code and found that the rule the record names did not exist.

The published escalation of the S10 was `TX-2099: amount above 5000 [policy:escalation-and-review#high-amount]`,
which is the rule of the amount and not the rule of the currency. The reason was measured: with the same failure of
the reference rate and an amount of ARS 25000.00 the case escalates by the amount, and with ARS 1000.00, which is
under the limit, the escalation is empty. The failure of the currency, on its own, escalated nothing.

The code had the rule for the neighbouring failure and not for this one. `ledgerlens/tools/fx.py` returns the code
`UNSUPPORTED_CURRENCY` when there is no recorded rate for the pair that was asked for, and
`ledgerlens/verify/escalation.py` had a rule only for `UPSTREAM_UNAVAILABLE`, the failure of a source that could not
be read. The two are not the same: one is a source that is down, the other is a source that does not carry the pair.
The policy already covers the case, and the corpus says it twice: `data/policies/escalation-and-review.md` has the
rule `missing-data`, which counts a rate that was not found among the missing data, and
`data/policies/fx-reference-rates.md` sends the case to human review both when the source does not serve the pair
and when the service is unavailable. The policy had the rule and the code did not.

The reason of the scenario S11 had a second defect: it named the symptom, `UPSTREAM_UNAVAILABLE`, and not the rule
that decided. The S09 and the S10 published the anchor of the policy, and the S11 did not, so a reader of the
catalogue saw the error code of a client and not the rule of the product.

## Decision

**A currency pair the reference source does not publish is missing data: the case goes to a person under the rule
`escalation-and-review#missing-data`, and the reason names the pair, the day and the rule.**

The rule reads the failure of the reference rate from the trace, the way the rule of the unavailable rate reads it,
and it distinguishes the two failures: a source that could not be read and a pair that the source does not publish
are two sentences, because a person reading them has to know whether to wait or to look elsewhere. The reason names
the pair that was asked for and the day of the payment, says that the difference cannot be proven without the rate,
and carries the anchor of the policy, like the other reasons of the catalogue.

The reason of the unavailable rate gains the same anchor. Every reason of the catalogue names the rule that decided,
because a reader of a published case has to see the rule and not only the symptom.

## Alternatives considered

- **To correct ADR-068 and to publish the S10 as the failure of the amount.** Refused. The scenario exists because
  the reference source does not publish the currency of the payment, and the rule that was missing is a rule the
  policy already states. Publishing the case as the failure of the amount would leave the catalogue publishing a
  scenario that does not exercise the failure it names.
- **To make the rule of the amount cover the currency.** Refused. A rule that says "the amount is above the limit"
  cannot say that a rate does not exist, and a rule that says everything escalates is not a rule.
- **To treat the two failures of the reference rate as one.** Refused. A source that is down and a source that does
  not carry the pair are different facts about the world, and a person who has to act on the case needs to know which
  one it is.
- **To add the sentence to the policy and to rebuild the index of the corpus.** Deferred, and it is not a debt. The
  rule of `missing-data` already counts a rate that was not found, so the sentence is a spelling of a rule that is
  already written. When the sentence is added, the index of the corpus is rebuilt in the same change, because the
  digest of the corpus moves with it (ADR-055).

## Consequences

- **The scenario S10 escalates by the currency and not only by the amount**, and the reason names the pair, the day
  and the rule. With an amount under the limit, the escalation is no longer empty.
- **The reason of the scenario S11 names the rule** that sent the case to a person, like the other two.
- **Two bundles of the catalogue change** and are recaptured, the S10 and the S11.
- **The two neighbouring codes stay out of the rule**: `DATE_UNAVAILABLE`, a day outside the series, and
  `UNSUPPORTED_SOURCE_PAIR`, a pair the source does not serve at all. They are a line each in the same function when
  the product decides that they are the same rule, and this record does not claim them.
- **The policy text does not change in this push.** The rule of `missing-data` already says what the code now does.

## Links

- [ADR-068, the published catalogue holds the failures and not only the cases the agent resolves](ADR-068-the-published-catalogue-holds-the-failures-and-not-only-the-cases-the-agent-resolves.md)
- [ADR-055, the corpus of the policies carries the hash of its content](ADR-055-the-policy-index-carries-the-hash-of-the-corpus.md)
- [the rules of the escalation](../../ledgerlens/verify/escalation.py)
- [the policy of the escalation](../../data/policies/escalation-and-review.md)
- [the policy of the reference rates](../../data/policies/fx-reference-rates.md)
