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
 * The end to end test of the playback of the recorded run.
 *
 * Why this file exists: a recording that a visitor cannot walk through is a recording nobody can trust. The visitor
 * starts the recording, stops it, steps forward and backward, moves it with the slider, restarts it and changes its
 * speed. Two promises are checked here and they are the two that the site makes: the state of the screen at a position
 * is always the same, however the visitor reached that position, and the speed never changes the order of the events
 * nor the timing the panels show.
 *
 * Why the suite runs with two devices: the site turns the automatic playback off when the device asks for less motion,
 * so the device that asks for it is the device where the visitor walks through the recording by hand, and the device
 * that does not ask for it is the device where the recording moves by itself. The cases of the two devices never mix,
 * because the site answers the preference of the device and not the wish of the test. The two devices are driven by the
 * emulation of the media feature of the page, because the site reads the preference of the device with `matchMedia` and
 * answers it as soon as the page is open.
 *
 * The test runs against the static export served as plain files, exactly as the files arrive in a browser. Every
 * assertion is about what the visitor sees and about what the controls do.
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
 * Moves the recording forward with the keys of the slider, the way a keyboard visitor does.
 *
 * Why the slider and not the buttons of the playback: the slider is another way to reach a position, and the screen at
 * a position has to be the same however the visitor reached it.
 */
async function moveForwardWithTheKeys(page: Page, steps: number): Promise<void> {
  const position = page.getByLabel("Position of the recording");
  await position.focus();
  for (let step = 0; step < steps; step += 1) {
    await position.press("ArrowRight");
  }
}

/**
 * Plays the recording until it stands at the given position, and says how long the browser waited.
 *
 * Why the time is measured: the speed of the playback is a promise about the interval between two events, so the only
 * way to prove that the speed changes the interval is to measure the wait of the browser.
 */
async function timeUntilThePosition(page: Page, target: number): Promise<number> {
  const position = page.getByLabel("Position of the recording");
  const started = Date.now();

  await expect
    .poll(async () => Number(await position.inputValue()), { timeout: 20_000 })
    .toBeGreaterThanOrEqual(target);

  return Date.now() - started;
}

test.describe("the playback with the device that asks for less motion", () => {
  test.beforeEach(async ({ page }) => {
    // The device asks for less motion before the page is opened, so the site reads the preference of the device from
    // the first moment. The emulation of the media feature is the way a test drives the preference of a device.
    await page.emulateMedia({ reducedMotion: "reduce" });
  });

  test("the automatic playback is off and the control says why", async ({ page }) => {
    await openScenario(page);

    const play = page.getByRole("button", { name: "Play the recording" });
    const position = page.getByLabel("Position of the recording");

    // The control cannot act, and it says why it cannot act.
    await expect(play).toHaveAttribute("aria-disabled", "true");
    await expect(
      page.getByText("The automatic playback is off because this device asks for less motion."),
    ).toBeVisible();

    // The visitor who presses it anyway does not move the recording. The press is dispatched and not clicked, because a
    // browser driver refuses to press a control that carries `aria-disabled`, and the proof is about the site and not
    // about the driver.
    await play.dispatchEvent("click");
    await expect(position).toHaveValue("0");

    // The wait is longer than the interval of the clock, so the check is not a check of a moment.
    await page.waitForTimeout(600);
    await expect(position).toHaveValue("0");
  });

  test("the step forward and the step back move the recording and the screen is the same for the same position", async ({
    page,
  }) => {
    await openScenario(page);

    const recordedRun = page.getByRole("region", { name: "The recorded run" });
    const position = page.getByLabel("Position of the recording");
    const atTheBeginning = await recordedRun.innerText();

    // One step forward changes the screen.
    await page.getByRole("button", { name: "Next event" }).click();
    await expect.poll(async () => recordedRun.innerText()).not.toBe(atTheBeginning);

    // One step back brings the visitor to the screen they came from.
    await page.getByRole("button", { name: "Previous event" }).click();
    await expect.poll(async () => recordedRun.innerText()).toBe(atTheBeginning);

    // The same position reached in another way gives the same screen. The state of a position always comes from the
    // reducer of the events of the repository, and never from the way the visitor reached that position.
    await moveForwardWithTheKeys(page, 5);
    await expect(position).toHaveValue("5");
    const byTheSlider = await recordedRun.innerText();

    await page.getByRole("button", { name: "Restart the recording" }).click();
    await expect(position).toHaveValue("0");
    await moveForwardWithTheKeys(page, 5);
    await expect(position).toHaveValue("5");
    const byTheSteps = await recordedRun.innerText();

    expect(byTheSteps).toBe(byTheSlider);
  });

  test("the reset of the recording returns the visitor to the beginning", async ({ page }) => {
    await openScenario(page);

    const recordedRun = page.getByRole("region", { name: "The recorded run" });
    const position = page.getByLabel("Position of the recording");
    const atTheBeginning = await recordedRun.innerText();

    await seekToTheEnd(position);
    await expect(recordedRun.getByText(`Event ${EVENTS} of ${EVENTS}.`)).toBeVisible();

    await page.getByRole("button", { name: "Restart the recording" }).click();

    // The position is at the beginning and the screen is the screen of the beginning.
    await expect(position).toHaveValue("0");
    await expect(recordedRun.getByText("The recording has no call of a tool yet.")).toBeVisible();
    await expect.poll(async () => recordedRun.innerText()).toBe(atTheBeginning);
  });

  test("the speed changes the control and never changes the order of the events", async ({ page }) => {
    await openScenario(page);

    const timeline = page.getByRole("region", { name: "The timeline of the recording" });
    const orderBefore = await timeline.getByRole("rowheader").allInnerTexts();

    const speed = page.getByLabel("Speed of the playback");
    await expect(speed).toHaveValue("1");
    await speed.selectOption("4");

    // The control shows the speed the visitor chose, and the address of the page carries it as a preference of the
    // view, because the speed is one of the two preferences the contract allows.
    await expect(speed).toHaveValue("4");
    await expect.poll(() => new URL(page.url()).searchParams.get("speed")).toBe("4");

    // The order of the events is the order of the recording, and the speed never changes it. The timeline holds every
    // event of the bundle, so no event disappears silently when the speed changes.
    const orderAfter = await timeline.getByRole("rowheader").allInnerTexts();
    expect(orderAfter).toEqual(orderBefore);
    expect(orderAfter).toHaveLength(EVENTS);
  });
});

test.describe("the playback with the device that lets the recording move", () => {
  test.beforeEach(async ({ page }) => {
    // The device does not ask for less motion, so the site lets the recording move by itself. The preference is named
    // here and not left to the machine, so that the suite means the same thing on every computer.
    await page.emulateMedia({ reducedMotion: "no-preference" });
  });

  test("the visitor starts the recording, stops it and the recording ends by itself", async ({ page }) => {
    // The playback of the whole recording takes about seven seconds at the speed of four, and the test waits for it.
    test.setTimeout(60_000);

    await openScenario(page);

    const position = page.getByLabel("Position of the recording");
    const play = page.getByRole("button", { name: "Play the recording" });
    const pause = page.getByRole("button", { name: "Pause the recording" });

    // The speed of four keeps the test short and changes nothing else.
    await page.getByLabel("Speed of the playback").selectOption("4");

    // The control of the play can act, because the device does not ask for less motion.
    await expect(play).not.toHaveAttribute("aria-disabled", "true");
    await expect(position).toHaveValue("0");

    // The visitor starts the recording and the recording moves without the visitor.
    await play.click();
    await expect
      .poll(async () => Number(await position.inputValue()), { timeout: 15_000 })
      .toBeGreaterThan(0);

    // The visitor stops it. The reason of the control of the pause is the sign that the recording stopped.
    await pause.click();
    await expect(page.getByText("The recording is not playing.")).toBeAttached();
    const stopped = await position.inputValue();

    // The wait is longer than the interval of the clock at the speed of four, so the check is not a check of a moment.
    await page.waitForTimeout(600);
    await expect(position).toHaveValue(stopped);

    // The visitor starts it again and the recording ends by itself.
    await play.click();
    await expect(
      page.getByText("The recording has finished. Restart the recording to play it again."),
    ).toBeAttached({ timeout: 40_000 });
    await expect(position).toHaveValue(String(EVENTS - 1));
    await expect(page.getByText(`Event ${EVENTS} of ${EVENTS}.`)).toBeVisible();
  });

  test("the speed changes how long the browser waits between two events", async ({ page }) => {
    test.setTimeout(60_000);

    await openScenario(page);

    const position = page.getByLabel("Position of the recording");
    const speed = page.getByLabel("Speed of the playback");
    const play = page.getByRole("button", { name: "Play the recording" });

    // At the speed of one the browser waits five hundred milliseconds between two events.
    await speed.selectOption("1");
    await play.click();
    const atTheSpeedOfOne = await timeUntilThePosition(page, 4);

    // The recording starts again, this time at the speed of four.
    await page.getByRole("button", { name: "Restart the recording" }).click();
    await expect(position).toHaveValue("0");
    await speed.selectOption("4");
    await play.click();
    const atTheSpeedOfFour = await timeUntilThePosition(page, 4);

    // The speed of four waits less than the speed of one. The speed changes the interval of the clock and nothing else.
    expect(
      atTheSpeedOfFour,
      `the recording waited ${atTheSpeedOfOne} ms at the speed of one and ${atTheSpeedOfFour} ms at the speed of four`,
    ).toBeLessThan(atTheSpeedOfOne);
  });
});
