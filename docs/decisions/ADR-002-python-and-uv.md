---
type: adr
status: accepted
date: 2026-11-07
---

# ADR-002: Python 3.12 and uv with a locked environment

Status: accepted. Date: 2026-11-07.

## Context

The system Python on the development machine is 3.15.0, too new for some of the AI dependencies. The machine's user-level `uv` configuration has `exclude-newer = "2026-10-17T00:00:00Z"`, a one-week quarantine for new packages. With it, `langchain` 1.4.9 (published on 2026-11-04) does not resolve.

## Decision

- Python 3.12, managed by `uv`, with `requires-python = ">=3.12,<3.13"` and `.python-version`.
- Dependencies in `pyproject.toml`, locked in `uv.lock`.
- `pyproject.toml` sets `[tool.uv] exclude-newer = "2026-11-08T00:00:00Z"`. Tested: the project value wins over the user value and `uv lock` resolves `langchain` 1.4.9. The value only moves forward when the lock is refreshed on purpose.
- The repository's check scripts use only the standard library and run on any Python 3.9 or newer, with `python3 -I`.

## Alternatives considered

- **System Python (3.15).** Rejected: packages such as `faiss-cpu` and `fastembed` may not have wheels for it (not verified), and the result would depend on the machine.
- **`pip` and `requirements.txt`.** Rejected: no lock with hashes and no Python version management.
- **Poetry.** Works, but `uv` is already installed and resolves faster.

## Consequences

- Anyone who clones the repository runs `uv sync` and gets the same versions, even with a different `uv` configuration.
- Updating a dependency requires changing the `exclude-newer` date and redoing the lock, as a deliberate step.
