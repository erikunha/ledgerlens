import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Locator, type Page } from "@playwright/test";

// The origin of the site comes from the module of the suite, so the origin this file asserts is the
// origin the configuration really serves, and the checks of the network cannot become vacuous.
import { SITE_ORIGIN } from "./site-origin";

/**
 * The number of the events of the published recording of the scenario S01, read from the bundle the site
 * serves. The recording is re-captured when the corpus moves, so the count is read and never written.
 */
const EVENTS = readFileSync(join(process.cwd(), "public", "replay", "s01", "events.jsonl"), "utf8")
  .split("\n")
  .filter((line) => line.trim().length > 0).length;


/**
 * The end to end test of the recorded demo.
 *
 * Why this file exists: the recorded demo is the half of the demo that a visitor can use with no key, no provider and
 * no network. The only proof that this is true is a browser that opens the exported site and behaves like a visitor,
 * so the test runs against the static export served as plain files, exactly as the files arrive in a browser.
 *
 * The three promises the test proves are written down in the names of the cases: the recorded run plays on the exported
 * site, the mode the visitor reads is the sandbox and never a live one, and no request of the page leaves the origin of
 * the site for the origin of the backend.
 *
 * The reader moved to the route of the scenario, so the navigation of the three cases is the route of the scenario and
 * not the catalog. The three cases stay, with their names and their assertions, because the viewer keeps the accessible
 * names it always had. The catalog itself has its own suite, in `catalog.spec.ts`.
 *
 * Every assertion is about what the visitor sees, on the text that is on the screen. The queries use the roles and the
 * accessible names wherever the interface carries them, because the site is built for a reader with a screen reader.
 */

/**
 * The origin of the backend of the demo.
 *
 * Why the name is here: the recorded demo must never call it. The default of the site is this origin, and the live
 * mode is the only half of the demo that calls it.
 */
const BACKEND_ORIGIN = "http://localhost:8010";

/**
 * The requests the page made, and the ones that left the origin of the site.
 *
 * Why they are module state: the listener of the requests is installed before the navigation, so the first request of
 * the page is already watched. Every case ends with the same check, so no case of this file can pass with a request
 * that escaped.
 */
let requestsMade: string[] = [];
let requestsThatEscaped: string[] = [];

test.beforeEach(async ({ page }) => {
  requestsMade = [];
  requestsThatEscaped = [];

  page.on("request", (request) => {
    const url = new URL(request.url());
    requestsMade.push(request.url());
    if (url.origin !== SITE_ORIGIN) {
      requestsThatEscaped.push(request.url());
    }
  });
});

/**
 * Opens the recorded demo and waits for the recording to be on the screen.
 *
 * Why the table is the wait: the table of the calls of the tools appears only when the bundle of the scenario was
 * read and accepted, so it is the real sign that the recording is there. There is no sleep and no wait for a network
 * that does not come.
 */
async function openRecordedDemo(page: Page): Promise<void> {
  await page.goto("/replay/scenario/S01");
  await expect(page.getByRole("heading", { name: "Recorded demo", level: 1 })).toBeVisible();
  await expect(
    page.getByRole("table", { name: "The calls of the tools of the recorded run" }),
  ).toBeVisible();
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

/**
 * Fails when any request of the page left the origin of the site.
 *
 * Why the message names the URLs: a failure that only says that something escaped leaves the reader to guess what,
 * and the URL is the whole of the evidence.
 */
function expectEveryRequestStayedOnTheSite(): void {
  expect(
    requestsThatEscaped,
    `The recorded demo must not call any origin other than ${SITE_ORIGIN}. The requests that escaped are: ${
      requestsThatEscaped.join(", ") || "none"
    }`,
  ).toHaveLength(0);
}

test("the recorded demo plays the published recording on the exported site", async ({ page }) => {
  await openRecordedDemo(page);

  // The recorded run is a region with an accessible name, and the visitor reads it.
  const recordedRun = page.getByRole("region", { name: "The recorded run" });
  await expect(recordedRun).toBeVisible();

  // At the beginning of the recording there is no call of a tool yet.
  await expect(recordedRun.getByText("The recording has no call of a tool yet.")).toBeVisible();

  // The visitor seeks to the end of the recording and the run is played.
  const position = page.getByLabel("Position of the recording");
  await seekToTheEnd(position);

  await expect(recordedRun.getByText(`Event ${EVENTS} of ${EVENTS}.`)).toBeVisible();
  await expect(recordedRun.getByText("The status of the run is:")).toBeVisible();

  // The calls that the capture recorded are on the screen, with the names the capture gave.
  const calls = page.getByRole("table", { name: "The calls of the tools of the recorded run" });
  await expect(calls.getByRole("rowheader")).toHaveCount(4);
  await expect(calls.getByRole("rowheader", { name: "query_ledger" })).toBeVisible();
  await expect(calls.getByRole("rowheader", { name: "search_policies" })).toBeVisible();
  await expect(calls.getByRole("rowheader", { name: "get_reference_fx" })).toBeVisible();
  await expect(calls.getByRole("rowheader", { name: "calculate" })).toBeVisible();

  expectEveryRequestStayedOnTheSite();
});

test("the recorded demo shows the sandbox mode and never says that it is live", async ({ page }) => {
  await openRecordedDemo(page);

  const recordedRun = page.getByRole("region", { name: "The recorded run" });

  // The mode of the manifest is on the screen, and the page says the same mode.
  await expect(recordedRun.getByText("mode: deterministic_sandbox")).toBeVisible();
  await expect(page.getByText("mode: deterministic_sandbox").first()).toBeVisible();
  await expect(recordedRun.getByText("scenario: S01")).toBeVisible();
  await expect(recordedRun.getByText("run: replay-s01")).toBeVisible();
  await expect(recordedRun.getByText("capture: scripted_fixture")).toBeVisible();

  // The note of the capture says out loud that the recording is not a live execution.
  await expect(
    recordedRun.getByText("This is not a live execution and it calls no model."),
  ).toBeVisible();

  // The recording is never presented as a live run. The page links to the live mode, so the check is about the labels
  // of the recording and not about the word live.
  await expect(page.getByText("mode: live")).toHaveCount(0);
  await expect(recordedRun.getByText("live run")).toHaveCount(0);

  expectEveryRequestStayedOnTheSite();
});

test("the recorded demo never calls the origin of the backend", async ({ page }) => {
  // The catalog is opened first, because the catalog of the scenarios is the file that the reader of the site reads
  // before it opens a bundle.
  await page.goto("/replay");
  await expect(page.getByRole("heading", { name: "The scenarios" })).toBeVisible();

  await openRecordedDemo(page);

  // The artifacts of the published recording are read from the origin of the site itself, so the check is not
  // vacuous: the requests really happened.
  expect(requestsMade.some((url) => url.includes("/replay/index.json"))).toBe(true);
  expect(requestsMade.some((url) => url.includes("/replay/s01/manifest.json"))).toBe(true);
  expect(requestsMade.some((url) => url.includes("/replay/s01/events.jsonl"))).toBe(true);

  // Every request of the page went to the origin of the site.
  expect(requestsMade.length).toBeGreaterThan(0);
  for (const url of requestsMade) {
    expect(new URL(url).origin, `the request to ${url} must go to ${SITE_ORIGIN}`).toBe(SITE_ORIGIN);
  }

  // The origin of the backend is never called.
  expect(
    requestsMade.filter((url) => url.startsWith(BACKEND_ORIGIN)),
    `the recorded demo must not call ${BACKEND_ORIGIN}`,
  ).toHaveLength(0);

  expectEveryRequestStayedOnTheSite();
});
