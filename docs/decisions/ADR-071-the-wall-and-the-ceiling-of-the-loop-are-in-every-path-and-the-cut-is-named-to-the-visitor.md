---
type: adr
status: accepted
date: 2026-11-24
---

# ADR-071: The wall and the ceiling of the loop are in every path, and the cut is named to the visitor

Status: accepted. Date: 2026-11-24.

## Context

The review of this branch read the promise and the code side by side, and found that the promise held in the paths
that ship and not in the path a visitor walks into.

The promise about the tools is unconditional. `docs/contracts/tools.md` says that a tool that raises does not take
the run down and that the investigation ends with `requires_human_review`, and that every tool returns an object and
never raises to the model. The wall that turns the failure of a tool into data is the middleware that
`ledgerlens/agents/integrator.py` installs when it builds the graph of the demo and of the evaluation. The live path
does not use that graph: `ledgerlens/api/live_case.py` builds a second one over the tools that the bridge wraps, and
it built it without the middleware. The consequence was measured: a tool that raised, for example the policy index
that could not be read, ended the run with `status: failed` and the raw exception in the error, the model never read
an envelope, and the visitor got an internal error and no case for a person.

The promise about the ceiling was ADR-054: every way of reaching the graph is bounded, and the number that stops the
graph comes from the same cap as the number that stops the provider. Two things were false. The configuration that
reached the graph carried no limit of steps, because the limit was written inside `investigate` and nowhere else, and
an integrator whose graph was built elsewhere, which is exactly the live one, had no bound at all on that path. And a
budget with no cap of the model calls was cut at the cap of the shipped paths, with a sentence that named a cap nobody
had given: "the turn reached the cap of the limit model calls".

The cut was also invisible. In the live path the turn that the ceiling stopped ended as a run with `status:
completed`, an empty answer and no cap named, while the result itself carried the sentence of the cut in
`missing_information`. The visitor saw nothing.

## Decision

**The wall is in every path, the ceiling is derived in every path, and a turn that the ceiling stops says so to the
visitor.**

### The wall

The graph of the live path carries the same middleware as the graph of the demo and of the evaluation. A tool that
raises becomes the envelope `TOOL_FAILED` that the model reads, and the result carries the code of the failure and
`requires_human_review`. The wall does not swallow what is not a failure of a tool: the ceiling of the run, the
refusals of the product and the cancellation of the run keep failing the run with the cap named, because a cap that
the model reads as a tool failure is a cap the model can work around.

### The ceiling

Every path that reaches the graph carries the limit of the steps, derived from the caps of the turn. The derivation
happens in one place, and the limit that the configuration already carries is never loosened and never raised above
the derived one. When the caller gave no cap of the calls of the model, the graph is not left without a ceiling, but
the ceiling of the graph is named as the ceiling of the graph, with the number of the steps, and never as a cap of
the run.

### The cut

A turn that the ceiling stops and that has no answer returns the sentence of the cut, so that the visitor reads what
stopped the run instead of an empty answer. The sentence is the one the result carries, not a second telling of the
same limit.

## Alternatives considered

- **To leave the live path without the wall and to correct the contract instead.** Refused. The contract describes
  what the product does for a person who waits for an answer, and a failed run with an internal exception is not an
  answer for anybody. The wall is the cheaper of the two changes and the one that makes the product behave the way
  its own documentation says it behaves.
- **To let the wall swallow the ceiling of the run.** Refused. A ceiling that reaches the model as a tool failure is
  a ceiling the model can work around, and the run would go on with a budget that is already spent.
- **To keep the ceiling only inside `investigate` and to narrow the docstring of `Integrator.invoke`.** Refused. A
  path that reaches the graph without a bound is a path where the loop runs until the provider stops it, and a
  docstring that describes the paths that are bounded is a docstring that the reader has to check against the code.
- **To give the live turn the ceiling of the visitor, in this record.** Refused, and it stays a debt. The connection
  between the turn of the live path and the ceiling the visitor asked for is the task T120, it crosses the coordinator
  of the run and the case, and it is a change of the contract of the run. This record says what is true today: the
  live path runs under the ceiling of the published paths, and the visitor who asked for more does not get it.

## Consequences

- **A tool that raises no longer takes a live run down.** The model reads the envelope, the result carries
  `TOOL_FAILED` and `requires_human_review`, and the visitor reads the answer of the model.
- **Every path that reaches the graph is bounded**, and the number that bounds it comes from the same cap as the
  number that bounds the provider.
- **The cut is visible.** A live run that the ceiling stops answers with the sentence of the cut, and the sentence
  names the limit that stopped it.
- **The ceiling of the graph is named as such** when the caller gave no cap of the calls of the model, and the
  sentence no longer invents a value.
- **The live path still runs under the ceiling of the published paths** (twelve calls of the model, sixteen of the
  tools, 120 seconds), and the ceiling the visitor asked for is not the one that applies. That is the debt T120, and
  the readiness audit of 2027 carries it.
- **The number that stops the graph is now held by a test**, and the test fails when the derived number changes.

## Links

- [ADR-054, the agent loop has a ceiling in every path](ADR-054-the-agent-loop-has-a-ceiling-in-every-path.md)
- [ADR-013, the public trace is a versioned contract](ADR-013-public-trace-as-a-versioned-contract.md)
- [the contract of the tools](../contracts/tools.md)
- [the wall of the demo and of the evaluation](../../ledgerlens/agents/integrator.py)
- [the live path](../../ledgerlens/api/live_case.py)
- [the budget of the turn](../../ledgerlens/agents/budget.py)
