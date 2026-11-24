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
# The engine of Node is a hard failure here and not a warning: the frontend declares the major it supports in its
# engines, and a machine with another major has to say so at the install instead of in the middle of the build.
echo "== npm ci (locked dependencies)"
npm ci --engine-strict

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
#
# What the check below reads is the OUTPUT OF THE BUILD that ran just above, not a folder that is on the disk.
# The build writes the export again every time it runs, so moving a file out of out/ before the gate is not a way
# to make the gate fail, and the check never sees a stale export. What the check proves is that the build itself
# wrote one page per scenario of the catalog, that the page it wrote is the page of the scenario and not the
# page of 404, and that the build wrote the page of the architecture, the tour of the six subsystems, with a
# heading and with the six labels of the nodes.
# The check itself lives in a script of its own, so that it can be tested: a check that lives inside this file
# cannot be proved to fail when it has to fail.
#
# The site publishes TWO catalogs, the recordings of the scripted model and the recordings of a real model, and
# each one has its own folder and its own page in the export (ADR-075). The check runs once for each of them: a
# gate that checked only the first one would let a build with no page of the second catalog pass, and a visitor
# of that catalog would land on nothing.
echo "== the build wrote one page per scenario of the catalog, with the content of the scenario"
echo "== the build wrote the page of the architecture, with a heading and the six labels of the nodes"
node "${REPOSITORY_ROOT}/scripts/check_export_pages.mjs" \
  "${REPOSITORY_ROOT}/apps/web/out/replay" replay
node "${REPOSITORY_ROOT}/scripts/check_export_pages.mjs" \
  "${REPOSITORY_ROOT}/apps/web/out/replay-real" replay-real

echo "gate_web: ok"
