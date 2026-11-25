---
type: adr
status: accepted
date: 2026-11-25
---

# ADR-100: The guide of the cold start is data that names regions of the reader

Status: accepted. Date: 2026-11-25.

## Context

The recording of a case and the reader of the recording exist, and nothing told a first-time
visitor where to start or what the trace means. The milestone of
[specs/007](../../specs/007-r1-cold-start-guided-replay/spec.md) is the guided cold start: the path
that takes a visitor who knows nothing about the repository to one resolved case, in steps, with no
key and no network.

The path could have been written as a page of its own, with the steps drawn as code. A path written
as code can promise anything and no test can read it, and a path that draws the reader is a second
reader of the same recording.

## Decision

**The guide of the cold start is data that names regions of the reader, the guide adds no verdict
of its own, the guided path asks no provider and no key, and the three minutes of the design
package stays a hypothesis until a consented measurement exists.**

### The guide is data

The steps of the cold start live in `apps/web/lib/replay/guide.ts` as a list of values: the region
of the reader each step names, the sentence that explains it and the kind of the step. The test of
the guide reads the list without a browser and refuses a step that names no region of the reader, a
last step that carries no limitation, a guide that does not name the capture it walks and a step
that states a verdict the bundle does not carry.

### The guide names regions and never owns the layout

A step names a region of the reader, and the reader is the one that shows the region: the regions
of the tabs are the tabs of the reader, and the other regions are places of the page of the reader.
The component of the tour asks the reader to show a region and never draws the reader, because a
tour that owned the layout would be a second reader, and two readers of the same recording would
disagree one day.

### The guide adds no verdict of its own

The sentences of the steps explain what the reader shows, and the decision of the case is the
decision the recording carries. The step of the decision states the action it states as a field, so
the test compares the stated action with the recommended action of the bundle, and a guide that
states a verdict the bundle does not carry is refused.

### The guided path asks no provider and no key

The path reads the published artifacts of the site and nothing else. The end to end test of the
path watches every request of the browser and refuses a request that leaves the origin of the site,
and it refuses a dialog, a field or a sentence that asks for a key.

### The three minutes stays a hypothesis

The design package says a visitor understands one case in three minutes. No consented measurement
of a visitor exists, so the three minutes is a hypothesis of the package and not a number of the
repository, and this record refuses to publish it as a measurement.

## Consequences

- The guide of the scenario S01 is data, and the test of the guide checks its promises without a
  browser.
- The reader of the recording carries the anchors of the regions of the guide, and the component of
  the tour draws the steps over the reader.
- The catalog of the recorded demo offers the guided path, and the path opens the scenario S01 with
  no request to the backend.
- The controls of the path are reachable with the keyboard and are never smaller than 44 pixels, so
  the entrance works for everyone who arrives.
- A new scenario that wants a guided path adds its guide to the data, and the same tests check it.

## Links

- [the specification of the milestone](../../specs/007-r1-cold-start-guided-replay/spec.md)
- [ADR-042, the site of the demo serves the published artifacts](ADR-042-the-site-of-the-demo-serves-the-published-artifacts.md)
- [ADR-074, a case ends in a decision and the decision belongs to the code](ADR-074-a-case-ends-in-a-decision-and-the-decision-belongs-to-the-code.md)
- [ADR-075, the site publishes two catalogs](ADR-075-the-site-publishes-two-catalogs-and-each-bundle-declares-the-one-it-belongs-to.md)
