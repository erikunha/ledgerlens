# The per case report of the verifier over verification_set (role tuning)

The verification status is available. A missing model is not a pass: a case whose verification is unavailable is a case without a verdict, and it is never counted as a pass.

Cases with a verdict: 30 of 30. Correct: 30. False supported: 0. False contradicted: 0. Without a verdict: 0.

| case | expected | got | outcome | claim | evidence |
|---|---|---|---|---|---|
| t01 | supported | supported | correct | Refund R-0412 was issued on 2026-10-05. | Refund R-0412 for transaction TX-2048 was issued on 2026-10-05 with status paid, in BRL. |
| t02 | supported | supported | correct | Chargeback CB-0310 is in stage evidence_requested. | Chargeback CB-0310 on transaction TX-2060 is in stage evidence_requested, reason code NRC, deadline 2026-11-12. |
| t03 | supported | supported | correct | Settlement ST-0044 was paid. | Settlement ST-0044 of merchant M-03 has status paid and was paid on 2026-10-14, in BRL. |
| t04 | supported | supported | correct | Transactions TX-2051 and TX-2052 were charged on the same card fingerprint. | Transactions TX-2051 and TX-2052 were charged to customer C-0733 on the same card fingerprint, same amount and same merchant, two minutes apart. |
| t05 | supported | supported | correct | A customer has 14 days to dispute a duplicate charge. | Policy: a customer has 14 days to dispute a duplicate charge after the statement date. |
| t06 | supported | supported | correct | The refund was paid in BRL. | Refund R-0412 for transaction TX-2048 was issued on 2026-10-05 with status paid, in BRL. |
| t07 | supported | supported | correct | Transaction TX-2048 was captured in EUR on 2026-10-01. | Transaction TX-2048 of 100.00 EUR was captured on 2026-10-01 for merchant M-03. |
| t08 | supported | supported | correct | The deadline for chargeback CB-0310 is 2026-11-12. | Chargeback CB-0310 on transaction TX-2060 is in stage evidence_requested, reason code NRC, deadline 2026-11-12. |
| t09 | supported | supported | correct | Merchant M-03 settles in BRL. | Merchant M-03 Casa Verde Foods has settlement currency BRL and country BR. |
| t10 | supported | supported | correct | The payout moves to 2026-10-14 because 2026-10-12 is a bank holiday. | The payout moves to 2026-10-14 because Monday 2026-10-12 is a bank holiday. |
| t11 | supported | supported | correct | The ECB reference rate for EUR to BRL on 2026-10-05 was 5.6339. | ECB reference rate EUR to BRL on 2026-10-05 was 5.6339. |
| t12 | supported | supported | correct | Chargeback CB-0310 has reason code NRC. | Chargeback CB-0310 on transaction TX-2060 is in stage evidence_requested, reason code NRC, deadline 2026-11-12. |
| c01 | contradicted | contradicted | correct | Refund R-0412 was issued on 2026-10-03. | Refund R-0412 for transaction TX-2048 was issued on 2026-10-05 with status paid, in BRL. |
| c02 | contradicted | contradicted | correct | Settlement ST-0044 was not paid. | Settlement ST-0044 of merchant M-03 has status paid and was paid on 2026-10-14, in BRL. |
| c03 | contradicted | contradicted | correct | Chargeback CB-0310 was won. | Chargeback CB-0310 on transaction TX-2060 was lost after review. |
| c04 | contradicted | contradicted | correct | The deadline for chargeback CB-0310 is 2026-11-20. | Chargeback CB-0310 on transaction TX-2060 is in stage evidence_requested, reason code NRC, deadline 2026-11-12. |
| c05 | contradicted | contradicted | correct | Transaction TX-2048 was captured in USD. | Transaction TX-2048 of 100.00 EUR was captured on 2026-10-01 for merchant M-03. |
| c06 | contradicted | contradicted | correct | The refund request was rejected. | The refund request R-0412 was approved and paid. |
| c07 | contradicted | contradicted | correct | A customer has 30 days to dispute a duplicate charge. | Policy: a customer has 14 days to dispute a duplicate charge after the statement date. |
| c08 | contradicted | contradicted | correct | Merchant M-03 settles in USD. | Merchant M-03 Casa Verde Foods has settlement currency BRL and country BR. |
| c09 | contradicted | contradicted | correct | The payout moves to 2026-10-15. | The payout moves to 2026-10-14 because Monday 2026-10-12 is a bank holiday. |
| c10 | contradicted | contradicted | correct | Refund R-0412 was never issued. | Refund R-0412 for transaction TX-2048 was issued on 2026-10-05 with status paid, in BRL. |
| n01 | not_enough_evidence | not_enough_evidence | correct | The customer contacted support twice about the refund. | Refund R-0412 for transaction TX-2048 was issued on 2026-10-05 with status paid, in BRL. |
| n02 | not_enough_evidence | not_enough_evidence | correct | Transaction TX-2048 used a Visa card. | Transaction TX-2048 of 100.00 EUR was captured on 2026-10-01 for merchant M-03. |
| n03 | not_enough_evidence | not_enough_evidence | correct | Merchant M-03 sells food and groceries online. | Settlement ST-0044 of merchant M-03 has status paid and was paid on 2026-10-14, in BRL. |
| n04 | not_enough_evidence | not_enough_evidence | correct | The customer prefers to receive messages by email. | Transactions TX-2051 and TX-2052 were charged to customer C-0733 on the same card fingerprint, same amount and same merchant, two minutes apart. |
| n05 | not_enough_evidence | not_enough_evidence | correct | The chargeback was filed by the issuing bank in Germany. | Chargeback CB-0310 on transaction TX-2060 is in stage evidence_requested, reason code NRC, deadline 2026-11-12. |
| n06 | not_enough_evidence | not_enough_evidence | correct | The merchant will likely appeal the decision. | Settlement ST-0044 of merchant M-03 has status paid and was paid on 2026-10-14, in BRL. |
| n07 | not_enough_evidence | not_enough_evidence | correct | The customer account was opened last year. | Policy: a customer has 14 days to dispute a duplicate charge after the statement date. |
| n08 | not_enough_evidence | not_enough_evidence | correct | A reviewer from the risk team looked at the case. | ECB reference rate EUR to BRL on 2026-10-05 was 5.6339. |
