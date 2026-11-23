/**
 * The regression guard of the accessibility of the reader.
 *
 * Why this file exists: the contract of the milestone declares the accessibility of the replay as part of the
 * contract, not as a polish of the end of it, and the review of the milestone found that the whole block of the
 * accessibility had no test at all. Five mutations of that block left the whole suite green: the tree turned into a
 * plain list, the current row of the timeline lost its `aria-current`, a heading jumped a level, the main of the page
 * stopped being a landmark and the footer stopped being one too.
 *
 * Every case here proves ONE rule of that block, and every case can fail. The rules are:
 *
 * 1. the tree of the investigation is a TREE: a tree, tree items with their level, the parents say they are
 *    expanded, one tab stop, and the arrow keys with Home and End walk it;
 * 2. the timeline of the recording is ONE tab stop, the current row carries `aria-current`, and the number of the
 *    event is a cell and not a stop of the keyboard;
 * 3. the outline of the headings never skips a level;
 * 4. the controls of the playback are never `disabled`, and the control that would do nothing carries
 *    `aria-disabled` and a reason a reader can hear;
 * 5. the preference for the reduced motion stops the automatic playback, and the control says why;
 * 6. the skip link moves the FOCUS to the main, and not only the scroll;
 * 7. the shell has one banner, one main and one content information, and the banner carries the name of the site;
 * 8. the state is never only a colour.
 *
 * Rules 1 and 2 are about the tree and the timeline, which the review of the milestone already covers with the
 * `agent-trace.test.tsx` file for the VISIBLE mark; this file covers the SEMANTICS and the KEYBOARD of the same two
 * components.
 *
 * Every case runs with no key and no network: the bundle of the case is the published bundle of the scenario S01,
 * read from the disk of the repository, and the fetch of the runtime is a fake that answers with the same artifacts.
 */

import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TraceTimeline } from "@/features/agent-trace/TraceTimeline";
import { TraceTree } from "@/features/agent-trace/TraceTree";
import { ReplayControls } from "@/features/replay/ReplayControls";
import { ReplayProvider } from "@/features/replay/ReplayProvider";
import { ReplayViewer } from "@/features/replay/ReplayViewer";
import { AppShell } from "@/features/shell/AppShell";
import { loadReplay, type LoadedReplay } from "@/lib/api/replay";
import type { ReplayBundleManifest, ScenarioIndexEntry, TraceEvent } from "@/lib/api/schemas";
import type { TimelineRow, TraceTreeNode } from "@/lib/replay/selectors";

/**
 * Finds the folder of the published bundle of the scenario S01 on the disk.
 *
 * Why the search goes up from the working folder: the artifacts are published in `site/replay` at the root of the
 * repository and copied into `apps/web/public/replay` by the build, and the test must find them in either place.
 */
function findPublishedBundle(): { manifest: string; events: string; provenance: string } {
  const roots: string[] = [];
  let current = process.cwd();
  for (;;) {
    roots.push(current);
    const parent = dirname(current);
    if (parent === current) {
      break;
    }
    current = parent;
  }

  const candidates = [
    ...roots.map((root) => join(root, "public", "replay", "s01")),
    ...roots.map((root) => join(root, "site", "replay", "s01")),
  ];

  for (const folder of candidates) {
    if (!existsSync(join(folder, "events.jsonl"))) {
      continue;
    }
    return {
      manifest: readFileSync(join(folder, "manifest.json"), "utf8"),
      events: readFileSync(join(folder, "events.jsonl"), "utf8"),
      provenance: readFileSync(join(folder, "provenance.json"), "utf8"),
    };
  }
  throw new Error("the published bundle of the scenario S01 was not found on the disk of the repository");
}

/** The published bundle of the scenario S01, read from the disk of the repository. */
const PUBLISHED = findPublishedBundle();

/** The manifest of the published bundle, as `site/replay/s01/manifest.json` holds it. */
const MANIFEST = JSON.parse(PUBLISHED.manifest) as ReplayBundleManifest;

/** The provenance file of the published bundle, as `site/replay/s01/provenance.json` holds it. */
const PROVENANCE = JSON.parse(PUBLISHED.provenance) as Record<string, unknown>;

/** The events of the published recording, in the order of the recording. */
const EVENTS: readonly TraceEvent[] = PUBLISHED.events
  .split("\n")
  .filter((line) => line.trim() !== "")
  .map((line) => JSON.parse(line) as TraceEvent);

/** The card of the scenario in the published catalog, as `site/replay/index.json` holds it. */
const SCENARIO: ScenarioIndexEntry = {
  id: "S01",
  name: "fx_markup_refund",
  question: "Why was the BRL refund for TX-2048 lower than the EUR payment?",
  concepts: [],
  data_origin: "UCI Online Retail II",
  status: "Recorded",
  capture_kind: "scripted_fixture",
  bundle_path: "s01",
};

/** The bundle that the loader of the case answers with. */
const LOADED: LoadedReplay = { manifest: MANIFEST, events: EVENTS, provenance: PROVENANCE };

/**
 * The commit of the checkout that the links of the engineering drawer open.
 *
 * Why the case carries a commit: the reader opens the engineering drawer, and the links of the
 * drawer open the tree of that commit. The case does not read the repository, so it names a commit
 * of forty hexadecimal characters and the drawer shows the links of that tree (ADR-046).
 */
const COMMIT = "0123456789abcdef0123456789abcdef01234567";

/**
 * The tree of the case: three spans, one of them with a child.
 *
 * Why the tree is written by hand: the rule of the tree is about the SEMANTICS of the roles and the keyboard, and a
 * tree of three spans proves both of them without the weight of the whole recording.
 */
const NODES: readonly TraceTreeNode[] = [
  {
    spanId: "root",
    parentSpanId: null,
    name: "investigate chain",
    runType: "chain",
    depth: 0,
    startedSeq: 1,
    endedSeq: 2,
    children: [
      {
        spanId: "child",
        parentSpanId: "root",
        name: "query_ledger chain",
        runType: "chain",
        depth: 1,
        startedSeq: 3,
        endedSeq: 4,
        children: [],
      },
    ],
  },
];

/** The rows of the case: three events of the recording. */
const ROWS: readonly TimelineRow[] = [
  {
    seq: 1,
    eventType: "span.started",
    label: "investigate",
    at: "2026-11-14T11:00:14.000+00:00",
    latencyMs: null,
    error: null,
    isTool: false,
  },
  {
    seq: 2,
    eventType: "span.ended",
    label: "investigate",
    at: "2026-11-14T11:00:14.500+00:00",
    latencyMs: 500,
    error: null,
    isTool: false,
  },
  {
    seq: 3,
    eventType: "span.started",
    label: "query_ledger",
    at: "2026-11-14T11:00:15.000+00:00",
    latencyMs: null,
    error: null,
    isTool: true,
  },
];

/**
 * Stubs the fetch of the runtime with the published artifacts of the repository.
 *
 * Why the fetch is stubbed: the reader reads the state of the provider, and the provider reads the bundle through
 * the loader of the case. The fetch is stubbed with the same artifacts, so that a reader that reaches for the network
 * on its own finds the same published bundle and never a network of its own.
 */
function stubFetch(): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      const body = url.endsWith("manifest.json")
        ? PUBLISHED.manifest
        : url.endsWith("events.jsonl")
          ? PUBLISHED.events
          : url.endsWith("provenance.json")
            ? PUBLISHED.provenance
            : "";
      return { ok: true, status: 200, text: async () => body } as unknown as Response;
    }),
  );
}

/**
 * Renders the reader inside the provider of the replay.
 *
 * Why the provider is here: the reader stopped fetching by itself, so the state of the bundle lives in the provider
 * and the reader only draws it.
 */
function renderViewer(): void {
  stubFetch();
  render(
    <ReplayProvider scenario={SCENARIO} loader={vi.fn(async () => LOADED)}>
      <ReplayViewer commit={COMMIT} scenario={SCENARIO} />
    </ReplayProvider>,
  );
}

/**
 * Waits for the recorded run to be drawn, and gives the region of the run.
 *
 * Why the case waits for the slider and not for the region: the loading state carries the very same name as the run
 * itself, so a case that waits for the region can wake up while the run has drawn nothing yet.
 */
async function findLoadedRun(): Promise<HTMLElement> {
  await screen.findByRole("slider", { name: "Position of the recording" });
  return screen.getByRole("region", { name: "The recorded run" });
}

/**
 * Moves the recording to an event of the recording, the way a visitor moves it with the slider.
 *
 * Why the sequence number and not the position: the events of the published recording carry contiguous sequence
 * numbers, so the event of a sequence number sits at the index of that number minus one.
 *
 * Why the case waits for the counter of the events: the counter is the visible text that says where the recording
 * stands, and it is the sign that the recording really moved.
 */
async function seekToTheEvent(seq: number): Promise<void> {
  const slider = screen.getByRole("slider", { name: "Position of the recording" });
  fireEvent.change(slider, { target: { value: String(seq - 1) } });

  await waitFor(() => {
    expect(screen.getByText(`Event ${seq} of ${EVENTS.length}.`)).toBeInTheDocument();
  });
}

/**
 * Stubs the preference of the system for less motion.
 *
 * Why the stub is needed: jsdom has no media query at all, so the preference of the visitor is unknown to the reader
 * unless the case says what it is.
 */
function stubReducedMotion(reduced: boolean): void {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      matches: reduced,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  // The address of the case and the preferences of the view are put back where they were, so that a
  // case that writes them never reaches the case that runs after it.
  window.history.replaceState(null, "", "/");
  window.localStorage.clear();
});

describe("the tree of the investigation is a tree", () => {
  it("carries the roles, the levels and the expanded state of a tree", () => {
    // It proves that the tree is a tree and not a list of rows: the list carries the tree, the rows carry the items,
    // every row says at which level it sits, and a row that has children says that they are shown.
    render(<TraceTree nodes={NODES} selectedSpanId="root" onSelect={() => undefined} />);

    expect(screen.getByRole("tree")).toBeInTheDocument();

    const root = screen.getByRole("treeitem", { name: /investigate/ });
    const child = screen.getByRole("treeitem", { name: /query_ledger/ });

    expect(root).toHaveAttribute("aria-level", "1");
    expect(root).toHaveAttribute("aria-expanded", "true");
    expect(child).toHaveAttribute("aria-level", "2");
    expect(child).not.toHaveAttribute("aria-expanded");
  });

  it("is one tab stop, and the arrow keys with Home and End walk it", async () => {
    // It proves that the tree is ONE stop of the keyboard: the reader walks it with the arrows, so the other rows are
    // out of the tab order, and the arrows, Home and End move the focus over the rows.
    render(<TraceTree nodes={NODES} selectedSpanId="root" onSelect={() => undefined} />);

    const rows = screen.getAllByRole("treeitem");
    expect(rows.filter((row) => row.getAttribute("tabindex") === "0")).toHaveLength(1);
    expect(rows.filter((row) => row.getAttribute("tabindex") === "-1")).toHaveLength(rows.length - 1);

    const root = screen.getByRole("treeitem", { name: /investigate/ });
    root.focus();
    expect(document.activeElement).toBe(root);

    await userEvent.setup().keyboard("{ArrowDown}");
    expect(document.activeElement).toBe(screen.getByRole("treeitem", { name: /query_ledger/ }));

    await userEvent.setup().keyboard("{ArrowUp}");
    expect(document.activeElement).toBe(root);

    await userEvent.setup().keyboard("{End}");
    expect(document.activeElement).toBe(screen.getByRole("treeitem", { name: /query_ledger/ }));

    await userEvent.setup().keyboard("{Home}");
    expect(document.activeElement).toBe(root);
  });

  it("takes the name of the visible text and never a name that hides it", () => {
    // It proves that the accessible name of a row is the text the visitor reads: a name that hides the visible text
    // breaks the label in name of WCAG 2.5.3.
    render(<TraceTree nodes={NODES} selectedSpanId="root" onSelect={() => undefined} />);

    for (const row of screen.getAllByRole("treeitem")) {
      expect(row).not.toHaveAttribute("aria-label");
    }
  });
});

describe("the timeline of the recording is one tab stop", () => {
  it("keeps the number of the event out of the tab order", () => {
    // It proves that the number of the event is a CELL and not a stop of the keyboard: the visitor reaches it with the
    // arrows, inside the table, and never tabs through every event of the recording.
    render(<TraceTimeline rows={ROWS} position={1} onSeek={() => undefined} />);

    const numbers = screen.getAllByRole("button", { name: /^\d+$/ });
    expect(numbers.length).toBeGreaterThan(0);
    for (const number of numbers) {
      expect(number.getAttribute("tabindex")).toBe("-1");
    }

    const stops = screen
      .getAllByRole("button")
      .filter((button) => button.getAttribute("tabindex") === "0");
    expect(stops).toHaveLength(0);
  });

  it("marks the row the visitor stands at as the current one", () => {
    // It proves that the row the visitor stands at carries `aria-current`, so a reader of a screen reader knows which
    // event of the recording the playback is at.
    render(<TraceTimeline rows={ROWS} position={1} onSeek={() => undefined} />);

    const current = screen.getAllByRole("row", { current: true });
    expect(current).toHaveLength(1);
    expect(current[0]).toBeDefined();
    expect(within(current[0] as HTMLElement).getByRole("button", { name: "2" })).toBeInTheDocument();
  });
});

describe("the outline of the headings of the reader", () => {
  it("never skips a level", async () => {
    // It proves that the outline of the headings mirrors the sections of the reader: the route has its h1, the
    // scenario has its h2, and every section of the reader has its h3, with nothing skipped in between.
    renderViewer();
    await findLoadedRun();

    const headings = Array.from(
      document.querySelectorAll("h1, h2, h3, h4, h5, h6"),
    ) as HTMLHeadingElement[];

    expect(headings.length).toBeGreaterThan(0);

    let previous = 0;
    for (const heading of headings) {
      const level = Number(heading.tagName.slice(1));
      if (previous !== 0) {
        expect(level - previous).toBeLessThanOrEqual(1);
      }
      previous = level;
    }
  });
});

describe("the controls of the playback", () => {
  const NOOP = () => undefined;

  it("are never disabled, and the control that would do nothing says so", () => {
    // It proves that a control that would do nothing stays in the keyboard, carries `aria-disabled` and points at a
    // reason a reader can hear. A `disabled` attribute would take the control out of the keyboard.
    render(
      <ReplayControls
        phase="ready"
        position={0}
        total={3}
        speed={1}
        onPlay={NOOP}
        onPause={NOOP}
        onStep={NOOP}
        onSeek={NOOP}
        onReset={NOOP}
        onSpeedChange={NOOP}
      />,
    );

    const previous = screen.getByRole("button", { name: "Previous event" });
    const next = screen.getByRole("button", { name: "Next event" });

    for (const control of [previous, next]) {
      expect(control).not.toBeDisabled();
      expect(control).not.toHaveAttribute("disabled");
    }

    // the visitor stands at the first event, so the step back would do nothing
    expect(previous).toHaveAttribute("aria-disabled", "true");
    const reasonId = previous.getAttribute("aria-describedby");
    expect(reasonId).not.toBeNull();
    const reason = document.getElementById(reasonId as string);
    expect(reason?.textContent?.trim().length ?? 0).toBeGreaterThan(0);

    // the step forward can act, so it carries no mark of a block
    expect(next).not.toHaveAttribute("aria-disabled");
  });

  it("say that the step forward would do nothing at the last event", () => {
    // It proves that the other end of the recording is told to the visitor in the same way.
    render(
      <ReplayControls
        phase="ready"
        position={2}
        total={3}
        speed={1}
        onPlay={NOOP}
        onPause={NOOP}
        onStep={NOOP}
        onSeek={NOOP}
        onReset={NOOP}
        onSpeedChange={NOOP}
      />,
    );

    expect(screen.getByRole("button", { name: "Next event" })).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByRole("button", { name: "Previous event" })).not.toHaveAttribute("aria-disabled");
  });
});

describe("the preference for less motion", () => {
  it("stops the automatic playback and the control says why", async () => {
    // It proves that a visitor who asked the browser for less motion is not shown a recording that moves by itself,
    // and that the control tells them why the recording waits for them.
    stubReducedMotion(true);
    renderViewer();
    await findLoadedRun();

    const play = screen.getByRole("button", { name: "Play the recording" });
    await waitFor(() => expect(play).toHaveAttribute("aria-disabled", "true"));

    expect(screen.getByText(/asks for less motion/i)).toBeInTheDocument();

    fireEvent.click(play);
    await new Promise((resolve) => setTimeout(resolve, 50));

    // The region does not carry the counter of the events any more: it announces the step of the run, and the
    // recording never moved, so it says nothing at all. The counter stays visible in the page as ordinary text.
    expect(screen.getByRole("status").textContent).toBe("");
    expect(screen.getByText(`Event 1 of ${EVENTS.length}.`)).toBeInTheDocument();
  });

  it("lets the recording play when the visitor did not ask for less motion", async () => {
    // It proves that the two states differ: without the preference the control can act, so a reader is never told
    // that a control is blocked when it is not.
    stubReducedMotion(false);
    renderViewer();
    await findLoadedRun();

    const play = screen.getByRole("button", { name: "Play the recording" });
    await waitFor(() => expect(play).not.toHaveAttribute("aria-disabled"));
  });
});

describe("the shell of the site", () => {
  it("has one banner, one main and one content information, and the banner carries the name of the site", () => {
    // It proves that the landmarks of the page are the ones a reader navigates by, and that the banner says which
    // site it is instead of being an anonymous banner.
    render(
      <AppShell>
        <p>the content of the page</p>
      </AppShell>,
    );

    const banners = screen.getAllByRole("banner");
    expect(banners).toHaveLength(1);
    expect(banners[0]).toHaveAccessibleName("LedgerLens");

    expect(screen.getAllByRole("main")).toHaveLength(1);
    expect(screen.getAllByRole("contentinfo")).toHaveLength(1);
  });

  it("moves the focus to the main with the skip link", async () => {
    // It proves that the skip link moves the FOCUS and not only the scroll: a visitor who follows it lands on the
    // content and the keyboard continues from the content.
    render(
      <AppShell>
        <p>the content of the page</p>
      </AppShell>,
    );

    const skip = screen.getByRole("link", { name: "Skip to the main content" });
    expect(skip).toHaveAttribute("href", "#main");

    skip.focus();
    await userEvent.setup().click(skip);

    await waitFor(() => {
      expect(document.activeElement).toBe(screen.getByRole("main"));
    });
  });
});

describe("the state is never only a colour", () => {
  it("tells the current row of the timeline with a mark a reader can see", () => {
    // It proves that the row the visitor stands at wears a mark that is not a tint of the background: a tint is a
    // mark a reader with low vision cannot see, and a tint that a hovered row also wears tells the reader nothing.
    render(<TraceTimeline rows={ROWS} position={1} onSeek={() => undefined} />);

    const current = screen.getByRole("button", { name: "2" });
    const ordinary = screen.getByRole("button", { name: "1" });

    // the mark the reader sees: the weight of the number and the border on its left
    expect(current.className).toContain("font-semibold");
    expect(ordinary.className).toContain("font-medium");
    expect(current.className).toContain("border-l-2");
    expect(ordinary.className).toContain("border-transparent");
  });

  it("tells the chosen span of the tree with a mark a reader can see", () => {
    // It proves the same for the tree: the chosen span wears a heavier name, the mark that survives the forced
    // colours mode of the system, where a tint of the background does not.
    render(<TraceTree nodes={NODES} selectedSpanId="root" onSelect={() => undefined} />);

    const chosen = screen.getByRole("treeitem", { name: /investigate/ });
    const ordinary = screen.getByRole("treeitem", { name: /query_ledger/ });

    expect(chosen).toHaveAttribute("aria-selected", "true");
    expect(chosen.querySelector("span")?.className).toContain("font-semibold");
    expect(ordinary.querySelector("span")?.className).toContain("font-medium");
  });
});

describe("the live region of the reader", () => {
  it("announces the step politely and never assertively", async () => {
    // It proves that the step of the recording is announced through ONE polite region and never through an
    // assertive one: a recording that interrupts the visitor at every event is a recording nobody can listen to.
    renderViewer();
    await findLoadedRun();

    const polite = document.querySelectorAll('[aria-live="polite"]');
    expect(polite.length).toBe(1);

    const region = polite[0];
    expect(region).toBeDefined();
    expect(region).toHaveAttribute("role", "status");
    expect(region).toHaveAttribute("aria-atomic", "true");

    // The region says nothing while the recording stands at its first event and the playback has not started: a
    // region that holds a sentence when the page loads is announced by some readers as soon as it appears.
    expect(region?.textContent).toBe("");

    // no assertive region, no alert, and no log: the reader never interrupts the visitor
    expect(document.querySelectorAll('[aria-live="assertive"]')).toHaveLength(0);
    expect(document.querySelectorAll('[role="alert"]')).toHaveLength(0);
    expect(document.querySelectorAll('[role="log"]')).toHaveLength(0);
  });

  it("moves the focus to the region once, when the playback starts", async () => {
    // It proves the focus rule of the region: the focus moves to the region ONCE, when the playback starts, and it
    // never comes back while the recording runs. A reader that is pulled back to the region on every event of the
    // recording never hears the recording at all (FR-032).
    stubReducedMotion(false);
    renderViewer();
    await findLoadedRun();

    const region = screen.getByRole("status");
    expect(document.activeElement).not.toBe(region);

    await userEvent.setup().click(screen.getByRole("button", { name: "Play the recording" }));
    await waitFor(() => expect(document.activeElement).toBe(region));

    // The recording is stopped, so that the case does not run against a recording that moves by itself.
    await userEvent.setup().click(screen.getByRole("button", { name: "Pause the recording" }));

    // The recording moves, and the focus never comes back to the region.
    const slider = screen.getByRole("slider", { name: "Position of the recording" });
    slider.focus();
    fireEvent.change(slider, { target: { value: "15" } });

    await waitFor(() => expect(screen.getByText(`Event 16 of ${EVENTS.length}.`)).toBeInTheDocument());
    expect(document.activeElement).not.toBe(region);
  });

  it("announces the step of the run and never the counter of the events", async () => {
    // It proves that the region announces what the recording DID and not where it stands inside the list of the
    // events: the counter is a position, and the position is on the slider and in the text of the page.
    renderViewer();
    await findLoadedRun();

    await seekToTheEvent(16);

    const region = screen.getByRole("status");
    expect(region).toHaveTextContent("Step 1 of 4: query_ledger.");
    expect(region.textContent).not.toMatch(/Event/);

    // The counter of the events stays visible in the page, as ordinary text and outside the region.
    expect(screen.getByText(`Event 16 of ${EVENTS.length}.`)).toBeInTheDocument();
  });

  it("does not change its text when the recording moves inside a step", async () => {
    // It proves the granularity of the announcement: the region is rewritten only when the step of the run changes,
    // and not on every event of the recording. The call of the first step opens at the event 16 and closes at the
    // event 19, so the region says the same sentence at the two moments.
    renderViewer();
    await findLoadedRun();

    await seekToTheEvent(16);
    const region = screen.getByRole("status");
    const announced = region.textContent;
    expect(announced).toBe("Step 1 of 4: query_ledger.");

    await seekToTheEvent(19);
    expect(region.textContent).toBe(announced);
  });
});

describe("the loader of the bundle", () => {
  it("never throws at the caller", async () => {
    // It proves that the loader of the bundle returns the reason of the refusal and never throws: a reader cannot tell
    // which parts of a half drawn run are true.
    const failing = vi.fn(async () => {
      throw new Error("the site did not answer");
    });
    vi.stubGlobal("fetch", failing);

    const answer = await loadReplay(SCENARIO);

    expect(answer).toHaveProperty("error");
    expect(String((answer as { error: string }).error)).not.toBe("");
  });
});
