# Feature Specification: Runtime latency and cost per case

**Feature Branch**: `feature/v3`

**Created**: 2026-11-22

**Status**: Draft

**Input**: Design documents: `docs/decisions/ADR-054-the-agent-loop-has-a-ceiling-in-every-path.md`,
`docs/decisions/ADR-055-the-policy-index-carries-the-hash-of-the-corpus.md`,
`docs/decisions/ADR-056-two-vector-sites-and-one-protocol.md`,
`docs/v3/advanced-specs/R9-03-cost-per-correctly-resolved-case.md` and the metric table of
`docs/v3/docs/09-EVALUATION-AND-EXPERIMENTS.md:45`. User description: "The repository can say what its agent
answers and it can say whether its verifier is right, and it cannot say what a turn costs, how long a turn takes or
what a human review costs. The agent loop of the paths that ship has no ceiling, the index of the policies answers
from a corpus that may have moved, the promise that one file talks to FAISS is false, and the number of the latency
does not exist. The release gives the loop a ceiling that every path carries, ties the index to the corpus it was
built from, puts the vector library behind one protocol, and measures the latency and the cost of a case with the
hardware, the denominator and the role of the set in the report."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run a turn and know that it ends (Priority: P1)

The operator runs the demo, the evaluation or the live mode and knows that no investigation can run for ever. Every
path that reaches a provider carries the same ceiling: at most 12 calls of a model, at most 16 calls of a tool and
120 seconds of wall clock. A turn that a cap stopped is not a crash and not a stack trace: the caller receives a
result whose verdict is `requires_human_review` with the action `escalate_to_human`, the reason names the cap and
its value, and the answer that already exists stands. The follow-up of a turn spends what is left of the ceiling of
the turn and never a ceiling of its own. The operator reads the calls, the tokens and the elapsed time of the turn
on the result, and reads the cap that stopped it there too.

**Why this priority**: an unbounded loop is an unbounded bill and an unbounded wait, and the paths that ship are the
ones a reader and a reviewer hit.

**Independent test**: give the shipped loop a model that never stops calling tools and run it with the scripted
model of the repository. The call comes back as a result, the result names the cap that stopped it, and the
number of the calls of the model never passes 12.

### User Story 2 - Read the latency of a turn and know what it was measured on (Priority: P1)

The reader of the evaluation wants to know how long a turn takes. The report says the p50 and the p95, end to end
and per stage, over the thirty cases of `data/eval/eval_cases.jsonl`, and it says what it was measured over: the
processor, the memory, the system, the version of Python, the model and its temperature, the digest of the set and
the role of that set in the manifest of the datasets. Because the role of the set is `tuning`, the report says
plainly that the numbers are a tendency over thirty cases and not a generalization to unseen data. The same report
says what the wall clock cap of 120 seconds of ADR-054 is worth: the measurement comes back to the record with the
number, and the value of the cap changes when the measurement says it has to.

**Why this priority**: a latency without the hardware and the denominator is a number that nobody can compare with
anything, and the design package already asks for the p50 and the p95 with the hardware reported.

**Independent test**: run the measurement script on the machine of the reader and read the report. The report names
the set, its digest, its role, the denominator, the hardware and the two percentiles, and it prints the same
percentiles that the test of the percentile function produces for a known series.

### User Story 3 - Read the cost of an investigation and of a correctly resolved case (Priority: P1)

The reader of the evaluation wants to know what a case costs. The report says the cost of an investigation, the cost
per correctly resolved case, the cost of the cases that a human has to read and the total of the run. The money is
exact and comes from code with `Decimal`, and the price of every model carries its provenance and its date. When
the price of the model is unknown, the report says unknown and does not print a zero that would read as a gift. A
case that went to a human is a case that was not correctly resolved and it pays the cost of the review, and the
minutes of a review and the rate of an hour are assumptions of the run that the report shows and that a reader may
change. When no case was resolved, the cost per correctly resolved case is undefined and the report says why.

**Why this priority**: the cost of a case is the number that decides whether the system is worth running, and the
review of a human is a cost that no number of the repository counts today.

**Independent test**: give the economics module a run with a known price of a model, a known rate of a review and a
known number of resolved cases, and read the cost per correctly resolved case. The number is the exact division,
the denominator is visible, and a run with zero resolved cases produces an undefined value and an explanation.

### User Story 4 - Edit a policy and see the index refuse (Priority: P2)

The engineer edits a policy of `data/policies/` and commits it. The index that was built from the old text is stale,
and the loader says so before it loads anything: the refusal names the digest of the corpus of the disk, the digest
of the corpus the index was built from and the command that rebuilds it. The tool that answers with a policy turns
the refusal into the code `INDEX_STALE` of the envelope and does not search. The gate of the repository refuses a
commit whose committed index does not match the policies of the disk, and the check reads two files and never
downloads the model.

**Why this priority**: an answer that cites a policy version the text behind it does not have is a wrong answer
that looks right, and the failure is invisible until the policy is edited.

**Independent test**: edit one byte of one policy of `data/policies/` and run the check of the gate. The check exits
with a non zero code, names the file and the two digests, and writes nothing.

### User Story 5 - Swap the vector library and touch one file (Priority: P2)

The engineer who wants to replace the vector library opens `ledgerlens/vectorstore.py` and finds the import of the
library, the normalization of the vectors and the consent to open the pickle in the same place, behind three
operations and a handle that no caller names. The policy index and the case index keep their own lifecycle: the
policy index is a build artifact that is only loaded, and the case index is live data that rebuilds itself at read
time and says so in the note of the envelope when it does. A test reads the modules of `ledgerlens/` and refuses any
import of the library outside that one file. The runner of the evaluation is declared as the third site and says in
its docstring why it builds its own vectors.

**Why this priority**: the promise of one file was false, and a promise in prose is a promise that drifts. The
promotion of the promise to a check is what keeps it true.

**Independent test**: add an import of `langchain_community.vectorstores` to any module of `ledgerlens/` that is
not `ledgerlens/vectorstore.py` and run the guard. The guard fails and names the module that broke the promise.

### Edge Cases

- A turn that a cap stopped: the result carries the verdict, the reason names the cap and its value, and the
  answer that exists stands even when it is empty.
- A follow-up of a turn whose ceiling is already spent: the follow-up does not run, and the result says that the
  cap stopped the turn.
- A model whose price is unknown: the money is unknown and not zero, and the cost per correctly resolved case is
  not published as a measured number.
- A run with no correctly resolved case: the cost per correctly resolved case is undefined, with the reason.
- A case that a human has to read: it counts as a case that was not resolved, and it pays the cost of the review.
- A corpus of the policies that moved: the loader refuses before the store is loaded, and the store is never read.
- An index built over another corpus that has the same embedding and the same dimension: the digest is what refuses
  it, not the vector space.
- A machine that is not the machine of the published report: the numbers of another machine are another report and
  they say which machine they come from.
- A set whose role is `tuning`: every number over it says that it is a tendency and not a generalization.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every path that reaches a provider carries the ceiling of `RunBudget`, and `BudgetCoordinator` is the
  only thing that enforces it.
- **FR-002**: The ceiling of the shipped paths is 12 calls of a model, 16 calls of a tool and 120 seconds of wall
  clock, and the money cap is off while the price of the model is unknown.
- **FR-003**: A cap that was hit returns a result with `requires_human_review` and `escalate_to_human`, never an
  exception, and the reason names the cap and its value.
- **FR-004**: The follow-up of a turn shares the coordinator of the turn, and a turn whose ceiling is spent does not
  run the follow-up.
- **FR-005**: The result carries the usage of the turn: the calls, the tokens, the elapsed time, the two costs, the
  flag of the price and the cap that cut the turn.
- **FR-006**: The meta of the policy index carries the sha256 of the corpus, over the sorted names and the sha256 of
  the bytes of every file, and the loader compares it before it loads anything.
- **FR-007**: A stale index is refused with the code `INDEX_STALE` of the envelope, and the tool does not search.
- **FR-008**: The gate refuses a repository whose committed index does not match its policies, and the check reads
  the disk, writes nothing and never loads the model.
- **FR-009**: One module of `ledgerlens/` imports the vector library, and a test that reads the modules with `ast`
  refuses any other import of it.
- **FR-010**: The report of the latency says the p50 and the p95, end to end and per stage, with the hardware, the
  digest of the set, the role of the set and the denominator.
- **FR-011**: The cost of an investigation, the cost per correctly resolved case, the cost of the review and the
  total of the run are computed with `Decimal`, and the price of every model carries its provenance.
- **FR-012**: The minutes of a review and the rate of an hour are assumptions of the run, shown in the report and
  never a constant of the code.
- **FR-013**: A case that a cap cut is scored as a case that was cut and not as a wrong answer, and the report
  shows the two apart.
- **FR-014**: The measurement comes back to ADR-054 with the p50 and the p95 of the turn and the value that
  `max_wall_seconds` has to carry.

### Key Entities

- **Run budget**: the ceiling of a turn, declared in `RunBudget` and enforced by one `BudgetCoordinator`.
- **Usage of a turn**: the calls, the tokens, the elapsed time, the two costs and the cap that cut the turn, on the
  result.
- **Corpus digest**: the sha256 over the sorted names and the sha256 of the bytes of the policies, in the meta.
- **Vector protocol**: the handle and the three operations of `ledgerlens/vectorstore.py`.
- **Latency report**: the percentiles per stage with the hardware, the set, the role and the denominator.
- **Economics of a run**: the cost per investigation, the cost per correctly resolved case, the cost of the review
  and the total, with the provenance of every price.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A loop that never stops calling tools comes back as a result, and the number of the calls of the model
  never passes 12, checked by a test of the integrator.
- **SC-002**: A turn that a cap stopped carries `requires_human_review` with `escalate_to_human`, and the reason
  names the cap and its value.
- **SC-003**: The usage of the turn travels on the result, and the contract
  `docs/contracts/investigation_result.schema.json` accepts the new payload, checked by the test of the schemas.
- **SC-004**: The follow-up of a turn never calls the model past the ceiling of the turn, checked by a test.
- **SC-005**: The digest of the corpus moves when a byte of a policy moves, when a file is added and when a file is
  removed, and the loader of a stale index refuses before the store is loaded.
- **SC-006**: The tool of the policies answers with `INDEX_STALE` and does not search, and the code is in the
  docstring of the module and in `docs/contracts/tools.md`.
- **SC-007**: The check of the index is a step of `scripts/gate.sh`, it writes nothing, and it exits with a non zero
  code and a readable reason when the corpus moved.
- **SC-008**: The guard that reads the modules with `ast` fails when any module of `ledgerlens/` outside
  `ledgerlens/vectorstore.py` imports the vector library.
- **SC-009**: The report of the latency names the p50 and the p95, end to end and per stage, with the hardware, the
  digest of the set, the role of the set and the denominator, and a test reads the report and refuses a number that
  does not.
- **SC-010**: The cost per correctly resolved case is the exact division of the total by the number of the
  resolved cases, computed with `Decimal`, and it is undefined with a reason when the denominator is zero.
- **SC-011**: The price of every model carries its provenance and its date, and an unknown price is published as
  unknown and not as zero.
- **SC-012**: The cost of the human review is in the report, with the minutes and the rate that produced it, and a
  case that went to a human is counted as a case that was not resolved.
- **SC-013**: ADR-054 carries the measured p50 and the p95 of the turn and the value that `max_wall_seconds` has to
  carry, and the value in the code is the value in the record.
- **SC-014**: The whole suite runs offline with `LEDGERLENS_OFFLINE=1`, with no key and no network, and the check of
  the index is a step of the gate of the continuous integration.

## Assumptions

- The three decisions that carry the first three milestones are ADR-054, ADR-055 and ADR-056, and this
  specification does not decide what they decided.
- The measurement needs a provider and a machine, so it runs by hand and the guard that its numbers are honest runs
  in the gate.
- The set of the measurement is `data/eval/eval_cases.jsonl`, with thirty cases and the role `tuning` in the
  manifest of the datasets, so every number over it is a tendency and not a generalization.
- The price of the model of the shipped paths is unknown until the registry carries a verified price for it, and the
  cost of those paths is therefore unknown and not zero.
- The design package of the release is frozen, and the numbers of the design package that this release measures are
  read, never written.

## Out of scope

- The caps of the SQL and of the memory, which belong to the tools and to the memory.
- The deadline of a run, which is the deadline of the session and not the ceiling of the turn.
- The quality of the retrieval and of the answer, which the held out set of the retrieval measures and not this
  release.
- The digest of the model file under the same name and the outage of the embedding service, which ADR-055 names as
  the debts of its own record.
- The interface of the evaluation, which may show the numbers of this release but does not compute them.
