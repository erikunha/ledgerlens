---
type: adr
status: accepted
date: 2026-11-07
---

# ADR-007: Answer verification with an NLI model

Status: accepted. Date: 2026-11-07.

## Context

The project needs a check of factual consistency with a natural language inference (NLI) model (contradiction, support, neutrality) and a check of logical coherence. The model never decides whether a number is right.

## Decision

After the agent answers, the verifier:

1. extracts claims from the answer (each with a kind: fact, number, policy or inference);
2. for text claims, compares each one with the text of the cited evidence using `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` (premise: evidence, hypothesis: claim). The labels (entailment, neutral, contradiction) are read from `id2label` and never fixed in the code;
3. for numeric claims, compares the value with the result of the `calculate` tool, by code, never by NLI;
4. applies coherence rules (settlement with `net = gross - refunds - fees`, a status compatible with the last event, a recommended action compatible with the supported claims, and exchange-rate date with an origin: the rate the answer uses must be from a day that appears in a ledger date column of the turn or in the question, otherwise coherence fails, the day goes into `missing_information` and the case goes to human review; without ledger evidence the rule does not apply);
5. writes one verdict per claim (`supported`, `contradicted` or `not_enough_evidence`) and sets `requires_human_review` if there is a contradiction.

The decision thresholds are calibrated on the verification set and live in `ledgerlens/verify/thresholds.json`. The model loads on demand and lives in an optional `verify` extra. The tests use a deterministic stand-in, and a test marked `slow` uses the real model.

Claims and evidence are in English, the language the NLI model was trained on.

## Alternatives considered

- **An LLM as the only judge.** The project uses an NLI model. The judge stays as an extra signal.
- **A larger NLI model.** More accurate and slower. It stays as a configuration key.
- **Rules only.** They do not handle policy text.
- **ONNX variant of the model.** It would remove `torch`, but it was not tested.

## Consequences

- A small model can err on long texts (limit of 512 tokens). Claims and evidence are cut to fit.
- The verifier is one more step per answer, with a CPU cost.
- The false positive rate and the missed contradiction rate are measured targets, not assumptions.

## Readable premise and human review

**Premise.** The NLI model does not receive the tool's JSON. `render_premise` (`ledgerlens/verify/claims.py`) writes each row of a query as `column: value`, without the SQL. The SQL equality filters (`id = 'TX-0001'`) enter as columns, because a query on `status` alone does not say whose value it is. Filters with `OR`, `NOT`, a subquery or the same column with two values do not enter. An empty result becomes "zero rows found ... the record does not exist": with `rows: []` the model "contradicted" the true claim that the record does not exist. The sentence opens with "zero" and not "no", so a claim that only repeats the row count is not read as its negation. Policy, exchange rate, calculation, recalled case and record with parts become text; whatever has no known format passes as it came. The evidence stored in the result stays the original JSON.

For a premise longer than 1500 characters (the model reads 512 tokens), only the rows that cite the most ids from the claim are kept. Without this, the other similar rows (the settlements of the same merchant) made the model contradict a true claim.

Money values do not go through minor-unit conversion in the premise: the NLI model gave high entailment to a wrong value, so the value stays the job of `check_numeric`.

**Human review.** `requires_human_review` is raised by any of these rules:

- a contradicted claim;
- coherence failed;
- the share of claims with no verdict (`not_enough_evidence`) is above `unsupported_share_review` (0.34): one unverified claim in one or two escalates, one in three does not;
- an escalation rule of the policy applies to the rows (deadline, high amount, suspicious text);
- the flag already came raised (a tool failure with no recovery, or no evidence at all).

The share of claims with no verdict is the "verification could not be done" rule of the `escalation-and-review` policy. An answer with no evidence (variant A) or with no citations (variant B, which does not cite ids) has 100% of its claims with no verdict, so it always escalates. That is the behavior of the policy, not a defect, and the threshold was not moved. What was a defect: the unreadable premise and the truncated premise left correct answers with no verdict or contradicted.

## What is not a claim, a missing exchange rate and pronouns

**Sentences that claim nothing.** `extract_claims` creates no claim for a closing offer ("If you wish, I can detail...", "I am available") nor for a conclusion or caveat without a citation ("Therefore, ...", "In summary, ...", "Maybe ...", "It may be that ..."). A sentence without an evidence id never goes beyond `not_enough_evidence`, and two or three of them in a good answer pushed the no-verdict share above 0.34 and sent the case to review. A conclusion that cites evidence is still a claim, and so is "If the deadline expires, ...": only the "if you wish" is an offer. The 0.34 threshold did not change.

**Citations that close the paragraph.** A sentence without its own citation inherits the ids that close its paragraph ("... [api:1] [sql:1] [fx:...] [calc:1]."), only inside the paragraph and never beyond a blank line or a list item, and the NLI model judges it against that evidence. Inheritance gives the evidence, not the verdict: a value that the inherited `calculate` did not produce is not checked against it (rates: see the update on citations at the end). An offer and a caveat without their own citation stay out, and so does a conclusion, unless it states values.

**Pronouns.** A sentence that starts with "This settlement", "This dispute", "This refund" and similar gets the id of the previous sentence (`This settlement (ST-0002) ...`) when that sentence cites a single id of the kind the noun asks for. With two ids of the kind, or none, the sentence stays as it came. Without the id, the premise filter and the NLI model did not know which record the sentence was about.

**An exchange rate the source did not give.** `escalation.py` reads the trail: a `get_reference_fx` that failed with `UPSTREAM_UNAVAILABLE`, with no later call that obtained the same rate, raises human review, goes into `missing_information`, and the answer gains a sentence naming the rate (`EUR-BRL 2026-10-20`) when it does not cite it yet. There is no policy passage for this rule, so the reason carries no `policy:` id.

## Sign, direction and values without an origin in the numeric check

**Sign and direction.** `find_amounts` keeps the sign when the dash is attached to the number (`-14.08`, `BRL -3.00`); in `563.39 - 549.31` the dash is an operator. A sentence that states the direction in words ("14.08 lower", "more", "less", "higher") speaks in absolute value, and only the magnitude is compared with the `calculate` result, which carries the sign: which operand the calculation subtracted first does not show in the text (`566.79 - 549.31 = 17.48` and "17.48 less on the refund" are both right). Requiring the word to agree with the sign failed that sentence in an online run. Without a direction word, a flipped sign is still `contradicted`. Before, "14.08 lower" against `-14.08` became `contradicted` and sent the case to review because of a verifier error, not a model error.

**Value without an origin.** Before, one value in the sentence was enough to support the whole sentence, if it matched any cited `calculate` result: the `100` of a conversion with rate 1 supported a sentence whose `563.39` no calculation had produced. Now each stated value must match, with its sign, a result of a cited `calculate` or a cited ledger value (`_minor` columns divided by 100: `54,931.00` is not the ledger's `54931`). `supported` requires that no value is left without an origin and that at least one comes from a result or from the ledger; a value that only appears as an input of the calculation (the `formula`) is not enough. `contradicted` is kept for the clear pair: a single stated value, a single result, and the two differ. Any other leftover is `not_enough_evidence`, with the values without an origin in the verdict note.

## Which disputes count in deadline escalation

**Scope.** The rule on the card network deadline and the internal deadline applies to the disputes the conversation is about: those the question, the answer, the claims or the triage cite by id, or whose transactions they cite. Before, any dispute row the query brought back triggered the rule, and settlement ST-0044 went to a person because of two old disputes of the merchant (CB-0311 and CB-0312) that the question did not cite. With no id in the conversation, every row counts. The high amount and suspicious text rules do not change.

**Deadline read from the ledger.** The SQL the model writes can omit or rename columns (`stage AS status`, with no `id`), and the rule did not see the cited dispute. Now a dispute cited by id that the rows did not bring with `id`, `stage` and `deadline` is read from the ledger by code, opened read-only (the same file as the configuration, `LEDGERLENS_LEDGER_DB`, that the tools read). A ledger that is absent, unreadable or missing the dispute: nothing is added and verification goes on. The behavior of the tools did not change.

**Free text read from the ledger.** The same limitation applied to the suspicious text rule: in an online run (scenario S09) the model's SQL chose columns without `reason`, the instruction hidden in the reason of refund R-0750 did not reach the rule, and the case did not go to a person. Now the records that the question, the answer, the claims or the triage cite, and those the query brought back, are reread in full from the ledger (table by id prefix: `TX`, `R`, `CB`, `ST`, `M`, `C`), read-only, and the rule scans their text fields as well. The same record coming from the query and from the ledger counts once. A ledger that is absent, unreadable or missing the table: nothing is added. `verify_result` accepts `ledger_db`, and both integrators pass the `db_path` they were built with to the default verifier; an injected verifier does not change.

**Stated value without a cited calculation.** In an online run (scenario S08) sentences like "The fees were BRL 926.67 [sql:1]" went to the NLI model, which gave a low score to a value that is in the ledger, and the settlement was taken to a person by the share of claims without evidence. Now a claim that is not numeric (it does not cite `calculate`), states at least one money value and cites ledger evidence (`sql`, `ledger_api`) or exchange-rate evidence (`fx`) is checked by code, `method` numeric, and never reaches the NLI model. Each stated value must be exactly a number from the cited evidence: a `_minor` column divided by 100, `_major` as it is, and the stated currency must be the row's (`payout_currency` for `payout_amount_*`, otherwise `currency`, otherwise `settlement_currency`; a row without a currency accepts any). A column that is not money (`refund_window_days`, `rate`) only matches a value without a currency, and a percentage never matches. `supported` when all match; `contradicted` only in the clear pair (a single stated value, the sentence names a single money column, gross, refunds, fees or net, and that column has a single, different value); the rest is `not_enough_evidence`. Limit: only the numbers are checked. A sentence that is right on the values and wrong on the status ("the refund of BRL 549.31 was rejected") passes; the NLI model would catch it, but it gives a low score to true sentences with a value, which was the defect. Sentences without a money value, or that cite only policy, go to the NLI model as before.

## Citations at the end, conclusions with values and rates checked by code

**Defect.** The correct answer of an online run of scenario S01 ("... was 5.6339. Therefore, applying the lower rate of 5.4931 ... 549.31 ... 563.39 BRL. This explains the lower difference received on the refund [api:1]. [sql:1]. [fx:2026-10-20:EUR-BRL]. [calc:1].") went to human review for three causes, all in `claims.py` and `checks.py`.

**Citations separated by ". " at the end.** The rule that returns to a sentence the citation that comes after the period only recognized `[id]` followed by a space, so `[sql:1].` was left out. Each citation became a fragment of fewer than three words, discarded, and the paragraph "closed" only with the last one (`calc:1`): the first two sentences inherited only the calculation and the NLI model judged them against it. Now a sequence of citations after a period, each with or without a period, goes back into the previous sentence, before its period, and the paragraph closes with all of them.

**Conclusion with values.** "Therefore, applying the lower rate of 5.4931 ..." was discarded as a conclusion without its own citation, and with it went the numbers the answer most wants to prove. Now a conclusion without its own citation is a claim when it states at least one number and the paragraph cites evidence (it inherits that evidence). With no citation in the whole paragraph, or no number, it stays out. A caveat ("Maybe the value was 549.31") stays out even with a number: it does not assert the value, and checking it against the ledger would support it.

**Reference without a new fact.** "This explains/shows/indicates/demonstrates/confirms/means ... the difference" repeats what the earlier sentences claim. It went to the NLI model and was contradicted. Now it is not a claim when it states no number and no entity id (`TX-2048`), cited or not. "That is why, ..." was not added to this rule: with its own citation it says what follows and stays a claim; without its own citation it was already discarded as a conclusion.

**Rates.** A decimal with three or more places that is not a percentage (`5.4931`, `5.6339`, `5.6339 BRL per EUR`) is a rate: the currency that goes with it is the quote pair, not money, and a rate never counts as a money value in `has_currency_amount`. A sentence that states a rate and no money value, and cites ledger, API or exchange-rate evidence, is checked by code (`check_rates`), `method` numeric, and never reaches the NLI model to be approved by similarity: every stated number must be exactly a number from the cited evidence (`applied_rate`, `rate`, `_major` values), as in `check_ledger_amounts`, with no tolerance. `supported` when all match. `not_enough_evidence` when some rate is none of them. When the rates match but another number in the sentence is not confirmed by the code (a count, a percentage), the sentence goes to the NLI model as before. There is no `contradicted` for rates: no column is named by the sentence. A sentence with a rate and a money value stays in `check_ledger_amounts`, which already checked every stated number; there the rate matches any equal number from the ledger (`applied_rate`, `rate`), and money stays exact and in the column's currency. Limit, the same as before: only the numbers are checked. The sentence "the applied rate (5.4931) was lower than the reference (5.6339)" is supported because both numbers are in the ledger and the exchange-rate evidence; the comparison between them and the cause ("because") are not checked.

**Test.** `tests/verify/test_live_answers.py` takes the answer above with the real tool envelopes and forbids the NLI model: both claims come out `supported` by `numeric` and the case does not go to review.

## Thresholds calibrated with live sentences

**Why change them.** A threshold chosen on short, clean sentences sits on a plateau: the verification set gives the same result across a wide range, because the NLI model separates short English sentences at 0.0 or 1.0. That set does not discriminate a threshold. The sentences the agent writes are different: long, against `column: value` rows.

**Live set.** `data/eval/verification_live.jsonl` has 40 text claims: 28 written by `gpt-4.1-mini` in two online runs of the scenarios (the evidence is what the tools returned, stored with it) and 12 in which one fact of one of them was changed by hand (date, currency, status, count, negation). Each row carries the label, the origin and a note. The labels came from one person reading the evidence: `supported` when every fact in the sentence is in the cited evidence (a particular case of a general rule counts), `contradicted` when the evidence says something else, `not_enough_evidence` when the evidence does not say. One label (lv06) was revised after the first scoring, on the argument that the general rule covers the particular case. Numeric claims are left out: they go to `check_numeric`, not to the NLI model. Reading is subjective in judgment cases ("the refusal is correct"), and the set is small: the numbers below guide, they do not measure a rate.

**Rule.** Over the two sets together (30 + 40 text cases, real NLI model, premise built by `text_premise`): no false `supported` and no false `contradicted`, the highest accuracy, and on a tie the middle of the plateau. A false `supported` is the costly error: it lets through a sentence with no backing.

**Sweep** (accuracy over all cases; false `supported` and `contradicted`; accuracy on the live set only):

| entailment_min (contradiction_min 0.91) | accuracy | false supported | false contradicted | live |
|---|---|---|---|---|
| 0.50 | 0.829 | 2 | 0 | 0.700 |
| 0.70 | 0.786 | 1 | 0 | 0.625 |
| 0.76 | 0.771 | 1 | 0 | 0.600 |
| 0.77 to 0.84 | 0.786 | 0 | 0 | 0.625 |
| 0.85 | 0.771 | 0 | 0 | 0.600 |
| 0.90 | 0.743 | 0 | 0 | 0.550 |
| 0.95 | 0.729 | 0 | 0 | 0.525 |

| contradiction_min (entailment_min 0.81) | accuracy | false supported | false contradicted | live |
|---|---|---|---|---|
| 0.50 | 0.800 | 0 | 2 | 0.650 |
| 0.80 | 0.771 | 0 | 2 | 0.600 |
| 0.89 | 0.771 | 0 | 1 | 0.600 |
| 0.90 to 0.92 | 0.786 | 0 | 0 | 0.625 |
| 0.93 | 0.757 | 0 | 0 | 0.575 |
| 0.95 | 0.757 | 0 | 0 | 0.575 |

**Choice.** `entailment_min` 0.81 and `contradiction_min` 0.91, the middle of the plateau (0.77 to 0.84 by 0.90 to 0.92) where no case is a false `supported` or a false `contradicted`. There the verification set is right on all 30 cases and the live set on 25 of 40 (combined accuracy 0.786). `calibrated_with` and the rule are kept in `thresholds.json`; the slow test `test_the_chosen_thresholds_follow_the_calibration_rule_on_both_sets` redoes the sweep with the real model and fails if the thresholds leave the rule.

**What the sweep shows.** Lowering the support threshold lets an unbacked sentence through below 0.77: lv10 says how the net amount of a payout is calculated, and the passage it cites does not carry the formula. Lowering the contradiction threshold below 0.90 marks two sentences as contradicted that are not: lv17 (a conclusion about a rate the evidence does not carry) and lv21 (a true sentence about two captured purchases). The 15 cases still wrong at the chosen thresholds are all `not_enough_evidence` predictions: 12 true sentences that get low entailment and 3 contradictions the model does not see. That is a limit of the premise and of the model, not of the threshold, and a threshold does not fix it.
