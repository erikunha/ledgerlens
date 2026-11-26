---
document: chargeback-handling
title: Chargeback handling
topic: chargeback
version: 2026-10-01
language: en
---

# Chargeback handling at Acme Payments

## Overview {#overview}

A chargeback is a dispute the cardholder opens with the issuing bank to ask for a payment back. Acme Payments gets the notice of the dispute, informs the merchant and prepares the defense. This policy defines the stages, the deadlines and the evidence required.

## Dispute stages {#stages}

A dispute goes through stages in order. In `opened`, the dispute was announced to Acme. In `evidence_requested`, Acme asked the merchant for evidence. In `evidence_submitted`, the evidence was sent. In `won` or `lost`, the dispute was decided for or against the merchant. A resolved dispute never goes back to an earlier stage.

## Reason codes {#reason-codes}

Each dispute has a reason code. `FRD` means fraud, when the cardholder says they did not make the purchase. `NRC` means product or service not received. `NAD` means a product different from the description or defective. `DUP` means a duplicate charge. `OTH` covers the other cases. These five codes are internal codes of Acme, and no card network uses them: the mapping to the codes of the networks is a fact of the world, written down in `docs/policies-of-acme.md` with its source (the Visa Core Rules and the Mastercard Chargeback Guide, read on 2026-11-25). The code decides which evidence is asked of the merchant.

## Response deadline {#response-deadline}

Evidence must be sent at least one business day before the response deadline of the dispute. The response deadline is the deadline of Acme for the response of the merchant: it shows up in the dispute's deadline field, ten to fourteen days after the dispute is opened, and it is a house rule of Acme and not the deadline of the card network. The window of the card network itself is longer, thirty calendar days for the categories of Visa and the frames of Mastercard (source: the Visa Core Rules and the Mastercard Chargeback Guide, read on 2026-11-25), and it is written down in `docs/policies-of-acme.md`. The Acme Payments internal cutoff is one business day before the response deadline. A response sent after the response deadline loses the dispute automatically, with no review of the merits. For a Monday deadline, the cutoff is the preceding Friday if that Friday is a business day on the settlement currency's calendar. Otherwise, continue backwards to the preceding business day. For example, for a Monday, July 7, 2025 response deadline, the USD cutoff is Thursday, July 3 because July 4 is a US federal holiday. The EUR cutoff is Friday, July 4 because the TARGET calendar is open.

## How to count business days {#business-days}

Business days exclude Saturdays, Sundays and the bank holidays of the calendar of the merchant's settlement currency. To count the internal cutoff, go back one business day from the response deadline. If today's date is already past the internal cutoff, the dispute is late for the normal submission and must be escalated.

## Evidence checklist {#evidence-checklist}

The evidence depends on the reason code. For `FRD`, attach the confirmation of the device, the delivery address and contact with the customer. For `NRC`, attach the proof of delivery or of access to the service. For `NAD`, attach the product description, the photos and the message exchange. For `DUP`, attach the proof that the two charges come from different orders. The reason code picks the list.

## Evidence for fraud {#evidence-frd}

In a fraud dispute, the strongest evidence shows that the cardholder took part in the purchase: an IP address and a device already used in earlier purchases, delivery to the billing address, and conversations with the customer after the purchase. Without at least one of these, the chance of winning is low and the case should be reviewed with the merchant.

## Evidence for not received {#evidence-nrc}

In a dispute for a product not received, the main evidence is the proof of delivery with a date and a signature, or the tracking code with the carrier's confirmation. For digital services, the record of the customer's access to the service serves as proof. The delivery time promised to the customer must also be attached.

## Evidence for not as described {#evidence-nad}

In a dispute for a product different from the description, the merchant must show the description published at the time of purchase, photos of the product shipped and the exchange policy the customer accepted. If the customer already got a partial refund or an exchange, the proof must be attached, because it lowers the disputed amount.

## Evidence for a duplicate charge {#evidence-dup}

In a dispute for a duplicate charge, the defense shows that the two charges come from different orders, with distinct order numbers, items and times. If it really is a duplicate, the merchant should not dispute it: the right step is to refund the later charge, as the duplicate charge policy says.

## Who submits the evidence {#who-submits}

The merchant gathers the evidence and the Acme Payments disputes team checks it and forwards it. The analyst handling the case does not send evidence on their own. They confirm that the dispute is at the right stage, that the internal cutoff has not passed and that the evidence list for the reason code is complete.

## Outcome {#outcomes}

When the dispute is decided for the merchant, the dispute moves to `won` and the payment goes back to the captured status. When it is decided against, the dispute moves to `lost`, the payment moves to `charged_back` and the amount is debited from the merchant. Acme Payments cannot change the outcome.

## Chargeback fee {#fee-reference}

Each dispute opened creates a fixed fee charged to the merchant, even if the merchant wins the defense. The fee amount and the rule for charging it per period are in the fees and pricing policy. The fee is deducted in the settlement of the period in which the dispute was opened.

## Refund during a dispute {#refund-during-dispute}

A payment with an open dispute is not refunded, because the customer could get paid twice. If the merchant wants to return the amount, they must accept the dispute, and the outcome will be `lost`. The analyst must explain this rule to the customer and the merchant without promising a parallel refund.

## When to escalate {#escalation}

A dispute must be escalated to a human analyst when the response deadline is 2 days away or less, when the internal cutoff has already passed, when the amount exceeds 5,000 or when required evidence is missing. The full criteria are in the escalation and review policy.
