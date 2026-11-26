---
type: adr
status: accepted
date: 2026-11-22
---

# ADR-054: The agent loop has a ceiling in every path

Status: accepted. Date: 2026-11-22.

## Context

The shipped agent loop has no ceiling in the paths that actually ship, so one investigation can cost an unbounded
number of provider calls and an unbounded amount of wall clock. The audit that found it
(`findings/F2_runtime_and_retrieval.md` of the research effort of 2027) is right about the finding and wrong about
two line numbers, and this record verifies every claim against the code.

The design package has already decided the shape of the ceiling (`docs/design/docs/06-AGENT-RUNTIME-AND-TOOLING.md:38`
names the `RunBudget` with the nine caps, `:126` requires the hard limits, and the item `LL-V3-R6-06` is at
`docs/design/roadmap/IMPLEMENTATION-BACKLOG-V3.md:53`), and the package is frozen, so this record decides the wiring and
not the shape.

### The ceiling of the shipped loop is the default of a library

`investigate` builds the configuration of a turn in two lines: `ledgerlens/agents/integrator.py:261` sets
`configurable` and nothing else, and `ledgerlens/agents/integrator.py:270` merges it with the traced configuration,
which carries the run name and the callbacks and nothing else (`traced`, `:298-300`). There is no `recursion_limit`
in it, so the graph of `create_agent` runs with the default of the library, and the default of the library is
`{"recursion_limit": 9_999}` (`langchain/agents/factory.py:1899`, of langchain 1.4.9).

The old path had a ceiling and the new one lost it: `build_tools_agent_executor` takes `max_iterations: int = 8`
(`ledgerlens/agents/modern.py:122`), but that executor is the legacy demonstration of ADR-010 and not the agent that
ships (`ledgerlens/agents/integrator.py:212-217`). The corrections to the audit: `reserve_model_call` and
`reserve_tool_call` are at `ledgerlens/byok/budget.py:207` and `:240`, and not at `:400-423`.

### The budget of the run exists and holds in one path only

`RunBudget` (`ledgerlens/run_context.py:103-118`) already carries the nine caps that the design package names, and
`BudgetCoordinator` (`ledgerlens/byok/budget.py:165`) enforces them (`reserve_model_call` at `:207`,
`reserve_tool_call` at `:240`) and reports what the run spent (`report`, `:295`).

The wiring is in the live path only. `ModelCaller` (`ledgerlens/api/live_run.py:370`) holds the coordinator and
reserves every model call (`ledgerlens/api/live_run.py:449`) and every tool call (`ledgerlens/api/live_run.py:506`).
The four model slots of the agent reach the provider through the bridge (`ledgerlens/api/live_case.py:160`, the slots
at `:121-125`) and every tool through `wrap_tool` (`ledgerlens/api/live_case.py:241`).

The two paths a user and a reviewer actually hit carry nothing: the demo calls `investigate` with no budget
(`app/streamlit_app.py:368`) and the evaluation runner calls `investigate` with no budget (`ledgerlens/eval/run.py:349`),
and `build_integrator` (`ledgerlens/agents/integrator.py:169-226`) has no budget field to give one. The three paths
that reach a provider through `investigate` are these two and the live mode (`ledgerlens/api/live_case.py:448`). This
is the debt that ADR-015 declared (`docs/decisions/ADR-015-run-context-in-the-core.md:61-63`).

## Decision

**The ceiling of a turn is one object, reused, and every path that can reach a provider carries one. The follow-up
shares the ceiling of the turn. The numbers of the turn travel on the result.**

### 1. The caps live in `RunBudget` and the enforcement lives in `BudgetCoordinator`

There is no new object. The caps are the ones of `RunBudget` (`ledgerlens/run_context.py:103-118`) and the
enforcement is the one of `BudgetCoordinator` (`ledgerlens/byok/budget.py:165`), because ADR-034 already decided that
the coordinator is the only thing that enforces the caps and that the caps live in the `RunBudget` of the run context
(`docs/decisions/ADR-034-the-registry-the-budget-and-the-endpoint.md:88-93`). A second enforcer would be a second
source of the truth about the caps, and this repository has already been bitten by that (ADR-052). The coordinator
serves the paths that have no provider registry too: a registry without a verified price makes the money unknown
instead of zero (`ledgerlens/byok/budget.py:186`, `:305`).

The shipped ceiling is declared once, as a `RunBudget` constant of the core, and it is the same object for the demo,
for the evaluation and for the tests. The live mode brings the budget of the request (FR-025). The ceiling is per turn,
because one turn is one answer that one visitor waits for; the ceiling of a session is the deadline, which this record
does not decide.

### 2. The reservation has one owner per path, and the owner is the side that holds the provider

This is the rule that keeps the counters from being counted twice.

- In the live path the reservation belongs to the bridge and to `wrap_tool`, because they are the ones that reach the
  provider (`ledgerlens/api/live_case.py:160`, `:241`). The integrator adds no counter there.
- In the demo and in the evaluation there is no bridge and no wrapper, so the reservation belongs to the integrator,
  which asks the coordinator before every provider call and before every tool call of the turn.

The integrator learns which one it is from the caller: `investigate` takes the coordinator, and a coordinator that was
handed in is the one that counts, so the integrator installs no counter of its own. A caller that hands none gets the
shipped ceiling, built once per turn.

### 3. The concrete limits of the shipped ceiling

| Cap | Value | Why this number |
| --- | --- | --- |
| `max_model_calls` | 12 | The worst turn the evaluation exercises spends 7 calls of a model: the triage, one per plan step, the rewrite of the policy search (`ledgerlens/tools/policies.py:167`) and the answer. The follow-up adds at most 2 more, so 12 leaves three calls of headroom |
| `max_tool_calls` | 16 | The plan of a turn has at most 4 steps with a tool (the maximum of `data/eval/eval_cases.jsonl`) and the follow-up may repeat them. The ceiling of 16 leaves room for the retries of a search that returns nothing, and still stops a turn that loops |
| `max_wall_seconds` | 120 | A declared number and not a measured one: the repository has no latency measurement today. It is above the worst honest turn, and the milestone of the latency has to revisit it |

The money cap of the shipped ceiling is off, because the price of the model there is unknown, and the three caps of
the table hold the run: "the money limit stays off and the call, token and time limits hold the execution"
(`ledgerlens/run_context.py:104-108`).

The graph does not inherit the default of the library any more: the integrator passes an explicit `recursion_limit`,
computed by the code from the same cap of the calls of the models. A `GraphRecursionError` becomes the same verdict as
a cap that was reached, and the cap it names is the cap of the calls of the models.

### 4. What the caller sees when a limit is hit

The verdict is the one of the repository. `requires_human_review` is true and the recommended action is
`escalate_to_human` (`derive_action`, `ledgerlens/verify/escalation.py:334-337`). The `missing_information` of the
result carries the sentence that names the cap and its value, the way the refusal of the coordinator names it
(`ledgerlens/byok/budget.py:513-516`), and the reason reaches the reader of the trace through `review_reasons`
(`ledgerlens/observability/trace.py:236-241`). The answer is the one that exists, and it is empty when the model never
answered, and the caller receives a result and not an exception.

### 5. The follow-up is one follow-up of work

The follow-up is a second complete agent loop (`ledgerlens/agents/integrator.py:321-333`, `:329`), so the bound of one
follow-up is a bound of prompts and not of work. The coordinator is created once per turn and is not reset before it
(`ledgerlens/agents/integrator.py:283`). The follow-up therefore spends what the turn has left, and a turn whose
ceiling is already spent does not run the follow-up at all: the answer that already exists stands, the way it stands
today when the follow-up call fails (`ledgerlens/agents/integrator.py:330-332`), and the result says that the cap
stopped the turn. "One follow-up" keeps its meaning of one request and gains the meaning of a bounded amount of work.

### 6. The numbers of the turn travel on the result

`InvestigationResult` gains one optional field, `usage`, which carries what the turn spent: `model_calls`,
`tool_calls`, `input_tokens`, `output_tokens`, `elapsed_seconds`, `observed_cost_usd`, `estimated_cost_usd`,
`price_known` and `cut_by`. The result carries no such field today (`ledgerlens/schemas.py:147-161`), even though the
trace knows the tokens (`ledgerlens/observability/trace.py:395-397`). The money is a `Decimal` or nothing at all,
never a float and never a zero that would read as "the model was free". Every result that comes out of `investigate`
carries it, including the turn that triage sent back with a question, because the triage is a call of a model.

The record is declared in `ledgerlens/schemas.py` and not imported from `ledgerlens/byok/budget.py`, because the
import would close a cycle: `ledgerlens/byok/budget.py` imports `ledgerlens/run_context.py`, which imports
`ledgerlens/observability/trace_event.py`, which imports `ledgerlens/observability/trace.py`, which imports
`ledgerlens/schemas.py`. The conversion is the one place where the two shapes meet, and it carries the names of the
`CostReport` (`ledgerlens/byok/budget.py:106-132`).

What the implementation of this record did: the numbers of the turn travel in the outputs of the root span of the
trace (`ledgerlens/agents/integrator.py`, the `usage` and the `budget` beside the tokens of the run) and not in a
field of the result, because `ledgerlens/schemas.py` and the contract belong to another slice. The field of the
result is the task T119 below and it is not paid.

The contract `docs/contracts/investigation_result.schema.json` gains the property, and the test that proves a
generated result against the contract (`tests/test_schemas.py:33`) keeps proving it. The `schema_version` of the
result stays "1" (`ledgerlens/schemas.py:148`), because the field is optional and a payload of the old shape still
validates against the new contract, and the version moves only when a field changes its meaning or disappears.

### 7. The live path keeps its budget and does not get a second one

The coordinator of the live run holds the caps (`ledgerlens/api/live_run.py:870`) and the caller that reaches the
provider is the one that reserves (`ledgerlens/api/live_run.py:449`, `:506`). The wiring this record adds to the live
path is one thing: the coordinator reaches the agent through the caller that already holds it, because
`ledgerlens/api/live_case.py:448` calls `investigate` today without it. No counter is added and no cap is added.

### 8. What this record does not decide

- The measurement of the latency and of the cost per case (the p50 and the p95, the hardware, the denominator). It
  belongs to `specs/005-r4-runtime-latency-and-cost-per-case/`, and the wall clock of the table above is a number that
  this milestone has to revisit when the measurement exists.
- The caps of the SQL and of the memory (`max_sql_rows`, `max_sql_seconds`, `max_memory_items`), which belong to the
  tools and to the memory, and not to the loop of the agent.
- The deadline of a run (`deadline_at` in the context of the run).
- The other gaps of the audit (the index without a hash, the tool that raises, the injection defence of the policy
  text, the retrieval numbers) are records of their own.

## Consequences

- The demo, the evaluation and the live mode all carry a ceiling, and the ceiling of the shipped paths is one object
  read by all of them. A model that loops costs at most 12 calls of a provider and 16 calls of a tool per turn, and
  the turn stops with a verdict instead of running for ever.
- The cost of a turn is on the result, so a caller can price a turn without running an evaluation over it. The money
  is unknown and not zero in the shipped paths, because the price of the model there is unknown.
- A turn that a cap cuts is a result and not an exception, and the reason of the cut names the cap. The evaluation
  sees a cut case as a cut case, and the milestone of the cost per case has to score it as one and not as a wrong
  answer.
- The cost of the change is one handler and one field. The tools, the prompt and the verifier do not change.

## The debt of this record

The debt of ADR-015 was a budget that was in the object and held nothing, and this record pays the part of the agent
loop. What is left of that debt is the cap of the SQL, the cap of the memory and the deadline.

The debt of this record is the number that measures the ceiling. The wall clock of 120 seconds is declared and not
measured, because the repository has no latency measurement today, and a number that nobody measured may be wrong in
both directions: too small and a legitimate turn is cut, too large and a loop still costs a minute and a half. The
milestone of `specs/005-r4-runtime-latency-and-cost-per-case/` measures the p50 and the p95 of a turn and comes back
to this record with the number that the wall clock has to be. The implementation is a task of that milestone, in the
format the other tasks of the repository use:

```
- [x] T115 [P] Test the shipped loop stops at the cap of the calls and the turn comes back as a result, in tests/agents/test_integrator_budget.py
- [x] T116 [P] Test the follow-up spends the ceiling of the turn and not a ceiling of its own, in tests/agents/test_integrator_budget.py
- [x] T117 [P] Test the result carries the calls, the tokens and the two costs, in tests/agents/test_integrator_budget.py
- [x] T118 Implement the shipped ceiling of the agent loop in ledgerlens/agents/integrator.py, with the coordinator of the turn and the handler that reserves
- [ ] T119 Add the property `usage` to the result in ledgerlens/schemas.py and to the contract in docs/contracts/investigation_result.schema.json
- [ ] T120 Pass the coordinator of the live run to the agent in ledgerlens/api/live_case.py, without a second counter
```

What is still unpaid, after the implementation of T115 to T118:

- **T119, the field of the result**: the numbers of the turn travel in the trace and not in the result, because
  `ledgerlens/schemas.py` and `docs/contracts/investigation_result.schema.json` belong to another slice. The
  contract of the result does not carry the usage yet.
- **T120, the live path**: the live path builds its own graph over the wrapped tools
  (`ledgerlens/api/live_case.py`), so it does not carry the middleware of the integrator and it counts nothing
  here. Until the coordinator of the live run is handed to `investigate`, the live path is bounded by the
  shipped ceiling (12 calls of a model) and not by the budget of the request. The live path does not get a
  second counter: the bridge and `wrap_tool` are the ones that reserve there.
- **The calls of the models that the tools make** (the model that writes the SQL and the rewrite of the policy
  search) are not reserved by the integrator in the demo and in the evaluation, because they happen inside a
  tool and the integrator does not see them. The live path counts them through the bridge.
