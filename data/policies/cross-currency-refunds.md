---
document: cross-currency-refunds
title: Cross-currency refunds
topic: fx
version: 2026-10-01
language: en
---

# Cross-currency refunds at Acme Payments

## Overview {#overview}

This policy explains what happens when the customer pays in one currency and gets the refund in another. That happens when the currency charged to the merchant is different from the customer's billing currency, for example a payment in euros made by a customer whose card is in Brazilian reais.

## When a refund is cross-currency {#what-is-cross-currency}

A refund is cross-currency when the payment currency is different from the customer's billing currency. The requested amount stays in the payment currency, and the amount paid to the customer is computed in the customer's currency. Both amounts are recorded on the refund, together with the applied exchange rate, so the difference can be explained later.

## Rate on the refund date {#fx-at-refund-date}

The conversion of a cross-currency refund uses the rate on the refund date, not the rate on the payment date. That is why the customer can receive an amount different from what they paid, even when the refund is full in the merchant's currency. If the currency rose or fell between the two dates, that movement shows up in the amount returned, and it is not an error.

## Rate on the capture date {#charge-fx-at-capture}

On the charge, the conversion uses the reference rate on the capture date, with no markup. The amount the customer paid is the payment amount multiplied by that rate. The charge rate is recorded as a conversion of the charge kind, separate from the conversion of the refund kind, so the two can be compared.

## Merchant markup {#merchant-fx-markup}

Merchants on the `markup` plan can apply up to 3.0% over the reference rate when converting a refund. The markup lowers the applied rate: the applied rate is the reference rate on the refund date multiplied by one minus the markup. The markup must be in the merchant's settlement terms, and a markup above the limit must be taken to human review.

## Merchants on the standard plan {#standard-plan}

Merchants on the `standard` plan apply no markup. For them, the rate applied to the refund is the reference rate on the refund date itself. If the analyst finds a difference larger than rounding for a merchant on the standard plan, the difference is not a markup and the case must be investigated and, if needed, escalated.

## How to read the difference {#reading-the-difference}

The difference between what the customer paid and what they received has two parts. The first is the movement of the reference rate between the charge date and the refund date. The second is the merchant's markup over the refund reference rate. The two parts add up to the total difference, and the calculation must be done with the calculation tool, never in your head.

## Worked example {#worked-example}

Take a payment of EUR 200.00 converted on the charge at 5.5000, which gives BRL 1,100.00. On the refund day the reference rate is 5.4000 and the merchant applies a 2.0% markup, so the applied rate is 5.2920 and the customer receives BRL 1,058.40. The difference is BRL 41.60: BRL 20.00 comes from the rate movement and BRL 21.60 comes from the markup.

## Rounding {#rounding}

Applied rates are rounded to four decimal places and amounts to the currency's smallest unit, always with round half to even, which rounds ties to the even digit. It is the same method used in every calculation on the platform. One-cent differences between two calculations are usually a rounding effect.

## Customer payout currency {#payout-currency}

The refund is paid in the customer's billing currency, which is the currency of the original card or account. The paid amount and its currency are recorded on the refund. If the billing currency is the same as the payment currency, there is no conversion, no applied rate and the amount returned equals the amount requested.

## Currencies with no reference rate {#unsupported-currencies}

Not every currency has a published reference rate. The Argentine peso, for example, is not on the European Central Bank's list. When there is no reference rate, the analyst cannot estimate the markup: they must say the comparison is not possible, name the missing rate and take the case to human review.

## Explanation for the customer {#customer-explanation}

When explaining a refund lower than the payment, the analyst must separate the two causes: the exchange rate movement between the dates and the merchant's markup, when there is one. The reference rate is only a market reference and not the rate the merchant applied, and the answer needs to make that difference clear.

## Records {#records}

For each cross-currency refund the system keeps the requested currency and amount, the paid currency and amount, the applied rate, the rate date and the conversion identifier. The reference rate is not kept on the refund record: it is looked up from the official source at analysis time, and the source and date used go into the answer's evidence.
