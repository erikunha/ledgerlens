---
type: adr
status: accepted
date: 2026-11-22
---

# ADR-046: The architecture tour of the public site

Status: accepted. Date: 2026-11-22.

## Context

The release R1 of LedgerLens is a static export of Next.js that plays a recorded investigation to
any visitor, with no key, no account and no call to a model provider (ADR-040, ADR-042, ADR-043).
The repository holds forty five decision records in `docs/decisions/`, and the site holds five
rooms: the landing page, the catalog of the scenarios, the replay of a scenario, the live mode and
the sandbox of the visitor.

The user story 5 of the plan of the release is the only one that was never built. It is the tour of
the architecture: a diagram with the subsystems of the system, and a link from every node to the
exact module in the repository and to the record that explains why the module exists. The tasks of
the plan that describe it are T071 to T077 of `specs/001-r1-public-replay/tasks.md`, and ADR-043
named the whole group as the debt of this milestone.

The facts of the repository decide the shape of this milestone, and every fact below was measured,
not assumed.

**The route of a scenario is `/replay/scenario/<id>`, and the tasks of the plan name a route that
does not exist.** The folder `apps/web/app/(public)/demo/` is not in the tree. The file of the
route is `apps/web/app/(public)/replay/scenario/[scenario]/page.tsx`, it is a server component of
the static export, and it reads the card of the scenario from the published catalog with
`readPublishedCatalog` of `apps/web/lib/replay/catalog.ts`. The tasks T070 and T077 still name the
old path, and the path of the task T077 has to be corrected before the work starts.

**The drawer of a tool call was never built.** T048 is open, and the folder
`apps/web/features/agent-trace/` holds `TraceTimeline.tsx` and `TraceTree.tsx` and nothing else.
Two more tasks of the plan are marked as delivered and their files are not in the tree either: the
stepper of T047 (`RunStepper.tsx`) and the live region of T050 (`LiveRegion.tsx`). None of the three
is in the scope of this milestone, and this ADR says below whether the drawer of the engineering
tour waits for T048. It does not.

**ADR-041 decided that the rendered file of an interactive diagram does not live in the
repository.** The tool that renders the diagram of the live mode weighs about 820 KB and carries
em dashes and en dashes inside the template of its own viewer, so the repository commits the typed
source of the diagram and nothing else. The page of the architecture is a page of the site and it
cannot commit a rendered file of a diagram either, so this ADR has to say what the diagram of the
page is, and it has to say it without contradicting ADR-041.

**The ref of the links was measured, and no branch of the repository answers it today.** The
repository has two branches and no tag. The branch `main` is an ancestor of `feature/v3` and holds
ten of the forty five records (ADR-001 to ADR-010), so three of the six records this page has to
cite are not on `main` today. The published artifacts carry one commit, the `code_sha` of the
capture, `9dc3af946b223496c7ed2e897b1e4152bbf9234f`, and that commit holds seventeen of the
forty five records (ADR-001 to ADR-017), so a link pinned to it breaks for the record of the trace
and for the record of the scoped ledger. A link to a branch is a link that ages, and a link to a
commit that the page itself carries is a link that never moves. The decision below says which one
the page uses and why.

**The fence of the network is drawn already.** `apps/web/lib/api/client.ts` is the transport of
the live mode and of the sandbox, and it is the only module of the frontend that talks to the
backend. The recorded demo reads the published artifacts of its own origin and it calls nobody
(ADR-042, ADR-043). The page of the architecture belongs to the recorded demo, so it calls nobody
either.

## Decision

**The page of the architecture is `/engineering`, it is static and public, and it is built from a
typed source that lives in the repository.** The seven decisions below are the whole of it.

### 1. The format of the diagram on the page

**The typed source of the nodes is `apps/web/features/architecture/nodes.ts`, a module of the
frontend, and it is the ONE source of the content of the page.** It holds a readonly array of six
nodes, and every word the page shows about a subsystem is a word of that array.

**The diagram is an inline SVG drawn by the frontend, with fixed coordinates, and it is built by a
pure function of the array.** The picture measures nothing, it reads no clock, it draws no random
number, it has no transition and no animation, and it adds no dependency to the frontend. There is
no rendered file of the diagram in the repository and there is no build step that writes one.

**The accessible list is the twin of the picture, not a second copy of it.** It is rendered from the
same array, by the same component, it is always present in the page, and it is never behind a
toggle. There is never a second file with the content of a node, and a test proves that the picture
and the list carry the same six labels in the same order.

**ADR-041 is respected and not revised.** The rule of ADR-041 is that the typed source of a
diagram is committed and the rendered file is not, and that the tool that renders it is not a
dependency of the repository. This page commits the typed source and renders it in the browser,
which is the same rule and not an exception to it. The JSON of `docs/diagrams/live-mode.architecture.json`
is NOT read by the site: it is the source of the diagram of the live mode, the schema of the tool of
ADR-041, and this page is the tour of the subsystems of the recorded demo.

### 2. The target of the links to the code

**The base of every link to the code is
`https://github.com/erikunha/ledgerlens/blob/<ref>/<path>`, and `<ref>` is the full commit of the
checkout the site was built from.** The commit is read at build time by
`readRepositoryMeta` of `apps/web/lib/repository.ts`, which runs `git rev-parse HEAD` in the root
of the repository, the same way `code_sha` of `scripts/capture_replay.py` does today. Nobody
writes the commit by hand, and the build fails with a readable reason when the answer is not a
commit of forty lowercase hexadecimal characters.

**The reasons, in the order that they decided the matter:**

- **A commit never ages.** The file that the link opens is exactly the file that the sentence of
  the node describes, because both were written from the same tree. A link to a branch shows the
  code of today, and the sentence of the node was written for the code of the day the page was
  built.
- **A commit survives the branch.** The release merges the branch and the branch may be deleted
  afterwards, and every link the site ever served keeps opening the tree it described.
- **A branch is wrong today, and it was measured.** The branch `main` holds ten of the forty five
  records, so three of the six links of this page would answer 404 on the day the page is built.
- **The commit of the capture is wrong too, and it was measured.** The `code_sha` of the published
  artifacts is `9dc3af946b223496c7ed2e897b1e4152bbf9234f`, and that commit holds seventeen of the
  forty five records: a link pinned to it breaks for the record of the trace and for the record of
  the scoped ledger, because those two records were written after the capture.
- **A hand written commit is a constant that is wrong one day.** The alternative of pinning the
  commit in the source means that a release has to remember to update it, and a constant that a
  human updates is a constant that drifts.

**The page says which commit it describes.** The footer of the page carries the commit in full, so
a reader who follows a link and sees a file knows which tree the sentence was written for.

### 3. The target of the links to the records

**A record is reached with the same kind of URL: the base of the blob, the commit, and the path of
the file of the record in `docs/decisions/`.** The page shows the number and the title of the
record and the link opens the file of the record on GitHub, where the Markdown is rendered.

**The site does not copy the records.** A copy is a second source that drifts, and the rule of
ADR-042 is that the repository publishes the artifacts in one place and the site reads them there.
A record is a document of the repository, written for the reader of the repository, and the page is
a reader of the repository and not a mirror of it. The site would publish forty five documents it
does not own, and the second copy would answer with a record that is not the record of the
repository.

**The node carries the number, the title and the path of the record, and a test proves that the
three agree.** The number is the beginning of the path, the path exists in the tree, and the title
is the title of the file of the record, word for word. A record that is renamed breaks the gate and
not the page.

### 4. The engineering drawer

**The drawer lives in `apps/web/features/architecture/EngineeringDrawer.tsx` and it is built on the
`Sheet` primitive of the design system.** The primitive is a Radix dialog, so the drawer carries
`role="dialog"` and `aria-modal="true"`, the focus is trapped while it is open, the Escape key
closes it, and the focus returns to the control that opened it. The trigger keeps a reference to
itself and takes the focus back when the drawer closes, which is the rule that the user story 6 of
the plan states for a drawer.

**Two controls open it, and both open the same drawer.**

- The page of the architecture opens it with the node the visitor chose, so the drawer starts with
  the summary of that node and carries the three subsystems of the plan.
- The replay opens it from the section of the calls of the tools, in the tab of the execution. The
  drawer explains the guard, the arithmetic and the verification and links to the module of each
  one, which is what the user story 5 asks for.

**The drawer takes the context it was opened with, and it says what that context is.** The context
is a node of the architecture, and the drawer names it in its first sentence. When the drawer is
opened from the replay and no call is chosen, it says in words that it is not tied to one call,
because a drawer that pretends to be about a call it does not name is a drawer that lies.

**The drawer is born independent of T048 and T048 is NOT a prerequisite of this milestone.** The
drawer of the engineering tour is a component of its own, it renders from the same array as the
picture, and it takes a context that is optional. The drawer of a tool call (T048) is a different
thing: it shows the arguments and the output of one call of the recording. When T048 is built, it
may open the engineering drawer with the context of its call, and this milestone does not wait for
that. The consequence for the tasks: T077 does not depend on T048, and T048 stays open with the
work it names.

**The drawer never invents a sentence.** Every sentence it shows is the summary of a node of the
array, and every link it shows is a link built by the same builder that the picture uses.

### 5. The accessibility

**The contract of the page is the following, and the suite of the milestone proves it.**

- **The outline of the headings never skips a level.** The page carries one `h1`, the sections
  carry `h2`, the nodes carry `h3`, and nothing between them.
- **Every node of the picture is reachable with the keyboard, is activated with the Enter key and
  the Space key, and carries a visible text that names the subsystem.** The nodes of the picture
  are anchors of the SVG with an `href`, and an anchor with an `href` is in the tab order. The text
  of the node is the name of the subsystem, drawn in the picture, and the anchor carries a title
  with the sentence of the node.
- **Every node of the picture links to its module AND to at least one record**, which is what
  FR-029 asks for. The picture draws two anchors per node: the first opens the module, the second
  opens the number of the record.
- **The picture never animates.** It has no transition, no animation and no layout that depends on
  a measurement, so the preference for reduced motion has nothing to switch off in it and the
  picture is legible as a static picture in every case. The rule of `apps/web/app/globals.css`,
  which turns every transition off under the preference, keeps its place and covers the rest of
  the site.
- **The list of the fallback is always present and always navigable with the keyboard.** It is a
  list of the six nodes, each one a heading, a sentence and two links, and every link of it is a
  real anchor with a visible text.
- **The state is never only a colour and a control is never disabled.** The chosen node of the
  picture carries a mark that is not a tint, the same way the chosen span of the tree of the
  replay carries a border and a heavier name.

**The cost of the twin is named here.** The picture and the list carry the same six subsystems, so
a reader of a screen reader hears them twice. The price is paid because FR-029 asks for a
clickable diagram and the task T073 asks for the accessible list, and both are wanted by the
plan. The two are rendered from the same array, so they cannot disagree about a subsystem, and the
axe scan of the milestone (T079) has the last word on the duplication.

### 6. The limit of the page

**The page is static and public, and it reads its content at build time.** The data of the nodes
is compiled into the export by the compiler, the commit is read from the checkout while the export
is built, and the page makes no request of its own at run time.

**The page calls nobody.** It imports nothing from `apps/web/lib/api/client.ts` and nothing from
`apps/web/lib/api/live.ts`, and it calls no `fetch`. The only network code of the frontend lives
in `lib/api/`, and the page of the architecture is not part of it. A test reads the graph of the
modules of the page and refuses an import of the transport or a call of `fetch`.

**The page asks for nothing.** No key, no account, no login, no cookie and no query string. The
whole of the state of the visit is in the path of the page, and the path carries nothing else.

**The page invents no text.** Every sentence is written in the repository, in the array of the
nodes, and it is reviewed like any other text of the repository. There is no model in the page and
no sentence that a model wrote, and the page never computes a value: it shows a path, a number, a
title and a sentence, and nothing else.

### 7. The list of the nodes

**The page carries the six subsystems that the user story 5 names, and every path and every record
of this table exists in the tree of the repository.** The table was checked against the files of
the repository before this ADR was written.

| node | module | record | what it does, in one sentence |
| --- | --- | --- | --- |
| Query guard | `ledgerlens/tools/sql_guard.py` | ADR-005 "Text-to-SQL with a guard and a read-only connection" | The guard that only lets a query through when it is one single read of the tables of the ledger, so the model cannot write, cannot drop and cannot read the internal tables. |
| Scoped ledger copy | `ledgerlens/api/accounts.py` | ADR-038 "The live run reads the ledger of the branch of the visitor" and ADR-045 "The ledger of the recorded demo is a published artifact of the site" | The copy of the ledger that holds only the rows of one account, so a query cannot return the rows of another customer. |
| Decimal calculator | `ledgerlens/tools/calculator.py` | ADR-001 "Domain, payment investigation" and ADR-007 "Answer verification with an NLI model" | The arithmetic of the money, done with decimal numbers and named operations, so that a rate never becomes a rounding error. |
| Deterministic simulator | `ledgerlens/sim/pipeline.py` | ADR-009 "Public data first, simulation only for the gaps" | The builder of the ledger of the run, with a fixed seed and with the real public data where it exists, so the same command always writes the same rows. |
| Verifier | `ledgerlens/verify/checks.py` | ADR-007 "Answer verification with an NLI model" | The step that gives every claim of the answer a verdict, so a sentence that the evidence does not back never reaches the visitor as true. |
| Trace recorder | `ledgerlens/observability/trace.py` | ADR-013 "The public trace is a versioned contract" | The recorder of every run of the agent, which writes the public events of `ledgerlens/observability/trace_event.py` that the recording of this site replays. |

**The order of the nodes is the order of the run.** The guard reads the ledger, the copy of the
ledger decides what the guard may read, the simulator builds the ledger, the calculator does the
arithmetic on what it read, the verifier checks what the answer said, and the recorder writes down
what happened. The picture draws the six in that order, and the list of the fallback lists them in
that order.

**The three subsystems that the drawer explains are the first, the third and the fifth.** The guard,
the arithmetic and the verification are the three that the user story 5 names, and the drawer shows
the summary and the module of those three, with the record of each one beside it.

## The interface of the milestone

The files of the milestone, with the names they export:

| file | what it is |
| --- | --- |
| `apps/web/features/architecture/nodes.ts` | new: the typed source of the six nodes, `ArchitectureRecord`, `ArchitectureNode`, `ARCHITECTURE_NODES` |
| `apps/web/features/architecture/ArchitectureDiagram.tsx` | new: the picture and the accessible list, `ArchitectureDiagramProps`, `ArchitectureDiagram`, `ArchitectureNodeListProps`, `ArchitectureNodeList` |
| `apps/web/features/architecture/ArchitectureNodeCard.tsx` | new: the card of one node, `ArchitectureNodeCardProps`, `ArchitectureNodeCard` |
| `apps/web/features/architecture/AdrLink.tsx` | new: the link to one record, `AdrLinkProps`, `AdrLink` |
| `apps/web/features/architecture/SourceLink.tsx` | new: the link to one module, `SourceLinkProps`, `SourceLink` |
| `apps/web/features/architecture/EngineeringDrawer.tsx` | new: the drawer, `EngineeringDrawerProps`, `EngineeringDrawer` |
| `apps/web/lib/repository.ts` | new: the repository and its commit, `REPOSITORY_URL`, `REPOSITORY_BLOB_BASE`, `RepositoryMeta`, `readRepositoryMeta`, `sourceUrlOf`, `recordUrlOf` |
| `apps/web/app/(public)/engineering/page.tsx` | new: the route of the tour, and the URL of the page is `/engineering` |
| `apps/web/app/(public)/replay/scenario/[scenario]/page.tsx` | changed: the route reads the commit and hands it to the reader |
| `apps/web/features/replay/ReplayViewer.tsx` | changed: the props of the reader gain the commit, and the reader mounts the drawer |
| `apps/web/tests/unit/features/architecture-nodes.test.ts` | new: the paths of the nodes exist, the records agree with their files, the picture and the list carry the same nodes |
| `apps/web/tests/e2e/architecture.spec.ts` | new: the end to end suite of the page and of the drawer |

The shape of the data of the nodes:

```ts
export interface ArchitectureRecord {
  readonly number: string;
  readonly title: string;
  readonly path: string;
}

export interface ArchitectureNode {
  readonly id: string;
  readonly label: string;
  readonly summary: string;
  readonly module: string;
  readonly records: readonly ArchitectureRecord[];
}

export const ARCHITECTURE_NODES: readonly ArchitectureNode[];
```

The rules of the shape:

- **`id` is the identifier of the node and it never changes.** It is the key of the list, the name
  of the shape of the picture and the anchor of the deep link of the node.
- **`label` is the name of the subsystem, and it is what the visitor reads.** It is short, it is
  the same word in the picture and in the list, and it is the visible text of the anchor of the
  picture.
- **`summary` is one plain sentence.** It is what the drawer shows, it is the title of the anchor
  of the picture, and it is never longer than the sentence that the reader needs.
- **`module` is the path of the file in the repository, from the root of the repository.** It is
  never a URL, because the URL needs the commit and the commit belongs to the build.
- **`records` holds at least one record.** A node without a record is a subsystem the repository
  cannot justify, and the test refuses it.

The shape of the repository:

```ts
export const REPOSITORY_URL = "https://github.com/erikunha/ledgerlens";
export const REPOSITORY_BLOB_BASE = `${REPOSITORY_URL}/blob`;

export interface RepositoryMeta {
  readonly commit: string;
  readonly dirty: boolean;
}

export function readRepositoryMeta(root?: string): RepositoryMeta;
export function sourceUrlOf(path: string, commit: string): string;
export function recordUrlOf(path: string, commit: string): string;
```

The rules of the repository:

- **`readRepositoryMeta` runs at build time and never at run time.** It reads the commit of the
  checkout with `git rev-parse HEAD` and it reads whether the tree has changes that are not
  committed with `git status --porcelain`. A checkout without git, or an answer that is not a
  commit of forty lowercase hexadecimal characters, stops the build with a reason a reader of the
  build can act on, because a page whose links point at nothing is worse than a build that fails.
- **`sourceUrlOf` and `recordUrlOf` build the same URL.** The first opens a module and the second
  opens a record, and the two differ only in the path they carry. There is one base and one
  builder of the path, so a link of the picture and a link of the drawer cannot be spelled two
  ways.
- **`dirty` is said out loud.** When the tree was not clean, the footer of the page says that the
  site was built from a working tree with changes that are not committed. A page that describes a
  tree it does not match is a page that lies.

## What the tasks of the plan must say

| task | what it says today | what this milestone builds |
| --- | --- | --- |
| T071 | the end to end suite in `apps/web/tests/e2e/architecture.spec.ts` | the same path, and the suite covers the page, the links, the drawer and the keyboard |
| T072 | the nodes in `apps/web/features/architecture/nodes.ts` | the same path, and the shape above |
| T073 | the diagram in `apps/web/features/architecture/ArchitectureDiagram.tsx` with the accessible list fallback | the same path, and the list is the twin of the picture |
| T074 | the card in `apps/web/features/architecture/ArchitectureNodeCard.tsx` | the same path |
| T075 | the links in `AdrLink.tsx` and `SourceLink.tsx` | the same paths, and the base of the links lives in `lib/repository.ts` and in no other place |
| T076 | the page in `apps/web/app/(public)/engineering/page.tsx` | the same path, and the URL of the page is `/engineering` |
| T077 | the drawer in `apps/web/app/(public)/demo/[scenario]/page.tsx` | the path is wrong: the route of a scenario is `apps/web/app/(public)/replay/scenario/[scenario]/page.tsx`, and the drawer itself lives in `apps/web/features/architecture/EngineeringDrawer.tsx` |

**T048 is not a prerequisite of T077, and the two tasks do not share a file.** The drawer of a
tool call shows the arguments and the output of one call, and the drawer of the engineering tour
explains three subsystems. They meet only when T048 opens the drawer of the tour with the context
of its call, and that meeting is not a reason to wait.

**The gate of the frontend proves that the export holds the page.** `scripts/gate_web.sh` checks
that the export holds `engineering.html`, that the page carries a heading and that it carries the
six labels of the nodes, in the same way `scripts/check_export_pages.mjs` checks the page of the
catalog and the page of every scenario.

## What this milestone does not have

- **No rendered file of a diagram in the repository.** The picture is drawn by the frontend at run
  time from the typed source, and the tool of ADR-041 is not a dependency of the frontend.
- **No copy of a record and no copy of a module on the site.** The page links to the repository and
  it does not mirror it.
- **No request at run time.** The page calls nobody, asks for no key and reads no artifact of the
  network.
- **No text that a model wrote and no value that the browser computed.** The sentences are in the
  repository and the page shows them.
- **No change of the replay, of the live mode, of the sandbox and of the Python of the domain.**
  The milestone adds a route, a feature folder, one module of the library of the frontend and one
  field in the props of the reader.
- **No wait for T048, T047 and T050.** The three tasks stay open with the work they name.
- **No change of the validators of the published artifacts.** The page reads nothing of the
  artifacts of the recording.

## What it costs

The frontend gains one feature folder, one module of the library, one route and one field in the
props of the reader of the replay. The repository gains one decision record, and the page of the
tour can cite one record more than it could cite yesterday.

The cost that is not a number is the duplication of the six subsystems between the picture and the
list, and the commit that the page carries, which is a promise that the links of the page will
keep opening the tree they describe.

## Alternatives considered

- **(a) Commit the rendered HTML of the diagram, as the tool of ADR-041 renders it.** It breaks
  the rule of the language of the repository, it puts a large generated file in the history of a
  public repository, and it makes the frontend depend on a tool that lives outside it. ADR-041
  refused this already.
- **(b) Draw the diagram in the browser with a library of graphs.** It adds a dependency, it
  measures the text in the browser, and the layout of the picture would depend on a font that the
  visitor may not have. The six subsystems are a chain, and a chain is six boxes and five arrows.
- **(c) Read the JSON of `docs/diagrams/live-mode.architecture.json` and turn it into the nodes.**
  The JSON is the schema of the tool of ADR-041 and it holds the components of the live mode, with
  their positions and their boundaries. It is not the source of the six subsystems of the tour,
  and the site would have to read a file of `docs/` that is not published in the export, which
  would add a second copy to the build.
- **(d) Link to the branch `main`.** It is the branch the public repository publishes and it never
  disappears, but it is a link that ages and, measured today, it holds ten of the forty five
  records, so three of the six links of the page would answer 404 on the day the page is built.
- **(e) Link to the branch `feature/v3`.** It holds every path of the page today, but it is the
  branch of a release: it is merged and it may be deleted, and a link to it is a link that ages
  exactly like the link to `main`.
- **(f) Link to the `code_sha` of the published artifacts.** It is the only commit the site already
  carries, and it is the wrong one: it is the commit of the capture, and it holds seventeen of the
  forty five records. The page would link to a tree that predates half of the records it cites.
- **(g) Pin the commit in the source of the nodes.** It is immutable, but it is a constant that a
  release has to remember to update, and a constant that a human updates is a constant that is
  wrong one day.
- **(h) Tag the release and link to the tag.** A tag is immutable and it survives the branch, and
  it is the practice of most repositories. It was refused for one measured reason: the repository
  has no tag today, so the first link of the first page would answer 404 until the release creates
  one, and a ceremony that every release has to remember is a ceremony that is skipped.
- **(i) Copy the records into the site.** It would make the page readable without leaving it, but
  a copy is a second source that drifts, and ADR-042 refused the second copy of the artifacts for
  exactly this reason.
- **(j) Make the drawer of the engineering tour wait for the drawer of a tool call (T048).** It
  would tie the tour to a task of another user story, and the tour does not need it: the drawer
  renders from the same array as the picture and its context is optional.

## Consequences

A visitor of the site can open the tour of the architecture from the replay, see the six
subsystems of the system, and follow every node to the exact module in the repository and to the
record that explains why the module exists. The links are immutable: they open the tree the page
describes, today and in five years.

The picture and the list are the same six subsystems, drawn from one array, so the page cannot
show a subsystem that the list does not show, and the test proves it on every change of the
frontend.

The drawer of the engineering tour explains the guard, the arithmetic and the verification in
plain language, with a link to the module of each one, and it waits for nothing: it is a component
of its own, and the drawer of a tool call may open it later.

The page calls nobody. It is a static export like the rest of the site, it reads its content at
build time, and the only thing it asks of the reader is that the reader follows a link.
