import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Locator, type Page } from "@playwright/test";

/**
 * The number of the events of the published recording of the scenario S01, read from the bundle the site
 * serves. The recording is re-captured when the corpus moves, so the count is read and never written.
 */
const EVENTS = readFileSync(join(process.cwd(), "public", "replay", "s01", "events.jsonl"), "utf8")
  .split("\n")
  .filter((line) => line.trim().length > 0).length;


/**
 * The end to end test of the route of a scenario of the recorded demo.
 *
 * Why this file exists: the route of a scenario is the promise of the milestone. It shows the recorded run, the tree of
 * the investigation, the timeline, the provenance and the evidence, it lets the visitor walk through the recording and
 * come back to the same place, and it keeps the state of the visit in the URL with a closed allow list, so that a link
 * never carries a key, a handle, an answer or a free text of any kind.
 *
 * The test runs against the static export served as plain files, exactly as the files arrive in a browser. Every
 * assertion is about what the visitor sees and about the address of the page.
 */

/**
 * Shows a panel of the replay and proves that it is on the screen.
 *
 * Why the section is opened when the panel is not there yet: the panels of the replay live in the sections of the
 * replay, and a section that is not the open one is not in the page. The helper proves that the panel exists and that
 * the visitor can reach it.
 */
async function expectPanel(page: Page, name: string, section?: string): Promise<void> {
  const panel = page.getByRole("region", { name });

  if ((await panel.count()) === 0 && section !== undefined) {
    await page.getByRole("tab", { name: section }).click();
  }

  await expect(panel).toBeVisible();
}

/**
 * Opens the route of the scenario and waits for the recording to be on the screen.
 *
 * Why the table is the wait: the table of the calls of the tools appears only when the bundle of the scenario was
 * read and accepted, so it is the real sign that the recording is there. There is no sleep and no wait for a network
 * that does not come.
 */
async function openScenario(page: Page): Promise<void> {
  await page.goto("/replay/scenario/S01");
  await expect(page.getByRole("table", { name: "The calls of the tools of the recorded run" })).toBeVisible();
}

/**
 * Moves the slider of the recording to its last position, the way a visitor does.
 *
 * Why the keyboard: the control is a range input, so the visitor moves it with the keys. The End key moves it to the
 * last event, and the arrow key is the fallback for an engine that does not honor the End key on a slider.
 */
async function seekToTheEnd(position: Locator): Promise<void> {
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

test("the route of the scenario shows the overview, the tree, the timeline, the provenance and the evidence", async ({
  page,
}) => {
  await openScenario(page);

  // The recorded run is a region with an accessible name, and the visitor reads it.
  const recordedRun = page.getByRole("region", { name: "The recorded run" });
  await expect(recordedRun).toBeVisible();

  // The mode of the manifest, the scenario and the capture are on the screen, word for word as the artifact wrote them.
  await expect(recordedRun.getByText("mode: deterministic_sandbox")).toBeVisible();
  await expect(recordedRun.getByText("scenario: S01")).toBeVisible();
  await expect(recordedRun.getByText("run: replay-s01")).toBeVisible();
  await expect(recordedRun.getByText("capture: scripted_fixture")).toBeVisible();

  // The calls of the tools are on the screen when the visitor reaches the end of the recording, with the names the
  // capture gave them.
  const calls = page.getByRole("table", { name: "The calls of the tools of the recorded run" });
  await expect(calls).toBeVisible();
  await seekToTheEnd(page.getByLabel("Position of the recording"));
  await expect(calls.getByRole("rowheader", { name: "query_ledger" })).toBeVisible();
  await expect(calls.getByRole("rowheader", { name: "search_policies" })).toBeVisible();
  await expect(calls.getByRole("rowheader", { name: "get_reference_fx" })).toBeVisible();
  await expect(calls.getByRole("rowheader", { name: "calculate" })).toBeVisible();

  // The panels of the milestone are on the screen.
  await expectPanel(page, "The tree of the investigation", "Execution");
  await expectPanel(page, "The timeline of the recording", "Execution");
  await expectPanel(page, "The evidence of the answer", "Evidence");
  await expectPanel(page, "The claims of the answer", "Decision");

  // The amounts of the answer keep the money and the percentage apart. The money wears the currency of the run, and the
  // percentage wears the symbol of the percentage and no currency at all: a percentage is not money. The check runs
  // while the section of the decision is the open one, because the panel of the amounts lives in it.
  const amounts = page.getByRole("region", { name: "The amounts of the answer" });
  await expect(amounts).toBeVisible();
  await expect(amounts.getByText("BRL 566.79")).toBeVisible();
  await expect(amounts.getByText("BRL 549.31")).toBeVisible();
  await expect(amounts.getByText("2.50%")).toBeVisible();
  await expect(amounts.getByText("BRL 2.50")).toHaveCount(0);

  await expectPanel(page, "The provenance of the recording", "Provenance");
});

test("the visitor steps forward and backward and the screen is the same for the same position", async ({ page }) => {
  await openScenario(page);

  const recordedRun = page.getByRole("region", { name: "The recorded run" });
  await expect(recordedRun).toBeVisible();

  const atTheBeginning = await recordedRun.innerText();

  // One step forward changes the state of the screen.
  await page.getByRole("button", { name: "Next event" }).click();
  await expect.poll(async () => recordedRun.innerText()).not.toBe(atTheBeginning);

  // One step back brings the visitor to the state they came from, because the state at a position always comes from
  // the reducer of the events of the repository.
  await page.getByRole("button", { name: "Previous event" }).click();
  await expect.poll(async () => recordedRun.innerText()).toBe(atTheBeginning);
});

test("the reset of the recording returns the visitor to the beginning", async ({ page }) => {
  await openScenario(page);

  const recordedRun = page.getByRole("region", { name: "The recorded run" });
  await expect(recordedRun).toBeVisible();

  const position = page.getByLabel("Position of the recording");
  await seekToTheEnd(position);
  await expect(recordedRun.getByText(`Event ${EVENTS} of ${EVENTS}.`)).toBeVisible();

  await page.getByRole("button", { name: "Restart the recording" }).click();

  await expect(position).toHaveValue("0");
  await expect(recordedRun.getByText("The recording has no call of a tool yet.")).toBeVisible();
});

test("the URL of the page holds the identifier and the preferences and nothing else", async ({ page }) => {
  await openScenario(page);

  await expect(page.getByRole("region", { name: "The recorded run" })).toBeVisible();

  // The path holds the identifier of the scenario and nothing else.
  const url = new URL(page.url());
  expect(url.pathname).toBe("/replay/scenario/S01");

  // The query string holds only the two preferences of the contract. A key, a handle, an answer or a free text of any
  // kind never reaches the address of the page.
  for (const key of url.searchParams.keys()) {
    expect(["tab", "speed"], `the address of the page must not carry the parameter ${key}`).toContain(key);
  }

  // The visitor who picks a section sees it in the address, and nothing else goes with it.
  await page.getByRole("tab", { name: "Evidence" }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get("tab")).toBe("evidence");

  const afterTheChoice = new URL(page.url());
  expect(afterTheChoice.pathname).toBe("/replay/scenario/S01");
  for (const key of afterTheChoice.searchParams.keys()) {
    expect(["tab", "speed"], `the address of the page must not carry the parameter ${key}`).toContain(key);
  }
});

test("a visitor who arrives with a bare link keeps the route of the scenario", async ({ page }) => {
  await page.goto("/replay/scenario/S01?tab=evidence&speed=4");

  // The preferences of the URL are read and the route stays the route of the scenario.
  await expect(page.getByRole("region", { name: "The recorded run" })).toBeVisible();
  const url = new URL(page.url());
  expect(url.pathname).toBe("/replay/scenario/S01");
  expect(url.searchParams.get("tab")).toBe("evidence");
  expect(url.searchParams.get("speed")).toBe("4");
});
