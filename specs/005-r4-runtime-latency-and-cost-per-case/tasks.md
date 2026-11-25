---
description: "Task list for the runtime latency and the cost per case"
---

# Tasks: Runtime latency and cost per case

**Input**: Design documents from `specs/005-r4-runtime-latency-and-cost-per-case/`

**Prerequisites**: plan.md (required), spec.md (required), the three decisions that carry the milestones M23 to M25
(`docs/decisions/ADR-054-the-agent-loop-has-a-ceiling-in-every-path.md`,
`docs/decisions/ADR-055-the-policy-index-carries-the-hash-of-the-corpus.md`,
`docs/decisions/ADR-056-two-vector-sites-and-one-protocol.md`)

**Tests**: Every task that changes the behaviour of the repository ships its test before its code, and the gate of
the Python side is green before the commit. A task that is delivered says so, with **DELIVERED** and the evidence
of what it delivered.

**Organization**: Tasks are grouped by the milestone that delivers them, and the tasks of a milestone touch
disjoint files so that they can be worked on in parallel.

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[DELIVERED]**: the task is done, and the sentence names what it delivered
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `ledgerlens/`, `tests/`, `scripts/`, `data/`, `docs/` at repository root
- Paths shown below assume single project

## Milestone 23, the ceiling of the agent loop in every path that ships

**Purpose**: a turn always stops, and a turn that a cap stopped is a result and not an exception.

- [x] T115 [P] Test the shipped loop stops at the cap of the calls and the turn comes back as a result, in
  tests/agents/test_integrator_budget.py
  - **DELIVERED**: `tests/agents/test_integrator_budget.py::test_a_model_that_keeps_calling_a_tool_stops_at_the_cap_and_comes_back_as_a_result`: the shipped loop stops at the cap and the turn comes back as a result.
- [x] T116 [P] Test the follow-up spends the ceiling of the turn and not a ceiling of its own, in
  tests/agents/test_integrator_budget.py
  - **DELIVERED**: `test_the_follow_up_spends_the_ceiling_of_the_turn_and_not_a_ceiling_of_its_own`: the follow-up spends what the turn has left.
- [x] T117 [P] Test the result carries the calls, the tokens and the two costs, in
  tests/agents/test_integrator_budget.py
  - **DELIVERED**: `test_the_usage_of_the_turn_is_recorded_and_never_passes_the_budget` and `test_the_result_carries_the_calls_the_tokens_and_the_two_costs`: the result carries the calls, the tokens and the two costs.
- [x] T118 Implement the shipped ceiling of the agent loop in ledgerlens/agents/integrator.py, with the coordinator
  of the turn and the handler that reserves
  - **DELIVERED**: the shipped ceiling of the agent loop in `ledgerlens/agents/integrator.py`, with the coordinator of the turn and the handler that reserves, under ADR-054.
- [x] T119 Add the property `usage` to the result in ledgerlens/schemas.py and to the contract in
  docs/contracts/investigation_result.schema.json
  - **DELIVERED**: the property `usage` of the result in `ledgerlens/schemas.py` and in `docs/contracts/investigation_result.schema.json`: the calls, the tokens and the two costs, with the money a text or null.
- [x] T120 Pass the coordinator of the live run to the agent in ledgerlens/api/live_case.py, without a second counter

## Milestone 24, the digest of the corpus and the refusal of a stale index

**Purpose**: the index carries the hash of the corpus it was built from, and the gate refuses a repository whose
committed index does not match its policies.

  - **DELIVERED**: `ledgerlens/api/live_case.py` passes the coordinator of the live run to the agent as the `TurnBudget` of the turn with the owner `caller`, and `ModelCaller.budget` exposes the one counter of the run: no call of the provider is counted twice.
- [x] T121 Write the digest of the corpus in `ledgerlens/retrieval.py`, over the sorted names and the sha256 of the
  bytes of every `*.md` of the folder, and write the field `corpus_sha256` in the meta of `build_policy_index`, with
  the builder taking the folder or the digest, with the tests in `tests/retrieval/test_policy_index.py` that the
  digest moves when a byte of a policy moves, when a file is added and when a file is removed
  - **DELIVERED**: the digest of the corpus in `ledgerlens/retrieval.py` over the sorted names and the sha256 of the bytes, the field `corpus_sha256` in the meta, and the tests that the digest moves when a byte moves, when a file is added and when it is removed.
- [x] T122 Write the exception `IndexStale` and the comparison of the digest in `load_policy_index`, with the test in
  `tests/retrieval/test_policy_index.py` that a policy edited after the build makes the loader refuse and that the
  store is never loaded
  - **DELIVERED**: the exception `IndexStale` and the comparison of the digest in `load_policy_index`, with the test that a policy edited after the build makes the loader refuse and the store is never loaded.
- [x] T123 Map the refusal to the code `INDEX_STALE` in `ledgerlens/tools/policies.py`, add the code to the docstring
  of the module and to `docs/contracts/tools.md`, with the test in `tests/tools/test_policies.py` that the tool
  answers with `INDEX_STALE` and does not search
  - **DELIVERED**: the code `INDEX_STALE` in `ledgerlens/tools/policies.py` and in `docs/contracts/tools.md`, with the test that the tool answers with `INDEX_STALE` and does not search.
- [x] T124 Write `scripts/check_policy_index.py` and wire it into `scripts/gate.sh`, with the test in
  `tests/retrieval/test_check_policy_index.py` that the check refuses when the corpus moved and that it writes nothing
  - **DELIVERED**: `scripts/check_policy_index.py` wired into `scripts/gate.sh`, with the tests that the check refuses when the corpus moved and that it writes nothing.
- [x] T125 Rebuild the committed index over the corpus of the disk with `scripts/build_index.py` and commit
  `data/index/policies_fastembed/`, so the gate is green when the check lands

## Milestone 25, two vector sites and one protocol

**Purpose**: the promise about the vector library becomes a check, and the two lifecycles keep their own meaning.

  - **DELIVERED**: the committed index of `data/index/policies_fastembed/` rebuilt over the corpus of the disk, with the meta carrying the digest of the committed corpus.
- [x] T126 Write the module `ledgerlens/vectorstore.py` with the handle protocol `VectorStore` and the three
  operations `load_index`, `search_index` and `add_to_index`, with the test in `tests/retrieval/test_vectorstore.py`
  that a search returns the closest texts with the distance
  - **DELIVERED**: `ledgerlens/vectorstore.py` with the handle protocol `VectorStore` and the three operations `load_index`, `search_index` and `add_to_index`, with the test in `tests/retrieval/test_vectorstore.py` that a search returns the closest texts with the distance.
- [x] T127 Move the import of FAISS and its three uses out of `ledgerlens/retrieval.py` into the protocol module,
  keeping `build_policy_index`, `load_policy_index` and `search_policy_index` with the same signatures and the same
  results, with the tests of `tests/tools/test_build_index.py` and `tests/tools/test_policies.py` green
  - **DELIVERED**: the import of FAISS and its uses moved out of `ledgerlens/retrieval.py` into the protocol module, with `build_policy_index`, `load_policy_index` and `search_policy_index` keeping the same signatures and the same results, and the tests of the index and of the tool green.
- [x] T128 Move the import of FAISS and its three uses out of `ledgerlens/memory/long_term.py` into the protocol
  module, keeping the behavior of `CaseMemory` the same, with the test of `tests/memory/test_long_term.py` green
  - **DELIVERED**: the import of FAISS and its uses moved out of `ledgerlens/memory/long_term.py` into the protocol module, with the behavior of `CaseMemory` the same and the incremental add over `add_to_index(..., into=...)`, and the tests of the memory green.
- [x] T129 Write the guard in `tests/retrieval/test_vectorstore_boundary.py` that reads the modules of `ledgerlens/`
  with `ast` and refuses any import of `langchain_community.vectorstores` outside `ledgerlens/vectorstore.py`
  - **DELIVERED**: the guard in `tests/retrieval/test_vectorstore_boundary.py` that reads the modules of `ledgerlens/` with `ast` and refuses any import of `langchain_community.vectorstores` outside `ledgerlens/vectorstore.py`.
- [x] T130 Write the note of the rebuild in the case memory: the result of the recall says whether the index was
  rebuilt, and `recall_cases` says it in the note of the envelope, with the test in `tests/tools/test_recall_cases.py`
  - **DELIVERED**: the note of the rebuild in the case memory: `CaseMemory.last_store_rebuilt` says whether the index in use was rebuilt, and `recall_cases` says it in the `index_rebuilt` field and in the note of the envelope, with the test in `tests/tools/test_recall_cases.py`.
- [x] T131 Correct the docstring of `ledgerlens/retrieval.py:4-5`, so that no file says that one file talks to FAISS,
  and write in the docstring of `ledgerlens/eval/run.py` why the runner builds its own vectors

## Milestone 26, the measurement of the latency and of the cost per case

**Purpose**: the p50 and the p95 of a turn, the cost of an investigation and the cost of a correctly resolved case,
with the hardware, the denominator and the role of the set in the report.

  - **DELIVERED**: the docstring of `ledgerlens/retrieval.py` corrected, so that no file says that one file talks to FAISS, and the docstring of `ledgerlens/eval/run.py` says why the runner builds its own vectors.
- [x] T132 [P] Write `ledgerlens/eval/latency.py` with the names of the stages of a turn, the percentile that names
  the method it uses, and the collector that reads the spans of a trace, with the test in `tests/eval/test_latency.py`
  that the p50 and the p95 of a known series are the expected numbers and that the denominator is the count of the
  cases that produced a measurement
  - **DELIVERED**: `ledgerlens/eval/latency.py` with the names of the stages of a turn, the percentile of the nearest rank that names the method, and the collector that reads the spans of a trace, with the test in `tests/eval/test_latency.py` that the p50 and the p95 of a known series are the expected numbers and that the denominator is the count of the cases that produced a measurement.
- [x] T133 Write the latency of the cases in `ledgerlens/eval/run.py`, end to end and per stage, with the columns in
  `data/eval/report_online.md` and in `data/eval/report_offline.md`, with the test in `tests/eval/test_offline_report.py`
  that the report carries the p50 and the p95 with the denominator and the name of the set
  - **DELIVERED**: the latency of the cases in `ledgerlens/eval/run.py`, end to end and per stage, with the section in `data/eval/report_online.md` and in `data/eval/report_offline.md`, with the test in `tests/eval/test_offline_report.py` that the report carries the p50 and the p95 with the denominator and the name of the set.
- [x] T134 Write `scripts/measure_latency.py` that runs the thirty cases of `data/eval/eval_cases.jsonl`, that writes
  `data/eval/report_latency.md` with the processor, the memory, the system, the version of Python, the model and its
  temperature, the digest of the set and the role of the set of the manifest `data/eval/datasets.json`, and with the
  test in `tests/eval/test_measure_latency.py` that the report names the denominator and the hardware
  - **DELIVERED**: `scripts/measure_latency.py` that runs the cases of `data/eval/eval_cases.jsonl` and writes `data/eval/report_latency.md` with the processor, the memory, the system, the version of Python, the model and its temperature, the digest of the set and the role of the set, with the test in `tests/eval/test_measure_latency.py`.
- [x] T135 [P] Create the package `ledgerlens/economics/` with `ledgerlens/economics/costs.py`, the categories
  `model`, `compute`, `review` and `error_assumption` that do not overlap, the price with its provenance and its
  date, and the function that returns the cost per correctly resolved case and nothing at all when the denominator is
  zero, with the test in `tests/economics/test_costs.py` that the money is never a float and that the division by
  zero is refused
  - **DELIVERED**: the package `ledgerlens/economics/` with the categories that do not overlap, the price with its provenance and its date, and the cost per correctly resolved case that is nothing when the denominator is zero, delivered by `ledgerlens/economics/cost.py` and `ledgerlens/economics/assumptions.py` with the tests in `tests/economics/`.
- [x] T136 [P] Write the cost of the human review in `ledgerlens/economics/review.py`, with the minutes of a review
  and the rate of an hour as assumptions of the run and never as constants of the code, with the test in
  `tests/economics/test_review_cost.py` that the total of a run grows with the rate and that a case that goes to a
  human is counted as a case that was not correctly resolved
  - **DELIVERED**: the cost of the human review in `ledgerlens/economics/assumptions.py`, with the minutes of a review and the rate of an hour as assumptions of the run and never as constants of the code, with the test that the total grows with the rate and that a case that goes to a human is not in the denominator.
- [x] T137 Write the collection of the cost of a turn in `ledgerlens/eval/run.py`, from the usage of the result, with
  the refusal to publish a total when the price of the model is unknown, and with the score of a case that a cap cut
  as a case that was cut and not as a wrong answer, with the test in `tests/eval/test_cost_per_case.py`
  - **DELIVERED**: the collection of the cost of a turn in `ledgerlens/eval/run.py`, from the usage of the result, with the refusal to publish a total when the price of the model is unknown, and with the score of a case that a cap cut as a case that was cut and not as a wrong answer, with the test in `tests/eval/test_cost_per_case.py`.
- [x] T138 Write the report `data/eval/report_cost.md` with the cost of an investigation, the cost per correctly
  resolved case, the cost of the review, the total of the run, the provenance of every price, the missing pricing and
  the sensitivity to the rate of the review
  - **DELIVERED**: the report `data/eval/report_cost.md` with the cost of an investigation, the cost per correctly resolved case, the cost of the review, the total of the run not published, the provenance of every price, the missing pricing and the sensitivity to the rate of the review, written by `scripts/measure_cost.py`.
- [x] T139 Come back to `docs/decisions/ADR-054-the-agent-loop-has-a-ceiling-in-every-path.md` with the p50 and the
  p95 of the turn and the value that `max_wall_seconds` has to carry, and write the decision of the milestone
  `docs/decisions/ADR-057-the-latency-and-the-cost-of-a-turn.md`
  - **DELIVERED**: `docs/decisions/ADR-098-the-latency-and-the-cost-of-a-turn.md` with the p50 and the p95 of the turn and the value that `max_wall_seconds` carries: 120 seconds, until the measurement with the provider says otherwise.
- [x] T140 Write the guard `tests/eval/test_runtime_numbers_documentation.py` that reads `data/eval/report_latency.md`
  and `data/eval/report_cost.md` and refuses a published number that does not name the set it was measured over, the
  role of that set, the denominator and the hardware
  - **DELIVERED**: the guard `tests/eval/test_runtime_numbers_documentation.py` that reads `data/eval/report_latency.md` and `data/eval/report_cost.md` and refuses a published number that does not name the set it was measured over, the role of that set, the denominator and the hardware.
