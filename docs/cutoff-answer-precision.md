# Factual precision on dispute deadlines

The comparison covers ten English questions about two events. Missing the internal evidence cutoff requires human review. Sending the merchant response after its final deadline loses the dispute automatically. A policy lookup can explain either consequence without establishing the recorded status of a particular dispute. [Chargeback handling](../data/policies/chargeback-handling.md) and [escalation policy](../data/policies/escalation-and-review.md).

## How to read the comparison

Each version answered the same ten synthetic questions with GPT-4.1 and the same policy index. Five runs of the original missed-cutoff question measure variation. The other nine questions have one run per version. Four new questions test whether the wording change transfers to related requests. The run order was sequential. This is a paired offline comparison using live model calls. It does not measure visitor outcomes. [Trustworthy Online Controlled Experiments](https://experimentguide.com/).

A separate model reviewer saw the final answers in shuffled order without version labels. It counted distinct factual assertions in each answer and checked them against the two policies. Pooled precision divides supported assertions by all assertions. A clarification with zero assertions contributes to neither count. The fully correct answer count includes every trial and requires a useful answer to the question. This adapts claim-level evaluation to payment policy. [FActScore](https://aclanthology.org/2023.emnlp-main.741/).

The [comparison data](../data/eval/reports/cutoff-answer-precision.json) contain each question, both versions' answers, the review and the source hashes. To repeat the original missed-cutoff case on a checkout with an OpenAI key, run:

    uv run python -m scripts.report_policy_journeys --case cutoff-passed --repeat 5 --strict

The investigator and retrieval used OpenAI. The workflow's verifier used the offline stub in both versions. Its labels do not determine the scores here. One reviewer graded the answers. The repeated question accounts for five of fourteen trials in each arm, and the questions all concern disputes.

For a new answer-quality experiment, specify the failure, the reference that supports the scoring method, the authoritative evidence for each case and the acceptance criteria before changing the prompt. Run both versions on the same cases. Reserve independently written questions for transfer checks and report abstentions beside precision. Once an answer informs a prompt edit, its question counts as a regression case in later rounds.

## Results

| Question set | Control supported claims | Candidate supported claims | Control fully correct answers | Candidate fully correct answers |
| --- | ---: | ---: | ---: | ---: |
| All ten questions | 42/55 (76.4%) | 36/38 (94.7%) | 4/14 | 8/14 |
| Original missed-cutoff question, five runs | 20/29 (69.0%) | 15/15 (100%) | 0/5 | 5/5 |
| Four new questions, one run each | 12/13 (92.3%) | 12/13 (92.3%) | 2/4 | 1/4 |

Both versions gave a substantive answer on 13 of 14 trials. The candidate made fewer claims. Its improvement was concentrated in the question that motivated the edit. On the four new questions precision tied, and the candidate had one fewer fully correct answer. Both versions missed the distinction between when a response was sent and when it was received. The candidate also left a merchant's request for what to tell the disputes team incomplete. This sample gives no estimate of overall agent precision.

The intermediate comparison covered six questions and ten trials per arm. Its blinded reviewer counted 34/47 supported claims for the control and 32/40 for the intermediate prompt. The final comparison used a fresh reviewer and included four additional questions. Compare arms within each round.
