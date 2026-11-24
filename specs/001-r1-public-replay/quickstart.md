# The recorded demo of LedgerLens in five minutes

This is the quickstart of the first public release of LedgerLens. It is written for a reader who has never
seen the repository: it says how to install it, how to publish the recorded investigation, how to build the
site that shows it and how to check that everything still holds together.

What the release gives you is a site that replays one recorded investigation of a payment complaint. The
recording was made with the scripted model and the recorded exchange rate, so the site answers with no key,
no account and no network at all. The site is a static export: a folder of plain files that any content
delivery network can serve.

The binding documents are [the specification](spec.md), [the task list](tasks.md), [the plan](plan.md),
[the frontend](../../docs/frontend.md),
[ADR-042, the site of the demo serves the published artifacts](../../docs/decisions/ADR-042-the-site-of-the-demo-serves-the-published-artifacts.md)
and [ADR-043, the public site of the design package is complete](../../docs/decisions/ADR-043-the-public-site-of-the-design-package-is-complete.md).

Every command below exists in the repository. The answers of the commands are in
[the section 9](#9-what-the-commands-answer), and the proof that the release passed its own gate is in
[the record of the gate run](recorded-gate-run.md).

## 1. What you need

- Python 3.12, the version the repository pins in `.python-version`, and [uv](https://docs.astral.sh/uv/).
- Node 24 or newer, only for the site. The frontend declares the floor in `apps/web/package.json`.
- No key, no account and no network. Everything of this quickstart runs offline.

The backend (`uv run ledgerlens-demo --port 8010`) is **not** needed here. The backend serves the live mode
and the sandbox of the visitor, and the recorded demo talks to nobody. It is described in
[the quickstart of the live mode](../003-r3-bring-your-own-key/quickstart.md).

## 2. Install

From a clone of the repository:

```bash
uv sync --extra dev --extra app --extra api
```

The `dev` extra carries `pytest` and `ruff`, which the gate of the repository runs, and `jsonschema`, which
the export of the site needs to check the recorded events against the public schema. The `api` extra carries
the same `jsonschema` and the packages of the backend. The `app` extra carries `streamlit`, which only the
demo of the portal needs. For the recorded demo alone, `uv sync --extra dev --extra api` is enough.

## 3. The recording comes with the repository

The canonical recording is versioned with the code, in `data/eval/replay/s01/`:

| File | What it is |
|---|---|
| `manifest.json` | what the recording is: the mode, the scenario, the count of events, the sha256 of every file and the provenance of the capture |
| `events.jsonl` | the recorded execution, one JSON event per line |

The site does not read those files. The site reads the artifacts that the repository publishes in
`site/replay/`, and the export of the site is what turns the recording into them.

## 4. Capture the recording again (only if you have to)

```bash
uv run python scripts/capture_replay.py
```

The capture runs the planted scenario `S01` in a deterministic execution, with the scripted model and the
recorded exchange rate, and writes the bundle in `data/eval/replay/s01/`. It calls no model and it opens no
socket. Another scenario goes to another folder:

```bash
uv run python scripts/capture_replay.py --scenario S03 --out data/eval/replay/s03
```

The capture **refuses to run on a dirty tracked tree**, because the recording names the commit it was made
from and that claim has to be true. Commit or drop the changes and capture again. The refusal names the
files that are in the way.

### The second catalog: the recordings of a real model

The site publishes two catalogs. The one above holds the recordings of the scripted model, and it is a
formula: the same commit gives the same bytes. The second one holds the recordings of a real model, and it is
a run: the same commit gives a different answer every time.

```bash
LEDGERLENS_OFFLINE= LEDGERLENS_MODEL=gpt-4.1 uv run python scripts/capture_live_replay.py --all
```

This capture needs a key in the file of the environment (`OPENAI_API_KEY`), it calls the provider and it asks
the live reference source for the exchange rate. It **refuses to run offline**, because an offline machine runs
the scripted model and the mode `live_agent` would be a lie. It writes the bundles in
`data/eval/replay-real/<scenario>/`, and the verdicts of the claims are computed by the deterministic verifier
of the repository, so that anybody can re-verify a bundle offline (ADR-075).

## 5. Publish the artifacts

```bash
uv run python scripts/export_replay_site.py
```

That writes `site/replay/`: the events, the manifest and the provenance of every scenario, and the catalog
`site/replay/index.json` that lists them. The export is reproducible, so running it twice leaves the same
bytes on the disk, and it never writes outside the folder it was given.

To check what is already on the disk, without writing anything:

```bash
uv run python scripts/export_replay_site.py --check
```

The second catalog is exported with the same command and its own folder, and the mode of the catalog is
named, so that a recording of a real model cannot land in the folder of the sandbox:

```bash
uv run python scripts/export_replay_site.py data/eval/replay-real --out site/replay-real --mode live_agent
```

## 6. Check the digests and the budget

Two checks that the gate of the repository runs, right after the check of the export: they compare the
published artifacts with the canonical bundle, and the browser never sees the canonical bundle, so the
comparison has to happen in Python. Run them on their own when you want the answer without the rest of the gate.

The digests of the published files against the manifest of the canonical bundle:

```bash
uv run python scripts/verify_replay_digests.py
```

It prints one line per file it checked and it refuses, with a readable reason and a non zero exit code, when
a file the manifest declares is missing, when a digest does not match and when a file that neither the
manifest nor the export accounts for is published beside the manifest.

The size of the published artifacts against the budget of the repository:

```bash
uv run python scripts/measure_replay_budget.py
```

It prints a table with the bytes of every published file, the total and the number of events of the
recording, and it fails when the total is above the budget. The budget is the one the specification
declares, SC-004: the compressed payload of one scenario stays under 400 kilobytes.

## 7. Build the site and open it

```bash
cd apps/web && npm ci --engine-strict && npm run build && npm run preview
```

The install is locked, so the versions of the lock file are the versions that run. The build copies the
published artifacts of `site/replay/` into the tree of the frontend and writes the static export in
`apps/web/out/`. The preview serves that folder exactly as it is published.

The export is a folder of plain files, so the preview answers the files by their name:

- <http://localhost:3000/replay.html>, the catalog of the scenarios (the file `out/replay.html`);
- <http://localhost:3000/replay/scenario/S01.html>, the recording of the scenario `S01` (the file
  `out/replay/scenario/S01.html`);
- <http://localhost:3000/replay-real.html>, the catalog of the recordings of a real model (the file
  `out/replay-real.html`);
- <http://localhost:3000/replay-real/scenario/S01.html>, the recording of the scenario `S01` made with a real
  model (the file `out/replay-real/scenario/S01.html`).

The folder `out/replay/` is not the page: it holds the artifacts that the page reads (`index.json` and the
folder of every bundle), which is why the route of a scenario carries the extra segment `scenario`. The
reason is written out in [the frontend](../../docs/frontend.md).

For the work on the site, the development server serves the same pages with the routes of the application
and it reloads on the change:

```bash
cd apps/web && npm run dev
```

- <http://localhost:3000/replay>, the catalog of the scenarios;
- <http://localhost:3000/replay/scenario/S01>, the recording of the scenario `S01`;
- <http://localhost:3000/replay-real>, the catalog of the recordings of a real model;
- <http://localhost:3000/replay-real/scenario/S01>, the recording of the scenario `S01` made with a real model.

## 8. The two gates

```bash
bash scripts/gate.sh      # ruff, pytest offline, the check of the export, the digests, the budget
bash scripts/gate_web.sh  # npm ci, typecheck, lint, vitest, next build
```

The Python gate runs everywhere, including in GitHub Actions (`.github/workflows/gate.yml`). It lints, runs
the suite offline, checks that the published artifacts still match the bundle they claim to show, cross checks
the digests of the published artifacts against the canonical bundle and measures the published payload against
the budget of the specification. It stops at the first failure.

The Node gate is the gate of the frontend. It is a separate script and it is not folded into the Python
gate, because that one runs in places where Node is absent, and a gate that fails because a tool is missing
is not a gate.

The end to end suite of Playwright is a local command and it is not part of the gate, because the download
of the browsers is heavy:

```bash
cd apps/web && npm run test:e2e
```

## 9. What the commands answer

| Command | What it answers | What it answers today |
|---|---|---|
| `uv run python scripts/capture_replay.py` | The recording is fresh and it names the commit it was made from | it refuses on a dirty tracked tree, and it writes the bundle in `data/eval/replay/s01/` |
| `uv run python scripts/export_replay_site.py` | The published artifacts are the ones the export produces | it writes `site/replay/` and prints one line per artifact with its sha256 |
| `uv run python scripts/capture_live_replay.py --all` | The recordings of a real model are fresh and they name the commit they were made from | it refuses to run offline and it writes the bundles in `data/eval/replay-real/` |
| `uv run python scripts/export_replay_site.py data/eval/replay-real --out site/replay-real --mode live_agent` | The second catalog is published | it writes `site/replay-real/` and prints one line per artifact with its sha256 |
| `uv run python scripts/export_replay_site.py --check` | The published artifacts still match the bundle | `the artifacts in site/replay match the bundle` |
| `uv run python scripts/verify_replay_digests.py` | The digests the site publishes are the digests the Python loader computes | `the published artifacts match the canonical bundle`, and the gate of the repository runs it after the check of the export |
| `uv run python scripts/measure_replay_budget.py` | The published payload is inside the budget of the repository | the table of the files, the total and `the published artifacts are inside the budget`, and the gate of the repository runs it after the cross check of the digests |
| `bash scripts/gate.sh` | The Python side of the release holds, the digests and the budget included | `gate: ok`, and the record of the run is in [the record of the gate run](recorded-gate-run.md) |
| `bash scripts/gate_web.sh` | The frontend of the release holds | `gate_web: ok` |

## 10. When a command refuses

A refusal is a sentence with a reason, and every one of them has a fix:

| The refusal | What it means | What to do |
|---|---|---|
| the capture refuses a dirty tracked tree | the recording names the commit it was made from, and the tree is not that commit | commit or drop the changes, and capture again |
| the export check finds a difference | the published artifacts are not the ones the bundle produces | run the export without `--check`, and commit the result |
| the digest check reports a missing file | the site does not publish a file the manifest declares | run the export without `--check` |
| the digest check reports a digest that does not match | the published file is not the file of the recording | run the export without `--check`, and look at what changed in the bundle |
| the digest check reports a file nobody accounts for | something was published beside the manifest that no check covers | take the file away, or add it to the export |
| the budget check reports a payload above the limit | the recording grew past what the specification promises | look at the events of the scenario, and keep the payload inside the budget of SC-004 |

## 11. Where the design lives

- [the specification of the feature](spec.md), with the requirements and the success criteria;
- [the task list](tasks.md), with the work that is done and the work that is not;
- [the frontend](../../docs/frontend.md), with the three rooms of the site and the two gates;
- [the architecture](../../docs/architecture.md), with the decisions of the repository;
- [the decision records](../../docs/decisions/), one per decision that restricts the work ahead;
- [the baseline of the repository](../../verification/baseline.md), the record that freezes the state of the
  code, of the data and of the environment of a run of the gate.
