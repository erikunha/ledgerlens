# The policies of Acme, and what is real in them

Acme Payments is a fictional company, created for this project. The corpus of `data/policies/` is the
contract of that company: every rule of it is either a house rule of Acme, which is a commercial choice of a
fictional company, or an invention of this project, which is a simplification made for the sake of a demo. A
rule of the corpus never states what a card network, a central bank or a law requires (ADR-061).

This document is the context in which an analyst may answer a merchant who asks what the world really does.
It says, for every rule of the corpus, whether it is a rule of the world, a house rule of Acme or an
invention of this project, and it carries the rules of the world that the corpus does not state, with the
source of each and the date it was read. The audit of the truth of the policies and of the money marked some
rules as unverified, and the caveats are next to the rules they belong to.

The date of the reading of every source of this document is 2026-11-25.

## Chargeback handling (`data/policies/chargeback-handling.md`)

- **The dispute stages, the evidence checklist and the internal cutoff of one business day** are house rules
  of Acme: the stages, the checklist and the cutoff are commercial choices of the fictional company.
- **The response deadline of ten to fourteen days** is a house rule of Acme: it is the deadline of Acme for
  the response of the merchant, and it is not the deadline of any card network.
- **The window of the card network** is a rule of the world, and it is not in the corpus: under the Visa
  rules, the dispute response of the acquirer must be made within thirty calendar days of the dispute
  processing date, and under the Mastercard rules the response to a first chargeback has a frame of
  forty-five days. Source: the Visa Core Rules and Visa Product and Service Rules (the dispute response
  within 30 calendar days) and the Mastercard Chargeback Guide (the 45-day frame of the first chargeback),
  read on 2026-11-25 through the summaries of [PayKings](https://paykings.com/blog/chargeback-time-limits/)
  and [Chargeback Gurus](https://www.chargebackgurus.com/blog/dont-run-out-the-clock-understanding-chargeback-time-limits).
- **The reason codes FRD, NRC, NAD, DUP and OTH** are internal codes of Acme, and no network uses them. The
  mapping to the codes of the networks is a rule of the world: fraud maps to the 10.x family of Visa and to
  the 48xx family of Mastercard, not received maps to Visa 13.1, not as described maps to Visa 13.3, and a
  duplicate maps to Visa 12.6 (duplicate processing) and to the processing errors of Mastercard. Source: the
  Visa Core Rules (the reason code families 10, 12 and 13) and the Mastercard Chargeback Guide, read on
  2026-11-25 through the summaries of [Sparsu](https://www.sparsu.com/en/knowledge/visa/13-3) and
  [Aurai](https://aurai.dev/blog/visa-12-6-duplicate-processing-playbook).
- **The calendar of the internal cutoff** is a house rule of Acme: the cutoff counts one business day before
  the deadline of the dispute record, on the calendar of the dispute record.

## Cross-currency refunds (`data/policies/cross-currency-refunds.md`)

- **The markup below the reference rate** is a house rule of Acme: the merchant of the markup plan applies
  the markup below the reference rate when converting a refund, and the applied rate is the reference rate
  multiplied by one minus the markup. The arithmetic and the worked example of the corpus stand.
- **The ceiling of 3.0% over the markup** is a house rule of Acme, read with the rounding band of the policy
  of the reference rates.
- **The rounding of the conversion** is a choice of the platform: the mode of the rounding (half to even) is
  a commercial choice of Acme, and the common commercial practice rounds a tie away from zero. The corpus
  says the mode is the choice of the platform.
- **The rate of the capture date and the rate of the refund date** are house rules of Acme: the decomposition
  of the difference is the design of the demo.

## Duplicate charges (`data/policies/duplicate-charges.md`)

- **The detection rule of the four conditions and the interval of five minutes** are house rules of Acme:
  the merchant, the card fingerprint, the amount and the interval are the design of the demo.
- **The refund of the later charge within five business days** is a house rule of Acme.

## Escalation and review (`data/policies/escalation-and-review.md`)

- **The criteria of the escalation** (the contradicted claims, the missing data, the deadline of two days,
  the amount of five thousand) are house rules of Acme.
- **A contradiction with a policy may mean that the policy is wrong** is a rule of the corpus after the
  correction of the audit: the system does not resolve contradictions by picking a side, and the analyst is
  told that the policy may be the wrong one.

## Fees and pricing (`data/policies/fees-and-pricing.md`)

- **The processing fee of 2.9% and the fixed fee of 15.00 per chargeback** are house rules of Acme.
- **The rounding of the fee** is a choice of the platform: the mode of the rounding (half to even) is a
  commercial choice of Acme, and the common commercial practice rounds a tie away from zero. The corpus says
  the mode is the choice of the platform.

## Reference exchange rates (`data/policies/fx-reference-rates.md`)

- **The European Central Bank as the source of the reference rate** is a rule of the world: the ECB
  publishes the daily reference rates of the euro, and the Frankfurter service serves them. Source: the
  European Central Bank, the euro foreign exchange reference rates, and the Frankfurter service,
  read on 2026-11-25. The conditions of the use of the rates are quoted in `NOTICE`.
- **The closing PTAX rate of the Banco Central do Brasil** is a rule of the world: the Banco Central do
  Brasil publishes the PTAX rate of the Brazilian real. Source: the Banco Central do Brasil, read on
  2026-11-25.
- **The decimals, the single source and the comparison with the applied rate** are house rules of Acme: the
  four decimal places, the refusal to blend sources and the ceiling of 3.0% read with the band are the
  design of the demo.

## Refund policy (`data/policies/refund-policy.md`)

- **The refund window of thirty days and the windows per merchant** are house rules of Acme.
- **The floor of fourteen days** is a rule of the world: the consumer of the European Union has the right to
  withdraw from a distance contract within fourteen days, and a house rule of the refund window cannot be
  narrower than that right. Source: Directive 2011/83/EU of the European Parliament and of the Council of 25
  October 2011, Article 9(1), [EUR-Lex 32011L0083](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32011L0083),
  read on 2026-11-25. The corpus states the floor with this source.
- **The caveat of the audit:** the Brazilian right of regret of seven days, which is shorter than the
  fourteen of the Union and relevant to the merchants that trade in Brazil, was not verified by the audit,
  and the provision of the United Kingdom was not located. These gaps stay open (ADR-061).

## Settlement schedule (`data/policies/settlement-schedule.md`)

- **The weekly period, the components and the payout timing** are house rules of Acme.
- **The negative net** is a house rule of Acme after the correction of the audit: a settlement whose net is
  negative pays nothing, no payout is made and the negative balance is carried into the next settlement of the
  merchant, and the simulator of the repository implements the carry. Paying the negative net and also carrying
  the balance would recover the same money twice.

## The rules of the world the corpus does not state

The corpus never states what a card network, a central bank or a law requires. The rules of the world that
an analyst may need are the ones of this document: the window of the network (thirty calendar days of Visa,
forty-five days of Mastercard), the mapping of the reason codes, the floor of fourteen days of the Union,
the daily rates of the ECB and the PTAX of the Banco Central do Brasil. Every one of them carries the source
and the date it was read, and a rule of the world that is not here is a rule the analyst must look up before
answering.
