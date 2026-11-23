# LedgerLens Constitution

## Core Principles

### I. Evidence over fluency
Every claim in an answer points to the evidence that supports it: a SQL row, a policy chunk, an exchange-rate response or
a deterministic calculation. A claim with no evidence is marked unverified or removed. When data is missing, the agent
says what is missing and what would settle it, instead of guessing.

### II. Numbers come from code
Amounts, differences, fees and conversions are computed by deterministic Python functions with `Decimal`, never by the
language model. NLI and LLM judges never decide whether a number is right.

### III. Read-only and least privilege
The agent cannot change data. SQL runs on a read-only connection, one `SELECT` at a time, on allowlisted tables, with a
forced `LIMIT` and a timeout, after `sqlglot` validation. External calls have timeouts, retries with a cap and cached
fixtures.

### IV. Reproducible without credentials
Every test and demo runs with `LEDGERLENS_OFFLINE=1`: a scripted fake model, prebuilt embeddings and index, and
exchange-rate fixtures. Online mode only swaps the providers. Synthetic data is generated from a fixed seed. No real
customer data, ever.

### V. Truthful labels
A recorded trace is a recording, a sandbox run is a sandbox run, and a live run is a live run. The `mode` travels with
every event and with every bundle manifest, and the label of a replay never says "live". A number is published only with
the denominator it was measured over and the assumption it assumes.

### VI. Legacy where it teaches, modern where it matters
The integrator is built on `create_agent` from `langchain.agents`, with checkpointer short-term memory (ADR-010). The
older agent APIs appear only as short demonstrations from `langchain-classic`, each next to its current equivalent.
Shared building blocks (prompts, parsers, tools, retrieval, verification) are plain LCEL and `langchain-core`, so they
work with both.

### VII. Test first, measure always
Each tool and chain gets a unit test with the fake model before it is wired into the agent. Agent behaviour is measured
with a dataset and evaluators (quality and tool trajectory), not judged from a few good runs.

## Constraints

- Python 3.12, `uv`, dependencies pinned in `uv.lock`. Code identifiers in English; prompts, few-shot examples, policy
  data shown to the analyst, the UI and the docs in English.
- Provider-agnostic: models come from `init_chat_model` with names in `.env`; no provider is hard-coded outside
  configuration.
- Secrets only in `.env` (ignored by git); `.env.example` lists the names with no values. Callbacks and logs never print
  keys or full prompts with personal data.
- No em dash or en dash in prose.
- The public repository carries no course material, no machine paths of the author and no Portuguese.

## Workflow and quality gates

- `uv run ruff check` and `uv run pytest` (offline) pass before every commit.
- Each slice of the v3 roadmap ends with evidence a third party can rerun: a hash of origin, a test, a fixture or a
  trace, and the exact command.
- Decisions that constrain later work get an ADR in `docs/decisions/`, with the alternatives and why they lost.

## Governance

This constitution overrides other practices in this repository. Changing a principle needs a note in `docs/decisions/` and
a version bump.

**Version**: 2.0.0 | **Ratified**: 2026-11-11 | **Last Amended**: 2026-11-11 (principle V, English public edition)
