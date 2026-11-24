# The routing of the inference

The router of [ADR-078](decisions/ADR-078-the-model-of-each-slot-is-chosen-by-the-work-it-does.md) chooses the model
of each slot of a run by the task the slot does. This page says what the cascade is, what the router writes down,
the rules that keep the routing honest and the numbers of the comparison of the two routes, with the set they were
measured over.

A number without its dataset is a claim about nothing in particular. Every number of this page names the cohort
and the ledger it was measured over.

## The cascade

The deployment declares the cascade in `LEDGERLENS_MODEL_CASCADE`, from the lightest model to the most capable:
`gpt-4.1-mini` and then `gpt-4.1`. A slot takes the cheapest model of the cascade that is at or above the level its
task demands and that really has the capability the task needs.

| Slot | The task of the slot | The level | The model of the cascade |
| --- | --- | --- | --- |
| `triage` | read the question and write the plan of the investigation | light | `gpt-4.1-mini` |
| `policy` | rewrite the question of the analyst into the words of the corpus of the policies | light | `gpt-4.1-mini` |
| `sql` | write the statement that reads the ledger | standard | `gpt-4.1` |
| `agent` | plan the investigation and answer with the tools | robust | `gpt-4.1` |

A deployment that declares no cascade puts the model of `LEDGERLENS_MODEL` in every slot, which is the behaviour the
product had before the router existed.

The verifier is never routed. It is the deterministic judge of the repository and it runs on the machine of the
server.

## The nine fields of the decision

The router writes the decision down before the run starts, and it writes it once. The decision is a value, so a
reader can check what was decided and when, and a run whose decision changed in the middle is a run that can be
read as two runs.

| The field | What it carries |
| --- | --- |
| `case_id` | the case the decision is about |
| `case_type` | the type of the case |
| `risk_tier` | the tier of the case, verified before the routing decided |
| `allowed_provider_models` | the models of the allowlist that the deployment allowed |
| `chosen_model` | the model that runs the slot |
| `reason` | why that model and not another one |
| `budget` | the ceiling of the run, in words |
| `price_snapshot` | the price of the model, and the day it was verified, when the price was verified at all |
| `confidence_kind` | whether the capability of the model was really exercised or only declared |

The decision is published: the manifest of the bundle, the provenance of the site and the card of the catalogue
name the model of each slot, so a reader of a recording sees the division of the work and not only the model that
wrote the answer.

## The rules of the honesty

1. **A model only runs a task when the capability that task needs was really verified for it.** A model that never
   called a tool does not plan the answer with the tools. A model outside the allowlist is still a candidate,
   because a deployment may run a model the repository never exercised, but its capabilities are undeclared and the
   decision carries that kind of confidence.
2. **A model a human chose is never silently replaced**, in any path. The router chooses among the models the
   deployment allowed, and the choice of a person is the choice.
3. **A price that was never verified is unknown, and unknown is never zero.** A price of zero would say that the
   call was free. The price of `gpt-4.1` was never verified in this repository, so the money of the calls of that
   model is unknown and the numbers of this page say so.
4. **The decision is written once and never changes.** It is written before the run starts, it is carried by the
   trace as it is, and a run whose model changed in the middle is a run nobody can reason about.

A level that the cascade does not reach is said in words: the most capable model of the cascade runs the task and
the reason says that the level was not reached, because a silent downgrade is a lie about what ran.

## The live path keeps one model

The router does not touch the live mode of the visitor. [ADR-037](decisions/ADR-037-the-case-of-the-demo-runs-on-a-bridge-over-the-caller.md)
says that a run of the live mode has exactly one model: the four slots are four views of the same model and the
model never changes in the middle of the run. The comparison below is a measurement of the routing and not of the
live mode of a visitor.

## The fallback of a run

A model that fails a task is a model that was not capable enough for it, and the cascade has a model above it. The
retry of that task with the next model of the cascade is the fallback, and it is the one place of a run where a call
happens that the plan of the run did not ask for, so it is the one place where two rules hold.

1. **The consent comes from the deployment.** `LEDGERLENS_FALLBACK_ATTEMPTS` says how many retries a failed task may
   get, and `LEDGERLENS_FALLBACK_DIRECTION` says in which direction of the cascade they go.
   The default is no retry at all: the shipped paths behave exactly as they behaved before, and a run that spends a
   call nobody asked for is a run that spends money nobody approved.
2. **The remaining budget has to cover the retry, and the check happens before the call.** The reservation of the
   retry is what checks the caps, so the money of a retry the budget does not cover is never spent, and the caps of
   the run are the same before and after the decision. The reservation carries the tokens the caller plans, because
   a cap of the tokens and a cap of the money are caps of a planned call.

The retry goes up the cascade by default, because a model that failed a task is a model that was not capable enough
for it. A failure with no retry left stops the run with the reason and with no further call. The retry is never the
model that just failed: two providers may know a model by the same name, and the neighbour of the retry is the one
above the position of the failed model in the cascade.

The decision is a value: it carries the action, the model, the reason, the number of the attempts and the strategy,
so a reader of a recording of a run that retried sees the model of the retry and the reason of it. The decision moves
no counter of the budget, and the reservation is a step of its own that comes after it and before the call. The
module decides and reserves, and the caller calls.

The retry is wired into the run in the two places where a model of the run fails: the triage of the run and the
model of the graph. The models that the tools call, the statement that reads the ledger and the rewrite of the
search of the policies, are not wired yet.

Four of the rules of the wiring hold here, and they are the rules of the module:

1. **The retry never repeats a model that this task already tried.** The call that failed already happened and the
   money of it is already spent, and a retry that answers the same model would spend the budget of the run twice for
   the same failure. The rule is wider than the neighbour of the failed model: a cascade that holds the same model
   twice, or a retry whose model was the model of an earlier failure of the same task, stops the retry too.
2. **The retry is outside the reservation of the graph.** The reservation books the usage of a call under the model
   of that call, and a retry that ran inside it would book the tokens of the model of the retry under the model that
   failed. Every attempt of the turn is therefore reserved under its own model, and the reservation of the retry
   carries the input it is about to send and the output it asks for, so the cap of the money and the cap of the
   tokens are checked before the call. The model of the retry is built before it is reserved, so a deployment that
   cannot build it is not charged for a call that never happens. The plan of the retry of the triage is the whole
   prompt of the triage, its system message included, and not the complaint alone: the system message is the
   largest part of the call, and a plan built from the complaint alone would undercount it by two orders of
   magnitude and would let a cap pass a call that does not fit.
3. **The consent counts the retries of a task, and a task is a call of a model.** The triage is a task and each call
   of the graph is a task of its own, so a task that fails gets the retries the deployment consented to and the task
   that comes after it gets its own.
4. **The side that holds the provider is the one that reserves the call.** A turn that does not own the counting
   refuses the retry, because a retry that nobody reserves would spend the money of the run outside the caps of the
   run.

The caller that holds the provider builds the model of a retry, and the live path of the visitor holds the credential
of the visitor and not the key of the server, so the live path has no retry at all and keeps the one model of
ADR-037.

A turn of the graph that stops because the retry did not happen comes back as a result that names the reason, and
not as an exception that nobody reads. The result is the answer of a turn that owns the counting, and a turn whose
budget belongs to the caller raises the stop, because the caller is the one that has to read it. The decision of
the retry is in the trace of the turn, with the model of the retry and the reason of it, and a stop leaves a
decision in the trace too, so a reader of the trace sees a run that stopped and why. The decision of a stop carries
no model, because no model ran the retry, and the reason names the model that the retry would have used when there
was one. The cap that the budget recorded is the cap the result names.

The name of the model of the triage comes from the deployment when the router named the slot of the triage, and from
the model of the triage itself when the caller routed nothing. The demo of the repository names no slot at all. The
comparison of the routes carries the four names of the arm, and the retry of the triage reads the one of the slot of
the triage: the other three arrive at the run as the model objects of their slots, and the router named them where it
decided. The model of the graph is not named that way either: the graph knows the model it is running with, and the
retry of a call of the graph reads that one.

The tokens of the triage are not in the report of the coordinator: the chain of the triage answers with the plan and
not with the message of the provider, and the tokens of the provider are in the message. The tokens of the triage
are in the trace of the run, the plan of the retry of the triage is the whole prompt, and the gap is of the triage
path and not of the wiring.

The rate of the fallback of the comparison of the routes is still not measured: the comparison builds no runner, so
the zero it publishes says that the question was not asked.

## The economics of a cohort

The cost of a run is what the coordinator of the budget counts. The cost of a cohort is what the economics module
computes, and it is a different number: the total of the cohort, the number of cases the code resolved and the money
of a case that was actually settled.

The module reads the results of the runs that already happened and it never calls a model
([ADR-086](decisions/ADR-086-the-economics-module-computes-and-never-calls-a-model-and-an-unknown-stays-unknown.md)).
The oracle of a resolved case comes from the code that resolved it, and a case that went to a person is not a
resolved case: it pays the money of its review and it is not in the denominator.

Every amount is a `Decimal`, and every result carries the assumptions that produced it: the minutes of a review, the
rate of an hour and the price snapshot are assumptions of the reader and not facts of the repository.

The economics of the cohort of the comparison above are published in `data/eval/`, and the script
`scripts/export_economics.py` writes them from the published measurement:

| The measure | The arm `one_model` | The arm `cascade` |
| --- | --- | --- |
| the total of the cohort | 0.1116704 dollars | unknown |
| the cases the code resolved | 22 of 31 | 21 of 31 |
| the cost of a resolved case | 0.005076 dollars | unknown |
| the cases that went to a person | 0 | 0 |

The money of the arm of the cascade is unknown because the price of `gpt-4.1` was never verified in this repository,
and unknown is never zero. The cost of a resolved case of the arm of one model is the same number the comparison
above publishes, because the denominator is the same: the cases the code resolved with every expected fact found.

The comparison of the two arms publishes no difference, because the money of one of them is unknown, and the artifact
names the reason instead of printing a difference of nothing. The cost of a review is an assumption, and the cohort
of this measurement holds no case that went to a person, so no review money enters the published total.

[ADR-086](decisions/ADR-086-the-economics-module-computes-and-never-calls-a-model-and-an-unknown-stays-unknown.md)
is the decision that says what the economics module computes and what it refuses to publish.

[ADR-084](decisions/ADR-084-the-fallback-of-a-run-happens-only-with-a-consent-of-the-deployment-and-with-the-budget-that-is-left.md)
is the decision that says what a fallback has to carry to be allowed, and
[ADR-085](decisions/ADR-085-the-retry-of-a-failed-model-is-wired-into-the-triage-of-the-run-and-into-the-model-of-the-graph.md)
is the decision that says where the retry is wired into the run.

## The comparison of the routes

The comparison runs the same cohort of cases twice, over the same ledger: once with one model in the four slots,
which is the behaviour the product had before the router, and once with the cascade. The numbers are below, with
the set they were measured over.

The cohort is 31 cases, the file is `data/eval/eval_cases.jsonl`, its digest is
`5909f0fc62f8ef89d09b7a2da69b26d1c427182fb0c424a5ba934b72e855caaa` and the ledger of the two arms is the versioned
sample of the repository, `b1f1e6aedcd72fc20cabc1be83bbf4c00c3d0ef5b7fca1690dafc04d4552f678`. The measurement ran on
2026-11-24 with a real model, and the full report is `data/eval/routing_comparison.json` with the same numbers as
prose in `data/eval/routing_comparison.md`.

One run per case and one arm per model: the numbers are a trend and not a statistical significance.

| The measure | The arm `one_model` | The arm `cascade` |
| --- | --- | --- |
| the accuracy over 31 cases | 0.8134 | 0.7331 |
| the cases that carried every expected fact | 22 of 31 | 21 of 31 |
| the tokens per correct case | 11528 | 10461 |
| the money per correct case | 0.005076 dollars | unknown |
| the p95 of the latency | 10612 ms | 6412 ms |
| the calls | 145 | 131 |
| the fallbacks | 0 | 0 |
| the models | `gpt-4.1-mini` in the four slots | `gpt-4.1` in `agent` and `sql`, `gpt-4.1-mini` in `triage` and `policy` |

The accuracy by intent, with the number of cases behind every share:

| Intent | The cases | `one_model` | `cascade` |
| --- | --- | --- | --- |
| `chargeback_status` | 1 | 1.0 | 0.3333 |
| `duplicate_charge` | 1 | 1.0 | 1.0 |
| `fx_question` | 2 | 0.75 | 0.75 |
| `other` | 2 | 0.0 | 0.5 |
| `policy_question` | 4 | 0.75 | 0.5 |
| `refund_discrepancy` | 5 | 0.7429 | 0.4786 |
| `settlement_question` | 1 | 1.0 | 1.0 |
| `status_lookup` | 15 | 0.9333 | 0.9 |

What the numbers say and what they do not say:

1. **Over this run the arm of one model was the more accurate one**, 22 of the 31 cases against 21, and the page says
   it because the page publishes the measurement and not the hope of it. The routing does not win here.
2. **The comparison ran twice and the two runs disagreed.** The first run of the same comparison, over the same
   cohort and the same ledger, gave the cascade the higher accuracy: 21 of the 31 cases against 18 of the one
   model. The second run gave the one model 22 and the cascade 21. Two runs of the same comparison that disagree
   about which arm is more accurate are the proof that one run per case is a trend and not a significance, and
   the difference of the accuracy of the two arms is not established by this comparison.
3. **The tokens and the latency are on the side of the cascade, in both runs.** The cascade used 10461 tokens per
   correct case against 11528, and its p95 of the latency was 6412 ms against 10612 ms, and it made 14 calls less
   over the same cohort. The tokens were counted, so they can be put side by side.
4. **The cascade cannot be called cheaper, because its money is unknown.** The price of `gpt-4.1` was never verified
   in this repository, so the money of the 91 calls of that model is unknown, and unknown is never zero. The
   `one_model` arm paid a price that is known, 0.005076 dollars per correct case, and the comparison cannot put the
   two arms side by side in dollars.
5. **The intents with one or two cases do not decide anything.** `chargeback_status` is a single case that the two
   arms answered differently, and the one case says that the answer was not the same, and not which arm is better.
   The `refund_discrepancy`, with five cases, is the intent with the largest difference, and five cases over one
   run is not a measure.
6. **The rate of fallback is zero in both arms, and the number was not measured.** The repository does not have a
   fallback with a budget in this path, so the zero says that the question was not asked, and not that the routes
   never need one.
7. **The absolute numbers are not the numbers of the published online report.** The judge of the arms is the
   deterministic one with the stub of the NLI of the repository, and the client of the exchange runs on the
   fixtures of the repository. The report carries the judge in the field `judge`, and the two arms of the
   comparison are the ones that are comparable with each other.
8. **The live path is not measured here.** The live mode of a visitor keeps one model, and the comparison is a
   measurement of the routing over the cohort of the evaluation and not of the live mode.

The comparison is a hypothesis until it is measured, and
[ADR-083](decisions/ADR-083-the-routing-is-measured-against-one-model-over-the-same-cases-and-every-number-carries-its-set.md)
is the decision that says what a measured comparison has to carry to be published.

## How the comparison is run

```bash
LEDGERLENS_MODEL=gpt-4.1-mini LEDGERLENS_MODEL_CASCADE="gpt-4.1-mini,gpt-4.1" \
  uv run python scripts/measure_routing.py
```

The script writes `data/eval/routing_comparison.json`, the numbers with their denominator, and
`data/eval/routing_comparison.md`, the same numbers as prose. It refuses to run offline, because a comparison over
scripted answers measures the plumbing and not the routing.
