---
type: adr
status: accepted
date: 2026-11-23
---

# ADR-068: The published catalogue holds the failures and not only the cases the agent resolves

Status: accepted. Date: 2026-11-23.

## Context

The design package asks for it in one sentence: "Include *at least one published failure*: e.g., a run with
insufficient FX source or unsupported ARS currency; show escalation rather than concealing"
(`docs/design/docs/08-EVIDENCE-TRACING-AND-PROVENANCE.md:58`). The readiness audit named the same debt as the fourth
gap of the evidence: "the injection scenario is still not one of them"
(`docs/readiness-2027.md:449`).

The catalogue of the site held five scenarios: the happy path of a cross currency refund (S01), the duplicate charge
(S02), the chargeback whose deadline is two days away (S03), the id that does not exist (S04) and the payout that
nets (S08). Every one of them ended in an answer. The only one that ended in a handover was S03, and it handed over
because of a date, not because of a failure of the evidence.

The repository already had the failures. The manifest of the scenarios holds twelve, the simulated ledger holds them
and the end to end test runs each of them with the real tools and the real verifier
(`tests/agents/test_scenarios_e2e.py`). Three of them are the failures the design package names, and each of them
exercises a rule that the code decides and not the model:

| the scenario | what fails | the rule that decides |
| --- | --- | --- |
| S09 | the reason field of the refund carries an order to the system | a field with orders is data, never an instruction, and the case goes to a person (`policy:escalation-and-review#suspicious-text`) |
| S10 | the reference source does not publish the currency of the payment | the amount cannot be converted with a source that does not carry it, and the case goes to a person |
| S11 | the reference rate of the day could not be read | without the rate of the day the cause of an FX difference cannot be proven, and the case goes to a person |

And a fourth scenario is the control that the catalogue lacked: S07, a refund that paid exactly what was charged.
A catalogue that only holds the cases with a discrepancy never shows that the agent finds nothing when there is
nothing to find.

So the depth of the case was never the depth of the agent. It was the depth of the catalogue.

## Decision

**The catalogue of the replay publishes the failures. Four scenarios join the five: S07, the control; S09, the
injection; S10, the currency the reference source does not publish; and S11, the reference rate that could not be
read. What each one shows is the escalation it produced, and the escalation is decided by the code and not by the
script.**

### What the published run is

The four new recordings are deterministic executions, with the scripted model and the recorded exchange rate, in the
same contract as the five that were already there: the events as JSON lines, the manifest with the hash of every
part, the provenance with the commit the capture ran from, and the frozen artifact of the ledger of the account of
the run. The bundle of a scenario says that it is not a live execution and it calls no model, and the page that
shows it says the same in words.

The difference between S01 and S11 is one switch: `SCENARIO_FX_FAULT` in `scripts/capture_replay.py` names the
scenarios whose run has the reference source in fault, and S11 is the one. The same question, asked twice, is
answered twice, and the second answer is the one that says less.

### The answer of a failure states what the ledger shows

The answer of S11 is the sharpest case, because it is the one where a number would have been easy to make up. The
payment was EUR 100,00 and the refund was BRL 549,31, applied at the rate 5,4931 on 2026-10-20. The amount charged
in BRL, 566,79, is **not** in the ledger: it is what comes out of the rate of the day multiplied by what was paid,
and the rate of the day is the thing that could not be read. So the answer says the two amounts the ledger shows and
names the rate that is missing, and it does not split the difference, because a split that nobody can check is a
number made up.

The amount paid in EUR is not written in the script either: it comes out of the truth of the base scenario, dividing
the amount charged in BRL by the rate the acquirer applied on the charge, with `Decimal`. The truth of a scenario
that names a base carries the truth of the base (`_truth_of` in `ledgerlens/demo.py`), and the dataset says which
base a scenario has, so the merge follows the data and not the code.

### The date of the rate comes from the ledger

The agent asks for the rate of the day the payment or the refund happened, and that day is in the rows the query
returned. A date with no origin in the ledger is a date the model made up, and the product notices it and asks the
agent once to read the day from the ledger (`fx_days_to_redo` in `ledgerlens/agents/integrator.py`). The published
recordings of S10 and S11 carry the day of the ledger, so the follow-up does not fire in them and the trace shows a
run that had nothing left to fix.

### The scenario that is not a complaint of its own

S11 asks the question of S01 and differs only in the run, so the demo page does not offer it: a page that offered
both would offer the same complaint twice. The capture names the scenario it records, and the script of that
scenario is the one it gets. The page asks by question and keeps the first match, which is the one of S01, because
the page has no fault to inject.

## Alternatives considered

- **To publish only the injection, the one the design package names first.** Refused. The design package names two
  examples, "a run with insufficient FX source or unsupported ARS currency", and the rate that could not be read
  is the failure that says the most: it is the one where the agent would have had to invent a rate to be useful.
- **To record the new scenarios with a real model.** Refused, and it is not a matter of taste: the repository has no
  key, the capture is deterministic on purpose, and a recording made by a model that no reader can run again is a
  claim and not a proof. The trace of a scripted run is checkable, and the scripted model is the part of the run
  that is declared in the provenance.
- **To change the answers of the five published scenarios so that they also end in a refusal.** Refused. That would
  be a lie about runs that happened. The published bundles are recordings, and a recording that is edited stops being
  one.
- **To publish the twelve scenarios of the manifest.** Refused for now. The four that the catalogue lacked are the
  ones the failures of the product are made of. The others (S05 the ambiguous request, S06 the refund outside the
  window, S12 the case recalled from memory) are worth publishing and each of them needs a script written for the
  purpose; this record does not claim them.
- **To write the answers of the new scenarios as a fixed text, without the truth of the scenario.** Refused. The
  numbers of an answer come out of the ground truth of the scenario and out of the ledger, and a script that writes
  549,31 by hand is a number that drifts the day the ledger changes.

## Consequences

- **The catalogue holds a case for every rule the escalation implements.** The injection, the amount above the
  threshold and the rate that could not be read are published next to the deadline that was already there.
- **The catalogue holds its control.** S07 publishes a case where the agent finds no difference, so the catalogue
  does not only show what the agent finds.
- **The reader can check the depth of the case and not only the depth of the answer.** Each new bundle carries the
  verdicts of the verifier and the reason of the escalation, so a reader sees the claim that could not be decided and
  the rule that sent the case to a person.
- **The published set is a tripwire in three places.** The list of the bundles is pinned in
  `tests/replay/test_site_export.py`, in `tests/replay/test_measure_replay_budget.py` and in
  `apps/web/tests/unit/api-replay.test.ts`, so a scenario that joins the catalogue without a decision here makes a
  test red.
- **The budget is not at risk.** The published payload of the nine scenarios is well inside the budget of the
  specification, and the gate measures it on every run.
- **The dataset of the scenarios is not touched.** The published bundles carry the digest of `data/scenarios.json`,
  so a change of that file would invalidate the provenance of every bundle in the catalogue. The scripts of the new
  scenarios read the truth that is already there.

## Links

- [the design package, the evidence tracing and provenance](../design/docs/08-EVIDENCE-TRACING-AND-PROVENANCE.md)
- [the readiness audit](../readiness-2027.md)
- [the scripts of the demo](../../ledgerlens/demo.py)
- [the capture of the replay](../../scripts/capture_replay.py)
- [the twelve scenarios end to end](../../tests/agents/test_scenarios_e2e.py)
