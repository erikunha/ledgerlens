# Feature Specification: R1 Public Replay

**Feature Branch**: `feature/v3`

**Created**: 2026-11-11

**Status**: Draft

**Input**: User description: "Build the first public vertical slice of the LedgerLens web experience: a guided replay of a recorded agent investigation that any visitor can open in a browser without an API key, without a login and without a single call to a model provider. The visitor picks a scenario from a catalog, plays the recorded trace step by step on a timeline and in a span hierarchy, inspects the claims with their verdicts and the evidence behind them, browses the simulated payment ledger rows that the recorded run actually read, and follows the architecture diagram to the exact source modules and to the architecture decision records. The replay is truthful about what it is: it is a recording, it shows its provenance and its hashes, it never claims to be a live run, and the Python core stays the authority for every verdict and every amount."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Open the public site and choose a scenario with no key and no login (Priority: P1)

A visitor lands on the public site. No sign-up, no API key field, no cookie wall. The landing page states that all money is simulated and that the demonstration runs on recorded executions. The visitor opens the scenario catalog, sees each scenario card with its question, the concepts it demonstrates, its data origin and its status, and starts the guided replay of scenario S01. The replay opens in the `Recorded Replay` mode, the URL carries only the scenario id, and the page makes no request to any model provider.

**Why this priority**: This is the entry door of the whole project. Without a visitor who can reach a recorded case in seconds and without a key, there is no demonstration to show and no story to tell. Everything else in the feature is unreachable if this story fails.

**Independent Test**: Can be fully tested by opening the deployed landing page in a clean browser profile with no credentials and no stored cookies, choosing S01 from the catalog and asserting that the replay page renders the recorded run overview with the mode label `Recorded Replay`. Delivers the value "any visitor can see an authentic recorded investigation in under one minute".

**Acceptance Scenarios**:

1. **Given** a visitor with no account, no API key and no cookies, **When** the visitor opens the landing page, **Then** the page renders fully with static assets only and no credential input is requested anywhere.
2. **Given** the scenario catalog with the cards of S01, S09 and S10, **When** the visitor selects the S01 card, **Then** the replay of S01 opens and the address bar shows only the scenario id in the path, with no other value in the query string.
3. **Given** the S01 replay is open, **When** the network log of the page is inspected from the first paint to the end of the playback, **Then** no request is made to a model provider host, to an exchange rate service or to any write endpoint.
4. **Given** a scenario card whose status is `Editable` or `Live-compatible`, **When** the card is rendered, **Then** the status label reads exactly what the status is, and a scripted fixture scenario is labelled `Scripted fixture` in addition to `Recorded Replay`.
5. **Given** the catalog is open, **When** the visitor activates a card with the keyboard only, **Then** the card is reachable by Tab, shows a visible focus ring and opens the same replay as a pointer activation.

---

### User Story 2 - Watch the recorded trace step by step on the timeline and in the hierarchy (Priority: P1)

The visitor presses play and the recorded trace advances step by step: triage, plan, tool calls, verification, answer. A timeline shows the progression, a tree shows the nested spans with their observed wall time, and each step opens the tool arguments and the sanitized outputs. The visitor can pause, step forward and backward, jump with the slider or with the previous and next buttons, change the playback speed and reset the replay. Changing the speed never changes the order of the events nor the original measured timing shown next to each step.

**Why this priority**: The trace is the technical heart of the demonstration. A visitor who cannot see how the agent reached the answer will read the result as a black box, which is the opposite of what this project is about. It shares the P1 level with the entry door because both are needed for a meaningful first impression.

**Independent Test**: Can be fully tested by loading the S01 replay, pressing play, pausing after the third event, stepping forward and backward with the buttons and confirming that the rendered state for a given event index is always identical, and that the timeline shows the 57 recorded events of the bundle.

**Acceptance Scenarios**:

1. **Given** the S01 replay is ready, **When** the visitor presses play, **Then** the events are rendered one at a time in ascending sequence order and the original measured duration of each span stays visible next to the playback position.
2. **Given** the playback is running, **When** the visitor selects the speed control and chooses 4x, **Then** the event order, the event contents and the displayed original timings do not change, only the wall clock pacing of the animation changes.
3. **Given** the playback is at event 12, **When** the visitor presses the previous-step button and then the next-step button, **Then** the view returns to exactly the state rendered for event 12, with the same rows, the same claims and the same evidence.
4. **Given** the trace tree with nested spans, **When** the visitor uses Arrow Down and Arrow Up, **Then** the focus moves row by row through the tree and Home and End jump to the first and last row.
5. **Given** a span whose payload contains a SQL statement longer than the pane width, **When** the visitor opens it, **Then** the SQL scrolls horizontally inside the code pane only and the page itself does not scroll sideways.
6. **Given** the playback finished, **When** the visitor activates Reset, **Then** the replay returns to the first event with the final answer panel cleared, without a page reload.

---

### User Story 3 - Inspect a claim, its verdict and the evidence behind it (Priority: P2)

The final answer is shown as a list of claims. Each claim carries the text, the cited evidence, the verification method and a verdict: supported, contradicted or not enough evidence. The visitor opens a claim and reads the sanitized source excerpt, the origin reference and the retrieved timestamp. When a source is missing, the interface says `Not available` and the claim never shows a green supported state. When the verifier did not run, the verdict reads `Not verified` and no green badge appears.

**Why this priority**: This is the evidence over fluency principle made visible. It is the second thing a technical reviewer looks for after the trace, and it is what turns a replay into a proof. It is P2 because a visitor can already get value from the entry door and the trace alone.

**Independent Test**: Can be fully tested by opening the decision panel of the S01 replay, activating a claim, asserting that every cited evidence id exists in the published artifact, and asserting that the S09 bundle, whose verdict is a refusal, shows an explicit reason instead of a green badge.

**Acceptance Scenarios**:

1. **Given** a claim citing `sql:1`, `policy:refund-fx` and `calc:1`, **When** the visitor activates the citation, **Then** the evidence inspector opens with the sanitized excerpt, the source type and the origin reference of each source.
2. **Given** a claim whose evidence reference does not exist in the published artifact, **When** the decision panel renders, **Then** the reference shows `Not available` and the claim is not displayed as supported.
3. **Given** a bundle whose `verification_status` is `unavailable`, **When** the decision panel renders, **Then** the status reads `Not verified`, no green badge is drawn and the reason for human review is visible.
4. **Given** a verdict of `contradicted`, **When** the visitor reads the claim row, **Then** the label appears with an icon and with text, and the color is not the only carrier of the meaning.
5. **Given** the answer panel, **When** the visitor reads it, **Then** the recommended action, the final answer and whether human review is required are all visible, and no hidden reasoning of the model is claimed to be available.

---

### User Story 4 - Explore the payment ledger rows that the recorded run read (Priority: P2)

Beside the replay, the visitor opens the payment ledger of the simulated account. The table is dense and sortable, it shows the amount with the currency code, the type, the status and the counterparty. The rows that the recorded run actually read are marked, and selecting a row opens the business events, the refund and FX fields and the policy triggers that the agent used.

**Why this priority**: The ledger is what makes the case concrete. It shows that the evidence came from real rows of a simulated dataset and not from a paragraph written by a model. It is P2 because the trace and the claims already deliver the core demonstration.

**Independent Test**: Can be fully tested by opening the ledger panel of the S01 replay, sorting by amount, filtering by status and asserting that the rows marked as read are exactly the rows whose identifiers appear in the tool responses of the bundle.

**Acceptance Scenarios**:

1. **Given** the ledger panel of the S01 replay, **When** it renders, **Then** every amount is formatted with an explicit ISO currency code and no arithmetic is performed in the browser.
2. **Given** a table of 1000 rows, **When** the visitor sorts by amount or filters by status, **Then** the table stays usable and no page-level horizontal scroll appears.
3. **Given** a row the recorded run read, **When** the visitor selects it, **Then** the detail panel shows the transaction, the refund, the applied rate and the policy trigger, with a link to the source of the data.
4. **Given** a row the recorded run did not read, **When** the table renders, **Then** the row carries no read marker.
5. **Given** a transaction in status `disputed` or `partially_refunded`, **When** the visitor reads the row, **Then** the status is written in words as well as in color.

---

### User Story 5 - Browse the architecture and follow the links to the source and to the decision records (Priority: P3)

From the replay, the visitor opens the engineering drawer and the architecture page. A diagram shows the subsystems of the system: the read-only query guard, the scoped ledger copy, the decimal calculator, the deterministic simulator, the verifier and the trace recorder. Every node links to the exact module in the repository and to the architecture decision record that explains why it exists.

**Why this priority**: The architecture tour is what turns a visitor into a reader of the code, and it is the main differentiator for a technical recruiter. It is P3 because it enriches the demonstration without being required to understand it, and it is the piece that can be extended later without touching the replay.

**Independent Test**: Can be fully tested by opening the architecture page, activating a node, asserting that the link target exists in the repository, and asserting that each node references at least one decision record.

**Acceptance Scenarios**:

1. **Given** the architecture page, **When** the visitor activates the node of the query guard, **Then** the link opens the exact module of the guard in the repository and the decision record that describes the allowlist.
2. **Given** the engineering drawer opened from a tool call, **When** the visitor reads it, **Then** it explains in plain language the read-only guard, the deterministic decimal arithmetic and the verification step, with a link to each module.
3. **Given** the architecture diagram, **When** the visitor uses the keyboard, **Then** every node is reachable, activatable and has a text label that describes the subsystem.
4. **Given** the diagram, **When** the visitor prefers reduced motion, **Then** no layout animation runs and the diagram is readable as a static picture.

---

### User Story 6 - Use the replay on a mobile screen and with a keyboard only (Priority: P3)

The visitor opens the replay on a phone. The layout becomes a single column with accessible tabs for the execution, the evidence, the decision and the ledger, the text stays readable without sideways scrolling and the controls stay reachable with a thumb. The same visitor can also complete the whole journey with the keyboard only, from the catalog to the trace, the evidence and the architecture links, without ever needing a pointer and without getting trapped in a drawer.

**Why this priority**: Mobile and keyboard operation are the difference between a demo that a reviewer can open anywhere and a demo that only works on one laptop. It is P3 in priority order because it does not add a new capability, it guarantees access to the ones already built.

**Independent Test**: Can be fully tested by running the automated end-to-end suite at a viewport of 390 by 844 with the mouse disabled and by running the accessibility scan on every page of the feature.

**Acceptance Scenarios**:

1. **Given** a viewport of 390 pixels wide, **When** the visitor opens the replay and reads the timeline, the claims and the ledger, **Then** the page never scrolls horizontally and no essential content is clipped.
2. **Given** a viewport of 1440 pixels wide, **When** the replay renders, **Then** the execution, the evidence and the decision are visible side by side without hiding the mode label.
3. **Given** the visitor navigates with the keyboard only, **When** they move through the catalog, the replay, the evidence inspector and the architecture links, **Then** every action is possible and the focus indicator is always visible.
4. **Given** a drawer opened with the keyboard, **When** the visitor closes it with Escape, **Then** the focus returns to the control that opened the drawer.
5. **Given** the preference for reduced motion is active, **When** the replay runs, **Then** the automatic animation is disabled and the visitor steps through the events with the buttons.

---

### Edge Cases

- **Missing evidence**: a claim cites an evidence id that does not exist in the published artifact. The reference renders as `Not available`, the claim cannot be supported, and the incident is counted in the panel rather than hidden.
- **Tampered bundle**: the hash of `events.jsonl` does not match the hash declared in the manifest. The replay refuses to open, shows an explicit integrity error with the expected and the observed digest, and renders no partial result.
- **Stale snapshot**: the `snapshot_sha256` of the bundle differs from the hash of the currently published ledger. The provenance panel labels the bundle as stale, the run is not offered for comparison with the current snapshot and the comparison control is disabled with a reason.
- **Unsupported model or capture kind**: the bundle declares a model profile or a capture kind the interface does not support. The page explains what is not supported, disables playback and never renders a fabricated result or a substituted label.
- **Empty trace**: the bundle declares events but the array is empty, or the first event is not a start event. The page renders an empty state that states the recording has no events and offers a link back to the catalog.
- **Long SQL**: a tool call carries a SQL statement longer than the code pane. Only the code pane scrolls sideways, the page does not, and the statement is displayed with the literals sanitized.
- **One thousand ledger rows**: the ledger fixture holds 1000 rows. Sorting and filtering stay responsive, the table is paginated or virtualized so that not every cell is mounted at once, and the page does not scroll sideways.
- **Reduced motion**: the operating system asks for reduced motion. Every non-essential transition and the automatic playback animation are disabled, the visitor still steps through the events with the buttons and the timeline stays meaningful.
- **Screen reader**: a screen reader reads the replay. The live region announces the step summary and not every token, the verdict is announced with its label, the tree rows expose their expanded state and the drawer returns the focus to its trigger.
- **Provider failure**: the model provider is down, slow or returning an error. The replay page is static and keeps working, the error is confined to the panel that needs it and no conclusion is invented to replace it.
- **Duplicate and out-of-order events**: the bundle contains two events with the same sequence number, or the sequence numbers have a gap. The duplicates are ignored and the gap is reported, and the timeline keeps the ascending order.
- **Unknown event type**: a new event type appears in a newer bundle. The timeline shows it as an unrecognized event rather than dropping it silently.
- **Very long single answer**: the final answer is a long text. It is fully readable, it is not truncated without a way to see the rest, and it does not push the panels below into an unreadable width.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST serve the replay feature as a statically exported site, so that a visitor can open it with no server runtime, no session and no backend process.
- **FR-002**: The system MUST render every page of the feature for an anonymous visitor with no account, no API key and no login, and MUST NOT ask for a credential anywhere in the feature.
- **FR-003**: The system MUST present a scenario catalog whose cards show, for each scenario, the identifier, the name, the question, the concepts demonstrated, the data origin and the status label.
- **FR-004**: The system MUST open the replay of the selected scenario with the scenario identifier in the route path, and MUST NOT place any other value in the query string.
- **FR-005**: The system MUST load the replay from the published static artifact of the scenario and MUST NOT call any backend service while the replay is open.
- **FR-006**: The system MUST make zero HTTP requests to model provider hosts, to exchange rate services and to write endpoints while a replay is loaded and played, and an automated test MUST assert it.
- **FR-007**: The system MUST display the mode label `Recorded Replay` for every replay bundle, and the label of a replay MUST NOT contain the word "live" in any language.
- **FR-008**: The system MUST display the additional caption `Scripted fixture` for a bundle whose capture kind is a scripted fixture, and MUST NOT present it as a recorded real model run.
- **FR-009**: The system MUST display the provenance of the bundle: the captured mode, the capture timestamp, the model profile, the code commit hash, the snapshot hash, the prompt hash, the policy version and the digest of the bundle files, each only when the bundle declares it.
- **FR-010**: The system MUST use the playback clock for visual timing only, and MUST display the original measured duration of each event unchanged.
- **FR-011**: The system MUST offer the playback speeds 1x, 2x and 4x, and changing the speed MUST NOT change the order of the events nor the displayed original timings.
- **FR-012**: The system MUST rebuild the view state when the visitor seeks to an event index by reducing the events from the first one up to that index, and the same index MUST always produce the same view state.
- **FR-013**: The system MUST ignore duplicated events that share the same run identifier and sequence number, and MUST report a gap in the sequence instead of hiding it.
- **FR-014**: The system MUST map every `evidence.added` event to the canonical evidence identifier of the published result, and MUST render an event without a matching evidence as unavailable rather than dropping it.
- **FR-015**: The system MUST map every `claim.verdict` event to an existing claim identifier, and MUST render a verdict without a matching claim as unresolved.
- **FR-016**: The system MUST render a timeline with the nested spans, the observed wall time, the error and the token usage when the bundle reports them.
- **FR-017**: The system MUST offer explicit previous-step and next-step controls in addition to the timeline slider.
- **FR-018**: The system MUST let the visitor reset the replay to the initial state without reloading the page.
- **FR-019**: The system MUST show, for every claim, the claim text, the cited evidence identifiers, the verification method, the verdict label with an icon and with text, and the note when the bundle carries one.
- **FR-020**: The system MUST render a missing evidence reference as `Not available` and MUST NOT render that claim with a supported status.
- **FR-021**: The system MUST render the verification status `unavailable` or `timed_out` as `Not verified` and MUST NOT draw a green badge in that case.
- **FR-022**: The system MUST display the final answer, the recommended action and whether human review is required.
- **FR-023**: The system MUST open, on activation of a citation, the sanitized source excerpt with its origin reference and its retrieval timestamp.
- **FR-024**: The system MUST show the human reasoning limit on the interface: it MUST NOT claim that the hidden reasoning of the model is available.
- **FR-025**: The system MUST list in the ledger panel the payment rows of the account that the recorded run read, and MUST mark exactly those rows as read.
- **FR-026**: The system MUST format every amount with an explicit ISO currency code using the platform number formatter, and MUST NOT perform financial arithmetic in the browser.
- **FR-027**: The system MUST support sorting and filtering of the ledger rows over the bounded public dataset, and MUST keep the table usable with 1000 rows without mounting every cell at once.
- **FR-028**: The system MUST write the status of a row in words as well as in color.
- **FR-029**: The system MUST expose a clickable architecture diagram whose nodes link to the exact module in the repository and to at least one decision record.
- **FR-030**: The system MUST explain in plain language, in the engineering drawer, the read-only query guard, the deterministic decimal arithmetic and the verification step, with a link to each module.
- **FR-031**: The system MUST make every interactive control reachable and operable with the keyboard alone, and MUST expose a visible skip link.
- **FR-032**: The system MUST manage the focus: after the playback starts, the focus moves once to the status region, after a drawer closes the focus returns to the control that opened it, and the current step is announced.
- **FR-033**: The system MUST announce at most a step summary in the accessible live region, and MUST NOT announce every token or every rendered frame.
- **FR-034**: The system MUST NOT overflow horizontally at a viewport of 390 pixels and at a viewport of 1440 pixels; only code panes with monospace content MAY scroll horizontally.
- **FR-035**: The system MUST target the WCAG 2.2 level AA, and the automated accessibility scan MUST report zero critical and zero serious violations on every page of the feature.
- **FR-036**: The system MUST honour the preference for reduced motion by disabling the non-essential transitions and the automatic playback animation.
- **FR-037**: The system MUST NOT place any secret in the URL, in the client bundle or in the published artifacts, and the only state the URL carries is the scenario identifier and harmless view preferences.
- **FR-038**: The system MUST reject a bundle whose file digest does not match the digest declared in its manifest, showing an explicit integrity error and rendering no partial result.
- **FR-039**: The system MUST label a bundle whose snapshot hash differs from the hash of the published ledger as having a stale provenance, and MUST NOT offer it for comparison as the same snapshot.
- **FR-040**: The system MUST show an explanatory message and disable the playback when the bundle declares a model profile or a capture kind the interface does not support, and MUST NOT substitute a fabricated result.
- **FR-041**: The system MUST render an empty state with a link back to the catalog when the bundle carries no event.
- **FR-042**: The system MUST keep a provider failure local to the panel that needs it, and MUST NOT invent a conclusion to replace it.
- **FR-043**: The system MUST consume the published JSON schemas and the recorded artifacts as the only source of truth for the replay, and MUST NOT reimplement in the browser any domain rule of verification, calculation or policy.
- **FR-044**: The system MUST keep the Python core the authority for verdicts, amounts and policy, and MUST only format values that the published artifacts already carry.
- **FR-045**: The system MUST validate every artifact against the published schema version before rendering it, and MUST refuse an artifact whose schema version it does not know.

### Key Entities *(include if feature involves data)*

- **Scenario**: a curated case of the public dataset with an identifier, a name, the question, the concepts it demonstrates, the data origin, the status, the difficulty and the identifiers of the rows it involves. It is the entry the visitor chooses and the key of the published artifacts.
- **ReplayBundle**: the immutable published package of one recorded execution: the schema version, the replay identifier, the capture kind, the capture timestamp, the scenario identifier, the snapshot hash, the code commit hash, the model profile, the optional prompt hash, policy version and redaction version, the final result and the ordered list of events. It also carries the digest of each file, which the interface uses to prove integrity.
- **TraceEvent**: one observable step of the recorded execution: the schema version, the run identifier, the monotonic sequence number, the timestamp, the event type, the span identifier, the parent span identifier, the payload, the snapshot hash and the mode. The span tree, the timeline and the evidence panel are all projections of the ordered events.
- **Evidence**: one source that supports a claim: the stable identifier, the source type among SQL row, ledger API, policy chunk, exchange rate, calculation and case, the tool that produced it, the origin reference, the sanitized content and the retrieval timestamp. It is the only thing a claim may point to.
- **Claim**: one statement of the answer: the identifier, the text, the kind among fact, numeric, policy and inference, and the list of evidence identifiers it cites.
- **Verdict**: the verification decision about one claim: the claim it refers to, the label among supported, contradicted and not enough evidence, the method among NLI, numeric, rule and none, the evidence identifiers used and the optional note. It is produced by the Python core and only displayed.
- **LedgerRow**: one row of the simulated payment ledger: the transaction identifier, the account identifier, the amount with its currency, the date, the type, the status, the counterparty, the provider, the related refund and dispute identifiers, and the flag that says the recorded run read it.
- **ArchitectureNode**: one subsystem of the system: the identifier, the label, the description, the repository module it maps to, the decision records that justify it and the links shown in the diagram and in the engineering drawer.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A visitor with no key and no account reaches the first visible result of a recorded case in at most 60 seconds from the landing page, measured with an automated end-to-end run.
- **SC-002**: 100% of the automated end-to-end runs that open and play a replay record zero requests to a host outside the static origin, asserted for every scenario under test.
- **SC-003**: The replay page reaches a largest contentful paint under 2.5 seconds and a first contentful paint under 1.8 seconds on a throttled mid-range connection, measured on the deployed static site.
- **SC-004**: The compressed payload of one scenario, with the events, the result and the ledger rows, stays under 400 kilobytes.
- **SC-005**: 100% of the claims displayed for S01 cite at least one evidence identifier that exists in the published artifact, checked automatically against the artifact.
- **SC-006**: The word "live" appears zero times as the mode label of any replay page, checked automatically across every published scenario.
- **SC-007**: The accessibility scan reports zero critical and zero serious violations on all six pages of the feature, at 390 and 1440 pixels, and the full flow is operable with the keyboard alone.
- **SC-008**: No page of the feature reports a horizontal overflow, with the document width at most one pixel larger than the viewport width, at 390, 768 and 1440 pixels.
- **SC-009**: Two hundred randomized seeks over the S01 events produce the same rendered state for the same event index in 100% of the cases.
- **SC-010**: The ledger table with 1000 rows answers a sort or a filter in under 200 milliseconds and becomes usable in under one second on a mid-range laptop.
- **SC-011**: With the preference for reduced motion active, the automatic playback animation does not start and every non-essential transition is disabled.
- **SC-012**: The bundle digest shown on the provenance panel equals the digest that the Python loader computes for the same artifact, for 100% of the published scenarios.
- **SC-013**: Every event of the S01 bundle is rendered in the timeline, with the count of the bundle matching the count of the rendered rows.
- **SC-014**: The whole visitor journey of the feature, from the catalog to the architecture links, is covered by automated end-to-end tests that pass on Chromium and on WebKit, with at least eight distinct test cases.
- **SC-015**: The first visitor can complete the curated case without reading any documentation and without entering any credential, confirmed by the automated journey of SC-001.

## Assumptions

- The visitors are technical reviewers who want to see how a financial investigation is justified, and they arrive on a desktop or a modern phone with a current browser.
- The public dataset is simulated and already published in the repository, so the replay needs no live data source and no backend.
- The recorded artifacts of the curated scenarios exist or can be regenerated by the capture script from the repository, with the scripted model and the recorded exchange rate.
- The Python core stays the authority: the interface renders the published verdicts and amounts and never decides whether a number or a claim is right.
- The site is published as a static export behind a content delivery network, so the only network requests are for the static assets and the published artifacts.
- The browser is allowed to store harmless view preferences, such as the last visited tab or the theme, and nothing else.
- The visual design follows the design package: a calm neutral palette, semantic colors only for real verification states, monospace for identifiers and code, and a 4 pixel spacing scale.
- Automated accessibility coverage does not replace the manual pass with a screen reader and a keyboard, which is part of the acceptance of the feature.
- The capture of a real model run for the curated scenarios is out of scope of this feature: the published bundles of this slice are deterministic recordings, labelled as such.
