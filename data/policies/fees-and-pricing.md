---
document: fees-and-pricing
title: Fees and pricing
topic: fees
version: 2026-10-01
language: en
---

# Acme Payments fees and pricing

## Overview {#overview}

Acme Payments charges the merchant two fees: a processing fee proportional to the volume sold and a fixed fee per chargeback opened. The fees are deducted in the weekly settlement, in the merchant's settlement currency. There are no other fees on the platform.

## Processing fee {#processing-fee}

The processing fee is 2.9% of the gross volume captured in the settlement period. The gross volume is the sum of the payments captured in the settlement currency during the week, before refunds. The fee is computed on the gross volume and is not recomputed when a refund is paid later.

## Chargeback fee {#chargeback-fee}

For each chargeback opened in the period, Acme charges a fixed fee of 15.00 in the merchant's settlement currency. The fee applies to each chargeback opened in the period, whether the merchant later wins or loses the dispute. What counts is the date the dispute was opened, not the date of the original payment.

## How the fees add up {#fee-total}

The total fees of a settlement are the processing fee plus the fixed fee multiplied by the number of chargebacks opened in the period. That total is subtracted from the gross amount, together with the refunds, to give the net amount. Each part shows up separately in the settlement so the merchant can understand the deduction.

## Rounding {#rounding}

The processing fee is rounded to the currency's smallest unit, for example the cent, with round half to even. A tie goes to the even digit: 14.5 cents become 14 and 43.5 cents become 44. The fixed chargeback fee is already an exact amount and is not rounded.

## Calculation example {#fee-example}

A merchant with a gross volume of 10,000.00 in a week and two chargebacks opened pays 290.00 in processing fees and 30.00 in chargeback fees, which gives 320.00 in fees. If the refunds paid in the week add up to 400.00, the net amount is 10,000.00 minus 400.00 minus 320.00, that is, 9,280.00.

## Fees on refunds {#fees-on-refunds}

The processing fee is not returned when a payment is refunded. It is charged on the gross volume of the week in which the payment was captured. The refund lowers the net amount in the week it is paid, but does not change the fee of any earlier week.

## FX markup is not a fee {#fx-markup-is-not-a-fee}

The markup some merchants apply when converting cross-currency refunds is not an Acme Payments fee. It is the merchant's choice, described in their settlement terms, and it does not show up in the settlement as a fee. The cross-currency refund policy sets the limit.

## Fee currency {#fee-currency}

Fees are charged in the merchant's settlement currency. The fixed chargeback fee is 15.00 in that currency, with no conversion: a merchant that settles in Brazilian reais pays 15.00 reais, and one that settles in euros pays 15.00 euros. Payments in another currency do not count in the gross volume and so do not generate the weekly processing fee.

## Fee disclosure {#fee-disclosure}

The fees are in the merchant's terms and show up separately in each settlement. The analyst can explain the calculation to the merchant using the record's values and the rules of this policy, but does not negotiate fees or promise discounts. Requests for a different fee go to the sales team.

## Fee changes {#fee-changes}

A change in the fees only applies to settlement periods that start after the effective date and is announced to the merchant in advance. Settlements already computed do not change. This version of the policy applies from October 1, 2026.

## Questions about fees {#fee-questions}

When the merchant asks why the payout was lower than the sales, the answer separates three deductions: refunds paid in the week, the 2.9% processing fee on the gross volume and the fixed fee per chargeback opened. Each deduction is shown as a number, computed with the calculation tool, and nothing is estimated.

## When to escalate {#escalation}

Escalate when the recorded fee does not match the recomputed rule, when a settlement has a chargeback fee but no chargeback opened in the period, or when the merchant disputes the fee and asks for an exception. Exceptions are decided by the sales team and not by the analyst.
