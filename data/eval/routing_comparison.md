# The comparison of the routes

Real run of the two arms over the same cohort of cases, over the same ledger, with the deterministic judge of the repository. One run per case and one arm per model: the numbers are a trend and not a statistical significance. The dollars of a model whose price nobody verified are unknown, and unknown is never zero. The judge of the arms is the deterministic one with the stub of the NLI of the repository, and the client of the exchange runs on the fixtures of the repository: the absolute numbers are not the numbers of the published online report, and the two arms are the ones that are comparable with each other.

The cohort is 31 cases, the digest of the file is `5909f0fc62f8ef89d09b7a2da69b26d1c427182fb0c424a5ba934b72e855caaa` and the ledger of the two arms is `b1f1e6aedcd72fc20cabc1be83bbf4c00c3d0ef5b7fca1690dafc04d4552f678`.

## The arm `one_model`

One model in the four slots of the run: openai:gpt-4.1-mini.

| Slot | The model of the slot |
| --- | --- |
| agent | openai:gpt-4.1-mini |
| policy | openai:gpt-4.1-mini |
| sql | openai:gpt-4.1-mini |
| triage | openai:gpt-4.1-mini |

The accuracy is 0.8134 over 31 cases, and 22 of them carried every expected fact.

| Intent | The accuracy | The cases |
| --- | --- | --- |
| chargeback_status | 1.0 | 1 |
| duplicate_charge | 1.0 | 1 |
| fx_question | 0.75 | 2 |
| other | 0.0 | 2 |
| policy_question | 0.75 | 4 |
| refund_discrepancy | 0.7429 | 5 |
| settlement_question | 1.0 | 1 |
| status_lookup | 0.9333 | 15 |

The money per correct case is 0.005076 dollars, and the tokens per correct case are 11528.

The p95 of the latency is 10612 ms over 31 cases.

The rate of the fallback is 0.0 over 145 calls, and the number was not measured: the repository has no fallback with a budget in this path, so the rate was not measured.

| The model | The calls | The share | The tokens |
| --- | --- | --- | --- |
| openai:gpt-4.1-mini | 145 | 1.0 | 253628 |

## The arm `cascade`

The model of each slot, chosen by the task the slot does, read from the cascade.

| Slot | The model of the slot |
| --- | --- |
| agent | openai:gpt-4.1 |
| policy | openai:gpt-4.1-mini |
| sql | openai:gpt-4.1 |
| triage | openai:gpt-4.1-mini |

The accuracy is 0.7331 over 31 cases, and 21 of them carried every expected fact.

| Intent | The accuracy | The cases |
| --- | --- | --- |
| chargeback_status | 0.3333 | 1 |
| duplicate_charge | 1.0 | 1 |
| fx_question | 0.75 | 2 |
| other | 0.5 | 2 |
| policy_question | 0.5 | 4 |
| refund_discrepancy | 0.4786 | 5 |
| settlement_question | 1.0 | 1 |
| status_lookup | 0.9 | 15 |

The money per correct case is unknown, because the price of openai:gpt-4.1 was never verified, and the tokens per correct case are 10461.

The p95 of the latency is 6412 ms over 31 cases.

The rate of the fallback is 0.0 over 131 calls, and the number was not measured: the repository has no fallback with a budget in this path, so the rate was not measured.

| The model | The calls | The share | The tokens |
| --- | --- | --- | --- |
| openai:gpt-4.1 | 91 | 0.6947 | 174701 |
| openai:gpt-4.1-mini | 40 | 0.3053 | 44983 |

