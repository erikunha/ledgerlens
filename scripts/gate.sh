#!/usr/bin/env bash
# Local gate: lint and offline tests. Run from anywhere; stops at the first failure.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
export LEDGERLENS_OFFLINE=1
# same locale as CI (ubuntu, C.UTF-8): a test that depends on the machine's language fails here too
export LANG=C.UTF-8 LC_ALL=C.UTF-8

echo "== ruff check"
uv run ruff check

echo "== pytest -q (offline)"
uv run pytest -q

echo "gate: ok"
