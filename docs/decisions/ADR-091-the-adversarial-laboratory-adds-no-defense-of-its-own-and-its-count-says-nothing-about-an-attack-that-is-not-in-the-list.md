---
type: adr
status: accepted
date: 2026-11-24
---

# ADR-091: The adversarial laboratory adds no defense of its own, and its count says nothing about an attack that is not in the list

Status: accepted. Date: 2026-11-24.

## Context

The design package
[LL-V3-R13-02, safe adversarial laboratory](../design/advanced-specs/R13-02-safe-adversarial-laboratory.md)
proposes a laboratory where an agent is attacked on purpose and where the boundaries of the system are
inspectable. The repository already holds the boundaries: the guard of the SQL refuses a write and a table
outside the allowlist ([ADR-005](ADR-005-guarded-text-to-sql.md)), the read-only connection of the tool is the
second layer, the live path refuses a tool that does not exist, the scope of the session keeps one visitor out
of the branch of another, the budget of the run caps the calls and the money, and the scenario S09 of
`data/scenarios.json` already carries the instruction hidden in the note of a refund and declares that it is
data and never an instruction.

The question of the milestone of
[specs/015](../../specs/015-r13-safe-adversarial-laboratory/spec.md) was what the laboratory is when the
defenses already exist. The answer is that the laboratory is not a defense: it is the measurement of the
defenses the repository already has, with a list of canned exercises whose payloads are synthetic, and with a
result that says what was attacked, which layer answered, what was blocked and what is still open.

## Decision

**The laboratory adds no defense of its own, it accepts an exercise id and nothing else, it runs offline with
no key, the count of the unauthorized actions says nothing about an attack that is not in the list, and the
mapping of the taxonomy is proposed and not a certification.**

1. **The laboratory adds no defense of its own.** Every attempt of every exercise ends in a layer of the
   repository, and no attempt ends in the intent of the model. A laboratory that filtered the attacks itself
   would measure its own filter, and the boundaries of the product would stay unmeasured.
2. **A request of the laboratory accepts an exercise id of the list and nothing else.** The list of the
   exercises is data in the repository, with the hash of each fixture recorded, and a request that carries an
   extra field is refused, so no text of a visitor ever reaches a prompt of a provider.
3. **The exercises run offline with no key.** The scripted model and the fake provider run every exercise, so
   an attack never spends the money of anybody, and the script of the laboratory refuses to run with a key in
   the environment.
4. **The count of the unauthorized actions is computed and says nothing about an attack that is not in the
   list.** The count over the whole list is zero, and the count is computed by the tests over the results of
   the exercises, not written by hand. The page of the laboratory says the count says nothing about an attack
   that is not in the list, because a count of zero that reads as a clean bill of health is a count that will
   be misread.
5. **The mapping of the taxonomy is proposed and not a certification.** The page maps every exercise to its
   surface, to the layer that answers it and to the reference of the OWASP Top 10 for LLM Applications 2025 it
   belongs to, with the source named, and the page says in its first paragraph that the mapping is a proposal
   and not a compliance claim.
6. **The laboratory is behind a flag, and the rollback is the rollback of a route.** The flag
   `LEDGERLENS_ADVERSARIAL_LAB` is off in the shipped configuration, no route of the laboratory answers with
   the flag off, and the fixtures stay readable as data: the rollback of the laboratory is never the deletion
   of the attacks.

## Alternatives considered

- **To build the endpoint of the package.** Refused. The package wants a route that accepts canned ids, and
  the value of the laboratory is the exercises and their traces, not a route a stranger may call. A public
  endpoint would add a way in for the sake of a convenience.
- **To add a filter of the laboratory to the layers of the repository.** Refused. A laboratory that filtered
  the attacks itself would measure its own filter, and the layers of the repository are not touched by any
  task of the milestone.
- **To publish the count of the unauthorized actions without the restriction.** Refused. A count of zero that
  reads as a clean bill of health is a count that will be misread, and the page says the count says nothing
  about an attack that is not in the list.
- **To present the mapping of the taxonomy as a certification.** Refused. A mapping presented as a compliance
  claim would be a false claim, and the laboratory of the repository exists to avoid false claims.

## Consequences

- **The repository has the laboratory**, in `ledgerlens/adversarial/`: the list of the exercises
  (`exercises.py`), the record of the hashes (`hashes.py`), the runner (`runner.py`) and the result
  (`result.py`), with the tests in `tests/adversarial/`.
- **The fixtures and the results are data of the repository**, in `data/adversarial/fixtures/` and
  `data/adversarial/results/`, with the hash of each fixture recorded.
- **The page of the laboratory is [the page of the adversarial laboratory](../adversarial-lab.md)**, with the
  list of the exercises, the layer that answers each one, the count with the restriction it carries and the
  mapping of the taxonomy, proposed and not a certification.
- **The count of the unauthorized actions over the whole list is zero**, and the count is computed by the
  tests over the results of the exercises. The count says nothing about an attack that is not in the list.
- **The flag of the laboratory is off in the shipped configuration**, and the rollback of the laboratory is
  the rollback of a route and never the deletion of the attacks.

## Links

- [ADR-005, the guarded text to SQL](ADR-005-guarded-text-to-sql.md)
- [ADR-013, the public trace is a versioned contract](ADR-013-public-trace-as-a-versioned-contract.md)
- [the page of the adversarial laboratory](../adversarial-lab.md)
- [the specification of the milestone](../../specs/015-r13-safe-adversarial-laboratory/spec.md)
- [the design package](../design/advanced-specs/R13-02-safe-adversarial-laboratory.md)
