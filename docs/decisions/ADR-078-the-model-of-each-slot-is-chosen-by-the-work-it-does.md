---
type: adr
status: accepted
date: 2026-11-24
---

# ADR-078: The model of each slot is chosen by the work it does

Status: accepted. Date: 2026-11-24.

## Context

A run of this product has four model slots. The `agent` slot plans the investigation and answers with the tools. The
`triage` slot reads the question and writes the plan. The `sql` slot writes the statement that reads the ledger. The
`policy` slot rewrites the question of the analyst into the words of the corpus of the policies. Until now the four
slots took the same model, because the deployment named one model and the integrator asked for it four times.

The four tasks are not the same task. The triage reads a sentence and writes a plan of four lines. The rewrite of the
search of the policies is one sentence. The statement has to be correct against a schema that the model never sees. The
answer is made of tool calls, and it needs a model that really calls a tool and does not write the result of a call
as text. Paying the price of the hardest task on the easiest ones is money spent in the wrong place, and the price of
the answer is the price of the whole run.

The design package of the repository (the frozen import in `docs/v3/`) asks for exactly this, and it asks for it in a
specific way: `ai/03-MODEL-GATEWAY-ROUTING.md` describes a fixed cascade, and
`docs/v3/advanced-specs/R15-02-model-router-with-budgeted-fallback.md` asks for a router that decides on pre-verified
intent and risk and on the capability the provider really has, that writes an immutable decision naming the models
that were allowed, the model that was chosen and the reason, that never replaces a model a human chose, and that
never turns an unverified price into a price of zero.

Two decisions of this repository constrain the answer and are not changed by this ADR.

ADR-037 says that a run of the live mode has exactly one model: the four slots are four views of the same model and
the model never changes in the middle of a run. FR-013 says the same. The router therefore does not touch the live
mode of the visitor, and it does not touch a run that is already going.

ADR-P007 says that the main runtime stays a single agent with a deterministic verifier, and that multi-agent work is
experimental until a paired comparison measures a gain. The router is not multi-agent work: it is one agent with four
tasks, and the four tasks are the four slots the integrator already had. The verifier stays deterministic and is
never a model.

The repository also has the evidence for one more thing. The allowlist of the server said that the tool calling of
`gpt-4.1` was never exercised, and it was listed as `experimental`. The nine published recordings of a real model
(ADR-075) are the runs of that model calling `get_ledger_record`, `search_policies`, `get_reference_fx` and
`calculate` natively, so the allowlist now carries that model as `tested` with the capability `tool_calling`. Its
price is still absent, because nobody in this repository verified it.

## Decision

**The product chooses the model of each slot of the run by the task the slot does, and it writes the decision down
before the run starts.**

1. **There is a table of adequacy, and it is data.** `ledgerlens/agents/routing.py` holds, for each of the four
   slots, the task it does, the level the task demands and the capability the task needs. The triage and the rewrite
   of the policy search are light. The statement is standard. The answer with the tools is robust, and it is the only
   one that needs the capability `tool_calling`. A task that is not in the table has no model, and the router refuses
   it instead of guessing.
2. **The cascade is the order the deployment declares.** `LEDGERLENS_MODEL_CASCADE` names the models the deployment
   may run, from the lightest to the most capable. A slot takes the cheapest model of the cascade that is at or above
   the level of its task and that really has the capability the task needs. A deployment that declares no cascade
   gets the model of `LEDGERLENS_MODEL` in every slot, which is the behaviour the product had before this ADR.
3. **A level that the cascade does not reach is said in words.** When no model of the cascade reaches the level of
   the task, the most capable model of the cascade runs the task and the reason says that the level was not reached.
   A silent downgrade is a lie about what ran.
4. **A model only runs a task when its capability was really verified for it.** The capabilities come from the
   allowlist of the server, which is the only place where the repository says that a model really calls a tool. A
   model outside the allowlist is still a candidate, because a deployment may run a model the repository never
   exercised, but its capabilities are undeclared and the decision carries that kind of confidence.
5. **The decision is a value, written once, and it is published.** The decision names the case, the type of the case,
   the risk tier, the models that were allowed, the model that was chosen, the reason, the budget and the price. It
   never changes while the run goes on. The recording of a run publishes the model of each slot in the manifest of the
   bundle, in the provenance of the site and in the card of the catalog, so a reader sees the division of work and not
   only the model that wrote the answer.
6. **A price that was never verified is unknown, and unknown is never zero.** The decision carries the price of the
   model only when the allowlist verified it. `gpt-4.1` has no verified price, so the decision says that the money is
   unknown (ADR-034, ADR-078).
7. **The live mode of the visitor is not touched.** One run of the live mode has one model, and the visitor's choice is
   never replaced. The router applies to the configured path of the deployment and to the capture of the published
   recordings.

## Alternatives considered

- **To keep one model for the whole run and to call it a decision.** Refused. The four tasks are different and the
  price of the answer is the price of the whole run, so the cheapest model that can do the task is the honest choice
  for the task.
- **To let the model of the agent choose which model the other slots use.** Refused. A model that is already running
  the answer would have to be trusted to pick a model for the triage, and the choice would not be written down before
  the run.
- **To route on the intent of the case, which the triage discovers.** Refused for now, because the triage is the
  first thing the run does and the model of the triage has to be chosen before the triage runs. The decision carries
  the type of the case and the risk tier as the context the deployment declared, and the routing itself is by task.
- **To let the visitor choose a model per slot.** Refused. It would change ADR-037 and FR-013, and a comparison
  between two models that the visitor did not choose is not a comparison.
- **To give the router a price table of its own.** Refused. The allowlist already holds the price with the day it was
  verified, and a second table would be a second source of truth for money.
- **To use a free-form server URL for a model.** Refused. The models are named by the provider, and the router never
  accepts a URL.

## Consequences

- **The configured path of the deployment can spend less for the same answer.** The claim is a hypothesis until the
  paired comparison of the evaluation measures it, and the evaluation is what has to say whether it is true. Nothing
  in this ADR says that the cascade is better than one model: it says that the model of each task is chosen by the
  task.
- **The recording of a real model shows two models when the cascade declares two.** The published catalog of the
  recordings of a real model says which model wrote the plan, which model wrote the statement and which model wrote
  the answer.
- **A deployment that names a model outside the allowlist cannot run it.** The server runs the models it verified, and
  a model enters the allowlist when its tool calling was really exercised.
- **The multi-agent line is untouched.** The runtime is still one agent with a deterministic verifier, and the studio
  of specialists stays experimental and behind a flag until a paired comparison measures a gain (ADR-P007).

## Links

- [ADR-034, the registry, the budget and the endpoint](ADR-034-the-registry-the-budget-and-the-endpoint.md)
- [ADR-037, the case of the demo runs on a bridge over the caller](ADR-037-the-case-of-the-demo-runs-on-a-bridge-over-the-caller.md)
- [ADR-073, the published bundle carries the evidence its verdict was computed on and it is reproducible](ADR-073-the-published-bundle-carries-the-evidence-its-verdict-was-computed-on-and-it-is-reproducible.md)
- [ADR-075, the site publishes two catalogs and each bundle declares the one it belongs to](ADR-075-the-site-publishes-two-catalogs-and-each-bundle-declares-the-one-it-belongs-to.md)
- [ADR-077, the published bundle is verified against the answer the run verified](ADR-077-the-published-bundle-is-verified-against-the-answer-the-run-verified.md)
- [the table of adequacy and the router](../../ledgerlens/agents/routing.py)
- [the configuration that declares the cascade](../../ledgerlens/config.py)
- [the allowlist of the server](../../ledgerlens/byok/registry.py)
- [the capture that records the division of work](../../scripts/capture_live_replay.py)
