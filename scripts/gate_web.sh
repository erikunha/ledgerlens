#!/usr/bin/env bash
# Node gate of the frontend: the locked install, the type check, the lint, the unit tests and the static export.
# Run from anywhere; stops at the first failure.
#
# This gate is a separate script and it is not folded into scripts/gate.sh: that one is the gate of a Python
# repository and it runs in places where Node is absent. A gate that fails because a tool is missing is not a gate.
set -euo pipefail

# The root of the repository, so that the paths of the gate do not depend on the folder it was called from.
REPOSITORY_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# The commands of the gate run inside the frontend, which is the package that carries them.
cd "${REPOSITORY_ROOT}/apps/web"

# The build of Next.js must not phone home: the gate runs offline, and a telemetry call is a network call.
export NEXT_TELEMETRY_DISABLED=1

# The lock file decides the versions, so the install is reproducible and a broken lock fails the gate.
echo "== npm ci (locked dependencies)"
npm ci

# The type check proves that the types of the contracts and the types of the page agree.
echo "== npm run typecheck"
npm run typecheck

# The lint proves that the rules of the repository hold in the code of the frontend.
echo "== npm run lint"
npm run lint

# The unit tests prove the behaviour of the transport, of the URL contract and of the components.
echo "== npm test"
npm test

# The build proves that the static export still builds, which is the promise of the site of the demo.
echo "== npm run build (static export)"
npm run build

# The recorded demo has to be in the export: the site has to serve the artifacts the repository publishes,
# and a build that leaves the recording out is a build that serves nothing.
echo "== the recorded demo is in the export"
export LEDGERLENS_REPLAY_OUT="${REPOSITORY_ROOT}/apps/web/out/replay"
node <<'NODE'
const fs = require("node:fs");
const path = require("node:path");

const folder = process.env.LEDGERLENS_REPLAY_OUT;
const problems = [];

if (!fs.existsSync(folder)) {
  problems.push(`the export does not hold the recorded demo: ${folder} does not exist`);
} else {
  const catalogPath = path.join(folder, "index.json");
  if (!fs.existsSync(catalogPath)) {
    problems.push(`the export does not hold the catalog of the scenarios: ${catalogPath} is missing`);
  } else {
    let catalog = null;
    try {
      catalog = JSON.parse(fs.readFileSync(catalogPath, "utf8"));
    } catch (error) {
      problems.push(`the catalog of the scenarios is not a JSON document: ${error.message}`);
    }
    if (catalog !== null) {
      if (!Array.isArray(catalog)) {
        problems.push(`the catalog of the scenarios is not a list: ${catalogPath}`);
      } else if (catalog.length === 0) {
        problems.push(`the catalog of the scenarios is empty: ${catalogPath}`);
      } else {
        for (const card of catalog) {
          const directory = card.bundle_path || String(card.id || "").toLowerCase();
          for (const file of ["manifest.json", "events.jsonl"]) {
            const artifact = path.join(folder, directory, file);
            if (!fs.existsSync(artifact)) {
              problems.push(`the export does not hold the artifact ${artifact}`);
            }
          }
        }
        if (problems.length === 0) {
          console.log(`the export holds the catalog of ${catalog.length} scenario(s) and the bundle of every one of them`);
        }
      }
    }
  }
}

if (problems.length > 0) {
  for (const problem of problems) {
    console.error(`gate_web: ${problem}`);
  }
  process.exit(1);
}
NODE

echo "gate_web: ok"
