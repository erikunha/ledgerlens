import { expect, test, type Page } from "@playwright/test";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

/**
 * The end to end suite of the visual baselines of the public site.
 *
 * Why this file exists: the plan of the release asks for "the visual baselines at 390, 768 and 1440 pixels" in this
 * file (T087) and for the measurement of the paint of the page (T089). Both are measurements of the page as a
 * visitor receives it, and both belong to the same suite: the browser is the only place where the paint of a page
 * exists, and the browser is also the only place where the structure of a page can be read.
 *
 * Why the baseline is a STRUCTURAL one and not a picture of the page: the site uses the fonts of the system
 * (`apps/web/app/globals.css` declares `--ll-font-sans` from the stack of the platform and the folder of the assets of
 * the site holds no font file), and the continuous integration runs on `ubuntu-latest` while the author writes on a
 * machine of another platform. A picture of the page that is committed from one machine is the picture of the font of
 * that machine, and comparing it on the other one compares two different fonts. The baseline of this file therefore
 * compares the structure of the page: the role of each box, its accessible name, its title, its order and its
 * horizontal geometry, rounded to the whole pixel because the geometry of the browser is a fractional number. The
 * pixels are not compared, and ADR-051 says what the baseline catches and what it does not catch.
 *
 * Why the paint is measured here and not only in the script of the repository: the script of the repository measures
 * the paint with the arm that is opt in, and the arm needs a browser that the gate of the Python side must never
 * need. This file is the suite of the frontend, the browser is installed there, and the bound that the suite asserts
 * is the bound that catches a catastrophic regression. The promise of SC-003, which is a number of a deployed site on
 * a given connection, is measured and printed, and it is recorded by whoever runs the release.
 *
 * Why the baseline runs in one project only: the baseline is the same on every platform and on every engine, so the
 * suite measures it in the project of Chromium and skips the other three. Three widths times four projects times
 * four views would have been forty-eight runs of the same measurement.
 *
 * Why the scrollbar of the browser is hidden: the scrollbar is furniture of the platform and not of the design, and
 * it takes fifteen pixels of the width of the document on Linux and none on the machine of the author. With the
 * scrollbar hidden, the width of the document is the width of the viewport on every platform, and the comparison of
 * the geometry means the same thing everywhere.
 */

/**
 * One box of the baseline: the box the page has to show and where it has to be.
 */
interface BoxSpec {
  /** The name of the box inside the baseline, the way the file of the baseline names it. */
  readonly id: string;
  /** The selector that finds the box in the page. */
  readonly selector: string;
}

/**
 * One box of the page as it was measured: the structure of the box and its horizontal geometry.
 */
interface MeasuredBox {
  /** The name of the box inside the baseline. */
  readonly id: string;
  /** The role of the box, the way the accessibility of the page sees it. */
  readonly role: string;
  /** The accessible name of the box, empty when the box has none. */
  readonly name: string;
  /** The text of the first heading of the box, empty when the box holds no heading. */
  readonly title: string;
  /** The distance from the left edge of the document to the left edge of the box, in pixels. */
  readonly left: number;
  /** The width of the box, in pixels. */
  readonly width: number;
}

/**
 * The baseline of one view at one width.
 *
 * Why one file per view and per width: the suite runs its tests in parallel, and two tests that wrote the same file
 * would lose the width of the other one. A file of its own for each of them removes the race, and a reader of the
 * tree of the repository sees the twelve files of the set and knows what each one holds.
 */
interface Baseline {
  /** The name of the view. */
  readonly view: string;
  /** The route the view is at. */
  readonly route: string;
  /** The width of the viewport the baseline was measured at. */
  readonly width: number;
  /** The record that decided the shape of the baseline. */
  readonly decidedBy: string;
  /** The tolerance of the comparison of the geometry, in pixels. */
  readonly tolerance: number;
  /** The width of the document, which is the width of the viewport when the scrollbar is hidden. */
  readonly clientWidth: number;
  /** The boxes of the view, in the order of the page. */
  readonly boxes: readonly MeasuredBox[];
}

/**
 * One view of the baseline: a page of the site, a state of that page and the boxes of that state.
 */
interface ViewSpec {
  /** The name of the view, the way the file of the baseline names it. */
  readonly view: string;
  /** The slug of the view, the name of the files of the baseline without the width. */
  readonly slug: string;
  /** The route the view is at. */
  readonly route: string;
  /** The boxes of the view, in the order of the page. */
  readonly boxes: readonly BoxSpec[];
  /** The work that opens the view, when the view is not the state the route opens. */
  readonly prepare?: (page: Page) => Promise<void>;
}

/**
 * The folder of the baselines, next to the folder of this suite.
 *
 * Why the folder is not inside the folder of the suite: the baselines are not tests, and a reader of the tree of the
 * repository has to see them apart from the files that run.
 */
const BASELINE_FOLDER = join(__dirname, "..", "baselines");

/**
 * The widths of the baseline: the two of the design package and the one of the breakpoint in between.
 *
 * Why these three: SC-008 asks for the widths 390, 768 and 1440, and the width of 768 pixels is the breakpoint of
 * the design package, the width where the layout of the site changes.
 */
const WIDTHS: ReadonlyArray<{ readonly width: number; readonly height: number }> = [
  { width: 390, height: 844 },
  { width: 768, height: 1024 },
  { width: 1440, height: 900 },
];

/**
 * The tolerance of the comparison of the geometry, in pixels.
 *
 * Why eight pixels: it is two steps of the spacing, and it is the room the platform needs. The width of a scrollbar
 * is fifteen pixels on Linux, and the metrics of the system font differ by a few pixels between two platforms. A
 * change of the layout of the site moves a box by more than eight pixels, and a difference of the font does not.
 */
const TOLERANCE = 8;

/**
 * The environment variable that turns the comparison into a measurement that is written to the disk.
 *
 * Why the suite never writes the baseline by itself: a suite that rewrites the expectation of its own assertion is a
 * suite that cannot fail.
 */
const UPDATE_VARIABLE = "LEDGERLENS_UPDATE_BASELINES";

/**
 * The project of the suite that measures the baseline.
 *
 * Why this one: the baseline is the same on every platform and on every engine, and one measurement of it is enough.
 */
const BASELINE_PROJECT = "chromium-1440";

/**
 * The boxes that every page of the site shows, because the shell of the site writes them.
 */
const SHELL_BOXES: readonly BoxSpec[] = [
  { id: "banner", selector: "body > div > header" },
  { id: "main", selector: "body > div > main" },
  { id: "contentinfo", selector: "body > div > footer" },
  { id: "container", selector: "body > div > main > div" },
];

/**
 * The views of the baseline.
 *
 * Why these views: the home is the door of the site, the tab of the execution is the technical heart of the
 * demonstration, the tab of the ledger is the one that shows the rows of the simulated account, and the tour of the
 * architecture is the page that turns a visitor into a reader of the code. ADR-051 names the reasons and the cost of
 * the list, and the list is a curation and not a rule.
 */
const VIEWS: readonly ViewSpec[] = [
  {
    view: "the home",
    slug: "home",
    route: "/",
    boxes: [
      ...SHELL_BOXES,
      { id: "rooms", selector: "body > div > main > div > section[aria-label]" },
      { id: "card-recorded-demo", selector: "body > div > main > div > section[aria-label] > div:nth-child(1)" },
      { id: "card-sandbox", selector: "body > div > main > div > section[aria-label] > div:nth-child(2)" },
      { id: "card-live-mode", selector: "body > div > main > div > section[aria-label] > div:nth-child(3)" },
    ],
  },
  {
    view: "the recording of S01, the tab of the execution",
    slug: "scenario-s01-execution",
    route: "/replay/scenario/S01",
    boxes: [
      ...SHELL_BOXES,
      { id: "scenario", selector: "body > div > main > div > section" },
      { id: "run", selector: "body > div > main > div > section > section[aria-label]" },
      { id: "tabs", selector: "[role='tablist']" },
      { id: "panel", selector: "#ledgerlens-section-execution" },
      { id: "stepper", selector: "section[aria-label='The steps of the run']" },
      { id: "tree", selector: "section[aria-label='The tree of the investigation']" },
      { id: "timeline", selector: "section[aria-label='The timeline of the recording']" },
      { id: "calls", selector: "#ledgerlens-section-execution > div.rounded-lg" },
    ],
    prepare: async (page: Page): Promise<void> => {
      // the panels of the recording are on the screen only when the bundle of the scenario was read and accepted
      await waitForTheRecording(page);
    },
  },
  {
    view: "the recording of S01, the tab of the ledger",
    slug: "scenario-s01-ledger",
    route: "/replay/scenario/S01",
    boxes: [
      ...SHELL_BOXES,
      { id: "scenario", selector: "body > div > main > div > section" },
      { id: "run", selector: "body > div > main > div > section > section[aria-label]" },
      { id: "tabs", selector: "[role='tablist']" },
      { id: "panel", selector: "#ledgerlens-section-ledger" },
      { id: "ledger-panel", selector: ".ll-ledger-panel" },
      { id: "ledger-controls", selector: ".ll-ledger-controls" },
      { id: "ledger-pagination", selector: ".ll-ledger-pagination" },
    ],
    prepare: async (page: Page): Promise<void> => {
      await waitForTheRecording(page);
      await page.getByRole("tab", { name: "Ledger" }).click();
      await expect(page.getByRole("region", { name: /The ledger of the account/ })).toBeVisible();
    },
  },
  {
    view: "the tour of the architecture",
    slug: "engineering",
    route: "/engineering",
    boxes: [
      ...SHELL_BOXES,
      { id: "tour", selector: "[data-architecture-diagram]" },
      { id: "picture", selector: "[data-architecture-picture]" },
      { id: "node-list", selector: "[data-architecture-list]" },
    ],
  },
];

/**
 * The throttling of the measurement of the paint.
 *
 * Why these numbers: a connection of four megabits per second with one hundred milliseconds of latency is a phone on
 * a shared mobile network, which is the middle of the range and the machine most of the visitors are on, and a
 * processor four times slower is the same idea applied to the machine. The numbers are the ones the arm of the script
 * of the repository applies, so the two measurements can be compared with each other.
 */
const PAINT_CPU_RATE = 4;
const PAINT_DOWNLOAD_BYTES_PER_SECOND = 500_000;
const PAINT_UPLOAD_BYTES_PER_SECOND = 125_000;
const PAINT_LATENCY_MS = 100;

/**
 * The bound of the paint that the suite of the frontend asserts.
 *
 * Why the bound is far above the promise of SC-003: a machine that is shared, a container and a processor four times
 * slower make the wall clock noisy, and a test that goes red for the noise of the machine teaches the reader to
 * ignore the test. The bound catches the regression that matters, which is a site that ships a bundle that is ten
 * times too heavy, and it does not catch the millisecond. The promise of SC-003, a largest contentful paint under
 * 2.5 seconds and a first contentful paint under 1.8 seconds on the deployed site, is measured and recorded by
 * whoever runs the release.
 */
const PAINT_LCP_BOUND_MS = 8_000;
const PAINT_FCP_BOUND_MS = 5_000;

/**
 * The paint of a page, as the browser measured it.
 */
interface Paint {
  /** The moment of the first contentful paint, in milliseconds, null when the browser reported none. */
  readonly fcp: number | null;
  /** The moment of the largest contentful paint, in milliseconds, null when the browser reported none. */
  readonly lcp: number | null;
}

/**
 * Waits for the recording of the scenario `S01` to be on the screen.
 *
 * Why the table of the calls is the wait: the table appears only when the bundle of the scenario was read and
 * accepted, so it is the real sign that the recording is there. There is no sleep and no wait for a network that does
 * not come.
 */
async function waitForTheRecording(page: Page): Promise<void> {
  await expect(page.getByRole("table", { name: "The calls of the tools of the recorded run" })).toBeVisible();
}

/**
 * Opens the recording of the scenario `S01` and waits for it to be on the screen.
 *
 * Why the function is here and not only the wait: the measurement of the paint opens the page and then waits, and the
 * two steps are the same step in two places.
 */
async function openTheRecording(page: Page): Promise<void> {
  await page.goto("/replay/scenario/S01");
  await waitForTheRecording(page);
}

/**
 * Reads the boxes of the page and their geometry.
 *
 * Why the measurement happens in the page: the geometry of a box is a fact of the layout of the browser, and the
 * accessible name of a box is a fact of the accessibility of the page, and neither of them can be read from the
 * outside of the browser.
 *
 * Why the vertical geometry is not read: the height of a block of text depends on the number of lines the text takes,
 * and the number of lines depends on the width of the glyphs of the system font, which is one font on the machine of
 * the author and another one on the machine of the continuous integration. ADR-051 names the reason and the debt.
 */
async function measureTheBoxes(page: Page, boxes: readonly BoxSpec[]): Promise<MeasuredBox[]> {
  return page.evaluate((specs: BoxSpec[]) => {
    const nameOf = (element: Element): string => {
      const label = element.getAttribute("aria-label");
      if (label !== null && label.trim() !== "") {
        return label.trim();
      }

      const labelledBy = element.getAttribute("aria-labelledby");
      if (labelledBy !== null && labelledBy.trim() !== "") {
        const parts = labelledBy
          .split(/\s+/)
          .map((id) => document.getElementById(id)?.textContent ?? "")
          .join(" ");
        const text = parts.replace(/\s+/g, " ").trim();
        if (text !== "") {
          return text;
        }
      }

      return "";
    };

    const roleOf = (element: Element): string => {
      const declared = element.getAttribute("role");
      if (declared !== null && declared.trim() !== "") {
        return declared.trim();
      }

      const tag = element.tagName.toLowerCase();
      if (tag === "header") {
        return "banner";
      }
      if (tag === "main") {
        return "main";
      }
      if (tag === "nav") {
        return "navigation";
      }
      if (tag === "footer") {
        // a footer of the page is the content information, and a footer of a section is not
        const sectioning = element.closest("main, article, aside, nav, section");
        return sectioning === null ? "contentinfo" : "generic";
      }
      if (tag === "section") {
        return nameOf(element) === "" ? "generic" : "region";
      }

      return "generic";
    };

    const titleOf = (element: Element): string => {
      const heading = element.matches("h1, h2, h3, h4, h5, h6")
        ? element
        : element.querySelector("h1, h2, h3, h4, h5, h6");
      if (heading === null) {
        return "";
      }
      return (heading.textContent ?? "").replace(/\s+/g, " ").trim();
    };

    return specs.map((spec) => {
      const element = document.querySelector(spec.selector);
      if (element === null) {
        // a box that is not on the page is a box with no geometry, and the comparison says so
        return { id: spec.id, role: "", name: "", title: "", left: -1, width: -1 };
      }

      const rect = element.getBoundingClientRect();
      return {
        id: spec.id,
        role: roleOf(element),
        name: nameOf(element),
        title: titleOf(element),
        // the geometry of the browser is a fractional number, and the baseline holds whole pixels
        left: Math.round(rect.left + window.scrollX),
        width: Math.round(rect.width),
      };
    });
  }, [...boxes]);
}

/**
 * Reads the width of the document, which is the width of the viewport when the scrollbar is hidden.
 */
async function measureTheWidthOfTheDocument(page: Page): Promise<number> {
  return page.evaluate(() => document.documentElement.clientWidth);
}

/**
 * Compares the boxes of the page with the boxes of the baseline and returns the problems it found.
 *
 * Why the problems are sentences and not numbers: the next person has to read the failure and see the box that moved
 * and the two values that differ, without opening the file of the baseline and counting the lines.
 */
function compareTheBoxes(
  expected: readonly MeasuredBox[],
  actual: readonly MeasuredBox[],
  tolerance: number,
): string[] {
  const problems: string[] = [];

  if (expected.length !== actual.length) {
    problems.push(
      `the baseline holds ${expected.length} boxes and the page shows ${actual.length}: ${actual
        .map((box) => box.id)
        .join(", ")}`,
    );
    return problems;
  }

  expected.forEach((box, index) => {
    const measured = actual[index];
    if (measured === undefined) {
      return;
    }

    if (box.id !== measured.id) {
      problems.push(`the box ${box.id} of the baseline is the box ${measured.id} of the page`);
      return;
    }

    if (box.role !== measured.role) {
      problems.push(`the box ${box.id} has the role ${box.role} and the page shows the role ${measured.role}`);
    }
    if (box.name !== measured.name) {
      problems.push(`the box ${box.id} is named "${box.name}" and the page names it "${measured.name}"`);
    }
    if (box.title !== measured.title) {
      problems.push(`the box ${box.id} holds the title "${box.title}" and the page holds "${measured.title}"`);
    }
    if (Math.abs(box.left - measured.left) > tolerance) {
      problems.push(
        `the box ${box.id} starts at ${box.left} pixels and the page starts it at ${measured.left} pixels`,
      );
    }
    if (Math.abs(box.width - measured.width) > tolerance) {
      problems.push(`the box ${box.id} is ${box.width} pixels wide and the page shows it ${measured.width} pixels wide`);
    }
  });

  return problems;
}

/**
 * The name of the file of the baseline of a view at a width.
 *
 * Why the width is in the name: the suite runs its tests in parallel, and two tests that wrote the same file would
 * lose the width of the other one. A file of its own for each of them removes the race.
 */
function theNameOfTheFile(view: ViewSpec, width: number): string {
  return `${view.slug}-${width}.json`;
}

/**
 * Reads the baseline of a view from the disk.
 */
function readTheBaseline(file: string): Baseline {
  const path = join(BASELINE_FOLDER, file);
  return JSON.parse(readFileSync(path, "utf-8")) as Baseline;
}

/**
 * Writes the baseline of a view to the disk, the way the suite writes it when it is asked to measure it again.
 */
function writeTheBaseline(file: string, baseline: Baseline): void {
  if (!existsSync(BASELINE_FOLDER)) {
    mkdirSync(BASELINE_FOLDER, { recursive: true });
  }
  writeFileSync(join(BASELINE_FOLDER, file), `${JSON.stringify(baseline, null, 2)}\n`, "utf-8");
}

/**
 * Says whether the suite has to write the baseline again instead of comparing it.
 */
function theBaselineHasToBeWritten(): boolean {
  const value = process.env[UPDATE_VARIABLE];
  return value !== undefined && value.trim() !== "" && value.trim() !== "0";
}

/**
 * Reads the paint of the page out of the browser.
 *
 * Why the observer is installed before the navigation: the entries of the paint are buffered by the browser, and the
 * observer that is installed after the navigation misses the entries that were already recorded.
 */
async function readThePaint(page: Page): Promise<Paint> {
  return page.evaluate(() => {
    const first = performance.getEntriesByName("first-contentful-paint")[0];
    const store = (window as unknown as { __ledgerlensPaint?: { lcp: number } }).__ledgerlensPaint;
    return {
      fcp: first === undefined ? null : first.startTime,
      lcp: store === undefined || store.lcp <= 0 ? null : store.lcp,
    };
  });
}

/**
 * Waits for the paint of the page to settle, so that the number that is read is the last one of the page.
 *
 * Why the wait and not a fixed number of milliseconds: the largest contentful paint keeps changing while the page
 * loads, and a number that is read while the page is still loading is a number of a moment and not of the page.
 */
async function waitForThePaintToSettle(page: Page): Promise<void> {
  let previous: number | null = null;

  for (let attempt = 0; attempt < 60; attempt += 1) {
    const paint = await readThePaint(page);
    if (paint.lcp !== null && paint.lcp === previous) {
      return;
    }
    previous = paint.lcp;
    await page.waitForTimeout(250);
  }
}

// The baseline is measured once, in the project of Chromium: it is the same on every platform and on every engine.
test.beforeEach(({ browser: _browser }, testInfo) => {
  test.skip(
    testInfo.project.name !== BASELINE_PROJECT,
    "the baseline is measured once, in the project of Chromium, because it is the same on every platform",
  );
});

test.use({
  // the scrollbar is furniture of the platform: with it hidden, the width of the document is the width of the viewport
  launchOptions: { args: ["--hide-scrollbars"] },
});

for (const width of WIDTHS) {
  test.describe(`at ${width.width} pixels`, () => {
    test.use({ viewport: { width: width.width, height: width.height } });

    for (const view of VIEWS) {
      test(`the baseline of ${view.view} holds`, async ({ page }) => {
        await page.goto(view.route);

        if (view.prepare !== undefined) {
          await view.prepare(page);
        }

        const boxes = await measureTheBoxes(page, view.boxes);
        const clientWidth = await measureTheWidthOfTheDocument(page);
        const file = theNameOfTheFile(view, width.width);

        if (theBaselineHasToBeWritten()) {
          // the file is written whole, so that the parallel tests of the suite never write the same file
          writeTheBaseline(file, {
            view: view.view,
            route: view.route,
            width: width.width,
            decidedBy: "ADR-051",
            tolerance: TOLERANCE,
            clientWidth,
            boxes,
          });
          console.log(`the baseline of ${view.view} at ${width.width} pixels was written again`);
          return;
        }

        expect(
          existsSync(join(BASELINE_FOLDER, file)),
          `the baseline of ${view.view} at ${width.width} pixels is not on the disk: run the suite with ${UPDATE_VARIABLE}=1`,
        ).toBe(true);

        const baseline = readTheBaseline(file);
        const problems = compareTheBoxes(baseline.boxes, boxes, baseline.tolerance);
        if (Math.abs(baseline.clientWidth - clientWidth) > baseline.tolerance) {
          problems.push(
            `the document is ${clientWidth} pixels wide and the baseline holds ${baseline.clientWidth} pixels`,
          );
        }

        expect(
          problems,
          `the baseline of ${view.view} at ${width.width} pixels does not hold. The comparison of the geometry allows a tolerance of ${baseline.tolerance} pixels, and the boxes that changed are named above`,
        ).toHaveLength(0);
      });
    }
  });
}

test.describe("the paint of the recording", () => {
  test("the paint of the recording of S01 stays inside the bound of the suite", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });

    // The throttling is applied before the navigation, because the connection and the processor are the conditions
    // of the measurement and not a decoration of it.
    const client = await page.context().newCDPSession(page);
    await client.send("Network.enable");
    await client.send("Network.emulateNetworkConditions", {
      offline: false,
      downloadThroughput: PAINT_DOWNLOAD_BYTES_PER_SECOND,
      uploadThroughput: PAINT_UPLOAD_BYTES_PER_SECOND,
      latency: PAINT_LATENCY_MS,
    });
    await client.send("Emulation.setCPUThrottlingRate", { rate: PAINT_CPU_RATE });

    // The observer of the largest contentful paint is installed before the navigation, because the entries of the
    // paint that are already recorded are the ones that are missed by an observer that comes later.
    await page.addInitScript(() => {
      const store = { lcp: 0 };
      (window as unknown as { __ledgerlensPaint?: { lcp: number } }).__ledgerlensPaint = store;
      try {
        new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            store.lcp = entry.startTime;
          }
        }).observe({ type: "largest-contentful-paint", buffered: true });
      } catch {
        // a browser that does not know the type of the entry reports no number, and the test says so
      }
    });

    await openTheRecording(page);
    await waitForThePaintToSettle(page);

    const paint = await readThePaint(page);
    console.log(
      `the paint of the recording of S01: first contentful paint ${paint.fcp ?? "none"} ms, largest contentful paint ${
        paint.lcp ?? "none"
      } ms, with the processor ${PAINT_CPU_RATE} times slower and a connection of ${PAINT_DOWNLOAD_BYTES_PER_SECOND} bytes per second down, ${PAINT_UPLOAD_BYTES_PER_SECOND} bytes per second up and ${PAINT_LATENCY_MS} ms of latency`,
    );

    expect(paint.fcp, "the browser reported no first contentful paint").not.toBeNull();
    expect(paint.lcp, "the browser reported no largest contentful paint").not.toBeNull();
    expect(
      paint.fcp ?? Number.POSITIVE_INFINITY,
      `the first contentful paint of the recording is ${paint.fcp ?? "none"} ms and the bound of the suite is ${PAINT_FCP_BOUND_MS} ms`,
    ).toBeLessThanOrEqual(PAINT_FCP_BOUND_MS);
    expect(
      paint.lcp ?? Number.POSITIVE_INFINITY,
      `the largest contentful paint of the recording is ${paint.lcp ?? "none"} ms and the bound of the suite is ${PAINT_LCP_BOUND_MS} ms`,
    ).toBeLessThanOrEqual(PAINT_LCP_BOUND_MS);
  });
});
