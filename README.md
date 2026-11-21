# LedgerLens

[![gate](https://github.com/erikunha/ledgerlens/actions/workflows/gate.yml/badge.svg)](https://github.com/erikunha/ledgerlens/actions/workflows/gate.yml)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
![LangChain 1.4](https://img.shields.io/badge/langchain-1.4-green)
![runs offline](https://img.shields.io/badge/offline-no%20keys-lightgrey)
[![license MIT](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)

A LangChain agent that investigates payment complaints. It queries a transaction ledger, searches operations policies, compares against a reference exchange rate, does the arithmetic in code, and checks every claim in its own answer against the evidence it used. When the evidence is not enough, the answer says what is missing and the case goes to human review.

![LedgerLens Pay full screen on a MacBook Pro 16-inch: the statement with TX-2048 open and marked "asked about" and "read by assistant", and in Help the question, the trace summary and the agent trace opened (investigate, triage, prompt, model call, parser, agent)](docs/img/streamlit_hero.png)

## Why an agent

A payment operations analyst gets complaints like "the refund came back lower", "I was charged twice" or "the chargeback did not post". To answer, they combine four sources: the transaction ledger, policies, a reference exchange rate, and arithmetic that cannot be wrong. The path changes with every case:

- a status request needs only SQL;
- a refund in another currency needs SQL, policy, exchange rate and arithmetic, in that order;
- an ambiguous request needs a question back.

A fixed chain either runs every step every time or leaves cases out. The agent picks its steps from the request and the evidence, and the answer shows what it picked.

## What it does

- Turns the complaint into a validated triage object (Pydantic): intent, entities, urgency and a step-by-step plan. Triage runs before the agent, and the plan goes into the agent's context.
- Uses six tools:
  - `query_ledger`: text-to-SQL on a read-only database, with a guard that refuses `UPDATE`, `DROP` and internal tables;
  - `get_ledger_record`: the internal ledger API;
  - `search_policies`: policy search over a prebuilt FAISS index, with query rewriting;
  - `get_reference_fx`: ECB reference exchange rates through the Frankfurter API;
  - `calculate`: a calculator built on `Decimal`, so numbers never come from the model;
  - `recall_cases`: long-term case memory.
- Keeps the session history and retrieves similar past cases by meaning.
- Verifies every claim in the answer: an NLI (natural language inference) model judges the text claims, and code checks numbers, rates and exchange-rate dates against the cited evidence.
- Escalates to human review by rule: a dispute deadline close to expiring, suspicious text in a record, an exchange-rate source that is down, claims with no evidence.
- Returns an `InvestigationResult`: the answer, each claim with its evidence, a verdict per claim (`supported`, `contradicted`, `not_enough_evidence`), what is missing, and whether human review is needed.
- Never changes data. The agent only recommends.

## Architecture

```mermaid
flowchart TB
  U["Analyst: CLI or Streamlit"] --> S["Session: thread_id with checkpointer"]
  S --> T["Triage: intent, entities, plan (Pydantic)"]
  T -->|"plan in context"| A["Integrator agent: create_agent or AgentExecutor"]
  Q["Standalone question"] --> R{"Router: LLMRouterChain or LCEL equivalent"}
  R -->|"policy question"| PC["Policy chain (RAG)"]
  R -->|"investigation"| IC["Investigation chain"]
  R -->|"other"| D["Default route"]
  A --> TL["Tools"]
  TL --> T1["query_ledger: text-to-SQL, read-only"]
  TL --> T2["get_ledger_record: internal API"]
  TL --> T3["search_policies: FAISS"]
  TL --> T4["get_reference_fx: Frankfurter, ECB"]
  TL --> T5["calculate: Decimal"]
  TL --> T6["recall_cases: case memory"]
  A --> V["Verifier: NLI, numbers and coherence"]
  V --> O["InvestigationResult with verdicts"]
  O --> W["Write to case memory"]
```

One investigation, step by step:

```mermaid
sequenceDiagram
  participant An as Analyst
  participant Tr as Triage
  participant Ag as Agent
  participant To as Tools
  participant Ve as Verifier
  An->>Tr: "the refund came back lower"
  Tr->>Ag: plan: SQL, policy, exchange rate, calculation
  Ag->>To: query_ledger, search_policies, get_reference_fx
  To-->>Ag: rows, passages, rate (with evidence ids)
  Ag->>To: calculate(difference)
  Ag->>Ve: answer with claims
  Ve-->>An: claims with verdicts and what is missing
```

The integrator comes in two versions with the same tools, the same prompt and the same verifier: `create_agent` (LangChain 1.x, with a checkpointer) and `AgentExecutor` with `RunnableWithMessageHistory` over a SQLite history. The legacy APIs sit next to their current equivalents, for comparison ([ADR-010](docs/decisions/ADR-010-modern-integrator-legacy-as-demonstration.md)).

Details are in [`docs/architecture.md`](docs/architecture.md), [`docs/tools.md`](docs/tools.md) and the [decision records (ADRs)](docs/decisions/).

## Data

Real public data first, simulation only where no public source covers the need ([ADR-009](docs/decisions/ADR-009-public-data-first-simulation-for-gaps.md)):

| Layer | Source |
|---|---|
| Orders and cancellations | UCI Online Retail II (CC BY 4.0) |
| Reference exchange rates | ECB through Frankfurter v1, cross-checked against the Brazilian central bank PTAX rate |
| Business days | the `holidays` library (TARGET and B3 calendars) |
| Card brands | CC BY 4.0 BIN list |
| Simulated with a fixed seed | merchants, chargebacks, settlements and fees, exchange-rate markup, planted anomalies |

Events go into an append-only `events` table, and a projector builds the tables the agent reads. `data/scenarios.json` lists every planted anomaly with its ground truth. Attributions are in [`NOTICE`](NOTICE).

## Quickstart

### Offline, no keys

Needs Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra dev --extra app --extra api
export LEDGERLENS_OFFLINE=1
bash scripts/gate.sh        # ruff and pytest, all offline
```

In offline mode the chat model is a scripted model, embeddings are local (fastembed), HTTP reads recorded responses, and data comes from a committed sample. The agent code does not change. On the first run, fastembed downloads the embedding model into the local cache.

### Demo app (Streamlit)

The demo is a small payments portal, LedgerLens Pay, with fictional accounts from the generated data. It opens signed in as customer C-0412; **Switch demo account** at the top picks another customer or merchant of a planted case (for example merchant M-03 or merchant M-09). The left side shows that account's activity in tabs (Activity, Refunds, Disputes and, for a merchant, Payouts): amount first, then what the line is, its date and a status pill, with filters. Open a line to see its details (transaction id, card, exchange rate applied, fees, deadlines) and press **Ask about this**: the question about that line lands in the Help box on the right, ready to edit before sending. The agent answers as the support assistant. It gets the signed-in account and the line you picked as context, and its tools read a copy of the ledger that holds only that account's records.

Each answer carries the agent trace, a run tree like LangSmith's, drawn live while the agent works: triage, each model call (with tokens) and tool call (arguments, the response envelope and the generated SQL), the verdict on each claim and escalation. When the investigation ends, the trace collapses into a one-line summary and the answer appears below it, with its citations and the ledger records the assistant read marked on the statement. The switch **Show the agent trace** (on by default) hides the trace and the citations, so the answer reads as a support reply. Offline, the planted questions have scripted answers: the FX refund gap (TX-2048), the duplicate charge (TX-2051 and TX-2052), the dispute near its deadline (CB-0310), the payout calculation (ST-0044) and an id that does not exist (TX-9999). **Ask about this** is offered only on those lines; other questions need a configured model.

```bash
uv run streamlit run app/streamlit_app.py
```

### Watch it run

The video below is this app running online with a real model, recorded on 2026-11-11: the question, the agent trace drawn live while the agent works, and the answer with the citations of the sources it used.

![LedgerLens Pay running online: the question in the Help panel, the agent trace growing with the model calls and the tool calls, and the answer with the source citations](docs/img/ledgerlens_demo.mp4)

[docs/demo.md](docs/demo.md) has the recording notes: the mode, what the video shows, the numbers on screen and how it was recorded.

### Online, with a real model

Copy `.env.example` to `.env`, fill in the keys (`OPENAI_API_KEY` and, for traces and experiments, `LANGSMITH_API_KEY`), and run without `LEDGERLENS_OFFLINE`. The default model is `gpt-4.1-mini`, with live exchange rates.

## Live mode: bring your own key

The demo runs with no key at all. The live mode is the opt-in branch of it: the visitor runs a real case with a key of their own provider, inside a hard budget, and everything else keeps working exactly as before. In this milestone the branch is server side: the routes exist and the pages that consume them do not ([ADR-035](docs/decisions/ADR-035-the-facade-of-the-live-mode.md)).

The demo of the visitor is served by one command:

```bash
uv run ledgerlens-demo --port 8010
```

That command serves the wired application of the demo: the live mode and the sandbox of the visitor in one application, over one session issuer, one store of branches, one branch layer and one vault of the credentials, so the branch that the sandbox forks is the branch that the live run reads ([ADR-039](docs/decisions/ADR-039-the-wired-application-of-the-demo.md)). The visitor sees one cookie and one session over the two facades. The two facades alone are two visitors with an issuer each, and the plain factory of `uvicorn` still serves a live mode without a branch layer, which refuses every run with `503 BRANCH_LAYER_MISSING`. [The quickstart of the live mode](specs/003-r3-bring-your-own-key/quickstart.md) shows the whole flow, with the real answers.

What it does:

- the key arrives once, in `POST /v1/credentials`, and it lives in the memory of the server process and nowhere else: no file, no database, no log, no trace, no URL. The answer carries an opaque handle, the provider and the expiry, and never the key itself;
- the handle is bound to the session of the visitor. A handle of another session is refused with the same message as a handle that never existed;
- the credential dies when the visitor forgets it, when the session ends, when its time to live passes, when the vault is full, when the server restarts, or when the provider refuses the key too many times. A credential never outlives the session that holds it;
- the model comes from the catalogue of the server, which lists only the models whose tool calling was really tested. A model that is not in the allowlist is refused by the server, and a model that lacks the capability the architecture needs is refused with the missing capability named, never replaced by another one;
- the run is bounded by the caps the visitor sets: the calls of the model, the calls of the tools, the output tokens, the wall clock and the money. The contract also accepts the optional cap of the input tokens, which is checked on the plan of the run, before the call, because the size of the request is known before the call. The cost report shows the observed cost and the estimated cost apart, and a model whose price was never verified shows no amount at all;
- "forget key" is always there and takes effect at once, and cancelling a run stops the calls that have not started. A call that was already at the provider is a best effort, and the answer says so.

**The disclosure.** It travels in headers, because the contract of the handle accepts no other field:

| Header | What it says |
|---|---|
| `X-LedgerLens-Key-Storage` | the key is not stored: it lives in the memory of the server and the credential is dropped when the session ends |
| `X-LedgerLens-Billing-Disclosure` | your provider may charge you for the calls of this run |
| `X-LedgerLens-Key-Erasure` | the memory of the machine cannot be guaranteed to be erased: the server drops the key when the credential ends, but no runtime can promise that no copy of the text of the key survives in the memory of the interpreter or in a swap of the operating system |

**The limitation.** The product never writes the key anywhere and drops it when the credential ends, but nobody can promise that no copy of the text of the key survives in the memory of the interpreter or in a swap of the operating system. The server wipes what it can and says out loud that it cannot promise the rest.

While the product runs offline (`LEDGERLENS_OFFLINE=1`) the live mode is refused with a readable reason, and the replay and the sandbox keep working exactly as before.

## Results

Online evaluation: 30 cases, three runs of each variant, `gpt-4.1-mini` at temperature 0. Mean [min, max] over the three runs.

| Variant | Correctness | Groundedness | Tool trajectory (equivalent, unordered) | Explanation (LLM judge) | Sent to human review (of 30) |
|---|---|---|---|---|---|
| A: chain with no tools | 0.17 [0.17, 0.17] | 0.00 | 0.00 | 0.70 [0.69, 0.72] | 30.0 |
| B: ReAct agent | 0.55 [0.51, 0.58] | 0.00 | 0.64 [0.57, 0.70] | 0.83 [0.80, 0.87] | 29.0 [28, 30] |
| C: full agent with verifier | 0.82 [0.79, 0.85] | 0.74 [0.71, 0.76] | 0.73 [0.73, 0.73] | 0.79 [0.77, 0.81] | 9.3 [8, 10] |

- The full agent (C) gets the facts right far more often than the tool-free chain (A) and the ReAct agent (B), and it is the only variant whose answers are grounded in cited evidence.
- Verification keeps about two thirds of C's answers out of the human review queue. A and B cite no evidence, so every answer goes to review.
- C's tool trajectory reaches 0.73 with the declared equivalence (reading one record by id with `query_ledger` or `get_ledger_record`), short of the 0.80 target.
- On its 43-case verification set the verifier gets every verdict right: contradiction recall 1.00, no false positives.
- One B case failed in one run because the model wrote a malformed ReAct step; the harness now skips such steps instead of dropping the case.
- Thirty cases show a trend, not statistical significance. The run cost about US$ 0.59 at list price.

The full report is in [`data/eval/report_online.md`](data/eval/report_online.md); the offline report, with the scripted model, is in [`data/eval/report_offline.md`](data/eval/report_offline.md).

## Tests and gate

`bash scripts/gate.sh` runs `ruff check` and `pytest -q` with `LEDGERLENS_OFFLINE=1`. It is the same command CI runs ([`.github/workflows/gate.yml`](.github/workflows/gate.yml)). The tests cover the SQL guard, the calculator, the tools, the verifier and escalation, both integrators with deterministic scripts, the simulator and the evaluation. The `data/ledger.db` database is generated from the versioned sample and is not needed for the gate.

## Layout

```text
ledgerlens/   package: config, schemas, prompts, chains, tools, memory, agents, verify, observability, eval, sim
app/          Streamlit demo portal (LedgerLens Pay) with the Help assistant
scripts/      gate, build_index, fetch_public_data, record_fixtures
data/         policies, fixtures, prebuilt FAISS index, sample, evaluation sets and reports
tests/        pytest suites mirroring the package
docs/         architecture, tools, contracts and decisions (ADRs)
```

## Limitations

- The exchange rate is an ECB reference, not the rate the acquirer applied. The agent says so.
- The source orders are real but old, with shifted dates. Chargebacks, settlements, fees and markups are simulated and marked in the `origin` column.
- Thirty evaluation cases show a trend, not statistical significance.
- Policy retrieval from the offline index misses some hard questions; query rewriting recovers most of them ([ADR-006](docs/decisions/ADR-006-embeddings-and-index.md)).
- The NLI model often marks true sentences as not enough evidence, so many real answers still go to human review. Numbers, rates and exchange-rate dates are checked by code.
- The agent only recommends. It does not move money or change records.
- The live mode never writes the key to a file, a log or a trace and drops it when the credential ends, but no runtime can promise that no copy of the text of the key survives in the memory of the interpreter or in a swap of the operating system.
- A live run is paid for by the visitor: the provider of the visitor may charge the visitor for the calls of the run.

## License

MIT, see [`LICENSE`](LICENSE). Data sources keep their own licenses (see [`NOTICE`](NOTICE)).
