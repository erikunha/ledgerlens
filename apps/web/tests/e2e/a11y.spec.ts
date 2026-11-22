import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

/**
 * The end to end suite of the accessibility of the public site.
 *
 * Why this file exists: the site is a static export that a visitor reads with a screen reader, with a
 * keyboard or with a magnifier. The unit tests of the components check the rules of the repository
 * about the tabs, the outline of the headings, the controls that are never really disabled and the
 * focus that comes back to the trigger of a drawer, but a unit test never sees the page as a browser
 * builds it. This suite is the layer that walks the real pages of the export and asks the engine of
 * the industry what a person would really trip on.
 *
 * Why the pages are the ones of the public site: a visitor only ever sees the landing, the catalog,
 * the replay of a scenario, the sandbox and the live mode, and the replay has five sections that the
 * visitor opens one at a time. A section that is closed is not in the page, so each of the five is
 * scanned on its own. The replay is scanned once more with the drawer of a tool call open, because
 * a window of the page is only a part of the page while it is open, and the drawer is the part that
 * a visitor of the recording opens (ADR-048).
 *
 * Why the suite never switches a rule off: a rule that is off hides a real problem from the people
 * who read the site. If a rule of the design tokens has to be off, the comment of the call says which
 * one and why, and the rule stays on for every other page.
 *
 * The suite runs against the static export served as plain files, exactly as the files arrive in a
 * browser, in the two engines and the two viewports of the design package.
 */

/**
 * The results of one run of axe on one page.
 *
 * Why the type comes from the builder itself: the package of axe owns the shape of the results, and
 * a type written by hand here would drift away from the package the first time it changes.
 */
type AxeResults = Awaited<ReturnType<AxeBuilder["analyze"]>>;

/**
 * One violation that axe found on a page.
 *
 * Why the type is taken from the results: a violation is a node of the results of axe, and the
 * reader of the failure message has to see the same fields that axe itself reports.
 */
type AxeViolation = AxeResults["violations"][number];

/**
 * One page of the public site that the suite scans.
 */
interface PageUnderTest {
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
 * The label of the tab of the replay and the heading of the section it opens.
 *
 * Why the label and the heading travel together: the section of the replay is only in the page when
 * its tab is the open one, so the suite waits for the heading of the section and not only for the
 * label of the tab, which is always on the screen.
 */
const REPLAY_SECTIONS = [
  { label: "Execution", heading: "The execution of the recording" },
  { label: "Ledger", heading: "The ledger of the recording" },
  { label: "Evidence", heading: "The evidence of the recording" },
  { label: "Decision", heading: "The decision of the recording" },
  { label: "Provenance", heading: "The provenance of the recording" },
] as const;

/**
 * Waits until the page has no request of its own in flight.
 *
 * Why the wait: the sandbox and the live mode read the catalogue of the scenarios from the backend
 * of the demo, and the answer arrives after the page has already drawn its shell. A scan that ran in
 * the middle of that answer would report the state of a page that nobody ever sees.
 *
 * Why the failure is tolerated: a page that never settles is a page that is still waiting for
 * something, and the wait of the page itself is the one that has to fail when that happens.
 */
async function waitForThePageToSettle(page: Page): Promise<void> {
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
async function openThePage(page: Page, pageUnderTest: PageUnderTest): Promise<void> {
  await page.goto(pageUnderTest.path);
  await pageUnderTest.settle(page);
  await waitForThePageToSettle(page);
}

/**
 * Turns the violations of axe into a message a person can act on.
 *
 * Why the message names the rule, the selector and the reason: a report that only says that axe
 * found something leaves the reader with nothing to look at. The rule says what kind of problem it
 * is, the selector says where it is, and the reason says why the page is a problem for the person
 * who reads it.
 */
function describeViolation(violation: AxeViolation): string {
  const nodes = violation.nodes.map((node) => {
    const selector = node.target.join(" ");
    const reason = node.failureSummary ?? node.any[0]?.message ?? violation.description;

    return [`      selector: ${selector}`, `      reason: ${reason.replace(/\n/g, "\n      ")}`].join("\n");
  });

  return [
    `    rule: ${violation.id}`,
    `    impact: ${violation.impact ?? "unknown"}`,
    `    help: ${violation.help}`,
    `    reference: ${violation.helpUrl}`,
    ...nodes,
  ].join("\n");
}

/**
 * Turns the whole list of violations into the message of a failed case.
 */
function describeViolations(violations: readonly AxeViolation[]): string {
  return violations.map(describeViolation).join("\n\n");
}

/**
 * Scans the page with axe and fails the case when the page has a violation.
 *
 * Why the scan is the whole document and not a piece of it: the shell of the site carries the skip
 * link, the landmarks and the footer, and those are part of the page the visitor reads.
 *
 * Why no rule is switched off: a rule that is off hides a real problem from the people who read the
 * site, so the suite would rather be red than quiet.
 */
async function expectNoViolation(page: Page, name: string): Promise<void> {
  const results = await new AxeBuilder({ page }).analyze();

  expect(
    results.violations,
    `the page "${name}" has ${results.violations.length} accessibility violation(s) found by axe:\n${describeViolations(
      results.violations,
    )}`,
  ).toHaveLength(0);
}

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

/**
 * The pages of the public site, and the wait of each one of them.
 *
 * Why the wait of the replay names the manifest of the capture: the manifest arrives with the
 * bundle of the scenario, and the ledger of the recording arrives with the same bundle, so the
 * moment the manifest is on the screen is the moment every panel of the replay has its content.
 */
const PAGES_UNDER_TEST: readonly PageUnderTest[] = [
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

for (const pageUnderTest of PAGES_UNDER_TEST) {
  test(`${pageUnderTest.name} has no accessibility violation`, async ({ page }) => {
    await openThePage(page, pageUnderTest);
    await expectNoViolation(page, pageUnderTest.name);
  });
}

for (const section of REPLAY_SECTIONS) {
  test(`the replay of S01 has no accessibility violation in the section of ${section.label}`, async ({
    page,
  }) => {
    await page.goto(`/replay/scenario/S01?tab=${section.label.toLowerCase()}`);

    // The bundle of the scenario has been read, so every panel of the replay has its content.
    const recordedRun = page.getByRole("region", { name: "The recorded run" });
    await expect(recordedRun).toBeVisible();
    await expect(recordedRun.getByText("mode: deterministic_sandbox")).toBeVisible();

    // The section that the address of the page asks for is the open one, and it is the only one in
    // the page, so the scan is the scan of that section and not of the whole replay.
    await expect(page.getByRole("tab", { name: section.label })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("heading", { name: section.heading })).toBeVisible();

    await waitForThePageToSettle(page);
    await expectNoViolation(page, `the section of ${section.label} of the replay of S01`);
  });
}
