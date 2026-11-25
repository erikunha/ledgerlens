# Feature Specification: Cold start guided replay

**Feature Branch**: `feature/v3`

**Created**: 2026-11-23

**Status**: Draft

**Input**: Design documents: [ADR-013](../../docs/decisions/ADR-013-public-trace-as-a-versioned-contract.md),
[ADR-014](../../docs/decisions/ADR-014-replay-bundle-with-manifest-and-hash.md),
[ADR-041](../../docs/decisions/ADR-041-the-interactive-diagrams-are-rendered-outside-the-repository.md),
[ADR-042](../../docs/decisions/ADR-042-the-site-of-the-demo-serves-the-published-artifacts.md),
[ADR-043](../../docs/decisions/ADR-043-the-public-site-of-the-design-package-is-complete.md),
[ADR-060](../../docs/decisions/ADR-060-the-surfaces-that-answer-a-person-carry-the-sentence-of-the-ai-agent.md),
[ADR-073](../../docs/decisions/ADR-073-the-published-bundle-carries-the-evidence-its-verdict-was-computed-on-and-it-is-reproducible.md),
[ADR-075](../../docs/decisions/ADR-075-the-site-publishes-two-catalogs-and-each-bundle-declares-the-one-it-belongs-to.md),
[ADR-076](../../docs/decisions/ADR-076-the-answer-of-the-run-is-published-whole-because-the-claims-are-extracted-from-it.md),
[ADR-077](../../docs/decisions/ADR-077-the-published-bundle-is-verified-against-the-answer-the-run-verified.md) and the
design package [LL-V3-R1-02, cold start guided replay](../../docs/v3/advanced-specs/R1-02-cold-start-guided-replay.md).
The milestone that delivered the recording itself is [specs/001](../001-r1-public-replay/spec.md).

The package was written for a greenfield plan. The repository has since built the recording, the bundle, the static
export and the reader of the replay. This specification covers the part of the package that is still missing: the
guided cold start, the path that takes a visitor who knows nothing about the repository to one resolved case, and the
proof that the path asks no provider and no key.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A visitor who knows nothing understands one case in three minutes (Priority: P1)

A visitor arrives at the site with no key, no login and no knowledge of the repository. The front page offers a
guided path that opens the recorded scenario S01 and walks it in steps. Each step says what the reader is looking at
and why it matters. The visitor reaches the conclusion of the case, which is a decision and not an arithmetic
exercise, and reads what the case cannot decide. The path never asks for a key and never asks the network for
anything.

**Why this priority**: the recording exists and the reader exists, but nothing tells a first-time visitor where to
start or what the trace means. Without the guided path the catalog is a list of cards and the reader of the trace
assumes knowledge of LangChain, LangGraph and the vocabulary of the repository.

**Independent test**: open the guided path with the network disabled and no key in the environment, follow it to
the end, and assert that no request left the browser for a provider, that every step names a region that exists in
the page, and that the last step carries the decision of the case and the limits of what the case does not decide.

### User Story 2 - The visitor seeks back and sees the same events in the same order (Priority: P1)

The visitor moves the slider of the playback to an earlier point and then forward again. The reader rebuilds the
trace up to that point: the same events, in the same order, with the same numbers. Seeking back is not a second
playback of a summary and it never shows an event that the bundle does not carry.

**Why this priority**: the seek is the control a visitor uses to check a claim, and a reader that shows a different
history on the way back destroys the trust of the whole recording.

**Independent test**: play the recording of S01 to its end, seek to the middle, seek to the end and seek back to
the middle again. The state of the reader after the two seeks to the middle is identical, the order of the events
shown is the order of the events of the bundle, and the count of the events never grows.

### User Story 3 - The visitor clicks a citation and reads the exact line behind it (Priority: P1)

The reader shows a claim and the evidence it cites. The visitor clicks the citation and the reader shows the exact
row of the ledger, the exact passage of the policy or the exact value of the calculation that supports it. When the
source is behind a redaction, the reader says that the value was redacted and why, and it does not show a nearest
match instead.

**Why this priority**: the bundle carries the evidence its verdict was computed on, and the evidence is worthless to
a reader who cannot open it.

**Independent test**: open the claim panel of the recorded scenario S01, click every citation of the first claim and
assert that each one resolves to the record it names, that the money of a cited row is the exact `Decimal` string of
the row and never a float, and that a citation whose source is absent produces a stated refusal and not a nearby
record.

### User Story 4 - The visitor reaches the end and reads the decision and the limits (Priority: P2)

The last step of the guided path shows the conclusion of the case, the verdict the verifier gave, and the limits of
what the case can say. It then offers the two paths that continue the visit: the sandbox fork, where the visitor
changes a value and watches the case decide again, and the engineering page, where the visitor reads the code that
produced the recording.

**Why this priority**: a recording that ends with an answer leaves the visitor with nothing to do, and the two
paths that exist are the reason to keep the visitor on the site.

**Independent test**: follow the guided path to its last step and assert that the step carries the verdict, the
decision, at least one stated limitation, and the links to the sandbox fork and to the engineering page, and that
the fork it links to starts from the same base hash that the recording declares.

### User Story 5 - The path works with a keyboard and on a phone (Priority: P2)

A visitor who does not use a mouse follows the whole path with the keyboard: the steps are reachable in order, the
focus is visible, and the region that announces the step of the playback is polite. A visitor on a phone reads the
same steps and the same evidence without horizontal scrolling and with tap targets that are large enough.

**Why this priority**: the path is the entrance of a public repository, and an entrance that only works with a
mouse excludes part of the audience.

**Independent test**: run the guided path with the keyboard only, from the first step to the last, and assert that
every control receives a focus, that no step is skipped, and that the announced region carries the step. Run the
mobile test at the width of a small phone and assert that no element overflows the viewport and that every control
of the path is at least 44 pixels high.

### User Story 6 - A missing artifact produces a stated error and a local path (Priority: P3)

The published artifact of a scenario is missing. The page says so, names the file it looked for, and offers the
local path that regenerates it. It never draws an empty trace, never invents frames and never shows a case that
looks resolved because nothing was read.

**Why this priority**: the export is a build artifact and it can be missing or stale in a checkout of the
repository. The refusal has to be loud, because a silent empty replay reads as a case with no evidence.

**Independent test**: remove the published bundle of a scenario from the copy the site serves, open the page and
assert that the reader shows the refusal with its reason, that it draws no event, and that the page names the
command that rebuilds the artifact.

### Edge Cases

- A bundle whose manifest was tampered with: the reader refuses the whole bundle and shows the reason, because a
  tampered recording is not a recording.
- A bundle with fewer events than the guide expects: the guide adapts to the events that exist and names the step
  it cannot show, instead of showing a step with no content.
- A visitor who arrives in the middle of a scenario: the guide starts at the first step and the visitor may jump.
- A visitor with the preference of less motion: the playback does not advance on its own and the step controls
  stay.
- A scenario that was recorded with a real model and a scenario that was recorded with the scripted model: both
  are guided, and each one says which one it is.
- The same claim cited by two evidence ids: the reader shows both and does not merge them.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The guided path is a list of steps, each one naming a region of the reader and a sentence that
  explains it, and the list is data and not code that draws the page.
  - Test: `apps/web/tests/unit/features/replay-guide.test.ts` fails while a step names no region of the reader.
- **FR-002**: The guided path makes no request to a provider and needs no key, and it is proved by the absence of
  the request and not by a promise in the prose.
  - Test: `apps/web/tests/e2e/guided-replay.spec.ts` fails while the path issues a request that leaves the site.
- **FR-003**: Seeking to a position rebuilds the state from the events of the bundle up to that position, and the
  state after two seeks to the same position is identical.
  - Test: `apps/web/tests/unit/features/replay-guide.test.ts` fails while the state after the second seek differs
    from the state after the first.
- **FR-004**: Every citation of the reader resolves to the record it names, and a citation whose source is absent
  produces a stated refusal.
  - Test: `apps/web/tests/unit/features/replay-viewer.test.tsx` fails while a citation resolves to a different
    record or to a nearest match.
- **FR-005**: The money of a cited row is read as an exact `Decimal` string and never as a float.
  - Test: `apps/web/tests/unit/features/replay-viewer.test.tsx` fails while a cited amount is rounded to a float.
- **FR-006**: The last step of the guide carries the verdict, the decision of the case and at least one stated
  limitation, and it links to the sandbox fork and to the engineering page.
  - Test: `apps/web/tests/unit/features/replay-guide.test.ts` fails while the last step carries no limitation.
- **FR-007**: The fork that the guide links to starts from the base hash that the recording declares, and the
  recording itself is unchanged by the fork.
  - Test: `apps/web/tests/unit/features/replay-guide.test.ts` fails while the link names a scenario whose base
    hash differs from the one of the recording.
- **FR-008**: The path is usable with the keyboard only, every control takes a focus, and the announced region
  carries the step.
  - Test: `apps/web/tests/e2e/a11y.spec.ts` fails while a control of the path cannot be reached with the
    keyboard.
- **FR-009**: The path is usable at the width of a small phone, with no horizontal overflow and with tap targets of
  at least 44 pixels.
  - Test: `apps/web/tests/e2e/mobile.spec.ts` fails while a control of the path is smaller than 44 pixels.
- **FR-010**: A missing or tampered artifact produces a stated error with the name of the file and the command
  that rebuilds it, and the reader draws no event.
  - Test: `apps/web/tests/unit/features/replay-viewer.test.tsx` fails while a missing artifact produces an empty
    trace and no reason.
- **FR-011**: The guide says which capture it walks, a scripted model or a real model, and it never presents a
  recorded run as a live one.
  - Test: `apps/web/tests/unit/features/replay-guide.test.ts` fails while the guide does not name the capture.
- **FR-012**: The sentences of the guide are the sentences of the agent where the guide describes a conclusion, and
  the guide adds no verdict of its own.
  - Test: `apps/web/tests/unit/features/replay-guide.test.ts` fails while a step of the guide states a verdict that
    the bundle does not carry.

### Key Entities

- **Guide**: the ordered list of the steps of the cold start, each with the region of the reader it points at.
- **Step**: one entry of the guide, with the region it names and the sentence that explains it.
- **Playback position**: the index of the event the reader shows, the only state the browser keeps.
- **Citation**: the reference of a claim to the evidence that supports it, with the exact source behind it.
- **Limitation**: a statement of what the case cannot decide, published with the conclusion.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The guided path opens a scenario with no key, with no login and with the network disabled, and no
  request leaves the site.
- **SC-002**: A visitor reaches the conclusion of the guided path in under three minutes, measured over the
  scripted model and stated as a tendency over the sessions that were measured, not as a guarantee.
- **SC-003**: The state of the reader after two seeks to the same position is identical, and the order of the
  events shown is the order of the events of the bundle.
- **SC-004**: Every citation of the recorded scenario resolves to the record it names, and a missing source
  produces a stated refusal.
- **SC-005**: The last step of the guide carries the verdict, the decision, at least one limitation and the two
  paths that continue the visit.
- **SC-006**: The path passes the keyboard test and the mobile test of the gate of the frontend.
- **SC-007**: A missing artifact produces a stated error with the command that rebuilds it, and no event is
  drawn.
- **SC-008**: The guide names the capture it walks in every step that shows a conclusion.

## Assumptions

- The recording, the bundle, the static export and the reader already exist. This specification adds the guided
  path and the proofs the package asks for, and it does not rewrite the reader.
- The three minutes of the package is a target, not a measurement. The repository has no session analytics and
  the package itself asks for the analytics to be annotated with consent. Until a consented measurement exists,
  the number is a hypothesis and the report says so.
- The guide is a list of steps that point at regions of the reader. It does not draw a second interface and it
  does not own the layout.
- The wording of a step is the wording of the agent where the step describes a conclusion, because the decision
  belongs to the code and to the answer of the run, and a narrator that paraphrases it would be a second source of
  truth.
- The bundle of a scenario is immutable, and the guide never changes it.

## Out of scope

- The recording of new scenarios, the capture of a live run and the export of the site, which belong to
  [specs/001](../001-r1-public-replay/spec.md).
- The sandbox the guide links to, which belongs to [specs/002](../002-r2-visitor-sandbox/spec.md) and to
  [specs/008](../008-r2-isolated-sandbox-mutations/spec.md).
- The evidence graph behind the citations, which belongs to
  [specs/010](../010-r8-evidence-graph-and-provenance/spec.md).
- The analytics of the site. No event of the guide is sent anywhere until a consented measurement is designed and
  published with its own decision record.
- The live mode, which asks for a key and is not part of the cold start.

## Design documents

| Document | What it decides for this specification |
|---|---|
| [ADR-013](../../docs/decisions/ADR-013-public-trace-as-a-versioned-contract.md) | The trace of a run is a versioned contract, so the guide reads a contract and not a log. |
| [ADR-014](../../docs/decisions/ADR-014-replay-bundle-with-manifest-and-hash.md) | The bundle carries a manifest and a hash, so the reader can refuse a tampered recording. |
| [ADR-041](../../docs/decisions/ADR-041-the-interactive-diagrams-are-rendered-outside-the-repository.md) | The interactive diagram of the run lives outside the repository, so the guide does not try to redraw it. |
| [ADR-042](../../docs/decisions/ADR-042-the-site-of-the-demo-serves-the-published-artifacts.md) | The site serves the artifacts the repository publishes, so the guide reads the published copy. |
| [ADR-043](../../docs/decisions/ADR-043-the-public-site-of-the-design-package-is-complete.md) | The public site of the package is complete, so the guide is an addition to a finished surface and not a replacement. |
| [ADR-060](../../docs/decisions/ADR-060-the-surfaces-that-answer-a-person-carry-the-sentence-of-the-ai-agent.md) | A surface that answers a person carries the sentence of the agent, so the guide adds no verdict of its own. |
| [ADR-073](../../docs/decisions/ADR-073-the-published-bundle-carries-the-evidence-its-verdict-was-computed-on-and-it-is-reproducible.md) | The published bundle carries the evidence the verdict was computed on, so a citation resolves inside the bundle. |
| [ADR-075](../../docs/decisions/ADR-075-the-site-publishes-two-catalogs-and-each-bundle-declares-the-one-it-belongs-to.md) | The site publishes two catalogs, so the guide names the capture of the scenario it walks. |
| [ADR-076](../../docs/decisions/ADR-076-the-answer-of-the-run-is-published-whole-because-the-claims-are-extracted-from-it.md) | The answer of the run is published whole, so the guide reads the claims of the bundle and not a summary of them. |
| [ADR-077](../../docs/decisions/ADR-077-the-published-bundle-is-verified-against-the-answer-the-run-verified.md) | The published bundle is verified against the answer the run verified, so the guide may show the verdict of the bundle. |
| [LL-V3-R1-02](../../docs/v3/advanced-specs/R1-02-cold-start-guided-replay.md) | The design package this specification ports. |
| [specs/001](../001-r1-public-replay/spec.md) | The milestone that built the recording, the bundle and the reader. |

## Status

| Part | State in the repository on 2026-11-23 |
|---|---|
| The recording, the bundle with its manifest and its hash | Built. `ledgerlens/replay/bundle.py`, `ledgerlens/replay/capture.py` and `scripts/capture_replay.py` write them, and `ledgerlens/replay/site_export.py` exports them. |
| The reader of the recording | Built. `apps/web/features/replay/ReplayViewer.tsx`, `ReplayControls.tsx` and `apps/web/lib/replay/reducer.ts` hold the state, and the pages under `apps/web/app/(public)/replay/` read it. |
| The playback with the play, the pause, the step, the seek and the speed | Built. `apps/web/features/replay/usePlaybackClock.ts` and `apps/web/features/replay/ReplayControls.tsx` implement it. |
| The keyboard and the mobile tests | Built for the pages of the site. `apps/web/tests/e2e/a11y.spec.ts` and `apps/web/tests/e2e/mobile.spec.ts` cover the pages that exist today. |
| The guided cold start | Not built. There is no list of steps and no page that walks a first-time visitor through one case. |
| The proof that the path asks no provider | Not built as a test. The page avoids the backend by construction and no test asserts it. |
| The measurement of the three minutes | Not measured. No consented analytics exist, so the target of the package is a hypothesis. |
| The rollback to a static HTML page | Not built and not needed by the current reader, which is a static export already. The guide is data, so it is removed with one file. |

The package proposes a route `GET /replays/:id` that returns the immutable bundle. The repository does not need it:
the site is a static export and the bundle is served as a file next to the page, under ADR-042. This specification
follows the repository and does not add a route that would break the promise that the recorded demo calls nobody.
