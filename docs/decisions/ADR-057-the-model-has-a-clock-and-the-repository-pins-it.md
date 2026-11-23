---
type: adr
status: proposed
date: 2026-11-22
---

# ADR-057: The model has a clock and the repository pins it

Status: proposed. Date: 2026-11-22.

## Context

OpenAI marks `gpt-4.1-mini` as **Deprecated** with an announced shutdown date of **2027-01-14**. The notice is dated
**14 October 2026** and lists the dated snapshots, `gpt-4.1-mini-2025-04-14` among them, each with the status Deprecated,
the shutdown date of 14 January 2027 and `gpt-6-luna` as the recommended replacement in every row
(https://developers.openai.com/api/docs/deprecations, read on 22 November 2026). The API reference carries the same day
for the short name and for the snapshot (https://developers.openai.com/api/reference/resources/$shared, read on
22 November 2026). Today is 22 November 2026, so there are fifty three days.

The notice answers the day the snapshot stops, the status and the name of a recommended replacement. It does not answer
what happens to the **short name** `gpt-4.1-mini` on that day: it lists the snapshots, and OpenAI does not say whether
the alias is withdrawn with the snapshot, keeps pointing at it, or is re-pointed at another model. One report of the
Models API of 2 November 2026 returned the same `shutdown_date` of 2027-01-14 for the short names as well, and the
expected failure mode is an HTTP 404 with `model_not_found`. The report is second hand, so this record does not pretend
the notice answers the question of the alias.

The repository calls the short name. `ledgerlens/byok/registry.py:306` holds `model_id="gpt-4.1-mini"`, with the status
`tested` (`registry.py:309`) and a price transcribed by hand (`registry.py:311-316`: `source="manual"`,
`last_verified=date(2026, 11, 8)`, 0.40 USD per million input tokens and 1.60 USD per million output tokens), which is
the list price the published online evaluation used, transcribed on the day that evaluation ran
(`ledgerlens/byok/registry.py:296-298`). The published evaluation names the same short name
(`data/eval/report_online.md:7` and `data/eval/report_online.json:31`), and the renderer writes that line from the report
(`ledgerlens/eval/run.py:705`) at temperature zero (`ledgerlens/eval/run.py:216`).

The design package already says what to do with a model that goes away: "Model removed/deprecated: mark profile retired,
block new runs, keep recorded historical artifact with date; refresh tested registry and eval before re-enable"
(`docs/v3/docs/13-CI-CD-DEPLOYMENT-AND-RUNBOOKS.md:66`). A date in a document is a note, and a note is not a guard.

## Decision

**The repository pins the dated snapshot, records the announced shutdown day in the registry beside the price and the day
the price was verified, refuses the run on that day from the code that already refuses, and publishes beside every number
the identity of the model that produced it. The switch to the replacement is not decided here.**

### 1. The pin is the dated snapshot `gpt-4.1-mini-2025-04-14`

The `model_id` of the profile becomes `gpt-4.1-mini-2025-04-14`, and the `profile_id` stays `openai-gpt-4.1-mini`
because it is the internal stable identifier of the profile (`docs/v3/docs/07-BYOK-MODEL-REGISTRY.md:38`). From the day
of this record the server calls the dated snapshot and not the alias.

**Why the snapshot and not the alias.** The notice publishes a day for the snapshot and says nothing about the alias, and a
name whose fate after the announced day is unstated cannot be the name a published number rests on: the day the alias
stops and the day it answers with the weights of another model are different days, and the provider published one of them.

**What pinning does not buy.** The snapshot carries the same announced shutdown date, so the pin buys identity and not
life: a number published over this model stays a fact about these weights and not about a pointer. The cost is that the
server refuses an identifier that is not in its allowlist (`ledgerlens/byok/registry.py:4-6`), so a request that names
`gpt-4.1-mini` is refused with the sentence the registry already uses for that case
(`ledgerlens/byok/registry.py:391`).

### 2. The registry records the clock, the price and the day of each

The registry grows one record and no mechanism: a frozen dataclass of `ledgerlens/byok/registry.py`, shaped after
`Pricing` (`ledgerlens/byok/registry.py:149-219`) and placed next to it. It carries four fields: `snapshot`,
`announced_shutdown`, `source` (one of the three literals the price uses, `registry.py:158`) and `last_verified`, the day
the announcement was read against the provider.

It has the shape of `Pricing` in every respect that matters: a property that says whether it was checked
(`registry.py:163-171`), a `to_contract` that carries the days as text (`registry.py:173-180`), and a `from_contract`
that refuses a payload it cannot read with `ContractRefused` (`registry.py:182-219`). The rules are the rules of the
price: a record whose source is `unknown` carries no day and no snapshot at all (`registry.py:198-201`), and any other
source must carry the snapshot, the announced day and the day it was read, or the payload is refused naming what is
missing (`registry.py:211-213`).

**The price stays where it is.** The price of the default model keeps `source="manual"` and `last_verified=date(2026, 11,
8)` (`registry.py:312-313`), because that is the day the online evaluation ran and the day the list price was transcribed
by hand (`registry.py:296-298`), and a price that was verified on a day stays verified on that day. The price is not moved
into the new record and it is not duplicated: the runner reads it from the registry, and the price of the model that
replaces this one will be a new price with its own source and its own day.

### 3. On the announced day the run is refused, and the gate keeps the refusal true

**The decision is a refusal.** On and after 2027-01-14 a run that asks for the profile is refused by the registry, from
the day the registry carries. The refusal is `ModelNotAllowed` (`ledgerlens/byok/registry.py:83-92`), the refusal of the
family the live mode already uses, and its sentence names the profile, the announced day and the reason. It never quotes
the identifier the visitor sent, because the identifier of a model is a value of the visitor and it may hold a key of
their provider (`registry.py:87-89`).

**Where it lives.** `ProviderRegistry.require()` (`ledgerlens/byok/registry.py:372-400`) refuses a profile whose
announced shutdown is today or earlier, and `ProviderRegistry.catalogue()` (`registry.py:347-363`) stops offering it. The
status of the profile becomes `retired` by hand on that day, the status the type already knows (`registry.py:55`),
which the existing refusal of the registry already refuses (`registry.py:392-397`) and which is what the runbook asks for
(`docs/v3/docs/13-CI-CD-DEPLOYMENT-AND-RUNBOOKS.md:66`). The status is the record of what happened; the day is the rule
of what happens next.

**The guard that keeps the refusal true.** A new step of the gate, `scripts/check_model_registry.py`, reads the registry,
writes nothing and exits with a non zero code when a profile whose announced shutdown has passed is still offered, in
the style of `scripts/check_eval_datasets.py` (`scripts/check_eval_datasets.py:47-52`), and it is wired into
`scripts/gate.sh` next to the check of the datasets (`scripts/gate.sh:20-21`). The reason the check is a step of the
gate is the reason ADR-052 gave for its own: a check that is not part of a gate is a note for the next person, and the
next person is not there (`docs/decisions/ADR-052-the-manifest-of-the-eval-datasets.md:249-251`).

**Why not the other three.** A warning does not stop a run, a date in a policy document is a note (for the reason ADR-052
gave, `docs/decisions/ADR-052-the-manifest-of-the-eval-datasets.md:86-92`), and a check in the gate alone does not reach
the live mode: the refusal has to live in the code that answers the request. The decision is the refusal, and the check in
the gate is the guard that keeps it true.

### 4. A published number names the model that produced it

The rule of this record, beside the rule of ADR-052 that a number names its set and the role of that set:

> A published number names the identifier that was called and the dated snapshot of it, the day of the run, the
> temperature, the price with its source and the day it was verified, the set with its digest and its role, and the
> announced shutdown day of the model with the day the announcement was read.

Three of those seven are missing today: the dated snapshot is nowhere, the day of the run is nowhere (the only trace of
it is the day of the price, 8 November 2026, `ledgerlens/byok/registry.py:313`), and the announced shutdown day is
nowhere. The other four exist today.

**The numbers do not change.** The 0.82 of correctness, the 0.74 of groundedness, the 0.53 and the 0.73 of the trajectory
and the 9.3 cases of human review stay what they are (`data/eval/report_online.md:13-15`). What changes is that the
report says which model produced them, which snapshot it was and on what day. The price of the published run
(`data/eval/report_online.md:49-56`) is computed from the `Pricing` of the registry, a `Decimal` with a source and a day
(`ledgerlens/byok/registry.py:311-316`), and the report names the price it used; the table of the runner is a second copy
of that price, in floats with no day (`ledgerlens/eval/run.py:108`).

### 5. What this record does not decide

The switch to `gpt-6-luna` is not decided here. A recommended replacement in a notice of the provider is not a
measurement of this repository, and the replacement is a different model with a different price and a different behaviour,
so the behaviour of the replacement has to be measured over the same set before anything is switched. A number is a fact
about a set, and a set that changes is a new measurement
(`docs/decisions/ADR-053-the-held-out-set-and-the-blind-labelling.md:144-146`).

**The measurement, if it is made, is this.** The same instrument: the thirty cases of `data/eval/eval_cases.jsonl`, the
three variants, three runs each, temperature 0, the real tools and the real verifier (`data/eval/report_online.md:3`,
`ledgerlens/eval/run.py:216`). The same goals (`data/eval/report_online.md:29-33`): C beats A in correctness, the
trajectory of C unordered at least 0.80, the trajectory of C with the equivalent tools at least 0.80. Plus the cost per
correctly resolved case, with its own price and day. Plus two criteria the repository sets: only a model whose tool
calling was really exercised may carry the status `tested` (`ledgerlens/byok/registry.py:8-9`), and 28 of the 40
sentences of `data/eval/verification_live.jsonl` were written by `gpt-4.1-mini`
(`docs/decisions/ADR-007-nli-verification.md:104`, `data/eval/datasets.json:48`), so the sentences of another model are
another set, with another labelling pass and another entry in the manifest with the role `tuning`.

**Where that measurement would live.** In a new record in `docs/decisions/`, because an accepted record is never
rewritten and a change of an accepted decision is a new record (`AGENTS.md:20`); in a new report over the same thirty
cases; in a new dataset in `data/eval/datasets.json` with its digest and its role; and in a new profile of the allowlist,
with its own price, its own snapshot and its own clock. The replacement is not a row to edit.

### The tasks this record expects

The tasks are a new milestone block of `specs/005-r4-runtime-latency-and-cost-per-case/tasks.md`, which carries the ids
T115 to T140. The ids of this record continue from T140.

- [ ] T141 Test the record of the clock in the registry, in `tests/byok/test_registry.py`: the snapshot, the announced
  day, the source, the day it was read, the refusal of an incomplete payload and the money that stays a `Decimal`
- [ ] T142 Test the refusal on the announced day, in `tests/byok/test_registry.py`: a profile whose shutdown is today or
  earlier is refused with `ModelNotAllowed` naming the day, the catalogue does not offer it, and a future day still runs
- [ ] T143 Implement the record and the refusal in `ledgerlens/byok/registry.py` and the contract of the catalogue in
  `ledgerlens/api/byok.py`, with the `model_id` of the profile as the dated snapshot and the `profile_id` unchanged
- [ ] T144 [P] Write `scripts/check_model_registry.py` and wire it into `scripts/gate.sh`, with the test in
  `tests/byok/test_check_model_registry.py` that the check refuses a profile whose announced day has passed
- [ ] T145 Write the renderer of the model that produced a number in `ledgerlens/eval/run.py`, with the snapshot, the day
  of the run, the temperature and the price read from the registry, and the test in `tests/eval/test_online_path.py`

## Consequences

- The registry knows the day: the snapshot, the announced shutdown day, the source of the announcement and the day it
  was read, beside the price and the day the price was verified. The refusal is code and not a memory: on 2027-01-14
  the profile stops being offered and the runs are refused with a sentence that names the profile and the day.
- The recorded numbers stay readable. The report of today keeps its numbers and gains the identity of the model that
  produced them, the price of the published run stops being a float with no day, the gate grows one step that reads the
  registry and writes nothing, and the short name is refused by the server.

## The debt of this record

The debt of this record is the replacement and its measurement.

This record pins the model that is going away, refuses it on the day the provider published, and says what a published
number has to name. It does not decide what the repository runs after 2027-01-14, and that is the whole of what is left:
the numbers of this repository keep naming a model that stops answering on the announced day until a replacement is
measured over the same thirty cases with the same instrument.

Two debts hang inside that one. The first is the live set of the verifier: 28 of its 40 sentences were written by a
model that stops answering, so the set of the sentences of the next model has to be written and read again, and the
labels of a new set are a new labelling pass and a new entry in the manifest (`data/eval/datasets.json:48`). The second
is the price of the runner: `PRICE_PER_MTOK` (`ledgerlens/eval/run.py:108`) is a table of floats with no day.

And one question stays open, because the provider did not answer it: whether the short name stops on 2027-01-14. The
notice lists the snapshots and is silent about the alias, and the one report of the Models API of 2 November 2026 that
returned the same day for the short names is a report and not a promise. This record refuses the alias by refusing
everything that is not in the allowlist, so the question costs the repository nothing while it is open. If the alias
outlives the snapshot, the numbers of this repository are still facts about the snapshot, because that is the name they
name.
