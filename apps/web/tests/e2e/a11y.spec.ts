import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// The list of the pages of the site and the way of opening them live in one module, so that the
// suite of the console walks exactly the pages this suite scans.
import { PAGES_UNDER_TEST, openThePage, waitForThePageToSettle } from "./pages-under-test";

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
 * the replay of a scenario, the sandbox, the live mode and the tour of the architecture, and the
 * replay has five sections that the visitor opens one at a time. A section that is closed is not in
 * the page, so each of the five is scanned on its own. The replay is scanned once more with the
 * drawer of a tool call open, because a window of the page is only a part of the page while it is
 * open, and the drawer is the part that a visitor of the recording opens (ADR-048).
 *
 * Why the list of the pages lives in a module of its own: the suite of the console walks exactly
 * the same pages, and a second list would be a second truth about which pages of the site exist.
 *
 * Why the suite never switches a rule off: a rule that is off hides a real problem from the people
 * who read the site. If a rule of the design tokens has to be off, the comment of the call says which
 * one and why, and the rule stays on for every other page.
 *
 * Why the case fails on the violations of a critical or a serious impact: FR-035 asks the scan to
 * report zero critical and zero serious violations on every page of the feature, and those are the
 * impacts that stop a visitor from reading the page. Every rule of axe stays on, and the message of
 * a failed case names every violation that the scan found, whatever its impact.
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
 * The impacts of the violations that stop a visitor from using the page.
 *
 * Why the two impacts and not every impact: FR-035 asks the scan to report zero critical and zero
 * serious violations on every page of the feature, and those are the impacts that stop a person
 * from reading the page. A violation of a smaller impact is a defect of the page too, and the
 * message of a failed case names every violation that the scan found, whatever its impact, so
 * nothing is hidden.
 */
const BLOCKING_IMPACTS: readonly string[] = ["critical", "serious"];

/**
 * Scans the page with axe and fails the case when the page has a violation of a blocking impact.
 *
 * Why the scan is the whole document and not a piece of it: the shell of the site carries the skip
 * link, the landmarks and the footer, and those are part of the page the visitor reads.
 *
 * Why no rule is switched off: a rule that is off hides a real problem from the people who read the
 * site, so the suite would rather be red than quiet.
 */
async function expectNoViolation(page: Page, name: string): Promise<void> {
  const results = await new AxeBuilder({ page }).analyze();

  const blocking = results.violations.filter((violation) =>
    BLOCKING_IMPACTS.includes(violation.impact ?? ""),
  );

  expect(
    blocking,
    `the page "${name}" has ${blocking.length} accessibility violation(s) of a critical or a serious impact found by axe:\n${describeViolations(
      blocking,
    )}\n\nThe scan found ${results.violations.length} violation(s) in total:\n${describeViolations(
      results.violations,
    )}`,
  ).toHaveLength(0);
}

for (const pageUnderTest of PAGES_UNDER_TEST) {
  test(`${pageUnderTest.name} has no accessibility violation`, async ({ page }) => {
    await openThePage(page, pageUnderTest);
    await expectNoViolation(page, pageUnderTest.name);
  });
}

/**
 * The navigation of the rooms of the demo in the header of the site.
 *
 * Why the case is here: the header is the only place where the visitor reaches the four rooms of the
 * site, and a navigation that carries no landmark and no name is a navigation that a reader of a
 * screen reader cannot jump to and cannot tell apart from another one.
 *
 * Why the case counts the links of the navigation: the navigation is the way into the rooms, and a
 * navigation that lost a room is a room that the visitor cannot reach from any page.
 */
test("the header carries a navigation landmark that names the rooms of the demo", async ({ page }) => {
  await page.goto("/");

  const navigation = page.getByRole("navigation", { name: "The rooms of the demo" });
  await expect(navigation).toBeVisible();

  // The five rooms of the site are the five links of the navigation. The site publishes two catalogs, and
  // each one is a room of its own, so that a visitor on one of them can reach the other one from any page
  // (ADR-075).
  await expect(navigation.getByRole("link")).toHaveCount(5);

  // The room the visitor is in is the one that is marked, and the mark is an attribute and not a
  // colour, so a reader that does not see the colour still hears where the visitor is.
  await page.goto("/replay");
  await expect(navigation.getByRole("link", { name: "Recorded demo" })).toHaveAttribute(
    "aria-current",
    "page",
  );

  // The room of the catalog of a real model is marked on its own pages, and the room of the scripted
  // model is not marked there: a header that announced the wrong room would tell the visitor that
  // the recording of a real model is the recording of the scripted model (ADR-075).
  await page.goto("/replay-real");
  await expect(navigation.getByRole("link", { name: "Real model" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  await expect(navigation.getByRole("link", { name: "Recorded demo" })).not.toHaveAttribute(
    "aria-current",
    "page",
  );
});

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

/**
 * The stepper of the run in the section of the execution.
 *
 * Why this case is here: the stepper is a panel of the section of the execution, so the scan of that section already
 * sees it, with no rule switched off and no exception. The case adds the proof that the panel is really there with the
 * steps of the recording, because a scan of a page that lost the stepper would still be green (ADR-050).
 */
test("the section of the execution of S01 carries the stepper of the run", async ({ page }) => {
  await page.goto("/replay/scenario/S01?tab=execution");

  const recordedRun = page.getByRole("region", { name: "The recorded run" });
  await expect(recordedRun).toBeVisible();
  await expect(recordedRun.getByText("mode: deterministic_sandbox")).toBeVisible();

  const stepper = page.getByRole("region", { name: "The steps of the run" });
  await expect(stepper).toBeVisible();
  await expect(stepper.getByRole("listitem")).toHaveCount(4);
});

/**
 * The guided path of the cold start, walked with the keyboard.
 *
 * Why the case exists: the guided path is the entrance of a visitor who knows nothing about the
 * repository, and an entrance that only a pointer reaches is an entrance that is closed to part of
 * the visitors. The case walks every control of the tour with the keyboard alone, and it checks
 * that the region the step announced is in the page and carries content, because a region that
 * carries nothing is a region that does not carry the step.
 */
test("the controls of the guided path are reached with the keyboard and the region of the step carries the step", async ({
  page,
}) => {
  await page.goto("/replay/scenario/S01");
  await expect(page.getByRole("heading", { name: "The guided path" })).toBeVisible();

  const controls = page.getByRole("button", { name: "Show me" });
  const count = await controls.count();
  expect(count, "the guide drew no step").toBeGreaterThan(0);

  for (let index = 0; index < count; index += 1) {
    const control = controls.nth(index);
    await control.focus();
    await expect(control).toBeFocused();
    await page.keyboard.press("Enter");

    // The region the step announced is in the page and carries content: the anchor of a region of
    // the page received the focus, or the panel of the section of the step is the one that is open.
    const announced = page
      .locator("[id^='ledgerlens-region-']:focus, [id^='ledgerlens-section-']:visible")
      .last();
    await expect(announced).not.toBeEmpty();
  }
});
