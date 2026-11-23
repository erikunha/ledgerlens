---
type: adr
status: accepted
date: 2026-11-21
---

# ADR-042: The site of the demo serves the artifacts the repository publishes

Status: accepted. Date: 2026-11-21.

## Context

The site of the demo is a static export of Next.js, so the recorded demo is read from the static
folder `apps/web/public/`. That folder held a copy of the published artifacts, and the copy was
stale. It was written on 2026-11-11, before the export of the repository was corrected, and its
shape is not the shape the interface reads today.

The two shapes are different, and the difference was measured, not assumed.

`apps/web/public/replay/index.json` was an object with the keys `note`, `scenarios` and
`schema_version`, and each card carried the key `scenario` and a `data_origin` that was an object.
`site/replay/index.json` is a list of cards, and each card carries the key `id`, a `data_origin`
that is a string, plus `bundle_path`, `bundle_digest`, `data_origin_detail` and
`provenance_sha256`.

`apps/web/public/replay/s01/manifest.json` carried the key `schema_version`.
`site/replay/s01/manifest.json` carries the key `bundle_schema_version`, plus `capture_kind`,
`code_sha`, `model_profile`, `policy_version` and `recorded_at`. The `BundleManifest` of
`ledgerlens/replay/bundle.py` writes exactly that, in its `to_dict`.

The validators of the frontend were not the problem. They describe the artifacts the repository
publishes today: the schema of the manifest in `apps/web/lib/replay/validate.ts` requires
`bundle_schema_version`, the schema of one card of the catalog requires `id` and a `data_origin`
that is a string, and `validateScenarioIndex` requires the catalog to be a list. The stale copy was
the odd one out.

So the site of the demo was about to serve a recording that the repository does not publish, and the
code of the frontend had to be bent to read the stale copy. The loader of the bundle accepted a
manifest that spelled the version of the contract as `schema_version`, and the page of the recorded
demo read the catalog by hand, mapping `scenario` to `id` and joining the fields of an object
`data_origin` into a string.

A second copy of the artifacts, in the tree of the frontend and in the history of the repository,
is a copy that can go stale again, and nothing in the build of the frontend says that it must
match the recording the repository publishes.

## Decision

**There is exactly ONE source of truth for the recorded artifacts: the folder the repository
publishes, `site/replay/`.** The export of the repository keeps writing only there, and it never
writes inside `apps/`.

**The build of the frontend copies `site/replay/` into `apps/web/public/replay/` before it builds,
and the copied folder is not tracked by git.** A fresh clone, `npm ci` and `npm run build` always
serve the artifacts the repository publishes, and there is no second copy in the history that can
go stale.

**The frontend reads the artifacts exactly as they are published, with the validators of the
repository, with no workaround and no mapping by hand.** The loader reads the manifest with
`bundle_schema_version` and refuses anything else, and it refuses a manifest that spells the
version of the contract in any other way. The page of the recorded demo reads the catalog with
`validateScenarioIndex`.

## The interface of the milestone

In `apps/web/scripts/sync-replay-artifacts.mjs`, new:

```
export function syncReplayArtifacts({ source, destination }): { copied: string[]; removed: string[] }
```

The copy reads `site/replay/` from the root of the repository and writes
`apps/web/public/replay/`. It fails loudly when the source does not exist or is empty, because a
build that silently serves no recording is worse than a build that fails. It takes away the files of
the destination that the source does not have, so a scenario that left the set leaves the site too.
It prints what it copied.

The command is `node scripts/sync-replay-artifacts.mjs`, and it accepts `--source` and
`--destination` so that the test of the copy works in a temporary folder and never touches the
artifacts of the repository.

In `apps/web/package.json`, the `prebuild` and the `predev` scripts run the copy. The `build`
script stays `next build` and the `gate` script stays the way it is.

In `apps/web/.gitignore`, the copied folder `public/replay/` is not tracked.

In `scripts/gate_web.sh`, after the build, the gate proves that the recorded demo is in the
export: it checks that `apps/web/out/replay/index.json` exists, that the catalog is a list and
that the bundle of every scenario of the catalog is in the exported site. It fails with a readable
reason when they are not.

In `scripts/export_replay_site.py`, one sentence of the docstring says that the frontend tree is
open now and that the artifacts it reads are copied by the build of the frontend. The usage block
stays as it is.

## What this milestone does not have

- No change to the validators. `apps/web/lib/replay/validate.ts` is not edited, and the contract it
  describes is not relaxed in any way.
- No second copy of the artifacts in the history of the repository. The folder
  `apps/web/public/replay/` is not tracked.
- No mapping of the keys of the artifacts by hand, in the loader or in the page.
- No new route, no new page, no new component and no new dependency of the frontend.
- No change of the Python of the domain: the export keeps writing `site/replay` and nothing else.
- No change of the live mode, of the API and of `docs/v3/`.

## What it costs

The repository gains one script of the frontend, one test of that script, one ADR and one step of
the gate. The tree of the frontend loses the copy of the artifacts it held, which was the only
thing that was wrong with it.

## Alternatives considered

- **(a) Keep the copy in `apps/web/public/replay/` and update it by hand when the recording
  changes.** It is what the repository did, and it is the defect itself: the copy went stale
  without anybody noticing, because nothing compared the two.
- **(b) Make the validators of the frontend accept both shapes.** It would let the frontend read
  the stale copy and the published one. It also makes the contract of the artifacts two contracts,
  and the interface would have to guess which one it is looking at.
- **(c) Make the export of the repository write into `apps/web/public/replay/` as well.** The
  export would write inside a tree that belongs to another tool, and the tree of the frontend would
  carry artifacts that are not the ones the repository publishes.
- **(d) Let the frontend read the artifacts from the root of the repository at run time.** The site
  is a static export served by a content delivery network, so the files have to be inside the
  export.
- **(e) Read the artifacts at build time and bake them into the pages.** The catalog and the
  bundles would be part of the bundle of the pages, and the export would have to be rebuilt for
  every change of the recording, for no gain.

## Consequences

The site of the demo serves the recording the repository publishes, and it says so with the bytes
of the export: the copy is byte for byte the source, and the gate proves that the export holds the
catalog and the bundle of every scenario of it.

The frontend reads the artifacts with the validators of the repository, so the contract of the
artifacts is one contract and the code that reads them has no second spelling of anything. A
recording that does not pass the contract is refused with a reason a reader can act on, instead of
being read with a mapping that hides the difference.

The copy lives in the tree of the frontend but not in the history of the repository, so there is
nothing to keep in sync by hand: the build makes the copy, and a fresh clone always serves the
artifacts of the repository.
