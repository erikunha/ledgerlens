import { expect, test, type Page } from "@playwright/test";

// The origin of the site comes from the module of the suite, so the origin this file asserts is the
// origin the configuration really serves, and the checks of the network cannot become vacuous.
import { SITE_ORIGIN } from "./site-origin";

/**
 * The end to end test of the stepper of the run and of the live region of the reader.
 *
 * Why this file exists: the tree of the investigation answers which span opened which span and the timeline answers
 * what happened event by event, and neither of them answers the question a visitor asks first: how far along the run
 * am I, and which call is the current one. The stepper answers it, and the region of the reader announces it once per
 * step. Both of them are new pieces of the page, and both of them can break the page without breaking a single
 * component: a stepper that adds a stop of the keyboard changes the way the whole page is walked, and a region that is
 * rewritten on every event of the recording talks over the visitor who is reading it (ADR-050).
 *
 * Why the suite proves the keyboard path: the stepper is an indicator and never a control, so it must add no stop of
 * the keyboard, the tree must still be walked with the arrow keys and with Home and End, and the Enter key on the cell
 * of the event number must still move the recording.
 *
 * Why the suite proves the announcement path: the region speaks once per step, and never on an event that does not
 * change the step. The recording of the scenario S01 crosses four steps, and the region says six sentences in the whole
 * playback: the start, the four steps and the end.
 *
 * Why the suite watches the network: the recorded demo reads the published artifacts of the site and nothing else, so
 * every request it makes has to go to the origin of the site itself.
 *
 * The suite runs against the static export served as plain files, in the two engines and the two viewports of the
 * design package.
 */

/**
 * Opens the route of the scenario and waits for the recording to be on the screen.
 *
 * Why the table is the wait: the table of the calls of the tools appears only when the bundle of the scenario was read
 * and accepted, so it is the real sign that the recording is there. There is no sleep and no wait for a network that
 * does not come.
 */
async function openScenario(page: Page): Promise<void> {
  await page.goto("/replay/scenario/S01");
  await expect(page.getByRole("table", { name: "The calls of the tools of the recorded run" })).toBeVisible();
}

/**
 * Moves the recording to an event of the recording, the way a visitor moves it with the timeline.
 *
 * Why the number of the event and not the position: the events of the published recording carry contiguous sequence
 * numbers, and the number of an event is the name the visitor reads on the timeline.
 */
async function moveToTheEvent(page: Page, seq: number): Promise<void> {
  const timeline = page.getByRole("region", { name: "The timeline of the recording" });
  await timeline.getByRole("button", { name: String(seq), exact: true }).click();
  await expect(page.getByText(`Event ${seq} of 57.`)).toBeVisible();
}

test.describe("the stepper of the run", () => {
  test("shows the four steps of the recording of S01", async ({ page }) => {
    await openScenario(page);

    const stepper = page.getByRole("region", { name: "The steps of the run" });
    await expect(stepper).toBeVisible();

    const steps = stepper.getByRole("listitem");
    await expect(steps).toHaveCount(4);
    await expect(steps.nth(0)).toContainText("Step 1 of 4: query_ledger.");
    await expect(steps.nth(1)).toContainText("Step 2 of 4: search_policies.");
    await expect(steps.nth(2)).toContainText("Step 3 of 4: get_reference_fx.");
    await expect(steps.nth(3)).toContainText("Step 4 of 4: calculate.");
  });

  test("adds no stop of the keyboard", async ({ page }) => {
    await openScenario(page);

    const stepper = page.getByRole("region", { name: "The steps of the run" });
    await expect(stepper).toBeVisible();

    // The stepper is an indicator: it holds no control and no stop of the keyboard of its own.
    await expect(stepper.getByRole("button")).toHaveCount(0);
    await expect(stepper.getByRole("link")).toHaveCount(0);

    const stops = await stepper.evaluate(
      (node) =>
        node.querySelectorAll(
          'a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])',
        ).length,
    );
    expect(stops, "the stepper must not add a stop of the keyboard").toBe(0);

    // The walk of the keyboard of the page goes on and never lands inside the stepper.
    await page.getByLabel("Position of the recording").focus();
    for (let step = 0; step < 12; step += 1) {
      await page.keyboard.press("Tab");
      const inside = await page.evaluate(() => {
        const region = document.querySelector('[aria-label="The steps of the run"]');
        return region !== null && region.contains(document.activeElement);
      });
      expect(inside, "the focus must never land inside the stepper").toBe(false);
    }
  });

  test("leaves the tree and the timeline of the recording as they were", async ({ page }) => {
    await openScenario(page);

    /*
     * The recording is walked to its end, so that the tree carries every span of the capture: the tree of the
     * investigation shows the spans that already happened, and at the first event it holds only the first one.
     */
    const position = page.getByLabel("Position of the recording");
    await position.focus();
    await position.press("End");
    const last = await position.getAttribute("max");
    if ((await position.inputValue()) !== last) {
      for (let step = 0; step < 60 && (await position.inputValue()) !== last; step += 1) {
        await position.press("ArrowRight");
      }
    }
    await expect(page.getByText("Event 57 of 57.")).toBeVisible();

    // The tree is still walked with the arrow keys and with Home and End.
    const tree = page.getByRole("tree");
    const items = tree.getByRole("treeitem");
    await items.first().focus();

    await page.keyboard.press("ArrowDown");
    await expect(items.nth(1)).toBeFocused();

    await page.keyboard.press("End");
    await expect(items.last()).toBeFocused();

    await page.keyboard.press("Home");
    await expect(items.first()).toBeFocused();

    // The Enter key on the cell of the event number still moves the recording.
    const timeline = page.getByRole("region", { name: "The timeline of the recording" });
    await timeline.locator('[data-cell="15:0"]').focus();
    await page.keyboard.press("Enter");
    await expect(page.getByText("Event 16 of 57.")).toBeVisible();
  });
});

test.describe("the live region of the reader", () => {
  test("announces the step of the run once per step", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "no-preference" });
    await openScenario(page);

    const region = page.getByRole("status");

    // The region is empty while the recording stands at its first event and the playback has not started.
    expect(await region.evaluate((node) => node.textContent ?? "")).toBe("");

    await page.getByRole("button", { name: "Play the recording" }).click();

    // The focus moves to the region once, when the playback starts, and the region says the start of the recording.
    await expect(region).toBeFocused();
    await expect(region).toHaveText("The recording has not called a tool yet. It makes 4 calls.");

    // The recording is paused, so that the case walks it by hand and the steps do not move under the case.
    await page.getByRole("button", { name: "Pause the recording" }).click();
    await expect(page.getByText("The recording is not playing.")).toBeAttached();

    /*
     * The visitor takes the focus back before the recording moves. The region must never pull the focus again: a
     * reader that is pulled back to the region on every event of the recording never hears the recording at all
     * (FR-032).
     */
    await page.getByLabel("Position of the recording").focus();

    // The first step of the run: the call of the query of the ledger.
    await moveToTheEvent(page, 16);
    await expect(region).toHaveText("Step 1 of 4: query_ledger.");
    await expect(region).not.toBeFocused();

    // The recording moves INSIDE the step, and the region says the same sentence: the region speaks once per step.
    await moveToTheEvent(page, 19);
    await expect(region).toHaveText("Step 1 of 4: query_ledger.");

    // The recording crosses the three other steps of the run.
    await moveToTheEvent(page, 26);
    await expect(region).toHaveText("Step 2 of 4: search_policies.");

    await moveToTheEvent(page, 34);
    await expect(region).toHaveText("Step 3 of 4: get_reference_fx.");

    await moveToTheEvent(page, 42);
    await expect(region).toHaveText("Step 4 of 4: calculate.");
  });

  test("never carries the counter of the events", async ({ page }) => {
    await openScenario(page);

    // The counter of the events stays visible in the page as ordinary text.
    await expect(page.getByText("Event 1 of 57.")).toBeVisible();

    // The region is moved to a step of the run, and it still carries no counter of the events.
    await moveToTheEvent(page, 16);

    const region = page.getByRole("status");
    await expect(region).toHaveText("Step 1 of 4: query_ledger.");
    await expect(page.getByText("Event 16 of 57.")).toBeVisible();
    expect(await region.evaluate((node) => node.textContent ?? "")).not.toMatch(/Event/);
  });
});

test("every request of the page stays on the origin of the site", async ({ page }) => {
  const requestsMade: string[] = [];
  const requestsThatEscaped: string[] = [];

  page.on("request", (request) => {
    const url = new URL(request.url());
    requestsMade.push(request.url());
    if (url.origin !== SITE_ORIGIN) {
      requestsThatEscaped.push(request.url());
    }
  });

  await openScenario(page);

  // The check is not vacuous: the page really made requests.
  expect(requestsMade.length).toBeGreaterThan(0);

  expect(
    requestsThatEscaped,
    `the recorded demo must not call any origin other than ${SITE_ORIGIN}. The requests that escaped are: ${
      requestsThatEscaped.join(", ") || "none"
    }`,
  ).toHaveLength(0);
});
