# Implementation Plan: The safe adversarial laboratory

**Branch**: `feature/v3` | **Date**: 2026-11-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/015-r13-safe-adversarial-laboratory/spec.md`

## Summary

The design package proposes a laboratory where an agent is attacked on purpose and where the boundaries of the
system are inspectable. The repository already holds most of the boundaries and one of the attacks. The guard
of the SQL refuses a write, a table outside the allowlist and a function outside the allowlist, and the
read-only connection with its two second limit is the second layer. The live path refuses a tool that does
not exist, and the allowlist of the tools is decided by the code and never by a model. The scope of the
session keeps one visitor out of the branch of another, the budget of the run caps the calls, the tools and
the money, and the trace redacts what looks like a key. And the scenario S09 of `data/scenarios.json` already
carries the instruction hidden in the note of a refund and declares that it is data and never an instruction.

So the port is not a laboratory that adds a defense. It is a laboratory that measures the defenses the
repository already has, with a list of canned exercises whose payloads are synthetic, and with a result that
says what was attacked, which layer answered, what was blocked and what is still open. The endpoint of the
package is not built: the package wants a route that accepts canned ids, and the value of the laboratory is
the exercises and their traces, not a route a stranger may call. The list is data in the repository and a
request accepts an exercise id and nothing else, so no text of a visitor ever reaches a prompt of a provider.

The flag of the laboratory is off in the shipped configuration. The exercises run in the offline mode with the
fake provider, so an attack never spends the money of anybody, and the traces of the canned exercises are
readable without a key, so a reader may look at them.

## Technical Context

**Language/Version**: Python 3.12 for the core
**Primary Dependencies**: the existing `ledgerlens` core, the guard of the SQL, the offline provider fake and
the scripted model
**Architecture**: the laboratory lives in the domain, in `ledgerlens/adversarial/`, and it calls the agent of
`ledgerlens/agents/integrator.py` as it is, with the layers of the repository untouched
**Storage**: the list of the exercises and their fixtures live in `data/adversarial/`, with the hash of each
fixture, and the results of the exercises are published as pages under `docs/`
**Testing**: pytest offline with `LEDGERLENS_OFFLINE=1`, with the scripted model and the fixtures of the
exercises
**Constraints**: no key, no network, no process execution, no write to the ledger of the base, no change in
`docs/design/`, no new route in the public product

## The layers and the exercises, and why the laboratory adds no defense of its own

```mermaid
flowchart TD
    A["A canned exercise and its synthetic fixture"] --> B["The agent of the repository, unchanged"]
    B --> C{"Where does the attack land?"}
    C -->|"the text of a row of the ledger"| D["The tools and the prompt do not change"]
    C -->|"a query of the model"| E["The guard of the SQL refuses the write or the table"]
    C -->|"a tool that the model asks for"| F["The allowlist of the tools refuses it"]
    C -->|"a row of another visitor"| G["The scope of the session refuses it"]
    C -->|"a call of the model"| H["The budget of the run refuses it"]
    D --> I["The blocked action with the reason of the layer"]
    E --> I
    F --> I
    G --> I
    H --> I
    I --> J["The result: surface, expected boundary, trace, blocked actions, open risk"]
```

The diagram is the point of the milestone. Every arrow that leaves the agent ends in a layer of the
repository, and no arrow ends in the intent of the model. A laboratory that added a filter of its own would
measure its own filter and the boundaries of the product would stay unmeasured, which is the opposite of what
the package asks for.

## The list of the exercises

The list is data, and each entry carries the surface it attacks, the boundary it expects, the fixture it runs
and the hash of the fixture. The first entry is the one the repository already has.

| Exercise | Surface | The layer that answers |
|---|---|---|
| The instruction in the note of a refund (S09) | The text of a row of the ledger | The tools and the prompt of the agent, which do not change |
| The write in a generated query | The SQL of the model | The guard of the SQL |
| The table outside the allowlist | The SQL of the model | The guard of the SQL |
| The tool that does not exist | The call of the model | The allowlist of the tools |
| The row of another visitor | The scope of the session | The session folder and the store of the branch |
| The call that passes the cap | The money of the run | The coordinator of the budget |
| The forged evidence identifier | The join of the evidence | The verifier and the evidence of the bundle |
| The answer that invents a citation | The answer of the model | The verifier, which marks the claim unsupported |

The payloads are synthetic. They name the merchants of the corpus of the repository and they hold no key, no
address of a real service and no personal data, and a test reads every fixture to prove it.

## The result of an exercise

The result carries six things: the surface that was attacked, the boundary that was expected, the reference of
the trace, the actions that were blocked with the reason of the layer that stopped them, and the risk that is
still open. The open risk is not decoration. An exercise that passed says that the attack it holds did not
pass, and the risk that is still open names what the exercise did not settle. The count of unauthorized
actions is made by the tests over the whole list, and it says nothing about an attack that is not in the list,
so the page says so too.

## The mapping to the taxonomy of the threats

The page maps every exercise to its surface, to the layer that answers it and to the reference of the
taxonomy it belongs to, with the sources named. The mapping is a proposal. It is not a certification of the
repository, it is not a certification of the exercises, and the page says so in its first paragraph, because
a mapping presented as a compliance claim would be a false claim and the laboratory of the repository exists
to avoid false claims.

## The risks

- **A laboratory that becomes a way in.** The risk is a route that accepts free-form text and forwards it
  into a prompt of a provider with elevated tools. The guard is that the list is data, that a request accepts
  an exercise id and nothing else, that the laboratory is behind a flag and that the exercises run in the
  offline mode.
- **An exercise that proves nothing because the agent was weak.** The risk is an attack that failed for a
  reason that has nothing to do with the boundary. The guard is that the boundary that answers is named by
  the module that owns it and that the reason of the refusal is in the trace.
- **A count of zero that reads as a clean bill of health.** The risk is a reader who takes the zero
  unauthorized actions as a proof that the system is safe. The guard is the open risk of every exercise and
  the sentence on the page that says the count says nothing about an attack that is not in the list.
- **A fixture that holds something real.** The risk is a payload that carries a key, an address or personal
  data of a person. The guard is the test that reads every fixture and expects none of the three.
- **A laboratory that weakens the product to be able to attack it.** The risk is a defense that is turned off
  during an exercise so that the attack can succeed. The guard is that the layers are not touched by any
  task of this milestone, and the tests of the layers of the repository keep running.
- **A rollback that is not a rollback.** The risk is a feature that stays after the flag is off. The guard is
  that no route of the laboratory is registered when the flag is off and that the fixtures stay as data.

## The strategy for the validation

Every task ships its test before its code, and the gate of the Python side is the one that runs everywhere.
The tests of the laboratory are offline and use the scripted model, so no test of the laboratory opens a
socket and none of them reads a key. The count of unauthorized actions is a count made by the tests over the
whole list, and it is a count and not a claim: the test that computes it is the evidence and the page repeats
it with its restriction.

## What is out of scope

- The red team of a live deployment and any exercise of a provider of a visitor.
- The ingestion of documents and the office documents with instructions in them.
- Any change of the layers of the repository. The laboratory measures them.
- The route in the public product. The laboratory is a research feature with a flag, and its output is a
  trace and a published page.
- The frontend of `apps/web/`.

## The definition of done

1. The list of the exercises is data in `data/adversarial/`, with the hash of every fixture, and the first
   exercise is the scenario S09 of the repository.
2. A request of the laboratory accepts an exercise id of the list and nothing else, and the flag of the
   laboratory is off in the shipped configuration.
3. Every attempt of every exercise is stopped by the layer of the repository that owns the boundary, with the
   reason of the refusal in the trace.
4. The count of unauthorized actions over the whole list is zero, and the test computes it.
5. No fixture holds a key, an address of a real service or personal data.
6. The result of an exercise carries the surface, the expected boundary, the reference of the trace, the
   blocked actions and the open risk.
7. The mapping to the taxonomy is published with its sources and says that it is proposed and not a
   certification.
8. With the flag off, no route of the laboratory answers and the fixtures stay readable as data.

## The questions this milestone answers

- **Where the laboratory lives.** In the domain, in `ledgerlens/adversarial/`, next to the agent it exercises
  and never in the API layer, because the domain never imports the API.
- **Whether there is an endpoint.** No. The exercises are run by the tests and by the script of the
  publication, and their traces are published. A public endpoint would add a way in for the sake of a
  convenience.
- **What the exercises run against.** The agent of the repository, unchanged, with the layers of the
  repository unchanged.
- **Whether the laboratory adds a defense.** It does not. A laboratory that filtered the attacks itself would
  measure its own filter.
