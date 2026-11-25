# The comparison of the routes

Real run of the two arms over the same cohort of cases, over the same ledger, with the deterministic judge of the repository. One run per case and one arm per model: the numbers are a trend and not a statistical significance. The dollars of a model whose price nobody verified are unknown, and unknown is never zero. The judge of the arms is the deterministic one with the stub of the NLI of the repository, and the client of the exchange runs on the fixtures of the repository: the absolute numbers are not the numbers of the published online report, and the two arms are the ones that are comparable with each other.

The cohort is 31 cases, the digest of the file is `28f16cabcbb7391112ac6a7bbe6567ec877eeba3207dd1caa3c3933761362351` and the ledger of the two arms is `994667ee48fb14a1f59858b2861716e291e9bd235c0817bf9c34904a9e10e91a`.

## The arm `one_model`

One model in the four slots of the run: openai:gpt-4.1-mini.

| Slot | The model of the slot |
| --- | --- |
| agent | openai:gpt-4.1-mini |
| policy | openai:gpt-4.1-mini |
| sql | openai:gpt-4.1-mini |
| triage | openai:gpt-4.1-mini |

The accuracy is 0.7638 over 31 cases, and 21 of them carried every expected fact.

| Intent | The accuracy | The cases |
| --- | --- | --- |
| chargeback_status | 1.0 | 1 |
| duplicate_charge | 1.0 | 1 |
| fx_question | 0.75 | 2 |
| other | 0.0 | 2 |
| policy_question | 0.5 | 4 |
| refund_discrepancy | 0.6357 | 5 |
| settlement_question | 1.0 | 1 |
| status_lookup | 0.9333 | 15 |

The money per correct case is 0.005369 dollars, and the tokens per correct case are 12243.

The p95 of the latency is 10520 ms over 31 cases.

The rate of the fallback is 0.0 over 143 calls, and the number was not measured: the repository has no fallback with a budget in this path, so the rate was not measured.

| The model | The calls | The share | The tokens |
| --- | --- | --- | --- |
| openai:gpt-4.1-mini | 143 | 1.0 | 257105 |

## The arm `cascade`

The model of each slot, chosen by the task the slot does, read from the cascade.

| Slot | The model of the slot |
| --- | --- |
| agent | openai:gpt-4.1 |
| policy | openai:gpt-4.1-mini |
| sql | openai:gpt-4.1 |
| triage | openai:gpt-4.1-mini |

The accuracy is 0.76 over 31 cases, and 21 of them carried every expected fact.

| Intent | The accuracy | The cases |
| --- | --- | --- |
| chargeback_status | 0.6667 | 1 |
| duplicate_charge | 1.0 | 1 |
| fx_question | 0.75 | 2 |
| other | 0.5 | 2 |
| policy_question | 0.5 | 4 |
| refund_discrepancy | 0.5786 | 5 |
| settlement_question | 1.0 | 1 |
| status_lookup | 0.9 | 15 |

The money per correct case is unknown, because the price of openai:gpt-4.1 was never verified, and the tokens per correct case are 10161.

The p95 of the latency is 7168 ms over 31 cases.

The rate of the fallback is 0.0 over 128 calls, and the number was not measured: the repository has no fallback with a budget in this path, so the rate was not measured.

| The model | The calls | The share | The tokens |
| --- | --- | --- | --- |
| openai:gpt-4.1 | 90 | 0.7031 | 169745 |
| openai:gpt-4.1-mini | 38 | 0.2969 | 43651 |

