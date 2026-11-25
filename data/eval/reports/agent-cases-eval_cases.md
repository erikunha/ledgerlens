# The per case report of the agent over eval_cases (role tuning)

The correctness of the agent and the accuracy of the verifier are two different measurements over two different sets. This report publishes the correctness of the agent, and the accuracy of the verifier lives in the per case report of the verifier.

| case | scenario | correctness of the agent | trajectory | tools of the agent |
|---|---|---|---|---|
| EC-01 | S01 | 0.75 | 0.0 | query_ledger, query_ledger, get_reference_fx, get_ledger_record, calculate |
| EC-02 | S02 | 1.0 | 0.0 | query_ledger, query_ledger |
| EC-03 | S03 | 1.0 | 1.0 | query_ledger, search_policies |
| EC-04 | S04 | 0.5 | 1.0 | query_ledger |
| EC-05 | S05 | 0.5 | 1.0 | query_ledger |
| EC-06 | S06 | 1.0 | 0.0 | query_ledger, search_policies, query_ledger |
| EC-07 | S07 | 0.5 | 0.0 | get_ledger_record, get_ledger_record |
| EC-08 | S08 | 1.0 | 0.0 | query_ledger |
| EC-09 | S09 | 1.0 | 1.0 | query_ledger |
| EC-10 | S10 | 0.5 | 0.0 | query_ledger, get_ledger_record, get_reference_fx |
| EC-11 | S11 | 0.5 | 0.0 | query_ledger, calculate, get_reference_fx, get_reference_fx, query_ledger, get_reference_fx, get_reference_fx |
| EC-12 | S12 | 0.0 | 1.0 | recall_cases |
| EC-13 | None | 1.0 | 0.0 | query_ledger |
| EC-14 | None | 1.0 | 0.0 | query_ledger |
| EC-15 | None | 1.0 | 0.0 | query_ledger |
| EC-16 | None | 1.0 | 0.0 | query_ledger |
| EC-17 | None | 1.0 | 0.0 | query_ledger |
| EC-18 | None | 1.0 | 0.0 | query_ledger |
| EC-19 | None | 1.0 | 1.0 | query_ledger |
| EC-20 | None | 1.0 | 1.0 | query_ledger |
| EC-21 | None | 1.0 | 1.0 | query_ledger |
| EC-22 | None | 1.0 | 1.0 | query_ledger |
| EC-23 | None | 1.0 | 1.0 | query_ledger |
| EC-24 | None | 1.0 | 1.0 | query_ledger |
| EC-25 | None | 1.0 | 1.0 | search_policies |
| EC-26 | None | 1.0 | 1.0 | search_policies |
| EC-27 | None | 1.0 | 1.0 | search_policies |
| EC-28 | None | 0.0 | 0.0 |  |
| EC-29 | None | 1.0 | 1.0 | search_policies |
| EC-30 | None | 0.0 | 1.0 | search_policies |
| EC-01 | S01 | 0.25 | 0.0 | query_ledger, calculate |
| EC-02 | S02 | 1.0 | 0.0 | query_ledger |
| EC-03 | S03 | 1.0 | 1.0 | query_ledger, search_policies |
| EC-04 | S04 | 0.5 | 1.0 | query_ledger |
| EC-05 | S05 | 0.5 | 1.0 | query_ledger |
| EC-06 | S06 | 1.0 | 0.0 | query_ledger, search_policies, get_ledger_record |
| EC-07 | S07 | 0.5 | 0.0 | query_ledger, query_ledger, calculate |
| EC-08 | S08 | 1.0 | 0.0 | query_ledger |
| EC-09 | S09 | 1.0 | 1.0 | query_ledger |
| EC-10 | S10 | 0.5 | 0.0 | query_ledger, get_ledger_record, get_reference_fx |
| EC-11 | S11 | 0.5 | 0.0 | query_ledger, calculate, get_reference_fx, query_ledger, get_reference_fx |
| EC-12 | S12 | 0.0 | 1.0 | recall_cases |
| EC-13 | None | 1.0 | 0.0 | query_ledger |
| EC-14 | None | 1.0 | 0.0 | query_ledger |
| EC-15 | None | 1.0 | 0.0 | query_ledger |
| EC-16 | None | 1.0 | 0.0 | query_ledger |
| EC-17 | None | 1.0 | 0.0 | query_ledger |
| EC-18 | None | 1.0 | 0.0 | query_ledger |
| EC-19 | None | 1.0 | 1.0 | query_ledger |
| EC-20 | None | 1.0 | 1.0 | query_ledger |
| EC-21 | None | 1.0 | 1.0 | query_ledger |
| EC-22 | None | 1.0 | 1.0 | query_ledger |
| EC-23 | None | 1.0 | 1.0 | query_ledger |
| EC-24 | None | 1.0 | 1.0 | query_ledger |
| EC-25 | None | 1.0 | 1.0 | search_policies |
| EC-26 | None | 1.0 | 1.0 | search_policies |
| EC-27 | None | 1.0 | 1.0 | search_policies |
| EC-28 | None | 0.0 | 0.0 |  |
| EC-29 | None | 1.0 | 1.0 | search_policies |
| EC-30 | None | 0.0 | 1.0 | search_policies |
| EC-01 | S01 | 1.0 | 0.0 | query_ledger, calculate, get_reference_fx, get_ledger_record, calculate, get_ledger_record, get_reference_fx, calculate |
| EC-02 | S02 | 1.0 | 0.0 | query_ledger |
| EC-03 | S03 | 1.0 | 1.0 | query_ledger, search_policies |
| EC-04 | S04 | 0.5 | 1.0 | query_ledger |
| EC-05 | S05 | 0.5 | 1.0 | query_ledger |
| EC-06 | S06 | 0.5 | 0.0 | query_ledger, search_policies, query_ledger, query_ledger |
| EC-07 | S07 | 0.5 | 0.0 | get_ledger_record, get_ledger_record |
| EC-08 | S08 | 1.0 | 0.0 | query_ledger |
| EC-09 | S09 | 1.0 | 1.0 | query_ledger |
| EC-10 | S10 | 0.5 | 0.0 | get_ledger_record, get_reference_fx |
| EC-11 | S11 | 1.0 | 0.0 | query_ledger, calculate, get_reference_fx, get_ledger_record, get_ledger_record, get_reference_fx, get_reference_fx |
| EC-12 | S12 | 1.0 | 1.0 | recall_cases |
| EC-13 | None | 1.0 | 0.0 | query_ledger |
| EC-14 | None | 1.0 | 0.0 | query_ledger |
| EC-15 | None | 1.0 | 0.0 | query_ledger |
| EC-16 | None | 1.0 | 0.0 | query_ledger |
| EC-17 | None | 1.0 | 0.0 | query_ledger |
| EC-18 | None | 1.0 | 0.0 | query_ledger |
| EC-19 | None | 1.0 | 1.0 | query_ledger |
| EC-20 | None | 1.0 | 1.0 | query_ledger |
| EC-21 | None | 1.0 | 1.0 | query_ledger |
| EC-22 | None | 1.0 | 1.0 | query_ledger |
| EC-23 | None | 1.0 | 1.0 | query_ledger |
| EC-24 | None | 1.0 | 1.0 | query_ledger |
| EC-25 | None | 1.0 | 1.0 | search_policies |
| EC-26 | None | 1.0 | 1.0 | search_policies |
| EC-27 | None | 1.0 | 1.0 | search_policies |
| EC-28 | None | 0.0 | 0.0 |  |
| EC-29 | None | 1.0 | 1.0 | search_policies |
| EC-30 | None | 0.0 | 1.0 | search_policies |
