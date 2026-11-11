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
- The design package that drives the work is versioned in `docs/v3/`, imported by `scripts/import_v3_pack.py`.
- The local planning folders and the local notes stay out of git.

## Before each commit
```bash
bash scripts/gate.sh   # ruff, pytest offline
```
The same gate runs in GitHub Actions (`.github/workflows/gate.yml`).

## Secrets
- Keys only in `.env` (out of git). `.env.example` lists the names without values.
- Everything runs without a key with `LEDGERLENS_OFFLINE=1`.
