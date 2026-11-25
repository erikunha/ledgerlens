import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

// The origin of the site comes from the module of the suite, so the origin this file asserts is the
// origin the configuration really serves, and the checks of the network cannot become vacuous.
import { SITE_ORIGIN } from "./site-origin";

/**
 * The end to end test of the guided path of the cold start.
 *
 * Why this file exists: the guided path is the entrance of a visitor who knows nothing about the
 * repository, and the promises of that entrance are promises about the browser: the path issues no
 * request that leaves the site, it asks for no key, and the reader draws no event that the bundle
 * does not carry. A promise about the browser is proven in the browser, against the static export
 * served as plain files, and never in a unit test that simulates one.
 *
 * The listener of the requests is installed before the navigation, so the first request of the
 * page is already watched.
 */

/** The requests that left the origin of the site. */
let requestsThatEscaped: string[] = [];

test.beforeEach(async ({ page }) => {
  requestsThatEscaped = [];

  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.origin !== SITE_ORIGIN) {
      requestsThatEscaped.push(request.url());
    }
  });
});

/**
 * Opens the guided path from the catalog of the recorded demo.
 *
 * Why the path is opened from the catalog: the catalog is the page a visitor arrives at, and the
 * guided path is the link the catalog offers. The wait is the heading of the guide, because it
 * only exists once the scenario page drew the tour over the reader.
 */
async function openTheGuidedPath(page: Page): Promise<void> {
  await page.goto("/replay");
  await page.getByRole("link", { name: /start the guided path/i }).click();
  await expect(page.getByRole("heading", { name: "The guided path" })).toBeVisible();
}

/**
 * Walks every step of the guide, with the control of each step.
 *
 * Why the walk clicks every control: the promise is about the whole path and not about the first
 * screen of it, so the check happens after every step was asked for.
 */
async function walkEveryStep(page: Page): Promise<void> {
  const controls = page.getByRole("button", { name: "Show me" });
  const count = await controls.count();
  expect(count, "the guide drew no step").toBeGreaterThan(0);
  for (let index = 0; index < count; index += 1) {
    await controls.nth(index).click();
  }
}

test("the guided path issues no request that leaves the site", async ({ page }) => {
  await openTheGuidedPath(page);
  await walkEveryStep(page);

  expect(
    requestsThatEscaped,
    `the guided path must not call any origin other than ${SITE_ORIGIN}. The requests that escaped are: ${
      requestsThatEscaped.join(", ") || "none"
    }`,
  ).toHaveLength(0);
});

test("the guided path asks for no key", async ({ page }) => {
  await openTheGuidedPath(page);
  await walkEveryStep(page);

  // No dialog of a key, no field of a key, and no sentence that asks for one.
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.locator("input[type=password]")).toHaveCount(0);
  await expect(page.getByText(/api key/i)).toHaveCount(0);
});

test("the reader draws no event that the bundle does not carry", async ({ page }) => {
  const bundleEvents = readFileSync(
    join(process.cwd(), "public", "replay", "s01", "events.jsonl"),
    "utf8",
  )
    .split("\n")
    .filter((line) => line.trim().length > 0).length;

  await openTheGuidedPath(page);

  // The counter of the events names the total of the bundle and never a number above it.
  await expect(page.getByText(/^Event \d+ of \d+\.$/)).toContainText(`of ${bundleEvents}.`);

  // The slider of the position never goes past the last event of the bundle.
  const slider = page.getByRole("slider", { name: "Position of the recording" });
  const last = Number(await slider.getAttribute("max"));
  expect(last).toBe(bundleEvents - 1);

  // Seek to the end and back to the middle: the counter never shows an event above the bundle.
  await slider.fill(String(last));
  await expect(page.getByText(`Event ${bundleEvents} of ${bundleEvents}.`)).toBeVisible();
  await slider.fill(String(Math.floor(bundleEvents / 2)));
  const counter = page.getByText(/^Event \d+ of \d+\.$/);
  await expect(counter).toBeVisible();
  const shown = Number((await counter.textContent())?.match(/^Event (\d+) of/)?.[1]);
  expect(shown, "the reader showed an event above the position of the seek").toBeLessThanOrEqual(
    Math.floor(bundleEvents / 2) + 1,
  );
  expect(shown, "the reader showed an event the bundle does not carry").toBeLessThanOrEqual(bundleEvents);
});
