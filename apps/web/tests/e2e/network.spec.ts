import { expect, test, type Page } from "@playwright/test";

// The origin of the site comes from the module of the suite, so the origin this file asserts is the
// origin the configuration really serves, and the checks of the network cannot become vacuous.
import { SITE_ORIGIN } from "./site-origin";

/**
 * The end to end test of the guard of the network.
 *
 * Why this file exists: the recorded demo is the half of the demo that works with no key, no provider and no network,
 * and the only proof that this is true is a browser that watches every request the page makes. The recorded demo reads
 * the published artifacts of the site, and every one of those requests has to go to the origin of the site itself: a
 * request to the origin of the backend would mean that the recorded demo talks to the backend of the live mode, and
 * that the promise of the offline demo is not kept.
 *
 * The test runs against the static export served as plain files. The listener of the requests is installed before the
 * navigation, so the first request of the page is already watched.
 */

/**
 * The origin of the backend of the demo.
 *
 * Why the name is here: the recorded demo must never call it. The default of the site is this origin, and the live
 * mode is the only half of the demo that calls it.
 */
const BACKEND_ORIGIN = "http://localhost:8010";

/** The requests the page made, and the ones that left the origin of the site. */
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
 * Opens the two pages of the recorded demo, the catalog and the route of the scenario.
 *
 * Why both of them: the catalog reads the catalog of the scenarios and the route reads the bundle of the scenario, so
 * the two pages between them make every request that the recorded demo ever makes. The wait is the table of the calls
 * of the tools, because it appears only when the bundle was read, and the request of the file of the events is one of
 * the requests that the check below looks for.
 */
async function openTheRecordedDemo(page: Page): Promise<void> {
  await page.goto("/replay");
  await expect(page.getByRole("heading", { name: "The scenarios" })).toBeVisible();

  await page.goto("/replay/scenario/S01");
  await expect(
    page.getByRole("table", { name: "The calls of the tools of the recorded run" }),
  ).toBeVisible();
}

test("every request of the page stays on the origin of the site", async ({ page }) => {
  await openTheRecordedDemo(page);

  // The check is not vacuous: the pages really made requests.
  expect(requestsMade.length).toBeGreaterThan(0);

  for (const url of requestsMade) {
    expect(new URL(url).origin, `the request to ${url} must go to ${SITE_ORIGIN}`).toBe(SITE_ORIGIN);
  }

  expect(
    requestsThatEscaped,
    `the recorded demo must not call any origin other than ${SITE_ORIGIN}. The requests that escaped are: ${
      requestsThatEscaped.join(", ") || "none"
    }`,
  ).toHaveLength(0);
});

test("the origin of the backend is never called", async ({ page }) => {
  await openTheRecordedDemo(page);

  // The artifacts of the published recording are read from the origin of the site itself, so the check is not
  // vacuous: the requests really happened.
  expect(requestsMade.some((url) => url.includes("/replay/index.json"))).toBe(true);
  expect(requestsMade.some((url) => url.includes("/replay/s01/manifest.json"))).toBe(true);
  expect(requestsMade.some((url) => url.includes("/replay/s01/events.jsonl"))).toBe(true);

  // The origin of the backend is never called.
  expect(
    requestsMade.filter((url) => url.startsWith(BACKEND_ORIGIN)),
    `the recorded demo must not call ${BACKEND_ORIGIN}`,
  ).toHaveLength(0);
});
