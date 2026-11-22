---
type: adr
status: accepted
date: 2026-11-21
---

# ADR-043: The public site of the design package is complete

Status: accepted. Date: 2026-11-21.

## Context

The milestone that landed with the commit `5564423` gave the repository its first frontend: a
static export of Next.js in `apps/web/`, with the recorded demo on `/replay` and the live mode on
`/live`. The site reads the published artifacts of the recording and it calls nobody, so it works
with no key, no account and no network (ADR-040, ADR-042).

That milestone is a reader, not a site. The plan of the first release,
`specs/001-r1-public-replay/tasks.md`, asks for much more, and almost none of it was built. The
plan names a tree and a timeline selector, a provenance helper, a money formatter, a duration
formatter, a status mapper, a URL contract, a view preference store, a client of the static
artifacts, a shell, a state machine of the replay, a catalog, a route of the scenario, an
overview, an empty state, a failure state, four missing primitives, a README and three end to end
suites. At the moment of the writing of this ADR none of those files existed in the tree: the
milestone that carries them landed after it.

The gap is not only a list of missing files. The milestone that landed reads the artifacts with
the validators of the repository, and that is right (ADR-042). But it also reads the bundle with
a loader that lives inside the folder of the components, it renders the run with a state that
lives inside the reader itself, it renders the mode as the raw string of the manifest, and it
keeps no state in the URL at all. The pieces are there, but they are in the wrong shape for the
plan, and the plan cannot be executed on top of them without bending them.

The rules of the repository are the constraints of this milestone. The money comes out of the
domain as a `Decimal` and the interface never invents a number (FR-026, FR-044). The published
artifacts are the only source of truth for what the site shows (FR-043, FR-045). The URL carries
the scenario identifier and the harmless view preferences and nothing else (FR-037). A recorded
run is never presented as a live one (FR-007).

One thing about the published artifacts has to be written down, because it decides what the
milestone can show. The static export of the repository publishes three files per scenario: the
manifest, the events and the provenance. It does not publish the result of the run, the document
that the bundle contract calls `run_result`, with the claims, their kinds and their texts. What
the published recording of `S01` does carry is the answer, the verdicts and the amounts, but
inside the outputs of the spans: the final answer in the output of the `investigate` chain, the
verdicts in the outputs of the three `verifier` spans, the amounts in the output of the
`calculate` tool, and the identifiers of the evidence in the outputs of the four tools. The
milestone renders what the artifacts carry. It does not publish the result, and it does not
reconstruct the claims of the answer by parsing the text of the answer in the browser.

## Decision

**The milestone closes the public site of the design package.** The site has a catalog of the
scenarios, a route of the scenario, the tree of the investigation, the timeline, the provenance
panel, the evidence of the answer, the state of the playback, the empty state and the failure
state, and the state of the visit is kept in the URL with a closed allow list.

**The milestone is split in four sets with disjoint files**, so that four workers write at the
same time without touching the same file. This ADR is the contract between them: the file names,
the exported names and the exact signatures are written here, so that no two workers guess the
same thing.

### What the milestone delivers

- The catalog of the published scenarios on `/replay`, with the identifier, the name, the
  question, the concepts, the data origin and the status of each card, read with
  `validateScenarioIndex` and with no mapping by hand.
- The route of the scenario on `/replay/scenario/<id>`, for example `/replay/scenario/S01`, with
  the scenario identifier in the path and nothing else in the path.
- The tree of the investigation, built from the spans of the recording, with the nesting of the
  spans, the arrow navigation and the home and the end navigation.
- The timeline, with one row per event of the recording, the observed moment, the error and the
  duration the capture measured.
- The provenance panel, with the digest of the bundle, the mode of the recording, the capture
  kind, the moment of the capture, the model profile, the hash of the code, the hash of the
  snapshot, the policy version and the freshness of the snapshot.
- The evidence of the answer: the answer text, the recommended action, the flag of the human
  review, the verdicts with their method and their note, and the evidence with the identifier,
  the tool that produced it and the sanitized content the tool returned.
- The state of the playback, with the play, the pause, the step forward, the step back, the
  reset and the speed, and the state of the visit kept in the URL.
- The empty state, for a bundle that carries no event, and the failure state, for a bundle that
  the validators or the integrity check refuse.

### What the milestone does not deliver, and why

- **The table of the ledger with a thousand rows, the account switcher and the detail of a row**
  (the plan T064 to T070, the user story 4). They need a new published artifact: the export of
  the repository does not publish the rows that the run read. Adding it is a change of the
  Python export and of the contract of the artifacts, not a change of the interface, and it
  belongs to the milestone that extends the export.
- **The published result, and with it the text and the kind of the claims** (the plan T053, T054
  and the user story 3 in full). The static export publishes the manifest, the events and the
  provenance, and not the `run_result` of the bundle. The evidence panel of this milestone shows
  the verdicts and the evidence that the events carry, and the claim that the recording does not
  carry is rendered as `Not available` with the identifier and the note of the verdict, never as
  a text that the interface invented.
- **The architecture page, the diagram and the engineering drawer** (the plan T071 to T077, the
  user story 5). ADR-041 decided that the interactive diagrams are rendered outside the
  repository, and the drawer needs the map of the modules, which is a document of its own.
- **The mobile journey suite and the accessibility scan with the axe rule** (the plan T078, T079,
  the user story 6). The shell of this milestone is already a single column under 768 pixels and
  honours the preference for reduced motion, but the suite that proves it, and the dependency of
  the scan, come with the milestone of the accessibility.
- **The ledger of the live mode, the API of the browser and the domain of the Python** (the plan
  T026, T065). Nothing in this milestone touches the Python of the domain.

### The money and the duration

The rule of the repository is that the money comes out of the domain as a `Decimal` and that the
interface never invents a number. The published recording carries the amounts as decimal text:
the output of the `calculate` tool carries `{"charge": "566.79", "gap": "17.48", "markup":
"14.08", "markup_pct": "2.50", "rate_move": "3.40", "refund": "549.31"}`. The interface renders
that text. It never multiplies it, never rounds it, never converts it and never assumes a
currency it did not read.

**A percentage is not money.** A percentage never carries the currency of the run: it is a number
that means something else, and the currency of the run would say something false about it. The unit
of every value of the breakdown of the calculation is read out of the NAME of the value, because the
name is where the recording declares the unit (`markup_pct`), and it is the name the reader sees in
the panel of the amounts. The money values keep the currency of the run, which was read from the
`to_currency` of the tool that read the rate.

`apps/web/lib/format/money.ts`, new:

```ts
export const MONEY_UNAVAILABLE = "Not available";

export function formatMoney(
  amount: string | null | undefined,
  currency: string | null | undefined,
): string;
```

The rule of `formatMoney`:

- The `amount` is the decimal text that the server or the artifact carries, for example
  `"566.79"`. It is read as text and never as a number: the formatter never calls `Number`, never
  calls `parseFloat` and never builds a `BigInt` out of it, because every one of those turns a
  decimal into a binary float and a binary float of a financial amount is a different amount.
- The formatter NEVER multiplies and NEVER rounds. The fraction of the amount is kept exactly as
  it was written: it is never padded with zeros, never cut, never rounded to two places. The
  integer part is only grouped with the separator of the locale, which changes no digit and no
  sign. The locale is **fixed** to `en-US`, so the number that the server writes into the export
  and the number that the browser reads are the same number on every machine: a static export is
  written in one locale and read in another, and a separator that depends on the machine is a
  difference between the two sides of the same artifact.
- The currency is written with its explicit ISO 4217 code, in upper case. A currency that is not
  three letters is shown as it was read, never guessed and never mapped to a country.
- When the amount is absent, the formatter returns `MONEY_UNAVAILABLE`.
- When the currency is absent, the formatter returns the grouped amount followed by
  `, currency not available`. It never assumes the currency of the run, and it never reuses the
  currency of another amount.
- An amount that does not match the decimal grammar (`^-?\d+(\.\d+)?$`) is shown as it was read,
  after the currency code. The formatter never repairs it, because a repair is an invention.

`apps/web/lib/format/money.ts` exports the formatter of the percentage too, so that the rule of
the digits of the site is written in one place and the two units can never drift apart:

```ts
export function formatPercentage(percentage: string | null | undefined): string;
```

The rule of `formatPercentage`:

- The percentage is read as text, exactly like an amount: the fraction is kept as it was written, it
  is never rounded and never padded with zeros, and the integer part is only grouped with the
  separator of the locale `en-US`, which is the same rule the money follows.
- The formatter takes NO currency and writes none. The symbol of the percentage goes right after the
  digits, with no space, so that a reader never has to guess the unit of a number that sits among
  money values.
- A percentage that is missing gives `MONEY_UNAVAILABLE`, and so does a percentage that does not
  match the decimal grammar. The money shows a broken amount as it was read, after the code of the
  currency; a percentage has no currency to carry that text, and a unit written on a broken value
  would be an invention, so the interface says that the percentage is not available.

The unit of an amount travels in the projection, not in the formatter: the selectors export the
type `AmountUnit`, and the interface `AmountSummary` carries the field `unit`. The detection of a
percentage is WORD based: a name declares a percentage when one of its alphanumeric words is
`pct`, `percent` or `percentage`, or when the name carries the symbol `%`. The projection never
guesses the unit from the size of the number, because a number of the same size can be money or a
percentage, and the interface never invents a fact the recording does not carry.

`apps/web/lib/format/duration.ts`, new:

```ts
export const DURATION_UNAVAILABLE = "Not available";

/** The ORIGINAL timing: the duration the capture measured, for one event. */
export function formatOriginalDuration(latencyMs: number | null | undefined): string;

/** The PLAYBACK timing: how far the visitor has moved in the recording. */
export function formatPlaybackOffset(offsetMs: number): string;

/** The ORIGINAL timing: the moment the event was recorded, in ISO 8601. */
export function formatObservedMoment(at: string | null | undefined): string;
```

The rule of the three functions:

- The ORIGINAL timing is what the capture measured. `formatOriginalDuration` renders the
  `latency_ms` of the event exactly as the recording carries it, in milliseconds below one
  second and in seconds with one decimal above it, and `formatObservedMoment` renders the `at`
  of the event in ISO 8601. Neither of them reads the clock of the browser, and neither of them
  reads the speed of the playback.
- The PLAYBACK timing is the position of the visitor in the recording. `formatPlaybackOffset`
  renders the distance from the first event of the recording as `mm:ss`.
- The speed of the playback (1, 2 or 4) changes only the interval the browser waits between two
  events. It NEVER changes the displayed original timing, and it NEVER changes the order of the
  events (FR-010, FR-011). The two functions are separate on purpose: a visitor that confuses
  the offset with the measured duration reads a lie, because the offset is how far the visitor
  moved and the duration is what the agent took.
- When the recording carries no duration, the formatter returns `DURATION_UNAVAILABLE`. It never
  substitutes the offset for the missing duration.

`apps/web/lib/format/status.ts`, new:

```ts
export type StatusTone = "neutral" | "success" | "danger" | "warning" | "accent";

export interface StatusLabel {
  readonly label: string;
  readonly tone: StatusTone;
}

export function formatRunStatus(status: string | null | undefined): StatusLabel;
export function formatVerdict(label: string | null | undefined): StatusLabel;
export function formatToolStatus(status: string | null | undefined): StatusLabel;
```

The rule of the three functions: they map the words of the domain to the words of the reader and
to a tone, and nothing else. The run statuses are `idle`, `running`, `completed`, `failed` and
`cancelled`. The verdicts are `supported`, `contradicted` and `not_enough_evidence`, plus
`not_verified` for the case where the verifier itself was unavailable, which is not a verdict.
The status of a tool is the status the capture recorded. A word that the mapping does not know is
shown as it was read, with the neutral tone, never with a tone that was guessed. The tone always
repeats the label, and it never replaces it.

### The state of the replay

The provider of the replay is a state machine. Its states are `idle`, `loading`, `ready`,
`playing`, `paused` and `completed`. Its reducer is pure: it reads no clock, it draws no random
number and it touches nothing outside its arguments, so the same sequence of actions always ends
in the same state, and the state at a position always comes from the reducer of the events of the
repository (`reduceToIndex`), never from a mutation in place (FR-012).

`apps/web/features/replay/ReplayProvider.tsx`, new:

```ts
export type ReplayPhase = "idle" | "loading" | "ready" | "playing" | "paused" | "completed";

export interface ReplayState {
  readonly phase: ReplayPhase;
  readonly scenario: ScenarioIndexEntry | null;
  readonly manifest: ReplayBundleManifest | null;
  readonly events: readonly TraceEvent[];
  readonly position: number;
  readonly error: string | null;
  readonly refusalReasons: readonly string[];
  readonly provenance?: Readonly<Record<string, unknown>> | null;
  readonly integrity?: BundleIntegrity;
}

export type ReplayAction =
  | { readonly type: "load"; readonly scenario: ScenarioIndexEntry }
  | {
      readonly type: "loaded";
      readonly manifest: ReplayBundleManifest;
      readonly events: readonly TraceEvent[];
      readonly provenance?: Readonly<Record<string, unknown>> | null;
      readonly integrity?: BundleIntegrity;
    }
  | { readonly type: "refused"; readonly reason: string; readonly reasons?: readonly string[] }
  | { readonly type: "play" }
  | { readonly type: "pause" }
  | { readonly type: "seek"; readonly position: number }
  | { readonly type: "step"; readonly delta: -1 | 1 }
  | { readonly type: "reset" }
  | { readonly type: "completed" };

export function replayReducer(state: ReplayState, action: ReplayAction): ReplayState;

export interface ReplayProviderProps {
  readonly children: ReactNode;
  readonly scenario: ScenarioIndexEntry | null;
  readonly loader?: (index: ScenarioIndexEntry) => Promise<LoadedReplay | { error: string }>;
}

export function ReplayProvider(props: ReplayProviderProps): ReactElement;

export interface UseReplayResult {
  readonly state: ReplayState;
  readonly dispatch: (action: ReplayAction) => void;
  readonly view: ReplayState;
}

export function useReplay(): UseReplayResult;
```

The rule of the machine:

- `load` moves the machine to `loading` and clears the events, the position and the refusal.
- `loaded` moves it to `ready` with the events of the recording. A bundle with no event is still
  `ready`, and the empty state is what the viewer renders.
- `play` moves `ready` or `paused` to `playing`. `pause` moves `playing` to `paused`. The clock of
  the playback is a hook of its own (`usePlaybackClock`), and it only dispatches `seek` and
  `completed`, so the clock never rewrites the state of the machine.
- `seek` moves the position and stays in the same phase, except that it moves `completed` back to
  `paused`, because the visitor went back into the recording. The position is clamped to the range
  of the events.
- `step` moves the position by one and behaves like `seek`.
- `reset` returns the machine to `ready` with the position at zero, and it never reloads the
  bundle (FR-018).
- `completed` moves `playing` to `completed`.
- **A refused artifact shows the reason and never a partial render.** The action `refused` sets
  the phase back to `idle`, empties the events, empties the manifest, puts the position at zero
  and keeps the reason in `error`. The viewer renders the failure state and nothing else when
  `state.error` is not null: no tree, no timeline, no evidence and no answer. A half drawn run is
  worse than no run, because a reader cannot tell which parts of it are true.
- **The state keeps the provenance of the bundle, because the panel of the provenance needs it.**
  The client of the artifacts reads the file `provenance.json` of the bundle, and the digest of
  the bundle that the panel shows lives in that file and nowhere else: the manifest publishes the
  digest of `events.jsonl` and not the digest of itself. The state therefore carries the
  provenance, the action `loaded` carries it, and the action `refused` empties it with the rest.
  A panel that shows "Not available" for a digest that the artifact publishes says something
  false about the artifact, and the panel of the provenance is the one place where that lie
  matters the most.
- **The provenance and the integrity are OPTIONAL in the state and in the action `loaded`.** The
  two fields were added to the machine after the machine was written down, so a state that was
  built before the field existed stays valid, and a loader that was written before the field
  existed stays valid too. The provenance is null when the bundle publishes no provenance file,
  and a bundle that carries no integrity is a bundle whose integrity is UNKNOWN: never a bundle
  that was checked and never a bundle that was refused. The action `refused` empties the
  provenance and the integrity with the rest of the state, because a stale integrity is a claim
  about a bundle that is not on the screen.

### The URL

The URL carries the scenario identifier and the harmless view preferences, and nothing else.

- The scenario identifier is in the PATH, never in the query string (FR-004). The path of a
  scenario is `/replay/scenario/<id>`, and the identifier is the one the catalog publishes, for
  example `S01`.
- The query string carries exactly two keys, `tab` and `speed`, and they are the whole of the
  allow list. Every other parameter is ignored, whatever it holds.
- The URL NEVER carries anything that came from a visitor: no key, no handle, no answer, no text
  of a run, no identifier of a person, no identifier of an account, no free text of any kind
  (FR-037). The helper reads only the allow list, so a parameter it does not know is dropped
  before it reaches the state of the interface.
- The position of the playback is NOT in the URL. It is the transient state of the session of the
  replay, and a link that carried it would be a link to a moment of a run for no gain.

`apps/web/lib/state/urlState.ts`, new:

```ts
export const REPLAY_TABS = ["execution", "evidence", "decision", "provenance"] as const;
export type ReplayTab = (typeof REPLAY_TABS)[number];

export const PLAYBACK_SPEEDS = [1, 2, 4] as const;
export type PlaybackSpeed = (typeof PLAYBACK_SPEEDS)[number];

export interface ViewPreferences {
  readonly tab: ReplayTab;
  readonly speed: PlaybackSpeed;
}

export const DEFAULT_VIEW_PREFERENCES: ViewPreferences = { tab: "execution", speed: 1 };

export function isReplayTab(value: string): value is ReplayTab;
export function isPlaybackSpeed(value: number): value is PlaybackSpeed;
export function readViewPreferences(search: string): ViewPreferences;

/** The query string that carries the preferences, with the question mark in front, or the empty string. */
export function writeViewPreferences(preferences: ViewPreferences): string;
export function scenarioPath(scenarioId: string): string;
export function parseScenarioId(pathname: string): string | null;
```

The rule of the helpers: `readViewPreferences` reads the query string of a location and returns
the preferences, ignoring every parameter that is not in the allow list, and falling back to the
default of each field that is absent or that is not a legal value. `writeViewPreferences` returns
the query string that carries the preferences, in the order `tab` and then `speed`, and it
returns the empty string when the preferences are the defaults, so that the URL of a visitor who
changed nothing stays clean. `scenarioPath` returns `/replay/scenario/<id>` with the identifier
as the catalog publishes it. `parseScenarioId` returns the identifier of the path, or `null` when
the path is not the path of a scenario.

**The shape of the string that `writeViewPreferences` returns is exact.** When the preferences are
the defaults the function returns the empty string, with no question mark and nothing else. When
they are not the defaults it returns the query string WITH the question mark in front, for example
`"?tab=evidence&speed=2"`, so that the caller concatenates the returned string straight onto the
path of the scenario and writes `/replay/scenario/S01?tab=evidence&speed=2`. A caller that adds a
question mark of its own writes a URL with two of them, and a caller that drops the one the helper
returns writes `/replay/scenario/S01tab=evidence`. The question mark is part of the returned
string because the reader of the query string is the `search` of a location, and a browser always
writes the question mark in front of it: the write and the read are the inverse of one another, and
the caller does not have to know whether it has to add the question mark.

`apps/web/lib/state/viewPreferences.ts`, new:

```ts
export const VIEW_PREFERENCES_STORAGE_KEY = "ledgerlens.view-preferences.v1";

export function loadViewPreferences(storage?: Storage): ViewPreferences;
export function saveViewPreferences(preferences: ViewPreferences, storage?: Storage): void;
export function clearViewPreferences(storage?: Storage): void;
```

The rule of the store: the storage is the `localStorage` of the origin of the site, under the key
`ledgerlens.view-preferences.v1`, and it NEVER a cookie. The cookie of the origin of the backend
is the identity of the session of the visitor, and the recorded demo must never touch it. The
stored payload holds the two fields of the preferences and nothing else; a stored value that does
not parse falls back to the defaults, and a stored field that is not a legal value is ignored.
The URL wins over the store for the fields the URL carries, and the store wins for the fields the
URL does not carry, so a visitor who arrives with a bare link keeps the preferences of the last
visit.

### The provenance

The provenance panel shows the digest of the bundle, the mode of the recording and the freshness
of the snapshot, with the other fields of the manifest when the manifest carries them.

`apps/web/lib/replay/provenance.ts`, new:

```ts
export type SnapshotFreshness = "fresh" | "stale" | "unknown";

export interface ProvenanceSummary {
  readonly bundleDigest: string | null;
  readonly modeLabel: string;
  readonly captureLabel: string;
  readonly recordedAt: string | null;
  readonly snapshotSha256: string | null;
  readonly codeSha: string | null;
  readonly modelProfile: string | null;
  readonly policyVersion: string | null;
  readonly files: Readonly<Record<string, string>>;
  readonly freshness: SnapshotFreshness;
  readonly freshnessReason: string;
  readonly integrity: BundleIntegrity;
  readonly integrityReason: string;
}

export interface ProvenanceInput {
  readonly manifest: ReplayBundleManifest | null;
  readonly provenance?: Readonly<Record<string, unknown>> | null;
  readonly publishedSnapshotSha256?: string | null;
  readonly integrity?: BundleIntegrity;
}

export function modeLabel(mode: TraceMode | null | undefined): string;
export function captureLabel(kind: CaptureKind | null | undefined): string;
export function formatDigest(digest: string | null | undefined): string;
export function snapshotFreshness(
  bundleSha256: string | null | undefined,
  publishedSha256: string | null | undefined,
): SnapshotFreshness;
export function summarizeProvenance(input: ProvenanceInput): ProvenanceSummary;
```

**The type `BundleIntegrity` is NOT declared in this module.** It is declared in
`apps/web/lib/api/replay.ts`, which is the one place that reads the artifacts, and
`apps/web/lib/replay/provenance.ts` IMPORTS it from there with
`import type { BundleIntegrity } from "@/lib/api/replay";`. The module declares and exports
`SnapshotFreshness` and nothing else of the kind, and the table of Set A names exactly that.

The rule of the label of the mode: **the site publishes only `deterministic_sandbox`, and the
label never says live.**

- `modeLabel` returns `Recorded Replay` for `deterministic_sandbox` and for `recorded_replay`.
- `modeLabel` returns `Live agent` for `live_agent`, and the replay route REFUSES a bundle that
  declares `live_agent`, with the reason that this site publishes only the deterministic sandbox.
  The refusal happens in the client of the artifacts, right after the manifest passes the
  contract, so the bundle never reaches the state and the label never reaches a visitor.
  The label therefore never reaches a visitor of the replay.
- The raw mode of the manifest stays visible, because it is what the artifact says. The overview
  of the run shows the badge `mode: deterministic_sandbox`, and the panel of the provenance, which
  is another tab of the reader, shows the label `Recorded Replay`. The reader shows the raw value
  and the label, so the raw value is never hidden and the label is never a lie.
- `captureLabel` returns `Scripted fixture` for `scripted_fixture` and `Real model recorded` for
  `real_model_recorded` (FR-008). A bundle with the kind `scripted_fixture` is never presented as
  a run of a real model.

The rule of the digest: the digest shown is the one the artifact publishes, the `bundle_digest` of
the provenance file, which is the sha256 of the manifest (ADR-014). The browser NEVER invents a
digest and NEVER shows a digest it did not read. `formatDigest` shortens it for the reader, with
the first and the last four characters and an ellipsis in the middle, and it returns `Not
available` when there is no digest.

The rule of the freshness: the freshness is `fresh` only when a comparable hash is published and
matches, `stale` only when a comparable hash is published and differs, and `unknown` when there
is nothing to compare with. The published artifacts of the repository carry the hash of the
dataset file (`dataset_sha256`) and the hash of the snapshot the run read (`snapshot_sha256`),
and those two are not comparable: they are the hash of two different things. So the panel says
`unknown` and says out loud that the freshness could not be checked, and it NEVER shows a bundle
as fresh or as stale on a comparison it did not make. The field `freshnessReason` carries that
sentence.

The rule of the integrity of the bundle: the check of the digests is either made or it is not,
and the panel says which one it was.

- `verifyBundleDigests` returns the state of the check with its verdict: `checked` when the
  digests were really computed and match, and `unknown` when the browser did not offer the Web
  Crypto, which needs a secure context.
- The state travels with the bundle: the loader puts it in `LoadedReplay.integrity`, the state of
  the replay carries it, and the summary of the provenance carries it with the sentence that
  explains it in the field `integrityReason`.
- A bundle whose integrity was NOT checked is never presented as verified, and a bundle whose
  integrity WAS checked is never presented as unverified. The panel says, in words, that the
  digests match the ones the artifact published, or that the digest was not verified because the
  browser did not offer the Web Crypto.
- The absence of the Web Crypto is NOT a refusal: a bundle over plain http is shown, with its
  integrity honestly declared as not checked.

### The accessibility of the replay

The site is built for a reader with a keyboard, a reader with a screen reader and a reader with
low vision, and the target is WCAG 2.2 level AA. These rules are part of the contract of the
milestone, not a polish of the end of it.

- The tree of the investigation is a TREE, not a list of buttons. The container carries
  `role="tree"`, the nodes carry `role="treeitem"` with `aria-level` for the depth and
  `aria-expanded` on the nodes that have children, and the arrow keys walk it, with Home and End
  going to its ends. The accessible name of a node CONTAINS its visible text, because a name
  that hides the words the reader sees is a violation of WCAG 2.5.3. The tree is ONE tab stop:
  the node that holds the focus is the only one in the tab order, and the other nodes are reached
  with the arrow keys, with a roving tabindex.
- The timeline of the recording is ONE navigation group and ONE tab stop of the keyboard. The
  table is not a row of fifty seven stops: the reader moves the position of the recording with the
  keyboard and knows where the recording is, without tabbing through every event of the recording.
  The number of the event is a CELL of the table and not a stop of the keyboard, and the ROW of the
  table that the visitor stands at carries `aria-current="true"`, so a reader knows which event of
  the recording the playback is at. The attribute sits on the row and NOT on the button of the cell
  of the event number, because that button is not a stop of the keyboard either: it carries
  `tabIndex={-1}`, the visitor reaches the cell with the arrow keys of the table, and the Enter key
  on the cell of the event number moves the recording to that event. The table of the design system
  takes the attribute through the optional callback `rowAttributes`, so that the caller of the table
  is the one that knows which row it is, and a table used without the callback gives its rows no
  attribute at all.
- **The outline of the headings of the reader NEVER SKIPS A LEVEL.** That is the invariant, and it
  is the one the reviewer measured with zero jumps on the four tabs. The route carries the `h1` of
  the page and the `h2` of the scenario, and the levels below them are the ones the code really
  uses, per tab:
  - the tab of the execution carries the `h3` of the section and the `h4` of the tree, of the
    timeline and of the calls of the tools;
  - the tab of the evidence carries the `h3` of the section, the `h4` of the panel of the answer and
    the `h5` of the verdicts and of the evidence the run gathered;
  - the tab of the decision carries the `h3` of the section and the `h4` of the claims and of the
    amounts of the answer;
  - the tab of the provenance carries the `h3` of the panel of the provenance and the `h4` of the
    files of the bundle.

  No tab carries a level that no code has, and no tab jumps one: from the `h1` of the route to the
  `h2` of the scenario, to the `h3` of the tab, to the `h4` of the panel and to the `h5` of the
  verdict, one level at a time.
- The controls of the playback are never `disabled`. The control the visitor is standing on never
  goes away under their feet: a button that would do nothing says so with `aria-disabled="true"`
  instead of disappearing from under the focus, because a focus that is dropped on the body of
  the document sends the next Tab back to the top of the page. The reason is a sentence a reader
  can hear, and the control points at it with `aria-describedby`, so a visitor who pressed the
  control and nothing happened gets an answer.
- The preference for reduced motion is honoured by the playback itself, not only by the CSS. A
  visitor who asked for less motion does not get an automatic advance of the recording; the
  visitor can still step and seek by hand, and the control says why the playback did not start.
- The skip link moves the FOCUS to the main, not only the scroll. The main takes `tabIndex={-1}`
  and receives the focus when the hash of the location changes to it.
- The shell has the landmarks: one `banner`, one `main` and one `contentinfo`, and the banner
  carries the accessible name "LedgerLens", so a reader who jumps between the landmarks of the
  page hears which site it is. The footer says what the site is and that it calls nobody.
- The state is never only a colour. A verdict, a status and a tone always carry the words too,
  and the badge of the warning tone paints itself with the dark tone of the warning, so that the
  text of a badge reaches the contrast of the normal text.
- **The box that scrolls the table sideways is NOT a tab stop, and it carries no name.** A reviewer
  called it a concern of WCAG 2.1.1 by the letter, and the choice of this milestone is to keep it
  that way, on purpose. The horizontal scroll IS operable with the keyboard, because the arrow keys
  move the focus between the cells of the table and the box follows the focus, and the contract pins
  the timeline as ONE navigation group and ONE tab stop, so a second tab stop would break the rule
  that the reviewer of the accessibility measured and approved. The table is one tab stop, the
  scroll follows the focus of the cells, and the box deliberately carries no tab stop of its own.

### The failure of the site

A refused bundle is not a broken site, and a broken site is not a refused bundle. The milestone
pins both, and the two never wear the same words.

The refusal of a bundle is the state of the recording: the client of the artifacts refuses a bundle
that does not pass the contract, that declares a live mode, or whose digests do not match, and the
reader renders the failure state of the recording and NOTHING else.

The failure of the SITE is the failure of the page itself, and the site has three boundaries for it:

- `apps/web/app/error.tsx`, the boundary of the segments: it catches every exception of every route
  of the site, and it renders INSIDE the root layout, so the visitor keeps the shell of the site,
  the landmarks and the words of the site. It offers the reset that draws the page again and the
  link to the catalog of the scenarios.
- `apps/web/app/global-error.tsx`, the boundary of the root: it catches the exception thrown by the
  shell or by the root layout, and it draws its own document, with the tags of the document and the
  stylesheet of the site, because the framework replaces the root layout when it shows this
  boundary.
- `apps/web/app/not-found.tsx`, the page of an address that the site does not publish.

The three boundaries share ONE component, `SiteFailure`, which lives in
`apps/web/app/error.tsx`, so that the site has ONE look of failure. The wording of the page of 404
differs from the wording of a crash, because an address that does not exist is not a crash, but the
look is the same.

None of the three ever shows the message of the error, the stack, a path of the server or the name
of an internal module. The message of an error of production carries the digest of the server and
the message of an error of development carries the name of an internal module, and neither of them
belongs to a visitor of a public site. The visitor is told that the page failed, what to do next
and where the way into the demo is, and nothing else.

**The export is static and has no page of 500.** The boundary of the root is therefore a boundary
of the BROWSER: it catches what happens while the browser draws the site, and no server of the
repository ever answers a request with an error, because there is no server of the repository.

### The length of the recording and the budget of the site

The milestone publishes ONE recording, the scenario `S01`, and it carries 57 events. The promise of
the site is made for THAT recording: the reader of a recording opens fast, the playback keeps the
speed its label promises, and the page holds a DOM that a browser draws without trouble.

**The site makes no promise about a recording that is longer than the one it publishes.** A
recording a hundred times longer does NOT keep the speed the label promises, and this ADR says so
here instead of hiding it.

The cost was measured on the static export with synthetic bundles built outside the repository:

| events | first render | median re-render of one tick | total of a full playback | real rate of the playback at the speed of 4 |
| --- | --- | --- | --- | --- |
| 57 (the one the site publishes) | 156 ms | 1.0 ms | 65.7 ms for 56 ticks | the recording ends before 12 s |
| 570 | 209 ms | 4.0 ms | 2390 ms for 569 ticks | 7.42 of 8 events/s (92.7 %) |
| 5700 | 490 ms | 46.9 ms at 14 %, 239.9 ms at 100 % | not measured | 5.25 of 8 events/s (65.6 %) |

The DOM holds 548 elements at the start of the published recording and 707 at its end, and at 5700
events it holds 40046 and 57039.

**Why the cost grows the way it grows.** The interval of the clock is the interval PLUS the cost of
the re-render, and the re-render is quadratic in the position: the reducer of the repository
rebuilds the accumulated state with a copy of the array on every event, and the reader reduces from
zero on every change of the position. The whole playback is therefore cubic in the length of the
recording, and the label of the speed of the playback is a promise about the INTERVAL of the clock,
not about the number of events a second that the machine really reaches.

**The debt.** The reducer copies the accumulated array on every event and the reader reduces from
zero on every position change. That is the debt of the milestone of the live mode and of the
interface of the sandbox, where the recording grows with the run: the shape of the reducer has to
change there, and it has to change before the recording grows.

### The card of the design system

**The panels of the replay carry their OWN card, and not the card of the design system.** The panels
`apps/web/features/agent-trace/TraceTree.tsx`, `apps/web/features/agent-trace/TraceTimeline.tsx`,
`apps/web/features/evidence/AnswerPanel.tsx`, `apps/web/features/evidence/ClaimList.tsx`,
`apps/web/features/shell/ProvenancePanel.tsx`, `apps/web/features/replay/ReplayViewer.tsx` and
`apps/web/features/evidence/EvidenceCard.tsx` write the surface of the card by hand, with the same
class strings that `apps/web/components/ui/Card.tsx` uses, and the card of the evidence is a
surface that the card of the design system does not even offer.

The reason it could not be reused as it is: `CardTitle` is hardcoded to `h3`, and the reader needs
an `h4` and an `h5` inside a section, because the outline of the headings never skips a level.

**The drift is a KNOWN one and not an accident.** The panels will drift from the card of the design
system the moment that card changes, and the fix is the work of the milestone of the live mode: the
card has to take the level of the heading, and then the panels of the replay use it.

### The four sets

The four sets have disjoint files. A file that is named in two sets is a defect of this ADR.

The tables of the sets below list the public surface of every module. Every module that this
milestone wrote ALSO exports a constant `__all__` that carries that same list, so that a reader who
opens a file sees the whole surface of the module at once, and a reader who reads this ADR sees the
same surface without opening a file. The `__all__` is a convention of the modules of this milestone
and it is not a part of the contract of the interface: a module that exports it does not export
anything else because of it, and the tables of this ADR are the contract.

#### Set A, the pure library layer

| File | Status | Exports |
| --- | --- | --- |
| `apps/web/lib/format/money.ts` | new | `MONEY_UNAVAILABLE`, `formatMoney`, `formatPercentage` |
| `apps/web/lib/format/duration.ts` | new | `DURATION_UNAVAILABLE`, `formatOriginalDuration`, `formatPlaybackOffset`, `formatObservedMoment` |
| `apps/web/lib/format/status.ts` | new | `StatusTone`, `StatusLabel`, `formatRunStatus`, `formatVerdict`, `formatToolStatus` |
| `apps/web/lib/replay/selectors.ts` | new | `TraceTreeNode`, `TimelineRow`, `EvidenceSummary`, `VerdictSummary`, `AmountUnit`, `AmountSummary`, `FinalAnswer`, `buildTraceTree`, `buildTimeline`, `collectEvidence`, `collectVerdicts`, `collectAmounts`, `collectCurrency`, `findFinalAnswer` |
| `apps/web/lib/replay/provenance.ts` | new | `SnapshotFreshness`, `ProvenanceSummary`, `ProvenanceInput`, `modeLabel`, `captureLabel`, `formatDigest`, `snapshotFreshness`, `summarizeProvenance` |
| `apps/web/lib/state/urlState.ts` | new | `REPLAY_TABS`, `ReplayTab`, `PLAYBACK_SPEEDS`, `PlaybackSpeed`, `ViewPreferences`, `DEFAULT_VIEW_PREFERENCES`, `isReplayTab`, `isPlaybackSpeed`, `readViewPreferences`, `writeViewPreferences`, `scenarioPath`, `parseScenarioId` |
| `apps/web/lib/state/viewPreferences.ts` | new | `VIEW_PREFERENCES_STORAGE_KEY`, `loadViewPreferences`, `saveViewPreferences`, `clearViewPreferences` |

Set A touches no React file and no Next file, and it imports nothing from `features/`. The
signatures of the selectors, which the components of Set C consume:

```ts
export interface TraceTreeNode {
  readonly spanId: string;
  readonly parentSpanId: string | null;
  readonly name: string | null;
  readonly runType: string | null;
  readonly depth: number;
  readonly startedSeq: number | null;
  readonly endedSeq: number | null;
  readonly children: readonly TraceTreeNode[];
}

export interface TimelineRow {
  readonly seq: number;
  readonly eventType: string;
  readonly label: string;
  readonly at: string;
  readonly latencyMs: number | null;
  readonly error: string | null;
  readonly isTool: boolean;
}

export interface EvidenceSummary {
  readonly evidenceId: string;
  readonly tool: string;
  readonly content: string | null;
  readonly ref: string | null;
  readonly seq: number;
}

export interface VerdictSummary {
  readonly claimId: string;
  readonly label: string | null;
  readonly method: string | null;
  readonly note: string | null;
  readonly evidenceIds: readonly string[];
  readonly seq: number;
}

/**
 * The unit of a value of the breakdown of the calculation.
 *
 * A percentage is not money: it carries no currency, and the panel writes it with the symbol of
 * the percentage.
 */
export type AmountUnit = "money" | "percentage";

export interface AmountSummary {
  readonly name: string;
  readonly amount: string;
  readonly currency: string | null;
  readonly unit: AmountUnit;
  readonly seq: number;
}

export interface FinalAnswer {
  readonly answer: string;
  readonly recommendedAction: string | null;
  readonly requiresHumanReview: boolean | null;
  readonly summary: string | null;
  readonly seq: number;
}

export function buildTraceTree(spans: readonly SpanState[]): TraceTreeNode[];
export function buildTimeline(events: readonly TraceEvent[]): TimelineRow[];
export function collectEvidence(toolCalls: readonly ToolCallState[]): EvidenceSummary[];
export function collectVerdicts(spans: readonly SpanState[]): VerdictSummary[];
export function collectAmounts(toolCalls: readonly ToolCallState[]): AmountSummary[];
export function collectCurrency(toolCalls: readonly ToolCallState[]): string | null;
export function findFinalAnswer(spans: readonly SpanState[]): FinalAnswer | null;
```

The rules of the selectors, which are projections and never decisions:

- `buildTraceTree` nests the spans by the `parent_span_id` of the events, and a span whose parent
  is not in the recording is a root. The depth of a node is its distance from a root.
- `buildTimeline` has one row per event of the recording, in the order of the recording, including
  the events the interface does not know, so that the count of the rows is the count of the bundle
  (SC-013).
- `collectEvidence` projects the evidence from the tool calls, because the published recording of
  `S01` carries no `evidence.added` event: the identifiers of the evidence and their content are
  in the outputs of the tools. An evidence identifier that no tool reported is not shown.
- `collectVerdicts` projects the verdicts from the spans whose `run_type` is `verifier`, and the
  claim identifier, the label, the method, the note and the cited identifiers are read from the
  output of the span. The verdict of a claim that the recording does not carry is rendered as
  unresolved, never as supported.
- `collectAmounts` projects the amounts from the output of the `calculate` tool, and it reads the
  decimal text exactly as it was written. It reads the unit of every value out of the NAME of the
  value: a name declares a percentage when one of its alphanumeric words is `pct`, `percent` or
  `percentage`, or when the name carries the symbol `%`, and every other name is money. The
  currency of an amount is left empty on purpose, because the currency of the run is another fact,
  read by `collectCurrency`, and the projection never attaches a currency to an amount it did not
  read with it.
- `collectCurrency` reads the currency of the run from the `to_currency` of the tool that read the
  rate. The tool `get_reference_fx` is believed first, and the fallback accepts any other tool whose
  name carries `fx`, `rate` or `exchange`, because the recording of a scenario may name the tool
  differently. The function returns `null` when the recording read no currency. The amount and the
  currency are two separate facts and the panel shows them as two separate facts.
- `findFinalAnswer` reads the output of the last `investigate` span: the answer, the recommended
  action, the flag of the human review and the summary. It returns `null` when the recording
  carries no such span.

#### Set B, the shell and the state

| File | Status | Exports |
| --- | --- | --- |
| `apps/web/components/ui/Tabs.tsx` | new | `TabItem`, `TabsProps`, `Tabs` |
| `apps/web/components/ui/Dialog.tsx` | new | `DialogProps`, `Dialog` |
| `apps/web/components/ui/Sheet.tsx` | new | `SheetProps`, `Sheet` |
| `apps/web/components/ui/Skeleton.tsx` | new | `SkeletonProps`, `Skeleton` |
| `apps/web/features/shell/AppShell.tsx` | new | `AppShellProps`, `AppShell` |
| `apps/web/features/shell/Header.tsx` | new | `HeaderProps`, `Header` |
| `apps/web/features/shell/ModeIndicator.tsx` | new | `ModeIndicatorProps`, `ModeIndicator` |
| `apps/web/features/shell/SkipLink.tsx` | new | `SkipLinkProps`, `SkipLink` |
| `apps/web/features/shell/ProvenancePanel.tsx` | new | `ProvenancePanelProps`, `ProvenancePanel` |
| `apps/web/features/replay/ReplayProvider.tsx` | new | `ReplayPhase`, `ReplayState`, `ReplayAction`, `replayReducer`, `ReplayProviderProps`, `ReplayProvider`, `UseReplayResult`, `useReplay` |
| `apps/web/lib/api/replay.ts` | new | `ARTIFACT_ROOT`, `BundleIntegrity`, `LoadedReplay`, `Sha256Hex`, `loadScenarioCatalog`, `loadReplay`, `verifyBundleDigests` |
| `apps/web/lib/api/provider.tsx` | new | `ScenarioCatalogLoader`, `ScenarioCatalogState`, `ScenarioCatalogProviderProps`, `ScenarioCatalogProvider`, `useScenarioCatalog` |
| `apps/web/features/replay/loadReplay.ts` | deleted | the loader moves to `apps/web/lib/api/replay.ts` |
| `apps/web/app/layout.tsx` | changed | the layout renders the `AppShell` |

The signatures of Set B:

```ts
// apps/web/components/ui/Tabs.tsx
export interface TabItem {
  readonly value: string;
  readonly label: string;
  readonly content: ReactNode;
}
export interface TabsProps {
  readonly items: readonly TabItem[];
  readonly value: string;
  readonly onValueChange: (value: string) => void;
  readonly label: string;
}
export function Tabs(props: TabsProps): ReactElement;

// apps/web/components/ui/Dialog.tsx
export interface DialogProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly title: string;
  readonly children: ReactNode;
  readonly trigger?: ReactNode;
}
export function Dialog(props: DialogProps): ReactElement;

// apps/web/components/ui/Sheet.tsx
export interface SheetProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly title: string;
  readonly children: ReactNode;
  readonly side?: "top" | "bottom" | "left" | "right";
}
export function Sheet(props: SheetProps): ReactElement;

// apps/web/components/ui/Skeleton.tsx
export interface SkeletonProps {
  readonly className?: string;
  readonly label?: string;
}
export function Skeleton(props: SkeletonProps): ReactElement;

// apps/web/features/shell/AppShell.tsx
export interface AppShellProps {
  readonly children: ReactNode;
  readonly mode?: TraceMode | null;
}
export function AppShell(props: AppShellProps): ReactElement;

// apps/web/features/shell/Header.tsx
export interface HeaderProps {
  readonly mode?: TraceMode | null;
}
export function Header(props: HeaderProps): ReactElement;

// apps/web/features/shell/ModeIndicator.tsx
export interface ModeIndicatorProps {
  readonly mode: TraceMode | null | undefined;
}
export function ModeIndicator(props: ModeIndicatorProps): ReactElement;

// apps/web/features/shell/SkipLink.tsx
export interface SkipLinkProps {
  readonly target?: string;
}
export function SkipLink(props: SkipLinkProps): ReactElement;

// apps/web/features/shell/ProvenancePanel.tsx
export interface ProvenancePanelProps {
  readonly summary: ProvenanceSummary;
}
export function ProvenancePanel(props: ProvenancePanelProps): ReactElement;

// apps/web/lib/api/replay.ts
export const ARTIFACT_ROOT = "/replay";

export interface LoadedReplay {
  readonly manifest: ReplayBundleManifest;
  readonly events: readonly TraceEvent[];
  readonly provenance: Readonly<Record<string, unknown>> | null;
  readonly integrity?: BundleIntegrity;
}

export type Sha256Hex = (bytes: ArrayBuffer) => Promise<string>;

export async function loadScenarioCatalog(
  fetchImpl?: typeof fetch,
): Promise<ScenarioIndexEntry[] | { error: string }>;

export async function loadReplay(
  index: ScenarioIndexEntry,
  fetchImpl?: typeof fetch,
): Promise<LoadedReplay | { error: string }>;

export async function verifyBundleDigests(input: {
  readonly manifest: ReplayBundleManifest;
  readonly eventsBytes: ArrayBuffer;
  readonly provenance?: Readonly<Record<string, unknown>> | null;
  readonly sha256?: Sha256Hex;
}): Promise<
  | { ok: true; readonly integrity: BundleIntegrity }
  | { ok: false; readonly reasons: readonly string[] }
>;

// apps/web/lib/api/provider.tsx
export type ScenarioCatalogLoader = () => Promise<ScenarioIndexEntry[] | { error: string }>;

export interface ScenarioCatalogState {
  readonly status: "idle" | "loading" | "ready" | "refused";
  readonly scenarios: readonly ScenarioIndexEntry[];
  readonly error: string | null;
  readonly reload: () => void;
}

export interface ScenarioCatalogProviderProps {
  readonly children: ReactNode;
  readonly loader?: ScenarioCatalogLoader;
}
export function ScenarioCatalogProvider(props: ScenarioCatalogProviderProps): ReactElement;
export function useScenarioCatalog(): ScenarioCatalogState;
```

The rules of Set B:

- The four primitives wrap the packages that the frontend already depends on: the tabs and the
  dialog are `@radix-ui/react-tabs` and `@radix-ui/react-dialog`, and the sheet is the dialog with
  a side. The milestone adds NO dependency: no package was added, no package was removed and no
  version of a package moved. The lock file of the repository moves by EXACTLY ONE line, the
  `engines.node` of the root package, which went from `>=20.0.0` to `>=24.0.0`, so that the
  manifest, the lock file, the README of the frontend and the workflow of the repository state one
  floor of Node and not three.
- The `AppShell` owns the landmarks, the header, the skip link and the column of the content. The
  layout renders it, and the layout keeps the language `en` and the metadata it has today.
- `lib/api/replay.ts` is the ONE place that reads the static artifacts: the catalog, the bundle
  and the provenance file of a scenario. The loader that used to live in
  `apps/web/features/replay/loadReplay.ts` moves here, with the same behaviour and the same
  refusal messages, and the file in the features folder is deleted. The folder of the components
  does not read the network.
- The catalog page reads the catalog THROUGH the provider of `lib/api/provider.tsx`, and the
  provider reads it through `loadScenarioCatalog`. A page that fetched the catalog on its own
  would be a second place that touches the network, and a provider that no page mounts is dead
  code: the catalog is fetched once, never refetched on focus, never retried, and a missing
  artifact is a refusal.
- The loader NEVER throws at the caller: it returns the bundle it read, or the reason it refused
  it.
- The integrity check of the digests uses the Web Crypto of the browser. A mismatch is a refusal
  with the expected digest and the observed digest (FR-038), and no partial result is rendered.
  The ABSENCE of the Web Crypto is not a refusal: the check is then `unknown`, and the panel says
  that the integrity was not checked. The function of the digest is injectable, so the unit test
  never needs a browser.
- **The three primitives `Dialog`, `Sheet` and `Skeleton` land UNUSED.** Nothing in the site mounts
  them today: they exist because the contract of this milestone names them, and they are exercised
  only by their own test, `apps/web/tests/unit/ui-primitives.test.tsx`. They land unused on purpose,
  so that nobody reads them as dead code by accident, and the milestone of the live mode is the one
  that mounts them.
- The provider of the catalog is the static friendly client: it fetches once, it never refetches
  on focus, it never retries, and a missing artifact is a refusal, not a retry.
- **The indicator of the mode is wired in the milestone of the live mode, and not in this one.**
  The layout of the root renders the shell with no mode (`<AppShell>{children}</AppShell>`), so the
  header passes `null` to the indicator and the indicator renders an empty fragment. That is not
  dead code by accident: the label of the mode is already visible in the tab of the provenance,
  which is where the contract of this milestone demands it, and the milestone of the live mode is
  the one that mounts the shell with a mode. A recorded run is never presented as a live one, and
  the label that says so is read in the provenance panel.

#### Set C, the pages and the components of the replay

| File | Status | Exports |
| --- | --- | --- |
| `apps/web/app/(public)/replay/page.tsx` | changed | the catalog of the scenarios |
| `apps/web/app/(public)/replay/scenario/[scenario]/page.tsx` | new | the route of the scenario |
| `apps/web/features/replay/ReplayViewer.tsx` | changed | `ReplayViewerProps`, `ReplayViewer` |
| `apps/web/features/replay/RunOverview.tsx` | new | `RunOverviewProps`, `RunOverview` |
| `apps/web/features/replay/ReplayEmptyState.tsx` | new | `ReplayEmptyStateProps`, `ReplayEmptyState` |
| `apps/web/features/replay/ReplayErrorState.tsx` | new | `ReplayErrorStateProps`, `ReplayErrorState` |
| `apps/web/features/replay/ReplayControls.tsx` | new | `ReplayControlsProps`, `ReplayControls` |
| `apps/web/features/replay/usePlaybackClock.ts` | new | `PlaybackClockOptions`, `DEFAULT_PLAYBACK_INTERVAL_MS`, `REDUCED_MOTION_QUERY`, `usePrefersReducedMotion`, `usePlaybackClock` |
| `apps/web/features/agent-trace/TraceTree.tsx` | new | `TraceTreeProps`, `TraceTree` |
| `apps/web/features/agent-trace/TraceTimeline.tsx` | new | `TraceTimelineProps`, `TraceTimeline` |
| `apps/web/features/evidence/AnswerPanel.tsx` | new | `AnswerPanelProps`, `AnswerPanel` |
| `apps/web/features/evidence/ClaimList.tsx` | new | `ClaimListProps`, `ClaimList` |
| `apps/web/features/evidence/EvidenceCard.tsx` | new | `EvidenceCardProps`, `EvidenceCard` |

The signatures of Set C:

```ts
// apps/web/features/replay/ReplayViewer.tsx
export interface ReplayViewerProps {
  readonly scenario: ScenarioIndexEntry;
}
export function ReplayViewer(props: ReplayViewerProps): ReactElement;

// apps/web/features/replay/RunOverview.tsx
export interface RunOverviewProps {
  readonly scenario: ScenarioIndexEntry;
  readonly manifest: ReplayBundleManifest;
}
export function RunOverview(props: RunOverviewProps): ReactElement;

// apps/web/features/replay/ReplayEmptyState.tsx
export interface ReplayEmptyStateProps {
  readonly scenarioId: string;
}
export function ReplayEmptyState(props: ReplayEmptyStateProps): ReactElement;

// apps/web/features/replay/ReplayErrorState.tsx
export interface ReplayErrorStateProps {
  readonly reason: string;
  readonly reasons?: readonly string[];
}
export function ReplayErrorState(props: ReplayErrorStateProps): ReactElement;

// apps/web/features/replay/ReplayControls.tsx
export interface ReplayControlsProps {
  readonly phase: ReplayPhase;
  readonly position: number;
  readonly total: number;
  readonly speed: PlaybackSpeed;
  readonly onPlay: () => void;
  readonly onPause: () => void;
  readonly onStep: (delta: -1 | 1) => void;
  readonly onSeek: (position: number) => void;
  readonly onReset: () => void;
  readonly onSpeedChange: (speed: PlaybackSpeed) => void;
}
export function ReplayControls(props: ReplayControlsProps): ReactElement;

// apps/web/features/replay/usePlaybackClock.ts
export interface PlaybackClockOptions {
  readonly phase: ReplayPhase;
  readonly position: number;
  readonly total: number;
  readonly speed: PlaybackSpeed;
  readonly intervalMs?: number;
  readonly onTick: (position: number) => void;
  readonly onComplete: () => void;
}

/** The interval the browser waits between two events at the speed of one, in milliseconds. */
export const DEFAULT_PLAYBACK_INTERVAL_MS = 500;

/** The media query that carries the preference of the visitor for less motion. */
export const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

/** The preference of the visitor for less motion, kept up to date. */
export function usePrefersReducedMotion(): boolean;

export function usePlaybackClock(options: PlaybackClockOptions): void;

// apps/web/features/agent-trace/TraceTree.tsx
export interface TraceTreeProps {
  readonly nodes: readonly TraceTreeNode[];
  readonly selectedSpanId: string | null;
  readonly onSelect: (spanId: string) => void;
}
export function TraceTree(props: TraceTreeProps): ReactElement;

// apps/web/features/agent-trace/TraceTimeline.tsx
export interface TraceTimelineProps {
  readonly rows: readonly TimelineRow[];
  readonly position: number;
  readonly onSeek: (position: number) => void;
}
export function TraceTimeline(props: TraceTimelineProps): ReactElement;

// apps/web/features/evidence/AnswerPanel.tsx
export interface AnswerPanelProps {
  readonly answer: FinalAnswer | null;
  readonly verdicts: readonly VerdictSummary[];
  readonly evidence: readonly EvidenceSummary[];
}
export function AnswerPanel(props: AnswerPanelProps): ReactElement;

// apps/web/features/evidence/ClaimList.tsx
export interface ClaimListProps {
  readonly verdicts: readonly VerdictSummary[];
}
export function ClaimList(props: ClaimListProps): ReactElement;

// apps/web/features/evidence/EvidenceCard.tsx
export interface EvidenceCardProps {
  readonly evidence: EvidenceSummary;
}
export function EvidenceCard(props: EvidenceCardProps): ReactElement;
```

The rules of Set C:

- The route of the scenario is a SERVER component, because a static export of a dynamic route
  needs the list of the parameters at build time. The page exports `generateStaticParams`, which
  reads `apps/web/public/replay/index.json` from the disk at build time (the folder the build
  copies, ADR-042), and `dynamicParams = false`, so
  the export holds one HTML file per published scenario and an unknown scenario is the page of
  `404`, never a guess at run time. The page reads the card of the scenario from the same file
  and hands it to the client component.
- The route is `/replay/scenario/<id>` and NOT `/replay/<id>`. The prefix `/replay` is BOTH the
  page of the catalog of the export (`out/replay.html`) and the folder of the published artifacts
  (`out/replay/`), so a bundle inside that prefix could not be a page of the export and a folder at
  the same time: the route of a bundle would have to answer at a path that the export already holds
  in two shapes, and a static file server would have to choose. The extra segment `scenario`
  removes the ambiguity. The path `/replay/s01` is a directory of the export and nothing else
  (`out/replay/s01/`, with no `out/replay/s01.html`), and the page of the scenario is written at
  `out/replay/scenario/S01.html`.
- The catalog page `/replay` keeps reading the catalog with `validateScenarioIndex`, keeps the
  refusal of a broken catalog with its reasons, and links to the route of the scenario instead of
  embedding the reader.
- The four sections of the reader are FOUR REAL TABS, rendered by the primitive
  `apps/web/components/ui/Tabs.tsx`, which wraps `@radix-ui/react-tabs`. The tab list is the
  accessible name "The sections of the replay", the tabs are "Execution", "Evidence", "Decision"
  and "Provenance", and the content of the CHOSEN tab is the only one on the page. A row of
  controls that looks like a tab list and does not behave like one is worse than no row at all:
  the arrow keys have to move the selection, the chosen tab has to own the panel, and the panel
  has to point at its tab. The chosen tab is the value of `tab` in the query string of the URL and
  the value kept in the local storage of the origin, so the tab a visitor opens is the tab they
  left.
- The step of the recording is announced. The summary of the step lives in a POLITE live region
  (`role="status"`, `aria-live="polite"`, `aria-atomic="true"`) that carries only the step, for
  instance "Event 12 of 57", and never the status of the run and never every token of the
  recording. The focus moves to that region ONCE, when the playback starts, and never again
  during the playback. A region that announces is never assertive.
- `ReplayViewer` keeps the accessible names it has today, because they are the contract of the
  end to end suite: the region `The recorded run`, the table `The calls of the tools of the
  recorded run`, the control `Position of the recording` and the badge `mode:
  deterministic_sandbox`. It stops loading by itself: it reads the state of the provider and
  renders the panels.
- The viewer renders the failure state and NOTHING else when the provider carries a refusal, and
  the empty state and nothing else when the bundle carries no event.
- The clock of the playback lives in `usePlaybackClock` and only dispatches. The speed changes the
  interval the clock waits, never the original timing that the panels show.
- **The interval the clock waits never falls below 16 milliseconds.** The clock waits the interval
  of the caller divided by the speed, rounded to the nearest millisecond, and the result is never
  shorter than 16 milliseconds: the delay is the maximum of 16 and the rounded quotient. The floor
  is a private constant of the module and not an export, and it exists because a speed of four over
  an interval of a few milliseconds would ask the browser for more frames than it can draw, and the
  reader would show a recording nobody can follow.
- The panel of the amounts writes a percentage with `formatPercentage` and a money value with
  `formatMoney`, and the money takes the currency that the recording read with the amount and the
  currency of the run otherwise. A percentage never takes a currency, because it is not money.

#### Set D, the tests, the documentation and the gate

| File | Status | Content |
| --- | --- | --- |
| `apps/web/tests/e2e/catalog.spec.ts` | new | the catalog of the published scenarios and the link to the route |
| `apps/web/tests/e2e/replay.spec.ts` | new | the route of the scenario, the tree, the timeline, the provenance, the evidence and the URL |
| `apps/web/tests/e2e/network.spec.ts` | new | the guard of the network |
| `apps/web/tests/e2e/recorded-demo.spec.ts` | changed | the cases it holds stay, the new assertions are added |
| `apps/web/tests/unit/features/replay-viewer.test.tsx` | changed | the reader of the milestone |
| `apps/web/tests/unit/features/replay-page.test.tsx` | changed | the catalog page of the milestone |
| `apps/web/tests/unit/features/replay-scenario-page.test.tsx` | new | the route of the scenario |
| `apps/web/tests/unit/format-money.test.ts` | new | the money formatter and the formatter of the percentage |
| `apps/web/tests/unit/format-duration.test.ts` | new | the duration formatter |
| `apps/web/tests/unit/format-status.test.ts` | new | the status mapper |
| `apps/web/tests/unit/replay-selectors.test.ts` | new | the selectors |
| `apps/web/tests/unit/replay-provenance.test.ts` | new | the provenance helper |
| `apps/web/tests/unit/url-state.test.ts` | new | the URL contract |
| `apps/web/tests/unit/view-preferences.test.ts` | new | the store of the preferences |
| `apps/web/tests/unit/replay-provider.test.tsx` | new | the state machine |
| `apps/web/tests/unit/api-replay.test.ts` | new | the client of the static artifacts |
| `apps/web/tests/unit/ui-primitives.test.tsx` | new | the four new primitives |
| `apps/web/README.md` | new | the install, the build, the export, the test and the gate of the frontend |
| `scripts/gate_web.sh` | changed | the check of the export of the scenarios |

### The seam between the sets

The files that the milestone `5564423` landed and that this milestone changes are named here,
with exactly what changes, because they are the seam and two workers must never touch the same
one.

- `apps/web/app/(public)/replay/page.tsx`: the catalog keeps the validator, the refusal and the
  cards, and it stops embedding the reader. It gains a link to `/replay/scenario/<id>`.
- `apps/web/app/(public)/replay/scenario/[scenario]/page.tsx`: new, the route of the scenario.
- `apps/web/features/replay/ReplayViewer.tsx`: it stops fetching by itself and it reads the
  provider. It keeps the accessible names it has today and it gains the panels.
- `apps/web/features/replay/loadReplay.ts`: deleted. Its behaviour moves to
  `apps/web/lib/api/replay.ts`, with the same messages.
- `apps/web/app/layout.tsx`: it renders the `AppShell`. The language, the metadata and the
  stylesheet stay as they are.
- `apps/web/tests/unit/features/replay-viewer.test.tsx`: the import of the loader moves from
  `@/features/replay/loadReplay` to `@/lib/api/replay`, and the cases assert the panels of the
  milestone.
- `apps/web/tests/unit/features/replay-page.test.tsx`: the cases assert the catalog and the link
  to the route.
- `apps/web/tests/e2e/recorded-demo.spec.ts`: the three cases it holds stay, the names they use
  stay valid because the viewer keeps them, and the file gains the assertions of the new
  journey.
- `scripts/gate_web.sh`: after the build, the gate proves that the export holds one HTML file per
  scenario of the catalog, at `out/replay/scenario/<id>.html`, and it fails with a readable reason
  when one is missing.

The files that changed OUTSIDE the seam are these, and each one changed for the reason the table
gives:

| File | Status | What changed and why |
| --- | --- | --- |
| `apps/web/package.json` | changed | the floor of the Node: the `engines.node` of the manifest went from `>=20.0.0` to `>=24.0.0`, so that the manifest, the lock file, the README of the frontend and the workflow of the repository state one floor and not three |
| `apps/web/package-lock.json` | changed | the same floor, in the lock file: EXACTLY ONE line moved, the `engines.node` of the root package. No dependency was added, no dependency was removed and no version of a dependency moved |
| `apps/web/playwright.config.ts` | changed | it reads the port and the origin of the suite from `apps/web/tests/e2e/site-origin.ts`, so that the origin the suite serves and the origin the specs of the network guard assert are the same by construction, and it never reuses a server that is already answering |
| `apps/web/components/ui/Badge.tsx` | changed | the component already existed: only its docstring and its `__all__` changed, so that the module carries the convention of the surface of the repository |
| `apps/web/components/ui/Table.tsx` | changed | the table of the design system gained the optional callback `rowAttributes`, so that the caller of the table says what the row carries: the row of the place the visitor stands at carries `aria-current`, and a table used without the callback gives its rows no attribute at all |
| `.github/workflows/gate.yml` | changed | the checkout is pinned by the SHA of the action, the Node is pinned exactly at `24.22.3`, and the duplicated install of the frontend was removed, because the install belongs to `scripts/gate_web.sh` |
| `apps/web/tests/e2e/site-origin.ts` | new | the single source of the origin of the suite: the port, the base URL of the browser, the command of the server and the URL the suite waits for all read it, and the specs of the network guard read the same origin |
| `apps/web/tests/unit/export-check.test.ts` | new | the test of the check of the export, which proves that the check fails when it has to fail |
| `apps/web/tests/unit/use-playback-clock.test.ts` | new | the test of the clock of the playback |
| `apps/web/tests/unit/features/error-boundary.test.tsx` | new | the test of the three boundaries of the site |
| `apps/web/tests/unit/features/agent-trace.test.tsx` | new | the test of the tree and of the timeline: the mark of the place the visitor stands at is not only a colour, and the indent of the tree is a sum of the steps of the scale of the design system |
| `apps/web/tests/unit/features/replay-accessibility.test.tsx` | new | the regression guard of the accessibility of the reader: the tree is a tree, the timeline is one tab stop, the outline of the headings never skips a level, the controls are never disabled, the step is announced politely, the reduced motion stops the clock, the skip link moves the focus and the shell carries its landmarks |
| `apps/web/tests/unit/features/replay-provenance-state.test.tsx` | new | the provenance and the integrity of the bundle in the state of the reader: the digest the artifact publishes reaches the panel, and the state never presents a bundle as checked when it was not |
| `apps/web/tests/unit/features/replay-states.test.tsx` | new | the states of the machine of the replay, and the purity of the reducer |
| `apps/web/tests/unit/network-fence.test.ts` | new | the fence of the network: `apps/web/lib/api/replay.ts` is the ONE place that reads the published artifacts, and the folder of the components never reads the network |
| `tests/test_public_clean.py` | changed | the guard of the dashes: the rule of the repository is a zero tolerance one, and it had no guard over the whole tree |
| `.gitignore` | changed | the handoff of the cycle and the folder of the tooling of the assistant stay out of git, so that a `git add -A` cannot publish the local notes of the machine |
| `docs/decisions/ADR-040-the-live-mode-on-the-origin-of-the-backend.md` | changed | the port of the suite of the end to end of the frontend moved to 3215 with the milestone of the public replay site, and the ADR that named the old port says so |
| `scripts/check_export_pages.mjs` | new | the check of the export, extracted out of the gate script so that it can be tested, and it reads the exported page as text, so that a route that answers 404 during the export does not pass the check |
| `apps/web/app/error.tsx` | new | the boundary of the segments of the site, and the component `SiteFailure` that the three boundaries share |
| `apps/web/app/global-error.tsx` | new | the boundary of the root of the site, which draws its own document |
| `apps/web/app/not-found.tsx` | new | the page of an address that the site does not publish |
| `apps/web/README.md` | new | the install, the build, the export, the test and the gate of the frontend |

With the table above, the list of the files of this milestone is complete. Nothing else that the
milestone landed changes. In particular the validators of
`apps/web/lib/replay/validate.ts`, the reducer of `apps/web/lib/replay/reducer.ts`, the types of
`apps/web/lib/api/schemas.ts`, the transport of the live mode and the page of the live mode are
NOT edited by this milestone.

### The tests that each set owes

Every test runs with NO key and NO network. The unit tests stub the fetch with the artifacts the
repository publishes, and the end to end suite runs against the static export served as plain
files.

Set A owes:

- `format-money.test.ts`: the formatter renders the decimal text with the ISO code, it never
  rounds and never multiplies, it keeps a fraction of more than two places, it says
  `Not available` when the amount is missing, it says that the currency is not available when the
  currency is missing, and it shows a malformed amount as it was read. The percentage formatter
  writes the symbol of the percentage and never a currency, it groups the digits with the same
  rule of the money, and it says `Not available` for a value that is not a decimal.
- `format-duration.test.ts`: the original duration is the duration of the capture and the playback
  offset is the distance of the visitor, and the two never appear in each other's place.
- `format-status.test.ts`: the labels of the domain and the tones, and the unknown word shown as
  it is with the neutral tone.
- `replay-selectors.test.ts`: the tree nests the spans, the timeline has one row per event, the
  evidence comes from the tool calls, the verdicts come from the verifier spans, the amounts keep
  their decimal text, the unit of an amount comes from the name of the value, and the currency comes
  from the exchange rate evidence.
- `replay-provenance.test.ts`: the label of the mode never says live for a published bundle, the
  digest is the one that was read, the freshness is `unknown` when there is nothing to compare
  with, and the freshness is `stale` when the comparable hashes differ.
- `url-state.test.ts`: the query string carries only `tab` and `speed`, a parameter that holds a
  key or a handle or an answer is ignored, and the path carries the identifier of the scenario.
- `view-preferences.test.ts`: the store is the `localStorage`, the fallback is the default, and
  nothing but the two fields is stored.

Set B owes:

- `replay-provider.test.tsx`: the machine goes from `idle` to `loading` to `ready`, then to
  `playing`, `paused` and `completed`; the `reset` returns to `ready` without reloading; and a
  refusal leaves the machine with no events and with the reason, so that no partial render is
  possible.
- `api-replay.test.ts`: the loader reads the published catalog, the manifest and the events; it
  refuses a catalog that does not pass the contract, a manifest that spells the version in
  another way and an event that is not a trace event; and the integrity check refuses a bundle
  whose digest does not match, with the expected and the observed digest.
- `ui-primitives.test.tsx`: the tabs, the dialog, the sheet and the skeleton behave as the
  primitives of the design package.

Set C owes:

- `replay-viewer.test.tsx`: the viewer shows the overview, the tree, the timeline, the
  provenance, the evidence and the verdicts; it shows the reason of a refused artifact instead of
  a partial render; and it shows the empty state for a bundle with no event.
- `replay-page.test.tsx`: the catalog shows the scenarios of the published catalog and links to
  the route of the scenario, and it refuses a catalog that does not pass the contract.
- The test of the route of the scenario, in
  `apps/web/tests/unit/features/replay-scenario-page.test.tsx`, which Set D writes: the route
  renders the scenario that the catalog publishes, and the URL of the page carries only the
  identifier and the preferences.

Set D owes:

- `catalog.spec.ts`: the catalog lists the published scenarios, and the link of a card carries
  the identifier of the scenario in the path.
- `replay.spec.ts`: the route renders the overview, the tree, the timeline, the provenance and
  the evidence; the visitor steps forward and backward and the state of the screen is the same
  for the same position; the reset returns to the beginning; and the URL of the page holds the
  identifier and the preferences and nothing else.
- `network.spec.ts`: every request of the page stays on the origin of the site, and the origin of
  the backend is never called.
- The README of the frontend: the install, the build, the export, the test and the gate, with the
  command of each one.

### The checks before the commit

- `bash scripts/gate.sh`, the Python gate of the repository: ruff, the tests offline and the
  check of the export.
- `bash scripts/gate_web.sh`, the Node gate of the frontend: the locked install, the type check,
  the lint, the unit tests and the static export, followed by the check that the export holds
  the catalog, the bundle of every scenario and the HTML of every scenario.
- The end to end suite with the chromium project:
  `cd apps/web && npm run test:e2e -- --project=chromium-390 --project=chromium-1440`.
  The projects of the webkit engine are not part of the check of this commit; the suite of this
  milestone is proved on chromium, and the webkit run is the check of the milestone of the
  accessibility.

## Alternatives considered

- **(a) Keep the plan of the first release as it is and build its six user stories.** The plan
  asks for the ledger of a thousand rows, the architecture page and the accessibility suite, and
  each of them needs an artifact or a document that the repository does not publish yet. Building
  them together would mean changing the Python export and the contracts in the same milestone as
  the interface, and the four workers would not have disjoint files.
- **(b) Keep the milestone `5564423` as it is and close the plan later.** The reader of that
  milestone fetches by itself, keeps no state and reads the mode as a raw string. The pieces of
  the plan would have to be bent around it, and the state machine of the replay would be born
  twice.
- **(c) Put the state of the playback in the URL, the position included.** A link that carries a
  position is a link to a moment of a run, and FR-004 asks that the query string carry nothing
  but the harmless preferences. The position is the transient state of the session.
- **(d) Compute the money in the browser.** The interface would multiply by a rate and round, and
  the number on the screen would be the number of the interface, not the number of the domain.
  The formatter renders the decimal text of the artifact and nothing else.
- **(e) Read the currency from the run instead of from the artifact.** The currency of an amount is
  a fact of the artifact, and the run of `S01` read a rate from the euro to the real. The panel
  reads it there, and it says that the currency is not available when the recording read none.
- **(f) Declare the snapshot fresh or stale from the hashes that the artifacts carry.** The
  `dataset_sha256` of the provenance is the hash of the dataset file and the `snapshot_sha256` is
  the hash of the snapshot that the run read. They are the hash of two different things, so
  comparing them would be a statement without a meaning. The panel says `unknown`.
- **(g) Route the scenario on `/replay/<id>`.** The prefix `/replay` is both the page of the
  catalog of the export (`out/replay.html`) and the folder of the published artifacts
  (`out/replay/`), so a bundle inside that prefix could not be a page of the export and a folder at
  the same time, and the static file server of the export would have to choose.
- **(h) Publish the result of the run in this milestone.** The result is the document with the
  claims, their kinds and their texts, and publishing it is a change of the export of the
  repository. The milestone keeps the interface on the artifacts that exist today, and the claims
  that the recording does not carry are rendered as `Not available`.

## Consequences

The site of the design package is complete as a site: a visitor with no key and no account opens
the catalog, picks a scenario, reads the tree of the investigation, the timeline, the provenance
and the evidence of the answer, steps through the recording, and comes back to the same view when
the page is reloaded, because the state of the visit is in the URL.

The interface invents nothing. The money is the decimal text of the artifact with the currency
that the artifact carries, the verdicts are the verdicts of the recording, the mode is the mode of
the manifest with a label that never says live, and a bundle that is refused shows the reason and
nothing else.

The four sets are independent. The contract between the workers is this ADR: the file names, the
exported names and the signatures are written down, so that a worker can write against the code
of another set before it exists.

The repository gains one ADR, the frontend gains the library layer, the shell, the state machine
and the panels, and the export of the site gains one HTML file per scenario, each one of them
proved by the gate.

## The resolutions of the open questions

The six questions above were put to the owner of the repository on the 21st of November of 2026,
and the answers are the following. They close the questions and they name the debt that the
milestone leaves behind. The seventh resolution is not an answer to a question: it is a decision of
this milestone, taken because the interface had to say what a percentage is before it could write
one.

1. **The published result stays out of this milestone.** The claims of the recording are read as
   the identifier of the claim, the label of the verdict and the note of the verifier, and the text
   of the claim is rendered as `Not available`, because the artifact does not carry it. Publishing
   the `run_result` is a change of the export of the repository and of the contract of the bundle,
   and it is the work of a milestone of its own. This is a named debt, not an oversight.
2. **The hash of the published ledger is still unknown.** The freshness of the snapshot is `unknown`
   and the panel says out loud that it could not be checked, because `dataset_sha256` and
   `snapshot_sha256` are the hash of two different things. FR-039 has to be read again when the
   export publishes the hash it means.
3. **The currency of the amounts is read from the exchange rate tool.** The `to_currency` of the
   output of `get_reference_fx` is the currency of the run, and the panel shows the amount and the
   currency as two separate facts. The amount and the currency are two facts of the artifact, and
   the amount alone is never enough to say what the money is.
4. **The name of the route is `/replay/scenario/<id>`, and the deviation from the plan is
   accepted.** The plan of the first release says `/demo/[scenario]`; the milestone landed
   `/replay`, and this ADR lands `/replay/scenario/<id>`. The prefix `/replay` is both the page of
   the catalog of the export (`out/replay.html`) and the folder of the published artifacts
   (`out/replay/`), so a bundle inside that prefix could not be a page of the export and a folder at
   the same time, and a static file server would have to choose.
5. **The absence of the Web Crypto is not a refusal.** The check of the digests needs a secure
   context. Over https and on `127.0.0.1` it works, and a deployment in plain http shows the
   integrity as not checked.
6. **The end to end suite of this milestone runs on chromium.** The projects of the webkit engine
   are the check of the milestone of the accessibility, where the suite of the mobile journey and the
   axe scan join.
7. **A percentage is not money.** The unit of every value of the breakdown of the calculation is
   read out of the NAME of the value, because the name is where the recording declares the unit
   (`markup_pct`), and it is the name the reader sees in the panel of the amounts. A percentage is
   written with the symbol of the percentage and NEVER carries the currency of the run; the money
   values keep the currency that the run read from the `to_currency` of the tool that read the rate.
   A percentage that is not a decimal shows `Not available`, because a unit written on a broken
   value would be an invention. This is a decision of the milestone: the interface never presents a
   number with a unit it did not read, and the name of the value is the only place the recording
   declares that unit.

The three answers that change the plan of the repository, beyond this ADR, are: the route is
`/replay/scenario/<id>`, the published result is a debt of a next milestone, and the next frontend
milestone is the interface of the sandbox, with the mutations, the diff and the history of the
branch of the visitor.

## Open questions

These questions could not be answered from the code of the repository, and they are the ones the
next milestone has to settle.

1. **The published result.** The bundle contract has the `run_result` with the claims, their
   kinds and their texts, and the static export does not publish it. When it is published, under
   which name, and does the catalog carry its digest too? The milestone reads the claims as
   identifiers with the note of the verdict.
2. **The hash of the currently published ledger.** FR-039 compares the hash of the snapshot of the
   bundle with the hash of the published ledger. The artifacts carry the hash of the dataset file
   and the hash of the snapshot of the run, and they are not comparable. Which hash is the one
   that FR-039 means, and where does the export publish it?
3. **The currency of the amounts.** The output of the `calculate` tool carries the decimal text
   without a currency, and the currency of the run is read from the output of the exchange rate
   tool. Is that the rule the domain wants, or must the export publish the currency with every
   amount?
4. **The name of the route.** The plan says `/demo/[scenario]` and the milestone landed `/replay`.
   This ADR decides `/replay/scenario/<id>` for the reason of the folders of the artifacts. The
   orchestrator has to accept the deviation from the plan.
5. **The integrity check without the Web Crypto.** The check of the digests needs a secure
   context. The site is served over https and the end to end suite runs on `127.0.0.1`, so it
   works there. A deployment in plain http would show the integrity as not checked.
6. **The engine of the end to end suite.** SC-014 asks for chromium and webkit, and the check of
   this commit is the chromium project. When does the webkit run join the gate?
