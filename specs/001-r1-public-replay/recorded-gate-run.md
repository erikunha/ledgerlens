# The record of a run of the gate

This file is the proof that the public site of LedgerLens passed its own gates, the Python one and the
Node one. It is the transcription of one real run, not a promise and not a reconstruction: every number
below came out of the run that happened on 2026-11-22, and the commands are the ones that produced it.

**This run is the first that covers EVERYTHING.** The earlier run of this file covered the Python gate
alone and said plainly what it did not cover. This one covers the Python gate, the Node gate of the
frontend, the unit tests of the frontend, the whole end to end suite of Playwright, the accessibility
scan that the suite carries, the structural baseline of the pages and the measurement of the paint. The
section [6](#6-what-this-record-does-not-cover) says what is still outside.

A record of a green run that was never run is a lie, so this file also says plainly what the run did
**not** cover.

## 1. What was measured

| | |
|---|---|
| Measured commit | `d3a640d06e7cd78ff9e9c9d48a25494a75ff3eca` |
| Commit subject | `docs(specs): the bookkeeping of the tasks of the milestones 15, 17 and 18` |
| Branch | `feature/v3` |
| Run at | 2026-11-22, on the machine of the author (the local clock read 15:36, UTC-3) |
| Tracked tree at the moment of the run | clean (`git status --porcelain --untracked-files=no` was empty) |

The commit is the commit of the tracked tree. This file, the record of the run, was written from the
output of the run, after the run, and it is the next commit of the branch. Nothing of the tree changed
between the run and this file.

## 2. The environment

The values are the ones `scripts/baseline.py` collects, read the same way, so that this record and the
[baseline of the repository](../../verification/baseline.md) speak about the same machine.

| | |
|---|---|
| Python | 3.12.13 |
| System | Darwin 25.6.0 (arm64) |
| uv | 0.11.21 (5aa65dd7a 2026-06-11 aarch64-apple-darwin) |
| Node | v24.22.1 |

## 3. The exact commands

```bash
cd <repository>
LEDGERLENS_OFFLINE=1 bash scripts/gate.sh
bash scripts/gate_web.sh
cd apps/web && npx playwright test --reporter=line
uv run python scripts/measure_replay_budget.py --paint
```

The gate of the Python side is the script `scripts/gate.sh`, and the gate of the frontend is the script
`scripts/gate_web.sh`. They are TWO gates and they are TWO jobs of `.github/workflows/gate.yml`, because
the Python gate is the gate of a Python repository and it runs in the places where Node is absent. A
gate that fails because a tool is missing is not a gate.

The end to end suite of Playwright is NOT a step of any gate, because the download of the browsers is
heavy. It ran here as a command of its own, against the static export that the build of the Node gate
wrote.

The arm of the paint is opt in and it is the one command of this record that is not a gate. It measures
the paint of the replay page with a browser, and the default arm of the same script, the one the Python
gate calls, stays the payload and never starts a browser.

## 4. The exact answers of the gates

The output of the run, in the order the gates produced it. The path of the machine was removed from the
lines that carry it, because the rule of the repository keeps the path of the author out of the versioned
files; the same rule that `scripts/baseline.py` applies to the record it writes.

```text
== ruff check
All checks passed!
== pytest -q (offline)
2951 passed, 6 skipped, 8 deselected, 419 warnings in 85.52s (0:01:25)
== export check (offline)
the artifacts in <repository>/site/replay match the bundle
== replay digests (offline)
the published artifacts match the canonical bundle
== replay budget (offline)
the published artifacts are inside the budget
gate: ok
```

The exit code of the gate was `0`.

```text
== npm ci (locked dependencies)
== npm run typecheck
== npm run lint
== npm test
 Test Files  60 passed (60)
      Tests  628 passed (628)
== npm run build (static export)
== the build wrote one page per scenario of the catalog, with the content of the scenario
== the build wrote the page of the architecture, with a heading and the six labels of the nodes
gate_web: ok
```

The exit code of the Node gate was `0`.

```text
  39 skipped
  285 passed (55.7s)
```

The exit code of the suite of Playwright was `0`.

### 4.1 The lint of the Python side

`ruff check` answered `All checks passed!`. The rule of the repository is a line of 120 characters and the
rule set is `E`, `F`, `I`, `UP` and `B` (`pyproject.toml`).

### 4.2 The suite of the Python side

`pytest -q`, run offline with `LEDGERLENS_OFFLINE=1` and with the locale of CI (`LANG=C.UTF-8`,
`LC_ALL=C.UTF-8`):

| | |
|---|---|
| Passed | 2951 |
| Skipped | 6 |
| Deselected | 8 |
| Warnings | 419 |
| Duration | 85.52s |

The six skips are the ones the suite declares, and none of them is a failure of the release:

```text
SKIPPED [1] tests/sandbox/test_branch_fork.py:300: the files of the store are only meaningful for the file backed one
SKIPPED [1] tests/sandbox/test_branch_fork.py:327: the files of the store are only meaningful for the file backed one
SKIPPED [1] tests/sandbox/test_branch_fork.py:348: the files of the store are only meaningful for the file backed one
SKIPPED [2] tests/sandbox/test_isolation.py: the layout on the disk belongs to the file backed store, not to the postgres one
SKIPPED [1] tests/sandbox/test_sandbox_api.py: the layout on the disk belongs to the file backed store, not to the postgres one
```

The 419 warnings are the deprecation warnings of the libraries the repository pins (LangChain, LangSmith and
pydantic). The suite declares none of them as an error.

### 4.3 The three checks of the published artifacts

The check of the export answered `the artifacts in <repository>/site/replay match the bundle`, the check
of the digests answered `the published artifacts match the canonical bundle`, and the measurement of the
budget answered `the published artifacts are inside the budget`.

The budget that was applied is the one the repository declares, SC-004 of
[the specification](spec.md): the compressed payload of one scenario stays under 400 kilobytes, which is
409600 bytes when the kilobyte is read as 1024 bytes. The published payload of the scenario `S01` is 8446
compressed bytes, so it sits far inside the budget.

### 4.4 The gate of the frontend

The Node gate ran the locked install, the type check, the lint, the unit tests of the frontend and the
build of the static export, and it answered `gate_web: ok`.

| | |
|---|---|
| Files of the unit tests | 60 |
| Tests of the unit tests | 628 |
| Pages of the export | one per scenario of the catalog, the page of the architecture and the page of 404 |

### 4.5 The suite of the end to end

The suite of Playwright ran against the static export, served as plain files, because that is exactly
what a visitor receives. It runs on four projects, Chromium and WebKit at 390 and 1440 pixels.

| | |
|---|---|
| Passed | 285 |
| Skipped | 39 |
| Duration | 55.7s |

The thirty-nine skips are the cases that a project of the suite does not run: the structural baseline of
the pages is the same on every platform and on every engine, so it is measured in the project of Chromium
alone, and the cases of the other three projects are skipped (ADR-051, decision 4).

**The accessibility scan is inside those 285.** The suite of Playwright carries the scan of the axes of
the pages of the feature, in `tests/e2e/a11y.spec.ts`, and it is a case of the suite like any other.

### 4.6 The measurement of the paint

`uv run python scripts/measure_replay_budget.py --paint` answered, with the exit code `0`:

```text
paint of the replay page: http://127.0.0.1:57803/replay/scenario/S01
export measured: <repository>/apps/web/out
throttling: the processor 4 times slower, 500000 bytes per second down, 125000 bytes per second up, 100 ms of latency

  first contentful paint: 388 ms
  largest contentful paint: 388 ms

  promise of SC-003: the first contentful paint under 1800 ms and the largest contentful paint under 2500 ms
  bound of the suite: the first contentful paint under 5000 ms and the largest contentful paint under 8000 ms
  the measurement is inside the promise of SC-003, and the promise is a number of the deployed site on the connection named above
```

The numbers of the promise are the numbers of SC-003: the first contentful paint under 1800 ms and the
largest contentful paint under 2500 ms, on a throttled mid-range connection. The bound of the suite is
deliberately looser, because a shared machine and a container make the wall clock noisy, and a case that
asserts 1800 ms exactly is a case that goes red for reasons that have nothing to do with the code.

## 5. How to reproduce this record

```bash
git checkout d3a640d06e7cd78ff9e9c9d48a25494a75ff3eca
LEDGERLENS_OFFLINE=1 bash scripts/gate.sh
bash scripts/gate_web.sh
cd apps/web && npx playwright test --reporter=line
uv run python scripts/measure_replay_budget.py --paint
```

The suite of Python is deterministic offline, so the counts of the section 4.2 are the counts of that
commit. The duration and the order of the warnings are not, and the record does not claim them. The
numbers of the paint are the numbers of ONE machine under ONE throttling, and the record does not claim
them for another machine.

The fingerprint of the whole state, with the versions, the data hashes and the score of the gate, is in
[the baseline of the repository](../../verification/baseline.md). The command that recomputes it is
`uv run python scripts/baseline.py --check`.

## 6. What this record does not cover

- **No online execution.** The real model and the live exchange rate do not enter here. The product is
  offline, and the path of the live mode answers `503 LIVE_MODE_OFFLINE` (ADR-043).
- **No deployment.** The site was not published and the numbers of the paint were taken against the
  static export of this repository, served on the loopback, and not against a deployed site.
- **The suite of Playwright is not a step of any gate.** It ran here as a command of its own. The
  continuous integration runs the two gates and not the suite, because the download of the browsers is
  heavy.
- **The wall clock of a run is not stable**, so the 85.52s of the section 4.2 and the 55.7s of the
  section 4.5 describe those runs and not the next ones.
- **The baseline of the repository was not recomputed** by this run. The command that recomputes it is
  `uv run python scripts/baseline.py --check`, and the record of the state that it freezes is the file
  `verification/baseline.md`.
