# The public site of LedgerLens

This folder holds the public site of the demo: a static export of Next.js that plays the recorded
investigations of the design package. The site reads the published artifacts of the repository and
it calls nobody, so it works with no key, no account and no network.

The Python of the domain is not here. The artifacts the site serves are copied into
`public/replay` by the build, out of `site/replay` at the root of the repository.

## What the site holds

- `/replay` is the catalog of the published scenarios. Every card links to the route of its
  scenario.
- `/replay/scenario/<id>` is the route of a scenario, for example `/replay/scenario/S01`. It shows
  the recorded run, the tree of the investigation, the timeline, the provenance, the evidence of the
  answer and the claims of the answer, and it lets the visitor play the recording step by step.
- `/live` is the live mode. It is the only half of the demo that talks to the backend, and it needs
  a key of your own.

The state of the visit lives in the URL with a closed allow list: the identifier of the scenario in
the path, and the two preferences of the view (`tab` and `speed`) in the query string. Nothing else
ever reaches the address of the page.

## The commands

Everything runs from this folder. Node 24 or later is needed, and nothing else: the site has no
server of its own and no database.

```bash
# The install of the locked dependencies. The lock file decides the versions.
npm ci

# The development server on http://localhost:3000, with the published artifacts copied first.
npm run dev

# The build. It copies the published artifacts into the public folder and it builds the site.
npm run build

# The export. It is the same command as the build, because the output of the build IS the export.
npm run export

# The export served as plain files, the way a visitor receives it.
npm run preview
```

The static export lands in `out`. It is a folder of files: `out/index.html` is the page of the site,
`out/replay.html` is the catalog of the scenarios and `out/replay/index.json` is the catalog itself,
`out/replay/s01/` holds the artifacts of the bundle of the scenario `S01`, and
`out/replay/scenario/S01.html` is the page of the scenario, for every scenario of the catalog.
The page of the catalog is the FILE `out/replay.html` and the artifacts are the FOLDER `out/replay/`.

## The tests

```bash
# The type check of the contracts and of the page.
npm run typecheck

# The lint of the rules of the repository in the code of the frontend.
npm run lint

# The unit tests of the interface, with no key and no network.
npm test

# The unit tests in watch mode, while the code is being written.
npm run test:watch
```

The unit tests live in `tests/unit`. They cover the formatters of the money, of the duration and of
the status, the contract of the URL, the store of the preferences, the projections of the recording,
the client of the static artifacts, the state machine of the replay and the components of the
interface.

## The end to end suite

The end to end suite lives in `tests/e2e` and runs with Playwright against the static export served
as plain files, exactly as the files arrive in a browser.

```bash
# The whole suite on the two chromium viewports.
npm run test:e2e -- --project=chromium-390 --project=chromium-1440

# One viewport only.
npm run test:e2e -- --project=chromium-1440
```

**The end to end suite is a local command and is not part of the gate.** The gate of the repository
runs the locked install, the type check, the lint, the unit tests and the static export. The end to
end suite needs a browser that is installed apart, and a build of the export, so it is run by hand
before a release and it is not folded into `scripts/gate_web.sh`.

### The port of the suite

The suite serves the static export on the port **3215** by default. The port comes from the
environment variable **`LEDGERLENS_E2E_PORT`**, and the default of 3215 is a port that belongs to this
project, not to a generic one, so it is unlikely to be the port of another project of the machine.

The port has one source, the module `tests/e2e/site-origin.ts`. The configuration of Playwright uses
it for the base URL of the browser, for the command that serves the export and for the URL it waits
for, and the specs of the network guard read the origin of the same module. The origin the suite
serves and the origin the specs assert are therefore the same by construction.

### Why the suite refuses to reuse a server

The configuration sets `reuseExistingServer` to `false`, always, and that is deliberate. This machine
runs other projects in parallel, and a port that answers may belong to one of them. When the suite
reused the server that was already there, a green run could have tested a site that is not
LedgerLens, and a green run that tested the wrong thing is worse than a red one.

The suite now always starts its own server. When the port is busy, the run fails loudly with a
readable reason that names the port, instead of quietly testing the server of somebody else.

### Two copies at the same time

When two copies of this repository have to run at the same time, give one of them its own port:

```bash
# The first copy, on the default port.
npm run test:e2e -- --project=chromium-1440

# The second copy, on a port of its own.
LEDGERLENS_E2E_PORT=3216 npm run test:e2e -- --project=chromium-1440
```

The variable accepts a port between 1 and 65535. A value that is not a port is refused with a
readable error, because a guess would put the suite on a port nobody expects.

## The gate

The gate of the frontend is a script of the repository and it runs from anywhere:

```bash
bash scripts/gate_web.sh
```

The gate does the locked install, the type check, the lint, the unit tests and the static export,
and then it proves that the export holds the catalog of the scenarios, the bundle of every scenario
and the page of every scenario at `out/replay/scenario/<id>.html`. It stops at the first failure and
it fails with a readable reason.

The Python gate of the repository is a different script, `bash scripts/gate.sh`, and it does not
fold the Node gate into it: a gate that fails because a tool is missing is not a gate.

## The rules of the folder

- The site never invents a number. The amounts come out of the domain as a `Decimal` and the
  interface renders the decimal text exactly as it was written.
- The site never calls the backend of the demo from the recorded replay, and it never writes a
  cookie of the origin of the backend: the cookie of the backend is the identity of the session of
  the visitor, and the recorded demo must never touch it.
- A recorded run is never presented as a live one.
- Every module starts with a docstring that says what it does and why, and every test case carries a
  comment that says what it proves.
