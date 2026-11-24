# The latency of a turn over the evaluation set

The set: `eval_cases` (`data/eval/eval_cases.jsonl`, digest `5909f0fc62f8ef89d09b7a2da69b26d1c427182fb0c424a5ba934b72e855caaa`), role `tuning` in the manifest of the datasets. A latency over a tuning set is a tendency and not a generalization.

The model: the scripted model of the offline evaluation, temperature 0. The latency measured is the latency of the plumbing of the turn on this machine.

The hardware: arm, 12 cores, 32 GiB, Darwin 25.6.0, Python 3.12.13.

The method of the percentile: nearest_rank. The denominator: 31 cases that produced a measurement.

| stage | p50 (ms) | p95 (ms) |
|---|---|---|
| end to end | 10.0 | 30.0 |
| triage | 1.0 | 1.0 |
| agent | 8.0 | 26.0 |
| verify | 1.0 | 1.0 |
| escalation | None | None |
