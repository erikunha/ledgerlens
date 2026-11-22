# The record of a run of the gate

This file is the proof that the first public release of LedgerLens passed its own gate. It is the
transcription of one real run, not a promise and not a reconstruction: every number below came out of the
run that happened on 2026-11-22, and the commands are the ones that produced it.

**This run happened before the cross check of the digests and the measurement of the budget joined the gate
of the repository.** The gate of that day answered with three steps, and the two checks of this milestone
ran as commands of their own against the same tree, in the sections [4.4](#44-the-check-of-the-digests) and
[4.5](#45-the-measurement-of-the-budget). The gate of the repository today runs both of them, right after
the check of the export, so a run of the gate today prints two steps more than the transcript of the
section 4.

A record of a green run that was never run is a lie, so this file also says plainly what the run did **not**
cover. The Node gate and the end to end suite of the frontend are **not** in this record, and the reason is
in [the section 6](#6-what-this-record-does-not-cover).

## 1. What was measured

| | |
|---|---|
| Measured commit | `bac3e7afe83380e46fb5c76ce3c6f6c8e28bd715` |
| Commit subject | `docs(verification): the baseline of the milestone of the sandbox of the visitor` |
| Branch | `feature/v3` |
| Run at | 2026-11-22T09:18:57+00:00 (the local clock of the machine read 06:18:57, UTC-3) |
| Tracked tree at the moment of the run | clean (`git status --porcelain --untracked-files=no` was empty) |
| Untracked files at the moment of the run | three of the four new files of this milestone: `specs/001-r1-public-replay/quickstart.md`, `scripts/verify_replay_digests.py` and `scripts/measure_replay_budget.py` |

The commit is the commit of the tracked tree. The four files of this milestone were not committed when the
gate ran, so they are not part of the measured commit; three of them were on the disk that the gate read, and
the gate therefore linted and scanned them. This record, the fourth file, was written from the output of the
run, after the run. The orchestrator commits the four.

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
```

The gate of the repository is the script `scripts/gate.sh`, and the run of this record went through it in
this order: the lint, the offline suite and the check of the export. It stops at the first failure.

Two more commands of this milestone ran against the same tree, and they are part of the proof of the
release:

```bash
uv run python scripts/verify_replay_digests.py
uv run python scripts/measure_replay_budget.py
```

## 4. The exact answers of the gates

The output of the run, in the order the gate produced it. The path of the machine was removed from the
lines that carry it, because the rule of the repository keeps the path of the author out of the versioned
files; the same rule that `scripts/baseline.py` applies to the record it writes.

The transcript is the output of the gate of that day, which had three steps. The two steps the gate of the
repository runs today, `== replay digests (offline)` and `== replay budget (offline)`, are not in it, because
they joined the gate after this run. Their answers are in the sections 4.4 and 4.5.

```text
== ruff check
All checks passed!
== pytest -q (offline)
...
2776 passed, 6 skipped, 8 deselected, 419 warnings in 87.47s (0:01:27)
== export check (offline)
the artifacts in <repository>/site/replay match the bundle
gate: ok
```

The exit code of the gate was `0`.

### 4.1 The lint

`ruff check` answered `All checks passed!`. The rule of the repository is a line of 120 characters and the
rule set is `E`, `F`, `I`, `UP` and `B` (`pyproject.toml`).

### 4.2 The suite

`pytest -q`, run offline with `LEDGERLENS_OFFLINE=1` and with the locale of CI (`LANG=C.UTF-8`,
`LC_ALL=C.UTF-8`):

| | |
|---|---|
| Passed | 2776 |
| Skipped | 6 |
| Deselected | 8 |
| Warnings | 419 |
| Duration | 87.47s |

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

### 4.3 The check of the export

`uv run python scripts/export_replay_site.py --check` answered:

```text
the artifacts in <repository>/site/replay match the bundle
```

That check compares what the export would write with what is on the disk and writes nothing, so the
published artifacts of `site/replay/` are the artifacts of the bundle of `data/eval/replay/s01/`.

### 4.4 The check of the digests

`uv run python scripts/verify_replay_digests.py` answered, with the exit code `0`. The gate of the
repository runs this check today, right after the check of the export, under the step `== replay digests
(offline)`:

```text
canonical bundle: <repository>/data/eval/replay/s01
published files: <repository>/site/replay/s01
scenario: S01
files checked:
  ok       events.jsonl  577939e532327f3af1a3897612f622d96edc27a620646437fb02c5fa5318de13
  ok       manifest.json  bbbe1e54fcae712df66a3a6096838ab5b7f8c938e2e47b7ef6681e43cafa84ac
  ok       provenance.json  bbbe1e54fcae712df66a3a6096838ab5b7f8c938e2e47b7ef6681e43cafa84ac
  ok       index.json  S01
the published artifacts match the canonical bundle
```

### 4.5 The measurement of the budget

`uv run python scripts/measure_replay_budget.py` answered, with the exit code `0`. The gate of the
repository runs this measurement today, right after the check of the digests, under the step `== replay
budget (offline)`:

```text
published folder: <repository>/site/replay
budget: 409600 bytes (400 kibibytes) per scenario, from SC-004 of specs/001-r1-public-replay/spec.md

  file                                    bytes      gzipped
  index.json                                872          527
  s01/events.jsonl                        70321         6801
  s01/manifest.json                         770          459
  s01/provenance.json                      1048          542
  TOTAL                                   73011         8329

  scenario                                bytes      gzipped   events
  s01                                     72139         7802       57

  events of the recording: 57
the published artifacts are inside the budget
```

The budget that was applied is the one the repository declares, SC-004 of
[the specification](spec.md): the compressed payload of one scenario stays under 400 kilobytes, which is
409600 bytes when the kilobyte is read as 1024 bytes. The published payload of the scenario `S01` is 7802
compressed bytes, so it sits far inside the budget.

## 5. How to reproduce this record

```bash
git checkout bac3e7afe83380e46fb5c76ce3c6f6c8e28bd715
LEDGERLENS_OFFLINE=1 bash scripts/gate.sh
```

The gate of that commit has the three steps of the transcript of the section 4, so the run above reproduces
that transcript. The two checks of this milestone are not steps of the gate at that commit, so they are
reproduced with the commands of the section 3, against the same tree.

The suite is deterministic offline, so the counts of the section 4.2 are the counts of that commit. The
duration and the order of the warnings are not, and the record does not claim them.

The fingerprint of the whole state, with the versions, the data hashes and the score of the gate, is in
[the baseline of the repository](../../verification/baseline.md). The command that recomputes it is
`uv run python scripts/baseline.py --check`.

## 6. What this record does not cover

- **The two steps the gate of the repository runs today** (`== replay digests (offline)` and `== replay budget
  (offline)`) were **not steps of the gate** at the moment of this run. The checks themselves did run against
  the same tree, as the two commands of the section 3, and their answers are in the sections 4.4 and 4.5.
- **The Node gate of the frontend** (`bash scripts/gate_web.sh`) was **not run** in this record. It needs the
  locked install of Node (`npm ci --engine-strict`) and the tree was shared with other work at the moment of
  this run. The command exists and it is the second job of `.github/workflows/gate.yml`.
- **The end to end suite of Playwright** (`cd apps/web && npm run test:e2e`) was **not run** in this record,
  for the same reason. It is a local command and it is not part of any gate, because the download of the
  browsers is heavy.
- **The accessibility scan** of the six pages of the feature was **not run** in this record.
- No online execution: the real model and the live exchange rate do not enter here.
- The wall clock of a run is not stable, so the 87.47s of the section 4.2 describes that run and not the next
  one.
