---
document: settlement-schedule
title: Settlement schedule
topic: settlement
version: 2026-10-01
language: en
---

# Acme Payments settlement schedule

## Overview {#overview}

Settlement is the payout to the merchant of the money from captured payments, after refunds and fees are deducted. This policy describes the period of each settlement, how the net amount is computed and on which day the payout is paid.

## Settlement period {#period}

Each settlement covers one week, Monday to Sunday, per merchant. A payment goes into the settlement of the week in which it was captured. A refund goes into the settlement of the week in which it was paid, even if the original payment is from an earlier week. A week is only settled after it ends.

## Components {#components}

Each settlement has four values, all in the merchant's settlement currency: the gross amount, which is the volume captured in the period, the refunds paid in the period, the fees of the period and the net amount. The fees include the processing fee on the gross volume and the fixed fee per chargeback opened, described in the fees and pricing policy.

## Net amount {#net-formula}

The net amount is the gross amount minus the refunds minus the fees. This math must add up exactly in every settlement. If the sum does not add up, there is a data error and the case must be escalated. The net amount can be negative when refunds and fees exceed the captured volume, and the merchant owes that balance to the next settlement.

## Payout timing {#payout-timing}

Settlements cover periods from Monday to Sunday, and the payout is paid 2 business days after the end of the period. The count skips weekends and the bank holidays of the settlement currency's calendar. The day the period ends does not count as a business day: the first business day is the first business day after the Sunday.

## Calendars per currency {#payout-calendars}

The holiday calendar depends on the settlement currency. For the euro, the European Central Bank's TARGET calendar applies. For the Brazilian real, the calendar of the Brazilian exchange B3 applies. For the US dollar, the calendar of United States federal holidays applies. For the other currencies only weekends are skipped. The calendar used is recorded together with the expected date.

## Holiday example {#holiday-example}

Take a period that ends on Sunday, October 11, 2026, settled in Brazilian reais. Monday, October 12 is a B3 holiday (Our Lady of Aparecida), so the first business day is Tuesday the 13th and the second is Wednesday the 14th. The payout is paid on October 14. On the same dates, a settlement in euros would be paid on Tuesday the 13th.

## Settlement currency {#settlement-currency}

Each merchant has a settlement currency, and the payout is made in it. Only payments made in the settlement currency go into the weekly calculation. A payment presented in another currency is settled outside the weekly flow and does not show up in the gross amount, and the analyst must point this out to a merchant puzzled by the difference.

## Settlement status {#status}

A settlement is `scheduled` when it has been computed and the expected date has not come yet. It moves to `paid` when the payout was made, and the actual payment date is recorded. A settlement still `scheduled` after the expected date means a delay and must be taken to human review. A paid settlement is never recomputed.

## Negative balance {#negative-net}

When a period's net amount is negative, no payout is made and the negative balance is deducted from the merchant's next settlement. The analyst must explain to the merchant that the balance comes from refunds or chargeback fees above the period's volume, showing the values of each component.

## Late payout {#late-payout}

A payout counts as late when the expected date has passed and the settlement is still `scheduled`. The common causes are invalid bank details, a hold for risk review and bank failures. The analyst does not fix the delay: they describe what the record shows and escalate the case to the operations team.

## Reconciliation {#reconciliation}

To check a settlement, add up the payments captured in the period in the settlement currency, add up the refunds paid in the period, recompute the fees with the current rule and confirm that the net amount equals gross minus refunds minus fees. The values must be computed with the calculation tool, with round half to even.

## Explaining a settlement {#explaining-a-settlement}

When the merchant asks how the payout was computed, the answer shows the period, the gross amount, the refunds, the fees split into processing and chargebacks, the net amount and the payment date, explaining any holiday that pushed the date. Every value cited must come from the record, and none may be estimated.
