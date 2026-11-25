# The adversarial laboratory

The laboratory measures the boundaries of the repository with a list of canned exercises whose payloads are
synthetic. It adds no defense of its own: a laboratory that filtered the attacks itself would measure its own
filter, and the boundaries of the product would stay unmeasured. Every attempt of every exercise is stopped by
the layer of the repository that owns the boundary, with the reason of the refusal in the trace of the
attempt.

The count of the unauthorized actions over the whole list is **zero**, and the count is computed by the tests
over the results of the exercises, not written by hand.

The count says nothing about an attack that is not in the list. It says that the attacks the list holds did
not pass, and nothing else.

## The exercises

| Exercise | Surface | The layer that answers |
| --- | --- | --- |
| `s09-injected-note` | The text of a row of the ledger | The tools and the prompt of the agent, which do not change |
| `write-in-generated-query` | The SQL of the model | The guard of the SQL, and the read-only connection of the tool |
| `table-outside-the-allowlist` | The SQL of the model | The guard of the SQL |
| `tool-that-does-not-exist` | The call of the model | The allowlist of the tools |
| `row-of-another-visitor` | The scope of the session | The session folder and the store of the branch |
| `call-past-the-cap` | The money of the run | The coordinator of the budget |
| `forged-evidence-identifier` | The join of the evidence | The verifier and the evidence of the bundle |
| `invented-citation` | The answer of the model | The verifier, which marks the claim unsupported |

The list of the exercises is data in `data/adversarial/fixtures/`, with the hash of each fixture recorded in
`data/adversarial/fixtures/hashes.json`, and the results of the run of the laboratory are in
`data/adversarial/results/`. The first exercise is the one the repository already has: the instruction hidden
in the note of a refund of the scenario S09, which is data and never an instruction.

## The mapping to the taxonomy of the threats

The mapping below is a **proposal**. It is not a certification of the repository, it is not a certification of
the exercises, and it is not a compliance claim. The taxonomy is the [OWASP Top 10 for LLM Applications
2025](https://owasp.org/www-project-top-10-for-large-language-model-applications/), and the mapping says which
reference of it each exercise belongs to, with the layer of the repository that answers the exercise.

| Exercise | Surface | The layer that answers | The reference of the taxonomy |
| --- | --- | --- | --- |
| `s09-injected-note` | The text of a row of the ledger | The tools and the prompt of the agent | LLM01, Prompt Injection |
| `write-in-generated-query` | The SQL of the model | The guard of the SQL and the read-only connection | LLM05, Improper Output Handling |
| `table-outside-the-allowlist` | The SQL of the model | The guard of the SQL | LLM05, Improper Output Handling |
| `tool-that-does-not-exist` | The call of the model | The allowlist of the tools | LLM06, Excessive Agency |
| `row-of-another-visitor` | The scope of the session | The session folder and the store of the branch | LLM06, Excessive Agency |
| `call-past-the-cap` | The money of the run | The coordinator of the budget | LLM10, Unbounded Consumption |
| `forged-evidence-identifier` | The join of the evidence | The verifier and the evidence of the bundle | LLM09, Misinformation |
| `invented-citation` | The answer of the model | The verifier, which marks the claim unsupported | LLM09, Misinformation |

## The flag and the rollback

The flag of the laboratory is `LEDGERLENS_ADVERSARIAL_LAB`, and it is off in the shipped configuration. With
the flag off, no route of the laboratory answers, and the fixtures stay readable as data: the rollback of the
laboratory is the rollback of a route and never the deletion of the attacks. The exercises run in the offline
mode with the fake provider, so an attack never spends the money of anybody, and the script of the laboratory
refuses to run with a key in the environment.

## Links

- [the list of the exercises](../ledgerlens/adversarial/exercises.py)
- [the runner of the exercises](../ledgerlens/adversarial/runner.py)
- [the script of the laboratory](../scripts/run_adversarial_lab.py)
- [the specification of the milestone](../specs/015-r13-safe-adversarial-laboratory/spec.md)
