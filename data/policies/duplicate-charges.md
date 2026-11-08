---
document: duplicate-charges
title: Duplicate charges
topic: duplicate
version: 2026-10-01
language: en
---

# Duplicate charges at Acme Payments

## Overview {#overview}

A duplicate charge happens when the same payment is captured twice by mistake, for example because the customer clicked pay twice or because the merchant sent it again. This policy defines how to recognize a duplicate and how to return the amount to the customer.

## Detection rule {#detection-rule}

Two captures count as duplicates when they have the same merchant, the same card (identified by the card fingerprint), the same amount and the same currency, and the second one happens within 5 minutes after the first. All four conditions must hold at the same time. The rule looks at the difference between the capture times, not between the authorization times.

## What is not a duplicate {#not-duplicates}

Two payments of the same amount at different merchants are not duplicates, even if the card and the time are the same. Two payments at the same merchant with different amounts, or with different cards, are not duplicates either. In these cases the analyst must ask the customer which payment they mean, instead of assuming a duplicate.

## Interval longer than 5 minutes {#time-gap}

If the two captures have the same merchant, card and amount, but the interval is longer than 5 minutes, the automatic rule does not apply. That does not prove the purchase was legitimate: the analyst must look at the order items and, if in doubt, escalate to a human analyst. Repeated legitimate purchases exist, such as two tickets for the same route.

## Returning the amount {#remedy}

Once the duplicate is confirmed, the later charge is refunded in full, that is, for the whole amount, within 5 business days. The first charge is kept. The refund goes back through the same payment method as the later charge and depends neither on the regular refund window nor on the merchant's approval.

## Who makes the refund {#who-refunds}

The refund of a duplicate charge can be started by an Acme Payments operator as soon as the detection rule is confirmed, without waiting for a request from the merchant. The analyst using the investigation system only recommends the action. Carrying out the refund is up to the operations team.

## What to check before recommending {#checks-before-recommending}

Before recommending the refund, check four points in the payment records: whether both payments have the same merchant, whether the card fingerprint is the same, whether the amounts and currencies are equal and whether the interval between the captures is 5 minutes or less. Also check that the later charge has not been refunded yet.

## Failures and retries {#retries-after-failure}

A declined attempt followed by an approved attempt is not a duplicate, because only the second payment was captured. The detection rule considers only captured payments. The analyst must ignore attempts with a failed status when looking for duplicates.

## Duplicate charge with FX {#duplicates-with-fx}

When the duplicate charge involves a currency conversion, returning the later charge follows the cross-currency refund policy. The customer receives the amount in their billing currency, computed on the refund date, and an FX difference between the dates may exist. The analyst must point this out to avoid a new question.

## What to tell the customer {#customer-communication}

The answer to the customer confirms that there were two equal charges within a short interval and states which one will be returned, the amount, the currency and the deadline of up to 5 business days. The answer blames neither the customer nor the merchant. If the duplicate was not confirmed, the answer explains why and asks for more information.

## When to escalate {#escalation}

Escalate when there are three or more similar charges, when the amount exceeds 5,000, when the charges have different merchants but the customer says they are the same purchase, or when the later charge already has a refund or an open dispute. In these cases the decision belongs to a person.

## Records {#records}

The duplicate refund recommendation records the identifiers of both payments, the merchant, the amount, the difference between the capture times and the rule applied. That makes it possible to redo the analysis later and show the merchant why the later charge was returned.
