# The latency of a turn over the evaluation set

The set: `eval_cases` (`data/eval/eval_cases.jsonl`, digest `28f16cabcbb7391112ac6a7bbe6567ec877eeba3207dd1caa3c3933761362351`), role `tuning` in the manifest of the datasets. A latency over a tuning set is a tendency and not a generalization.

The model: the scripted model of the offline evaluation, temperature 0. The latency measured is the latency of the plumbing of the turn on this machine.

The hardware: arm, 12 cores, 32 GiB, Darwin 25.6.0, Python 3.12.13.

The method of the percentile: nearest_rank. The denominator: 31 cases that produced a measurement.

| stage | p50 (ms) | p95 (ms) |
|---|---|---|
| end to end | 26.0 | 148.0 |
| triage | 2.0 | 7.0 |
| agent | 21.0 | 136.0 |
| verify | 2.0 | 9.0 |
| escalation | None | None |
