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

# The datasets of the evaluation must stay pinned: a dataset that moves without the manifest moving makes the
# numbers of the reports describe a file that is not on the disk anymore. The check reads the disk, writes
# nothing, and refuses with a readable reason and a non zero exit code, so the gate stops on the reason and
# not on a traceback.
echo "== eval datasets (offline)"
uv run python scripts/check_eval_datasets.py

# The registry of the feedback must match the records on the disk: a record that moves without the registry
# moving makes the loop describe a file that is not on the disk anymore, and a record of a visitor must never
# enter the shared set. The check reads the disk, writes nothing, and refuses with a readable reason and a
# non zero exit code, so the gate stops on the reason and not on a traceback.
echo "== feedback registry (offline)"
uv run python scripts/check_feedback_registry.py

# The committed policy index must describe the policies of the repository, because an index built from another
# corpus answers with text that is not on the disk, and every other check of the gate stays green while it
# happens. The check reads the disk, writes nothing, needs no model and no network, and refuses with a
# readable reason and a non zero exit code, so the gate stops on the reason and not on a traceback.
echo "== policy index (offline)"
uv run python scripts/check_policy_index.py

# The index of the documentation must describe the files that are on the disk, because an index that lies is
# worse than no index: a reader who follows a line of the index and finds nothing there stops trusting the
# index. The check reads the disk, writes nothing, and refuses with a readable reason and a non zero exit code,
# so the gate stops on the reason and not on a traceback.
echo "== docs index (offline)"
uv run python scripts/build_docs_index.py --check

# Every link of the documentation must point to a file of the repository, because a link that points to nothing
# is a promise the repository does not keep, and the index of the documentation is built from the names of the
# files and not from the links inside them. The check reads the disk, writes nothing, and refuses with a readable
# reason and a non zero exit code, so the gate stops on the reason and not on a traceback.
echo "== doc links (offline)"
uv run python scripts/check_doc_links.py

# The twin of the operations must stay honest: a run of the seed 42 is deterministic, and the two published
# catalogs of the recordings of the agent are untouched by a run of the twin. The check writes nothing and
# fails the gate with a readable reason, so the gate stops on the reason and not on a traceback.
echo "== twin (offline)"
uv run python scripts/check_twin.py

# The published artifacts must match the bundle they claim to show, or the site shows a recording that is not the
# one that was made. The check writes nothing and fails the gate when it finds a difference.
echo "== export check (offline)"
uv run python scripts/export_replay_site.py --check

# The published artifacts must carry the digests of the canonical bundle, because the browser checks the digests of
# what it downloads and nobody compares the two copies. The check reads the disk, writes nothing, and refuses with
# a readable reason and a non zero exit code, so the gate stops on the reason and not on a traceback.
echo "== replay digests (offline)"
# Every published scenario is cross checked, and not only the first one: a scenario that the site publishes and
# that nobody checks is a scenario that can drift without anyone noticing.
for bundle in data/eval/replay/s*; do
  slug="$(basename "$bundle")"
  uv run python scripts/verify_replay_digests.py --bundle "$bundle" --published "site/replay/$slug"
done

# The second catalogue, the recordings of a real model, is published with the same rules and is checked with the
# same scripts: the export must match the bundles, and every published scenario must carry the digests of the
# canonical bundle. The mode of the catalogue is named, so that a recording of a real model cannot land in the
# folder of the sandbox and the other way round (ADR-075).
echo "== export check of the catalogue of a real model (offline)"
uv run python scripts/export_replay_site.py data/eval/replay-real --out site/replay-real --mode live_agent --check

echo "== replay digests of the catalogue of a real model (offline)"
for bundle in data/eval/replay-real/s*; do
  slug="$(basename "$bundle")"
  uv run python scripts/verify_replay_digests.py --bundle "$bundle" --published "site/replay-real/$slug" \
    --index site/replay-real/index.json
done

# The published payload must stay inside the budget the specification declares (SC-004), and the number of events
# must agree with the manifest. The check reads the disk, writes nothing, and refuses with a readable reason and a
# non zero exit code, so the gate stops on the reason and not on a traceback.
echo "== replay budget (offline)"
uv run python scripts/measure_replay_budget.py

# The payload of the second catalogue is inside the same budget: a recording of a real model answers in more
# characters than a scripted one, and the budget is the promise of the specification for every scenario.
echo "== replay budget of the catalogue of a real model (offline)"
uv run python scripts/measure_replay_budget.py --site site/replay-real

# The published proofs must match the bundles they were built from: a proof that drifts from its bundle is a
# proof that asks the reader to trust the name and not the bytes. The check rebuilds the export, writes
# nothing, and refuses with a readable reason and a non zero exit code.
echo "== proof check (offline)"
uv run python scripts/export_proof_site.py --check

echo "gate: ok"
