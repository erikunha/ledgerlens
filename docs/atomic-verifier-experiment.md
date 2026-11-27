# Atomic verifier comparison

The experiment compares the published OpenAI prompt with a verifier that separates claims and checks their cited evidence. Both use the same GPT-4.1 mini snapshot at temperature zero. The candidate is experimental.

## Protocol

Freeze the new paired claims, expected verdicts and required answer facts before calling either model. Compare verdict accuracy, pairs with both verdicts correct and false entailments on identical inputs. Report the counts by behavioral slice. Treat a pair as one unit when interpreting results. The 48 previously inspected cases measure regression only.

For the answer comparison, use the same answer writer with the evidence, claim and verifier output in both arms. Preserve the complete responses. Grade each response against the case's required facts, checking for unsupported additions and material omissions. A complete answer covers every required fact without unsupported assertions. This measures answers in the experiment's verification task. The production investigation agent has a separate evaluation.

A candidate qualifies for further validation only if it increases new-case accuracy and fully correct pairs, has no increase in false entailments, delivers at least as many complete answers, and matches or exceeds the published 43/48 regression result. This small synthetic study cannot qualify a production rollout on its own.

## Sources

Minimal pairs and paraphrases isolate changes in behavior. [Ribeiro et al., Beyond Accuracy](https://aclanthology.org/2020.acl-main.442/). Splitting a response into individually verifiable claims follows [Min et al., FActScore](https://aclanthology.org/2023.emnlp-main.741/). Reporting slices follows [Huyen, Designing Machine Learning Systems](https://www.oreilly.com/library/view/designing-machine-learning/9781098107956/). Setting success metrics and guardrails in advance follows [Kohavi, Tang and Xu, Trustworthy Online Controlled Experiments](https://experimentguide.com/).

## Results

| Measure | Published classifier | Atomic classifier |
|---|---:|---:|
| Correct new claims | 22/24 | 21/24 |
| Both claims in a pair correct | 11/12 | 10/12 |
| Unsupported claims classified as entailed | 0 | 0 |
| Complete answers in the blinded review | 22/24 | 21/24 |
| Correct verdicts on the earlier regression set | 43/48 | 42/48 |

Both classifiers scored 6/6 on the event versus state slice. Both classified the two merchant delivery paraphrases as contradicted. The receipt confirms delivery to the bank and leaves delivery to the merchant unknown. These two errors are variants of one underlying example. The atomic classifier also produced an invalid conflict structure on a compound payout claim. An invalid output counts as incorrect, with no answer. On the earlier 48 cases it produced one invalid structure as well.

The candidate misses the criteria for further validation. The production verifier continues to use the published classifier. Exact quote matching can detect invented excerpts, but a model may omit a required part of the original claim or select an irrelevant passage. This study used one synthetic case author, one run per input and one automated reviewer. The reviewer saw the evidence, claim, required facts and anonymized answer. The review has no human adjudication.

[Paired cases and reference facts](../data/eval/atomic_verifier_pairs.json) · [Complete responses, verdicts and slice counts](../data/eval/reports/atomic-verifier-comparison.json) · [Blinded answer review](../data/eval/reports/atomic-verifier-answer-review.json)

To run a new paid comparison, configure the OpenAI key and run `uv run python -m scripts.compare_atomic_verifier --output /tmp/atomic-verifier-run.json`. A new run needs its own answer review.
