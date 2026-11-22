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

# The published artifacts must match the bundle they claim to show, or the site shows a recording that is not the
# one that was made. The check writes nothing and fails the gate when it finds a difference.
echo "== export check (offline)"
uv run python scripts/export_replay_site.py --check

# The published artifacts must carry the digests of the canonical bundle, because the browser checks the digests of
# what it downloads and nobody compares the two copies. The check reads the disk, writes nothing, and refuses with
# a readable reason and a non zero exit code, so the gate stops on the reason and not on a traceback.
echo "== replay digests (offline)"
uv run python scripts/verify_replay_digests.py

# The published payload must stay inside the budget the specification declares (SC-004), and the number of events
# must agree with the manifest. The check reads the disk, writes nothing, and refuses with a readable reason and a
# non zero exit code, so the gate stops on the reason and not on a traceback.
echo "== replay budget (offline)"
uv run python scripts/measure_replay_budget.py

echo "gate: ok"
