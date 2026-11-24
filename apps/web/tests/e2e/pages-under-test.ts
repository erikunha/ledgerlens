import { expect, type Page } from "@playwright/test";

/**
 * The list of the pages of the public site that the end to end suites walk.
 *
 * Why this module exists: the suite of the accessibility scans the pages of the site and the suite
 * of the console walks the same pages, and a second list would be a second truth about which pages
 * exist. A page that is added to one list and not to the other is a page that nobody scans, and
 * the day the tour of the architecture was left out of the accessibility suite is the day a defect
 * of that page could stay for ever. One list, shared by the suites that walk the pages.
 *
 * Why the list lives apart from the suite of the accessibility: the file of a suite is the file of
 * its cases, and importing a file of cases from another file would run those cases twice.
 *
 * Why the wait of each page is a property of the page: a page that carries a drawer is only the
 * page the visitor reads when the drawer is open, so the wait of that page opens the drawer of a
 * call before the scan of the page.
 */

/**
 * One page of the public site that the suites walk.
 */
export interface PageUnderTest {
  /** The name of the page, the way the title of the case names it. */
  readonly name: string;
  /** The path of the page in the export, with the query string of the page when it has one. */
  readonly path: string;
  /**
   * The waits that tell the suite the page has finished drawing what it draws.
   *
   * Why the wait may open a window: a page that carries a drawer is only the page the visitor
   * reads when the drawer is open, so the wait of that page opens the drawer of a call before the
   * scan of the page.
   */
  readonly settle: (page: Page) => Promise<void>;
}

/**
 * Waits until the page has no request of its own in flight.
 *
 * Why the wait: the sandbox and the live mode read the catalog of the scenarios from the backend
 * of the demo, and the answer arrives after the page has already drawn its shell. A scan that ran in
 * the middle of that answer would report the state of a page that nobody ever sees.
 *
 * Why the failure is tolerated: a page that never settles is a page that is still waiting for
 * something, and the wait of the page itself is the one that has to fail when that happens.
 */
export async function waitForThePageToSettle(page: Page): Promise<void> {
  try {
    await page.waitForLoadState("networkidle", { timeout: 10_000 });
  } catch {
    // The page has already drawn what it draws, and the wait of the page is the one that reports the
    // page that never settles.
  }
}

/**
 * Opens the page and waits for the mark that tells the suite the page has drawn its content.
 *
 * Why the mark is a piece of content and not a sleep: the content of the page is the thing the
 * visitor reads, and a scan of a page that has not drawn it yet would say nothing about the page
 * the visitor really gets.
 */
export async function openThePage(page: Page, pageUnderTest: PageUnderTest): Promise<void> {
  await page.goto(pageUnderTest.path);
  await pageUnderTest.settle(page);
  await waitForThePageToSettle(page);
}

/**
 * The pages of the public site, and the wait of each one of them.
 *
 * Why the wait of the replay names the manifest of the capture: the manifest arrives with the
 * bundle of the scenario, and the ledger of the recording arrives with the same bundle, so the
 * moment the manifest is on the screen is the moment every panel of the replay has its content.
 *
 * Why the tour of the architecture is in the list: the page is a room of the site like any other,
 * and a room that no suite walks is a room that nobody checks.
 */
export const PAGES_UNDER_TEST: readonly PageUnderTest[] = [
  {
    name: "the landing page",
    path: "/",
    settle: async (page: Page) => {
      await expect(
        page.getByRole("heading", {
          level: 1,
          name: "Evidence-first payment investigation, with a trace you can read",
        }),
      ).toBeVisible();
    },
  },
  {
    name: "the catalog of the scenarios",
    path: "/replay",
    settle: async (page: Page) => {
      await expect(page.getByRole("heading", { name: "The scenarios" })).toBeVisible();
      await expect(page.getByRole("link", { name: "S01 - fx_markup_refund" })).toBeVisible();
    },
  },
  {
    name: "the catalog of the scenarios of a real model",
    path: "/replay-real",
    settle: async (page: Page) => {
      await expect(page.getByRole("heading", { name: "The scenarios" })).toBeVisible();
      await expect(page.getByRole("link", { name: "S01 - fx_markup_refund" })).toBeVisible();
    },
  },
  {
    name: "the recording of S01 made with a real model",
    path: "/replay-real/scenario/S01",
    settle: async (page: Page) => {
      const recordedRun = page.getByRole("region", { name: "The recorded run" });
      await expect(recordedRun).toBeVisible();
      await expect(recordedRun.getByText("mode: live_agent")).toBeVisible();
    },
  },
  {
    name: "the sandbox of the visitor",
    path: "/sandbox",
    settle: async (page: Page) => {
      await expect(page.getByRole("heading", { level: 1, name: "The sandbox of the visitor" })).toBeVisible();
      await expect(page.getByRole("region", { name: "The published scenarios" })).toBeVisible();
    },
  },
  {
    name: "the live mode",
    path: "/live",
    settle: async (page: Page) => {
      await expect(page.getByRole("heading", { level: 1, name: "Live mode" })).toBeVisible();
      await expect(page.getByRole("heading", { name: "The model of the run" })).toBeVisible();
    },
  },
  {
    name: "the tour of the architecture",
    path: "/engineering",
    settle: async (page: Page) => {
      await expect(
        page.getByRole("heading", { level: 1, name: "The architecture of the recorded demo" }),
      ).toBeVisible();
      await expect(page.locator("[data-architecture-picture]")).toBeVisible();
    },
  },
  {
    /*
     * Why this page is scanned with the drawer open: the drawer of a tool call is a window of the
     * page, and the page that the visitor reads is the page with the window open. The drawer is
     * built on the primitive of the sheet, so it is a dialog of Radix with its own portal, its own
     * landmark and its own focus trap, and the scan has to see it (ADR-048, decisions 1 and 8).
     */
    name: "the replay of S01 with the drawer of a call open",
    path: "/replay/scenario/S01?tab=execution",
    settle: async (page: Page) => {
      const recordedRun = page.getByRole("region", { name: "The recorded run" });
      await expect(recordedRun).toBeVisible();
      await expect(recordedRun.getByText("mode: deterministic_sandbox")).toBeVisible();

      await moveTheRecordingToItsEnd(page);

      const calls = page.getByRole("table", { name: "The calls of the tools of the recorded run" });
      await expect(calls.getByRole("rowheader", { name: "query_ledger" })).toBeVisible();

      // The trigger of the drawer is the button of the row header of the table of the calls, and
      // the drawer opens about the call of that row (ADR-048, decision 2).
      await calls.getByRole("rowheader").first().getByRole("button").click();
      await expect(page.getByRole("dialog")).toBeVisible();
    },
  },
];

/**
 * Moves the recording of the replay to its last position, the way a visitor does.
 *
 * Why the recording has to move: the table of the calls of the tools shows the calls that already
 * happened, so the visitor has to walk the recording before the calls are on the screen, and the
 * drawer opens about one of those calls.
 *
 * Why the keyboard of the slider: the control is a range input, so the visitor moves it with the
 * keys. The End key moves it to the last event, and the arrow key is the fallback for an engine
 * that does not honor the End key on a slider.
 */
async function moveTheRecordingToItsEnd(page: Page): Promise<void> {
  const position = page.getByLabel("Position of the recording");
  const last = await position.getAttribute("max");
  expect(last, "the slider of the recording must name the last position").not.toBeNull();

  await position.focus();
  await position.press("End");
  if ((await position.inputValue()) !== last) {
    for (let step = 0; step < 60 && (await position.inputValue()) !== last; step += 1) {
      await position.press("ArrowRight");
    }
  }
  await expect(position).toHaveValue(last as string);
}

/** Every symbol this module exports, so that a reader sees the whole surface of the list at once. */
export const __all__ = [
  "PageUnderTest",
  "PAGES_UNDER_TEST",
  "openThePage",
  "waitForThePageToSettle",
] as const;
