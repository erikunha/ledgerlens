---
type: adr
status: accepted
date: 2026-11-22
---

# ADR-051: The structural baseline of the pages and the paint of the replay

Status: accepted. Date: 2026-11-22.

## Context

The release R1 publishes a static site that plays a recorded investigation to any visitor, with no key, no account and
no call to a model provider (ADR-042, ADR-043). Two tasks of the plan of the release are still open, and both of them
are about the promise of the speed of the site:

- **T087** asks for "the visual baselines at 390, 768 and 1440 pixels in `apps/web/tests/e2e/screenshots.spec.ts`".
- **T089** asks for "the payload and the paint measurement in `scripts/measure_replay_budget.py` with the thresholds of
  the success criteria".

The two success criteria behind them are written down:

- **SC-003 of `specs/001-r1-public-replay/spec.md`**: "The replay page reaches a largest contentful paint under 2.5
  seconds and a first contentful paint under 1.8 seconds on a throttled mid-range connection, measured on the deployed
  static site."
- **SC-004 of the same file**: "The compressed payload of one scenario, with the events, the result and the ledger rows,
  stays under 400 kilobytes."

SC-004 is already measured: `scripts/measure_replay_budget.py` reads the published artifacts, compresses them and
refuses when one scenario is above the budget. The script is a step of `scripts/gate.sh`, and the gate of the Python
side runs in the first job of the continuous integration, the job that has no Node and no browser.

Every fact below was measured in the tree of the repository, not assumed.

### The trap of the visual baseline

**The site has no font of its own.** `apps/web/app/globals.css` declares the two families of the design package as
custom properties built from the stack of the system (lines 66 to 68):

```css
--ll-font-sans: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif;
--ll-font-mono: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, Liberation Mono, monospace;
```

**The folder of the assets of the site holds no font file.** `apps/web/public/` holds one folder, `replay/`, which
carries the published artifacts of the recording. The layout of the site says why in its own docstring: "Why there is
no web font: the design tokens ask for the stacks of the platform, and a font file would make the build depend on a
network call for a page that has to work offline."

**The continuous integration runs on Linux.** `.github/workflows/gate.yml` declares two jobs, and both of them run on
`ubuntu-latest`. The first one installs uv and runs `bash scripts/gate.sh`; the second one installs Node 24.22.3 and
runs `bash scripts/gate_web.sh`. The end to end suite of Playwright is not part of either job.

**The consequence is the whole of the problem.** The pixels of a page are the pixels of the font of the machine that
drew them. A baseline of pixels that is committed from a Mac and compared on Linux is a comparison of two different
fonts, and the text of the page is drawn with a different number of glyphs per line, with a different height of the
line and with a different width of the box that holds it. A baseline of pixels can be green on the machine of the
author and red on the machine of the continuous integration, or the other way round, and neither of the two runs says
anything about the code. **A gate that fails on the machine of the continuous integration is not a gate**, and that is
the rule of the house that the quickstart already states about the two gates: "The Node gate is a separate script and
it is not folded into the Python gate, because that one runs in places where Node is absent, and a gate that fails
because a tool is missing is not a gate."

**The layout of the site is, on the other hand, the same everywhere.** The width of a column comes from the grid of
the design package and from the width of the viewport, and not from the glyphs of the font. The box of the catalog of
the scenarios is three columns at the viewport of 1440 pixels and one column at the viewport of 390 pixels, because
the breakpoint of the design package is at 1024 pixels (`apps/web/tailwind.config.ts`, the `screens` of the theme,
and `apps/web/app/page.tsx`, line 35). That decision is the same on every platform, and it is the decision a
regression breaks.

### The promise of the paint and the noise of a shared machine

**SC-003 is a promise about a deployed site on a given connection.** "A number without the conditions under which it
was taken is not a measurement", so the connection, the processor and the page have to be named with the number.

**A wall clock on a shared machine is noisy.** The continuous integration runs on a virtual machine that shares its
processor with the other jobs of the runner, and the local machine runs several projects at the same time. A test that
asserts 2.5 seconds exactly is a test that goes red for reasons that have nothing to do with the code, and a red test
that nobody trusts is worse than no test.

**The paint needs a browser, and the gate of the Python side must not need one.** The first job of the continuous
integration installs no Node, so the arm of the script that the gate calls must never start a browser.

## Decision

**The baseline is a STRUCTURAL one and not a pixel one, and the paint is measured in two layers: a generous bound
that the web suite asserts and the real numbers that are recorded. The eleven decisions below are the whole of it.**

### 1. The baseline compares the structure of the page and its horizontal geometry, and it does not compare the pixels

**The baseline of a page is a file of JSON that holds, for each box of the page, the role of the box, its accessible
name, the title of its first heading, its position and its width, rounded to the whole pixel.** The suite reads the
page, reads the boxes, and compares them with the file. The geometry of the browser is a fractional number, and a
fraction is a number no reviewer can read.

**The boxes are a curated list and not every element of the page.** The list is the one a reviewer reads: the banner,
the main region, the footer, the column of the content, the section of the page, the region of the recording, the row
of the tabs, the panel that is open, the tree of the investigation, the timeline of the recording, the panel of the
ledger, the picture of the architecture and the list of the subsystems. A box that is not in the list is not compared,
and the list is the debt of this record: a new panel of the site is not in the baseline until someone adds it.

**The comparison of the geometry has a tolerance of eight pixels.** A box that moved sideways, a column that appeared
or disappeared and a card that became the whole width are all changes of more than eight pixels. The tolerance is the
room that the platform needs: the width of a scrollbar is fifteen pixels on Linux and zero on the browser of the author,
and the metrics of the system font differ by a few pixels.

**What it catches:**

- a box that moved sideways, or a box that changed its width, because the layout of the site is decided by the grid
  of the design package and not by the font;
- a label that changed, because the accessible name and the title of the box are compared word for word;
- a panel that disappeared or a panel that appeared, because the list of the boxes is compared as a list;
- a page whose order of the panels changed, because the list of the boxes is ordered the way the page is;
- a document that grew sideways, because the width of the document is compared with the width of the viewport.

**What it does NOT catch, and the reason of every one of them:**

- **the vertical position of a box.** The height of a block of text depends on the number of lines the text takes, and
  the number of lines depends on the width of the glyphs of the system font, which is one font on the machine of the
  author and another one on the machine of the continuous integration. A vertical comparison is a comparison of two
  different fonts, which is the trap this record exists to close. The order of the boxes is compared instead, and a
  block that is inserted in the middle of the page changes the order of the boxes that follow it.
- **the height of a box**, for the same reason.
- **the pixels**: the colour, the weight of the type, the rendering of the glyphs and the shadow of a card. The
  baseline is not a picture and it does not pretend to be one.
- **the width of a table.** A table is sized by its content, and the content of a table is text, so the width of a
  table is a measurement of the font. The box that holds the table is compared instead, because the box is sized by
  the layout.
- **a change of the stack of the fonts** that keeps the same metrics. The stack of the fonts is a decision of the
  design package and not a decision of this record.

**How a failure is read by the next person.** The failure names the view, the width, the box, the value that the
baseline holds and the value that the page measured, and it says how far the two are from each other. The next person
opens the page at that width, looks at the box that the failure names, and sees what moved. A failure of the name or
of the title of a box is a change of a word and is read in the diff of the code. A failure of the position is a change
of the layout and is read in the diff of the stylesheet.

### 2. The vertical geometry is left out on purpose, and the scrollbar is hidden on purpose

**The suite hides the scrollbar of the browser and does not compare the vertical geometry of the boxes.** The
scrollbar is furniture of the platform and not of the design: it takes fifteen pixels of the width of the document on
Linux and none on the browser of the author, and a column that is centered moves by eight pixels because of it. The
suite starts Chromium with `--hide-scrollbars`, so the width of the document is the width of the viewport on every
platform.

**The vertical geometry is left out** for the reason named in the decision 1: the height of a block of text is a
measurement of the font of the machine. The record says it out loud instead of hiding it, because a baseline that
does not say what it does not catch is a baseline nobody can trust.

### 3. The pages of the baseline are the home, the recording of `S01` and the tour of the architecture

**The baseline covers four views of three pages:**

| view | route | what it holds |
| --- | --- | --- |
| the home | `/` | the banner, the main, the footer, the column, the region of the three rooms and the three cards |
| the recording of `S01`, the tab of the execution | `/replay/scenario/S01` | the box of the recording, the row of the tabs, the panel of the execution, the stepper, the tree, the timeline and the card of the calls |
| the recording of `S01`, the tab of the ledger | `/replay/scenario/S01` with the tab of the ledger open | the panel of the ledger, the panel of the account, the controls of the order and of the filter and the pagination |
| the tour of the architecture | `/engineering` | the tour, the picture of the diagram and the list of the subsystems |

**Why these pages and why these two tabs.** The home is the door of the site and the first thing a visitor sees. The
tab of the execution is the technical heart of the demonstration and it holds the three panels that the tree, the
timeline and the calls make. The tab of the ledger is the one that shows the rows of the simulated payment ledger and
the controls of the order and of the filter, which are the parts of the recording that a reader of the amounts reads
first. The tour of the architecture is the page that turns a visitor into a reader of the code, and its picture is
the one box of the site whose width is decided by the design package alone.

**Why the catalog of the scenarios is not in the baseline.** The catalog is a list of cards of the same shape as the
three cards of the home, and the home already covers that shape. A baseline that repeats the same shape on another
page buys nothing and doubles the size of the set that is committed to a public repository.

**Why four views and not three.** The tab of the ledger is a different page to the reader of the screen: the panels
that are open are not the same panels, and the baseline of the recording of `S01` has to describe the panel that is
open. The set of the committed baselines is twelve files of JSON, and the size of the set is reported with this record.

### 4. The widths are 390, 768 and 1440 pixels, and the suite sets them itself

**The three widths are the ones the specification names.** SC-008 says that no page of the feature reports a
horizontal overflow "at 390, 768 and 1440 pixels", and SC-007 asks for the accessibility scan at 390 and 1440. The
width of 768 pixels is the breakpoint of the design package (`--ll-breakpoint-md`), the width where the layout of the
site changes from the column of the phone to the layout of the tablet.

**The suite sets the three widths itself, inside the test, and it does not add a project to the configuration.** The
projects of the suite are the ones of the design package, 390 and 1440 pixels, and the file of the baseline sets the
width of the viewport of the browser before it opens the page. Adding a project of 768 pixels to
`apps/web/playwright.config.ts` would have run the thirteen other files of the suite at a third width, and the
configuration of the suite is not a file of this milestone.

**The baseline runs in one project only.** The baseline is the same on every platform and on every engine, so the
suite runs it in the project of Chromium at 1440 pixels and skips the other three. Three widths times four projects
times four views would have been forty-eight runs of the same measurement.

### 5. The pixel baseline is refused, and the reason is named

**The alternative of a pixel baseline is refused in both of its forms.**

- **A pixel baseline committed from the machine of the author.** The pixels of the text of the page are the pixels of
  the font of the machine of the author, and the machine of the continuous integration draws them with another font.
  The baseline would be red on the continuous integration, and the reader of the red run would have to decide that the
  red run is a fault of the machine and not a fault of the code. A gate that is red for a reason that has nothing to
  do with the code is a gate that everybody turns off.
- **A pixel baseline generated inside the image of Playwright on Linux.** The image is `mcr.microsoft.com/playwright`,
  and the repository already builds a Docker image, so the recipe exists. The baseline generated that way is green on
  Linux and only on Linux, because the pixels of the image of Playwright are the pixels of that image. The
  continuous integration would need a job of its own with Docker in it, the job of the end to end suite would have to
  run inside the image, and the author of the repository would have to have the image of Playwright on a machine
  that is not the machine of the continuous integration to write the baseline at all. The baseline would then be
  green in one place and absent in the other, and a baseline that nobody runs is not a gate either.
- **Both of them.** The structural baseline everywhere and the pixel baseline on the platform that generated it. The
  objection of the second form is the same: the pixel half of the set is green in one place and absent in the other.

**The debt of the refusal is named:** the repository does not compare the pixels of the site, and it never will
while the site uses the fonts of the system. A repository that wants to compare the pixels has to publish a font of
its own, and that is a decision of the design package and not of this milestone.

### 6. The paint is measured by an arm that is opt in, and the arm of the gate never starts a browser

**The default arm of `scripts/measure_replay_budget.py` is the payload, and it stays the payload.** The script
continues to read the disk, to compress the published artifacts and to refuse when one scenario is above the budget of
SC-004. It never opens a socket, it never starts a browser and it never needs Node. The first job of the continuous
integration keeps running it exactly as it runs it today.

**The arm of the paint is opt in and it is named `--paint`.** When it is asked for, the script measures the paint of
the recording of `S01` with a browser, it prints the numbers with the conditions under which they were taken, and it
refuses with a readable reason and a non zero exit code when the tool it needs is not there: no Node, no Playwright,
no browser downloaded, no static export built. A missing tool is a refusal with a reason and not a traceback.

**The measurement serves the static export that the repository publishes.** The script serves `apps/web/out` with the
standard library of Python, it opens the page of the recording of `S01` and it reads the paint of the page from the
timeline of the performance of the browser. The number that the arm prints carries the export it measured, so the
next person knows which build the number belongs to.

### 7. The throttling of the paint is named, and the numbers are the ones of a mid-range connection

**The throttling of the measurement is a processor four times slower and a connection of four megabits per second
down, one megabit per second up and one hundred milliseconds of latency.** The numbers are written in the output of
the arm and in the output of the web suite, and they are here:

| what is throttled | the number |
| --- | --- |
| the processor of the machine | four times slower (`Emulation.setCPUThrottlingRate` with the rate 4) |
| the download | 500000 bytes per second, which is four megabits per second |
| the upload | 125000 bytes per second, which is one megabit per second |
| the latency | one hundred milliseconds |

**Why these numbers.** A connection of four megabits per second with one hundred milliseconds of latency is a phone on
a shared mobile network, which is the machine most of the visitors of a public site are on, and it is the middle of
the range: it is faster than a network of the generation before and slower than the network of the office of the
author. The processor four times slower is the same idea applied to the machine: the processor of a laptop of a few
years ago.

**The throttling is the same in the two measurements.** The web suite and the arm of the script apply the same
numbers, so the numbers of the two places can be compared with each other.

### 8. The web suite asserts a generous bound, and the promise of SC-003 is a number that is recorded

**The two layers are two different things and they are both named.**

- **The bound of the suite catches a catastrophic regression.** The web suite asserts that the first contentful paint
  stays under five seconds and that the largest contentful paint stays under eight seconds, with the throttling of
  the decision 7. Those numbers are far above the promise of SC-003 on purpose: a machine that is shared, a container
  and a processor that is four times slower make the wall clock noisy, and a test that goes red for the noise of the
  machine teaches the reader to ignore the test. The bound of the suite catches the regression that matters, which is
  a site that ships a bundle that is ten times too heavy, and it does not catch the millisecond.
- **The promise of SC-003 is the number that is measured and recorded.** The promise is a largest contentful paint
  under 2.5 seconds and a first contentful paint under 1.8 seconds, on the throttled mid-range connection of the
  decision 7, on the deployed static site. The arm of the script prints the numbers it measured, and the person who
  runs the release records them in the quickstart of the feature, which is the place where the results of the gate
  live. The suite does not assert the promise, because the suite does not run on the deployed site and because the
  wall clock of a shared machine is not the clock of the promise.

**The two layers are both in the output of the arm.** The arm prints the numbers, it prints the promise of SC-003
next to them and it says whether the measurement is inside the promise, and it fails only on the bound of the suite,
because a bound that fails on a noisy machine is not a bound.

### 9. The numbers of the paint live in the quickstart of the feature, and the milestone does not write them

**The quickstart of the feature is where the results of the gate live, and the task that writes them belongs to
whoever runs the full gate.** The numbers that this milestone measured are reported to the person who runs the gate,
and that person records them in `specs/001-r1-public-replay/quickstart.md`. This record does not write that file, and
neither does the task list of the feature: the two are the work of the run of the gate, not the work of the code.

### 10. The baseline is committed as a file of JSON that a reviewer can read, and the suite can write it again

**The baseline of each view at each width is a file of JSON under `apps/web/tests/baselines/`.** The set of the
committed files is twelve of them, four views at three widths, and they are written with the two spaces of the
indentation of the repository. A reviewer reads the diff of the files and sees the box that moved, the label that
changed and the width that grew.

**Why one file per view and per width.** The suite runs its tests in parallel, and two tests that wrote the same file
would lose the width of the other one.

**The suite writes the file again when it is asked to.** The environment variable `LEDGERLENS_UPDATE_BASELINES` turns
the comparison into a measurement that is written to the disk, which is how the baseline is refreshed after a change
of the design that a person reviewed. The default is the comparison, because a suite that rewrites the expectation of
its own assertion is a suite that cannot fail.

### 11. The paint is measured in the web suite as well, and the file of the milestone carries the two measurements

**The web suite measures the paint of the recording of `S01` and asserts the bound of the decision 8.** The suite is
the place where the browser is installed, and the measurement of the same page with the same throttling has to be
comparable with the one of the arm of the script.

**The two measurements live in the same file of the end to end suite.** The file is `apps/web/tests/e2e/screenshots.spec.ts`,
the file that the task T087 names, and it carries the two measurements of the rendered page: the structure of the
pages and the paint of the recording. The name of the file is the name of the visual baseline, and the paint is the
other measurement of the same page.

## Consequences

A reviewer of the site can see, in the diff of a change of the frontend, the boxes that moved, the labels that
changed and the widths that grew, at the three widths the specification names, without a single pixel of the machine
of the author being compared with a pixel of the machine of the continuous integration. The gate of the baseline is
green on the machine of the author and on the machine of the continuous integration, because what it compares does not
depend on the machine.

The paint of the recording of `S01` is measured with the conditions written next to it, the promise of SC-003 is
compared with the numbers that were measured, and the suite of the frontend refuses a regression that is big enough
to matter without refusing the noise of a shared machine. The gate of the Python side keeps running without Node and
without a browser, and the arm that measures the paint is opt in and refuses with a reason when the tool is missing.

The costs are named here:

- **The repository does not compare the pixels.** A change of the colour, of the weight of the type or of the shadow
  of a card is not caught by the baseline. The suite of the frontend already checks the state that is never only a
  colour, and the change of a colour is a change that a person reads in the diff.
- **The vertical position of a box is not compared.** A block that is inserted above the other blocks of the page
  moves them down without changing their order, and the baseline does not see it. The change is read in the diff of
  the code.
- **A new panel of the site is not in the baseline until someone adds it.** The list of the boxes is a curation and
  not a rule, and a panel that was added is a panel that no baseline watches.
- **The number of the promise of SC-003 is not asserted by any test.** It is measured, printed and recorded by
  someone, and a regression that eats a quarter of the promise passes the bound of the suite.
- **The measurement of the paint exists in two places.** The arm of the script and the web suite each carry their own
  copy of the measurement of the browser, because the two live in two toolchains, and the throttling is written twice.
  The two copies have to stay the same, and the numbers of the decision 7 are the contract between them.

## What this forbids

- No pixel baseline of the pages, no committed picture of the site, and no comparison of the pixels of the rendering
  on any platform, while the site uses the fonts of the system.
- No vertical comparison of the boxes in the baseline, and no tolerance that hides a change of the layout behind a
  number large enough to accept a different font.
- No project of 768 pixels in the configuration of the suite, and no change of the suite of the other thirteen files
  of the end to end suite for the sake of the baseline.
- No browser, and no Node, in the default arm of `scripts/measure_replay_budget.py`, and no change of
  `scripts/gate.sh` for the sake of the paint.
- No assertion of the promise of SC-003 inside a suite that runs on a machine whose wall clock is not the clock of the
  promise.
- No baseline written by the suite in its default run, and no expectation that a suite rewrites by itself.
- No number of the paint without the conditions under which it was taken written next to it.
