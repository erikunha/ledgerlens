# The verification over the held out set

the model that produced the verdicts: MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli (the real model)
the revision of the weights: 6f5cf0a2b59cabb106aca4c287eed12e357e90eb (the commit that the calibration of ledgerlens/verify/thresholds.json recorded)
the thresholds applied: entailment_min 0.81, contradiction_min 0.91, max_premise_chars 4000 (the pinned ones of ledgerlens/verify/thresholds.json)
the labelled file: data/eval/verification_heldout.jsonl
the recipes of the generator (a private input of the report, not published, never a label): data/eval/heldout/recipes.jsonl

## Accuracy

- over the set: 24/48 (0.500)
- over the cases the model judged: 23/47 (0.489)
- decided by the code, without the model: 1

## The confusion matrix

| the reader \ the verifier | supported | contradicted | not_enough_evidence | total |
|---|---|---|---|---|
| supported | 10 | 0 | 9 | 19 |
| contradicted | 2 | 10 | 11 | 23 |
| not_enough_evidence | 2 | 0 | 4 | 6 |
| total | 14 | 10 | 24 | 48 |

the verifier said: supported 14, contradicted 10, not_enough_evidence 24
the reader said: supported 19, contradicted 23, not_enough_evidence 6

the false supported: 4
the false contradicted: 0

## The table by template

| template | cases | the reader said supported | the reader said contradicted | the reader said not_enough_evidence | right |
|---|---|---|---|---|---|
| hedge_shape | 8 | 3 | 4 | 1 | 4 |
| compound_shape | 8 | 1 | 4 | 3 | 3 |
| negation_shape | 8 | 4 | 4 | 0 | 4 |
| relative_period_shape | 8 | 4 | 4 | 0 | 0 |
| range_shape | 8 | 4 | 4 | 0 | 7 |
| two_source_shape | 8 | 3 | 3 | 2 | 6 |

## The reader and the recipes

the reading disagrees with the recipe of 2 case(s) of 48: ho-002, ho-013

## The limitations of this number

the contamination policy of the set: Thresholds, prompts and hyperparameters are tuned only against the datasets whose split_role is 'tuning'. A dataset with the role 'validation' may be scored but never tuned against. A dataset with the role 'held_out' may be read only by the final scoring step, and a tuning script that reads it has to fail. One dataset of this repository carries the role 'held_out' today: the verification_heldout, which is the labelled set of the blind reading. The answer key of the generator that wrote the set is not published, because a key that is public is not a key, and the two readings were instructed to be blind to it: each of them disagrees with it in two of the forty eight cases. No number over any other dataset of this repository may be presented as a generalization to unseen data.

the caveat of the set: The labels come from two independent blind machine readings with an adjudication of the divergences, each one instructed to be blind to the recipe of the case (ADR-059), and each one disagreeing with the key of the generator in two of the forty eight cases. The divergence between the two readings measures the noise of the rule with no answer key near it, and the divergence of each reading against the recipes measures the distance between a blind reading and the expectation of the writer. The reading is a machine reading, so it may share a blind spot with the model that the set measures, and the number over the set cannot claim to be free of it. It has one labeling pass and the repository has no mechanism to version a second one yet. No number over any other dataset of this repository may be presented as a generalization to unseen data.

## The cases

| id | the claim | the reader | the verifier | the method | the note |
|---|---|---|---|---|---|
| ho-001 | The dispute CB-0005 whose response window closed on 2026-10-21 was in stage won. | contradicted | not_enough_evidence | nli | Both readings answered contradicted: The evidence gives the deadline of CB-0005 as 2026-10-14, not the 2026-10-21 the claim names, although the stage won matches. |
| ho-002 | The refund R-0127 has the reason "Changed mind about the purchase" and the customer received the money. | supported | not_enough_evidence | nli | Both readings answered supported: The evidence records R-0127 with the reason Changed mind about the purchase and an issued_at date, so the refund was issued to the customer. The reading disagrees with the recipe of the case: the reader answered supported and the recipe expected a different label. |
| ho-003 | The period that the payout ST-0233 settled ran between 2026-10-19 and 2026-11-01. | contradicted | not_enough_evidence | nli | Both readings answered contradicted: The evidence gives the period of ST-0233 as 2026-10-19 to 2026-10-25, not up to 2026-11-01. |
| ho-004 | The dispute CB-0005 whose response window closed on 2026-10-14 was in stage won. | supported | not_enough_evidence | nli | Both readings answered supported: The evidence gives CB-0005 the deadline 2026-10-14 and the stage won, which are both parts of the claim. |
| ho-005 | The period that the payout ST-0196 settled ran between 2026-10-05 and 2026-10-18. | contradicted | contradicted | nli | Both readings answered contradicted: The evidence gives the period of ST-0196 as 2026-10-05 to 2026-10-11, not up to 2026-10-18. |
| ho-006 | The refund R-0127 has the reason "Product returned" and the customer received the money. | contradicted | not_enough_evidence | nli | Both readings answered contradicted: The evidence gives the reason of R-0127 as Changed mind about the purchase, not Product returned. |
| ho-007 | The period that the payout ST-0088 settled ran between 2026-08-31 and 2026-09-13. | contradicted | contradicted | nli | Both readings answered contradicted: The evidence gives the period of ST-0088 as 2026-08-31 to 2026-09-06, not up to 2026-09-13. |
| ho-008 | The refund R-0122 has the reason "Item damaged in delivery" and the acquiring bank confirmed the credit. | contradicted | not_enough_evidence | nli | Both readings answered contradicted: The evidence gives the reason of R-0122 as Product returned, not Item damaged in delivery. |
| ho-009 | The period that the payout ST-0013 settled ran between 2026-08-10 and 2026-08-23. | contradicted | contradicted | nli | Both readings answered contradicted: The evidence gives the period of ST-0013 as 2026-08-10 to 2026-08-16, not up to 2026-08-23. |
| ho-010 | The payment TX-1466 of merchant M-12 was not captured. | contradicted | contradicted | nli | Both readings answered contradicted: The evidence gives the status of TX-1466 as captured, so the claim that it was not captured says something else. |
| ho-011 | The payment TX-1206 was captured on 2026-09-30, and the refund policy says that a refund request is paid on the same business day or on the next one. | supported | supported | nli | Both readings answered supported: The evidence shows TX-1206 captured on 2026-09-30 and the cited policy states that a refund is paid on the same business day or on the next one. |
| ho-012 | It appears that the payment TX-0260 of merchant M-08 was charged back. | supported | supported | nli | Both readings answered supported: The evidence gives the status of TX-0260 as charged_back. |
| ho-013 | The payout ST-0130 for merchant M-23 was withheld, and the settlement schedule says that a period with a negative net amount gets no payout. | not_enough_evidence | supported | nli | Adjudicated as not_enough_evidence: the rule that evidence which contradicts itself says two things and so says nothing decided it, because the cited row shows ST-0130 with status paid and a paid_at date while the cited settlement schedule says that a period with a negative net amount gets no payout, so the cited evidence gives two opposite answers on whether the payout was withheld and therefore says nothing. The reading disagrees with the recipe of the case: the reader answered not_enough_evidence and the recipe expected a different label. |
| ho-014 | It appears that the payment TX-1867 of merchant M-04 was disputed. | supported | supported | nli | Both readings answered supported: The evidence gives the status of TX-1867 as disputed. |
| ho-015 | The refund R-0140 has the reason "Customer cancelled the order" and the merchant was told of it. | contradicted | not_enough_evidence | nli | Both readings answered contradicted: The evidence gives the reason of R-0140 as Charge not recognized by the customer, not Customer cancelled the order. |
| ho-016 | The payment TX-1338 of merchant M-20 was not disputed. | supported | not_enough_evidence | nli | Both readings answered supported: The evidence gives the status of TX-1338 as captured, which rules out the disputed status the claim denies. |
| ho-017 | The payment TX-0247 was captured on 2026-08-19, and the refund policy says that a refund request is paid on the same business day or on the next one. | contradicted | contradicted | nli | Both readings answered contradicted: The evidence shows TX-0247 captured at 2026-08-18, not on 2026-08-19 as the claim says. |
| ho-018 | The period that the payout ST-0088 settled ran between 2026-08-31 and 2026-09-06. | supported | supported | nli | Both readings answered supported: The evidence gives the period of ST-0088 as 2026-08-31 to 2026-09-06. |
| ho-019 | The payment TX-1663 of merchant M-12 was not captured. | contradicted | contradicted | nli | Both readings answered contradicted: The evidence gives the status of TX-1663 as captured, so the claim that it was not captured says something else. |
| ho-020 | The dispute CB-0006 whose response window closed on 2026-11-07 was in stage won. | contradicted | not_enough_evidence | nli | Both readings answered contradicted: The evidence gives the deadline of CB-0006 as 2026-10-31, not the 2026-11-07 the claim names. |
| ho-021 | The payment TX-1338 of merchant M-20 was not captured. | contradicted | contradicted | nli | Both readings answered contradicted: The evidence gives the status of TX-1338 as captured, so the claim that it was not captured says something else. |
| ho-022 | The dispute CB-0004 whose response window closed on 2026-11-01 was in stage evidence_submitted. | supported | not_enough_evidence | nli | Both readings answered supported: The evidence gives CB-0004 the deadline 2026-11-01 and the stage evidence_submitted. |
| ho-023 | The period that the payout ST-0233 settled ran between 2026-10-19 and 2026-10-25. | supported | supported | nli | Both readings answered supported: The evidence gives the period of ST-0233 as 2026-10-19 to 2026-10-25. |
| ho-024 | The dispute CB-0006 whose response window closed on 2026-10-31 was in stage won. | supported | not_enough_evidence | nli | Both readings answered supported: The evidence gives CB-0006 the deadline 2026-10-31 and the stage won. |
| ho-025 | The payment TX-0133 of merchant M-13 was not partially refunded. | supported | not_enough_evidence | nli | Both readings answered supported: The evidence gives the status of TX-0133 as captured, which rules out a partial refund. |
| ho-026 | The dispute CB-0004 whose response window closed on 2026-11-08 was in stage evidence_submitted. | contradicted | not_enough_evidence | nli | Both readings answered contradicted: The evidence gives the deadline of CB-0004 as 2026-11-01, not the 2026-11-08 the claim names. |
| ho-027 | The payment TX-1206 was captured on 2026-10-01, and the refund policy says that a refund request is paid on the same business day or on the next one. | contradicted | contradicted | nli | Both readings answered contradicted: The evidence shows TX-1206 captured at 2026-09-30, not on 2026-10-01 as the claim says. |
| ho-028 | The payment TX-0133 of merchant M-13 was not captured. | contradicted | contradicted | nli | Both readings answered contradicted: The evidence gives the status of TX-0133 as captured, so the claim that it was not captured says something else. |
| ho-029 | The refund R-0132 has the reason "Charge not recognized by the customer" and the case was closed by the risk team. | contradicted | not_enough_evidence | nli | Both readings answered contradicted: The evidence gives the reason of R-0132 as Item damaged in delivery, not Charge not recognized by the customer. |
| ho-030 | The period that the payout ST-0196 settled ran between 2026-10-05 and 2026-10-11. | supported | supported | nli | Both readings answered supported: The evidence gives the period of ST-0196 as 2026-10-05 to 2026-10-11. |
| ho-031 | The payment TX-0247 was captured on 2026-08-18, and the refund policy says that a refund request is paid on the same business day or on the next one. | supported | supported | nli | Both readings answered supported: The evidence shows TX-0247 captured on 2026-08-18 and the cited policy states that a refund is paid on the same business day or on the next one. |
| ho-032 | It appears that the payment TX-0467 of merchant M-20 was refunded. | not_enough_evidence | not_enough_evidence | none | Both readings answered not_enough_evidence: The claim cites no evidence at all, so nothing in the cited material says that TX-0467 was refunded. |
| ho-033 | The payment TX-0964 was captured on 2026-09-19, and the refund policy says that a refund request is paid on the same business day or on the next one. | supported | supported | nli | Both readings answered supported: The evidence shows TX-0964 captured on 2026-09-19 and the cited policy states that a refund is paid on the same business day or on the next one. |
| ho-034 | It appears that the payment TX-1867 of merchant M-04 was failed. | contradicted | not_enough_evidence | nli | Both readings answered contradicted: The evidence gives the status of TX-1867 as disputed, not failed. |
| ho-035 | The payout ST-0130 for merchant M-23 was made, and the settlement schedule says that a period with a negative net amount gets no payout. | not_enough_evidence | supported | nli | Adjudicated as not_enough_evidence: the rule that evidence which contradicts itself says two things and so says nothing decided it, because the cited row shows ST-0130 with status paid and a paid_at date while the cited settlement schedule says that a period with a negative net amount gets no payout, so the cited evidence gives two opposite answers on whether the payout was made and therefore says nothing. |
| ho-036 | The refund R-0132 has the reason "Item damaged in delivery" and the case was closed by the risk team. | not_enough_evidence | not_enough_evidence | nli | Both readings answered not_enough_evidence: The reason matches the evidence but the cited row never says that the case was closed by the risk team. |
| ho-037 | The dispute CB-0003 whose response window closed on 2026-09-30 was in stage won. | supported | not_enough_evidence | nli | Both readings answered supported: The evidence gives CB-0003 the deadline 2026-09-30 and the stage won. |
| ho-038 | The payment TX-1663 of merchant M-12 was not refunded. | supported | not_enough_evidence | nli | Both readings answered supported: The evidence gives the status of TX-1663 as captured, which rules out a refund. |
| ho-039 | The refund R-0140 has the reason "Charge not recognized by the customer" and the merchant was told of it. | not_enough_evidence | not_enough_evidence | nli | Both readings answered not_enough_evidence: The reason matches the evidence but the cited row never says that the merchant was told of the refund. |
| ho-040 | It appears that the payment TX-0260 of merchant M-08 was partially refunded. | contradicted | not_enough_evidence | nli | Both readings answered contradicted: The evidence gives the status of TX-0260 as charged_back, not partially_refunded. |
| ho-041 | The refund R-0122 has the reason "Product returned" and the acquiring bank confirmed the credit. | not_enough_evidence | not_enough_evidence | nli | Both readings answered not_enough_evidence: The reason matches the evidence but the cited row never says that the acquiring bank confirmed the credit. |
| ho-042 | It appears that the payment TX-0467 of merchant M-20 was captured. | contradicted | supported | nli | Both readings answered contradicted: The evidence gives the status of TX-0467 as refunded, not captured. |
| ho-043 | The dispute CB-0003 whose response window closed on 2026-10-07 was in stage won. | contradicted | not_enough_evidence | nli | Both readings answered contradicted: The evidence gives the deadline of CB-0003 as 2026-09-30, not the 2026-10-07 the claim names. |
| ho-044 | The period that the payout ST-0013 settled ran between 2026-08-10 and 2026-08-16. | supported | supported | nli | Both readings answered supported: The evidence gives the period of ST-0013 as 2026-08-10 to 2026-08-16. |
| ho-045 | It appears that the payment TX-1309 of merchant M-12 was partially refunded. | supported | supported | nli | Both readings answered supported: The evidence gives the status of TX-1309 as partially_refunded. |
| ho-046 | The payment TX-0964 was captured on 2026-09-20, and the refund policy says that a refund request is paid on the same business day or on the next one. | contradicted | contradicted | nli | Both readings answered contradicted: The evidence shows TX-0964 captured at 2026-09-19, not on 2026-09-20 as the claim says. |
| ho-047 | It appears that the payment TX-1309 of merchant M-12 was refunded. | contradicted | supported | nli | Both readings answered contradicted: The evidence gives the status of TX-1309 as partially_refunded, not refunded. |
| ho-048 | The payment TX-1466 of merchant M-12 was not failed. | supported | not_enough_evidence | nli | Both readings answered supported: The evidence gives the status of TX-1466 as captured, which rules out a failure. |
