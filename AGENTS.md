# Conventions of LedgerLens

A LangChain agent that investigates payment complaints. Public repository, read-only for outsiders.

## Language
- Prompts, examples, policy data, interface and docs in English.
- Code identifiers (modules, functions, variables) in English.
- No em dash (U+2014) and no en dash (U+2013) in any text.

## Code
- Every module starts with a docstring in English that says what it does and why, written for whoever reads the code for
  the first time.
- Non-obvious lines carry a short comment with the why, not the what.
- Numbers (amounts, exchange rates, fees) come out of functions with `Decimal`, never from the model.
- Test before the code: every tool and chain has a test with the scripted model (`ScriptedChatModel`).

## Documentation
- The documentation lives in `docs/`. Links in Markdown (`[text](path.md)`), never wikilinks.
- Diagrams in Mermaid whenever a flow, a sequence or a relation is clearer drawn.
- Every decision that restricts future work becomes an ADR in `docs/decisions/`.
- The design package that drives the work is versioned in `docs/design/`, imported by `scripts/import_v3_pack.py`.
- The local planning folders and the local notes stay out of git.

## Before each commit
```bash
bash scripts/gate.sh      # ruff, pytest offline, the check of the export
bash scripts/gate_web.sh  # npm ci, typecheck, lint, vitest, next build
```
The Python gate (`scripts/gate.sh`) is the one that runs everywhere, including in GitHub Actions
(`.github/workflows/gate.yml`). The Node gate (`scripts/gate_web.sh`) is the one of the frontend, and it runs in the
second job of the same workflow. The Node gate is not folded into the Python gate: a gate that fails because a tool is
missing is not a gate.

## Secrets
- Keys only in `.env` (out of git). `.env.example` lists the names without values.
- Everything runs without a key with `LEDGERLENS_OFFLINE=1`.
