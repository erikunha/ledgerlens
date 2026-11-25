import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

/**
 * The number of the events of the published recording of the scenario S01, read from the bundle the site
 * serves. The recording is re-captured when the corpus moves, so the count is read and never written.
 */
const EVENTS = readFileSync(join(process.cwd(), "public", "replay", "s01", "events.jsonl"), "utf8")
  .split("\n")
  .filter((line) => line.trim().length > 0).length;


/**
 * The end to end test of the narrow screen of the public site.
 *
 * Why this file exists: the demo has to be readable on a phone, and the promise of a phone is a promise of width. The
 * document of the page must never be wider than the screen, the wide content of the recording must stay inside the
 * boxes that the design system gives a sideways scroll, and the position of the recording has to stay reachable and
 * usable with the fingers of a visitor or with the keys of a keyboard.
 *
 * Why the measurement is a measurement: the width of the document is read from the browser and compared with the width
 * of the screen, the page is asked to scroll sideways to see whether it can, and the boxes that scroll sideways on their
 * own are looked for one by one. A guess about the layout would prove nothing, and a layout that changes would keep
 * the guess true.
 *
 * The test runs against the static export served as plain files, exactly as the files arrive in a browser.
 */

/**
 * What the browser measured about the sideways scroll of a page.
 *
 * Why the measurement is a value and not a boolean: a failure has to name the numbers, so that the reader of a red run
 * sees the width of the document and the width of the screen and does not have to guess.
 */
interface SidewaysMeasurement {
  /** The width of the content of the document. */
  readonly documentScrollWidth: number;
  /** The width of the screen, as the browser reports it. */
  readonly documentClientWidth: number;
  /** How far the page scrolled sideways when it was asked to. */
  readonly windowScrollX: number;
  /** The boxes of the page that can scroll sideways on their own. */
  readonly scrollBoxes: ReadonlyArray<{
    readonly tag: string;
    readonly className: string;
    readonly scrollWidth: number;
    readonly clientWidth: number;
    readonly holdsATable: boolean;
  }>;
}

/**
 * Measures the sideways scroll of the page and names the boxes that can scroll on their own.
 *
 * Why the page is asked to scroll: a document that is wider than the screen can still refuse to scroll, and the question
 * of the narrow screen is not only how wide the document is but whether the visitor can drag it sideways.
 *
 * Why the boxes are looked for: a box with an `overflow-x` of `auto` or `scroll` is a box that holds more than it
 * shows and that the visitor can move sideways, and the promise of the narrow screen is about those boxes: the wide
 * content of the recording stays inside them, and nothing else of the page moves sideways.
 */
async function measureTheSideways(page: Page): Promise<SidewaysMeasurement> {
  return page.evaluate(() => {
    const root = document.documentElement;
    const scrollBoxes: Array<{
      tag: string;
      className: string;
      scrollWidth: number;
      clientWidth: number;
      holdsATable: boolean;
    }> = [];

    for (const element of Array.from(document.querySelectorAll("*"))) {
      const overflowX = window.getComputedStyle(element).overflowX;
      if (overflowX !== "auto" && overflowX !== "scroll") {
        continue;
      }
      scrollBoxes.push({
        tag: element.tagName,
        className: element.getAttribute("class") ?? "",
        scrollWidth: element.scrollWidth,
        clientWidth: element.clientWidth,
        holdsATable: element.querySelector("table") !== null,
      });
    }

    window.scrollTo(9999, 0);
    const windowScrollX = window.scrollX;
    window.scrollTo(0, 0);

    return {
      documentScrollWidth: root.scrollWidth,
      documentClientWidth: root.clientWidth,
      windowScrollX,
      scrollBoxes,
    };
  });
}

/**
 * Opens the route of the scenario and waits for the recording to be on the screen, at its end.
 *
 * Why the recording is read to its end: the panel of the evidence and the panel of the decision only hold their content
 * when the recording has reached the calls of the tools, so a measurement taken at the beginning would measure an empty
 * page.
 */
async function openTheRecordingAtItsEnd(page: Page): Promise<void> {
  await page.goto("/replay/scenario/S01");
  await expect(page.getByRole("table", { name: "The calls of the tools of the recorded run" })).toBeVisible();

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
 * Fails when the document of the page is wider than the screen or when the page scrolls sideways.
 *
 * Why the two checks: the width of the document is the promise of the narrow screen, and the scroll of the window is
 * what the visitor would feel. A page that is wide but that refuses to scroll is still a page that is too wide, so both
 * of them have to hold.
 */
function expectNoSidewaysScroll(measurement: SidewaysMeasurement, width: number): void {
  expect(
    measurement.documentScrollWidth,
    `the document of the page is ${measurement.documentScrollWidth} pixels wide and the screen is ${width} pixels wide`,
  ).toBeLessThanOrEqual(measurement.documentClientWidth);

  expect(
    measurement.windowScrollX,
    `the page scrolled ${measurement.windowScrollX} pixels sideways when it was asked to`,
  ).toBe(0);
}

/**
 * The names of the boxes that may scroll sideways, with the widths they hold.
 *
 * Why the names are collected: a failure has to say which box moved sideways, or the reader of a red run has to hunt
 * for it in the page.
 */
function namesOfTheScrollBoxes(measurement: SidewaysMeasurement): string {
  return measurement.scrollBoxes
    .map((box) => `${box.tag}.${box.className} (${box.scrollWidth} pixels in ${box.clientWidth} pixels)`)
    .join(", ");
}

test.describe("the narrow screen of 390 pixels", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("the pages of the site do not scroll sideways", async ({ page }) => {
    for (const route of [
      "/",
      "/replay",
      "/replay/scenario/S01",
      "/replay-real",
      "/replay-real/scenario/S01",
      "/sandbox",
      "/live",
      "/engineering",
    ]) {
      await page.goto(route);
      await expect(page.getByRole("main")).toBeVisible();

      const measurement = await measureTheSideways(page);

      expectNoSidewaysScroll(measurement, 390);
    }
  });

  test("the recorded demo does not scroll sideways in any of its sections", async ({ page }) => {
    await openTheRecordingAtItsEnd(page);

    for (const section of ["Execution", "Evidence", "Decision", "Provenance"]) {
      await page.getByRole("tab", { name: section }).click();
      await expect(page.getByRole("tab", { name: section })).toHaveAttribute("aria-selected", "true");

      const measurement = await measureTheSideways(page);

      expectNoSidewaysScroll(measurement, 390);
    }
  });

  test("the pane of the source of the recording is the only box of the evidence that scrolls sideways", async ({
    page,
  }) => {
    await openTheRecordingAtItsEnd(page);
    await page.getByRole("tab", { name: "Evidence" }).click();

    // The pane of the source is on the screen, and it is the box that the stylesheet gives a sideways scroll.
    const pane = page.locator("dd.ll-code-pane").first();
    await expect(pane).toBeVisible();

    const measurement = await measureTheSideways(page);

    // Every box that can scroll sideways on the panel of the evidence is a pane of the source. The statement of the
    // evidence is long, and it stays inside its own box instead of making the page move sideways.
    expect(
      measurement.scrollBoxes.length,
      `the boxes that can scroll sideways are ${namesOfTheScrollBoxes(measurement)}`,
    ).toBeGreaterThan(0);
    for (const box of measurement.scrollBoxes) {
      expect(
        box.className,
        `the box ${box.tag} of the panel of the evidence can scroll sideways and only a pane of the source may do it`,
      ).toContain("ll-code-pane");
    }

    // The page itself does not move sideways.
    expectNoSidewaysScroll(measurement, 390);
  });

  test("the dense content of the recording stays inside the boxes of its tables", async ({ page }) => {
    await openTheRecordingAtItsEnd(page);

    const measurement = await measureTheSideways(page);

    // The tables of the recording are dense and they are wider than the screen of the phone, so the box of a table
    // scrolls sideways. The promise is that the wide content stays inside the box of its table and that nothing else of
    // the page moves sideways.
    expect(
      measurement.scrollBoxes.length,
      `the boxes that can scroll sideways are ${namesOfTheScrollBoxes(measurement)}`,
    ).toBeGreaterThan(0);
    for (const box of measurement.scrollBoxes) {
      expect(
        box.holdsATable,
        `the box ${box.tag}.${box.className} can scroll sideways and only the box of a table may do it`,
      ).toBe(true);
    }

    expectNoSidewaysScroll(measurement, 390);
  });

  test("the position of the recording is reachable and usable", async ({ page }) => {
    await openTheRecordingAtItsEnd(page);

    const position = page.getByLabel("Position of the recording");
    await expect(position).toBeVisible();

    // The control of the position fits in the screen of the phone.
    const box = await position.boundingBox();
    expect(box).not.toBeNull();
    expect((box?.x ?? 0) + (box?.width ?? 0)).toBeLessThanOrEqual(390);

    // The control takes the focus, so a keyboard visitor reaches it.
    await position.focus();
    await expect(position).toBeFocused();

    // The visitor moves the recording with the keys and the recording moves.
    await position.press("Home");
    await expect(position).toHaveValue("0");
    await position.press("ArrowRight");
    await expect(position).toHaveValue("1");
    await expect(page.getByText(`Event 2 of ${EVENTS}.`)).toBeVisible();
  });
});

test.describe("the wide screen of 1440 pixels", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("the recorded demo does not scroll sideways", async ({ page }) => {
    await openTheRecordingAtItsEnd(page);

    for (const section of ["Execution", "Evidence", "Decision", "Provenance"]) {
      await page.getByRole("tab", { name: section }).click();
      await expect(page.getByRole("tab", { name: section })).toHaveAttribute("aria-selected", "true");

      const measurement = await measureTheSideways(page);

      expectNoSidewaysScroll(measurement, 1440);
    }
  });
});

/**
 * The guided path of the cold start on the narrow screen.
 *
 * Why the case exists: the guided path is the entrance of the site, and the entrance has to work
 * on a phone. The controls of the path are never smaller than 44 pixels, so a finger reaches them,
 * and the path never overflows the viewport, so the visitor never drags the page sideways to read
 * a step.
 */
test("the controls of the guided path are at least 44 pixels and the path never overflows the phone", async ({
  page,
}) => {
  await page.goto("/replay/scenario/S01");
  await expect(page.getByRole("heading", { name: "The guided path" })).toBeVisible();

  const controls = page.getByRole("button", { name: "Show me" });
  const count = await controls.count();
  expect(count, "the guide drew no step").toBeGreaterThan(0);
  for (let index = 0; index < count; index += 1) {
    const box = await controls.nth(index).boundingBox();
    expect(box?.height ?? 0, `the control of the step ${index + 1} is smaller than 44 pixels`).toBeGreaterThanOrEqual(
      44,
    );
  }

  const fork = page.getByRole("link", { name: /mutate this case/i });
  const forkBox = await fork.boundingBox();
  expect(forkBox?.height ?? 0, "the fork of the guided path is smaller than 44 pixels").toBeGreaterThanOrEqual(44);

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow, "the guided path overflows the viewport of the phone").toBeLessThanOrEqual(0);
});
