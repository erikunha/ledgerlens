#!/usr/bin/env bash
# Validate the Streamlit pages and the artifacts shown in the portal.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export LEDGERLENS_OFFLINE=1
uv run ruff check app tests/app
uv run pytest -q tests/app tests/test_ai_disclosure.py
uv run python scripts/export_proof_site.py --check
uv run python scripts/export_eval_lab.py --check
echo "gate_web: ok"
