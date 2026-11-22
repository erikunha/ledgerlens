/**
 * The end to end suite of the drawer of a tool call of the recording.
 *
 * Why this file exists: the drawer of a call is the window where the visitor reads what a tool of
 * the recording received, what it returned and what statement it ran (ADR-048). The unit tests of
 * the drawer see the component alone, and this suite sees what a visitor sees: the trigger of the
 * row header of the table of the calls, the cell that is the stop of the keyboard, the drawer that
 * opens with the Enter key, the statement that is text and never markup, and the focus that comes
 * back to the cell that opened the drawer.
 *
 * Why the cases read the published bundle and not a fixture: a drawer that shows a made up call
 * proves nothing about the recording a visitor reads, so the statement, the literal and the number
 * of the event of the cases are the ones of the published scenario S01.
 *
 * Why the suite runs against the static export: the export is what a visitor receives, and the
 * drawer is a client component of it that calls nobody (ADR-040, ADR-042, ADR-043).
 */

import { expect, test, type Locator, type Page } from "@playwright/test";

/**
 * The statement of the published scenario, exactly as the recording carries it.
 *
 * Why the case carries the statement of the bundle: the drawer shows the text of the recording and
 * never a text of its own, so the proof has to use the text that the bundle ships.
 */
const RECORDED_SQL =
  "SELECT * FROM (SELECT kind, applied_rate, applied_at FROM fx_applied WHERE transaction_id = 'TX-2048' ORDER BY applied_at) LIMIT 50";

/**
 * The literal of the statement, as the recording wrote it.
 *
 * Why the case keeps the quotes of the literal: the statement carries the literal between quotes,
 * and the browser never masks it, because the rule about what a published recording may carry
 * belongs to the Python core (ADR-048, decision 5).
 */
const RECORDED_LITERAL = "'TX-2048'";

/**
 * The name of the first tool of the recording.
 */
const FIRST_CALL_NAME = "query_ledger";

/**
 * The number of the event that closed the first call of the recording.
 *
 * Why the number is nineteen: the call of the ledger of the scenario opened at the event sixteen
 * and closed at the event nineteen, and the drawer shows the number of the event that closed it.
 */
const FIRST_CALL_EVENT = "19";

/**
 * The position of the recording where the first call of the tools is already made.
 *
 * Why the position is twenty five: the call of the ledger of the scenario closed at the event
 * nineteen, so a recording that stands at the position twenty five already carries that call, and
 * the recording still has events after it.
 */
const POSITION_WITH_THE_FIRST_CALL = 25;

/**
 * The number of the node of the DOM that is a text.
 *
 * Why the number is here: the case proves that the statement is a text node and never markup, and
 * the number of the text node is the only way to say that from a browser.
 */
const TEXT_NODE = 3;

/**
 * Opens the route of the scenario and waits for the recorded run.
 *
 * Why the recorded run is the wait: the region of the recorded run appears only when the bundle of
 * the scenario was read and accepted, so it is the real sign that the recording is there. There is
 * no sleep and no wait for a network that does not come.
 */
async function openTheReplay(page: Page): Promise<void> {
  await page.goto("/replay/scenario/S01?tab=execution");

  const recordedRun = page.getByRole("region", { name: "The recorded run" });
  await expect(recordedRun).toBeVisible();
  await expect(recordedRun.getByText("mode: deterministic_sandbox")).toBeVisible();
}

/**
 * Moves the recording to a position with the keyboard of the slider, the way a visitor does.
 *
 * Why the keyboard and not the value of the control: the slider is a range input, and the visitor
 * moves it with the keys. The case reads the position the visitor stands at and presses the arrow
 * key as many times as the distance between the two positions.
 */
async function seekToPosition(page: Page, target: number): Promise<void> {
  const position = page.getByLabel("Position of the recording");
  await expect(position).toBeVisible();

  const current = Number(await position.inputValue());
  const steps = target - current;

  await position.focus();
  for (let step = 0; step < Math.abs(steps); step += 1) {
    await position.press(steps > 0 ? "ArrowRight" : "ArrowLeft");
  }
  await expect(position).toHaveValue(String(target));
}

/**
 * Opens the recording with its calls of the tools on the screen.
 *
 * Why the recording moves first: the table of the calls shows the calls that already happened, so
 * the visitor has to walk the recording before the calls are there (ADR-048, decision 3).
 */
async function openTheReplayWithItsCalls(page: Page): Promise<void> {
  await openTheReplay(page);
  await seekToPosition(page, POSITION_WITH_THE_FIRST_CALL);

  const calls = page.getByRole("table", { name: "The calls of the tools of the recorded run" });
  await expect(calls.getByRole("rowheader", { name: FIRST_CALL_NAME })).toBeVisible();
}

/**
 * Gives back the cell of the name of the tool of the first row of the table of the calls.
 *
 * Why the cell and not the button inside it: the cell is the stop of the keyboard of the table and
 * the button is the affordance of the pointer, so the cell is the element the cases reach and the
 * element that takes the focus back (ADR-048, decisions 2 and 7).
 */
function theCellOfTheFirstCall(page: Page): Locator {
  const calls = page.getByRole("table", { name: "The calls of the tools of the recorded run" });
  return calls.getByRole("rowheader").first();
}

/**
 * Moves the focus with the Tab key until the cell of the row holds it.
 *
 * Why the keyboard and not a call of the focus: a visitor reaches a cell with the Tab key, and a
 * case that calls the focus of an element would prove that the element can hold the focus and not
 * that the keyboard of the table reaches it.
 */
async function tabUntilTheCellHasTheFocus(page: Page, cell: Locator): Promise<void> {
  for (let step = 0; step < 150; step += 1) {
    const focused = await cell
      .evaluate((element) => element === document.activeElement)
      .catch(() => false);
    if (focused) {
      return;
    }
    await page.keyboard.press("Tab");
  }

  throw new Error("the cell of the name of the tool was not reachable with the Tab key");
}

/**
 * Reads the element that holds the focus, with the marks that tell what it is.
 *
 * Why the case reads the marks and not the text: the focus has to go back to the CELL of the row
 * and never to the button inside it, and the marks of the two elements are the only difference the
 * case needs.
 */
async function readTheFocus(
  page: Page,
): Promise<{ tag: string; role: string | null; cell: string | null; isButton: boolean } | null> {
  return page.evaluate(() => {
    const element = document.activeElement;
    if (element === null) {
      return null;
    }
    return {
      tag: element.tagName,
      role: element.getAttribute("role"),
      cell: element.getAttribute("data-cell"),
      isButton: element.tagName === "BUTTON",
    };
  });
}

test("the row header of the table of the calls is a real button and its cell is the stop of the keyboard", async ({
  page,
}) => {
  await openTheReplayWithItsCalls(page);

  const cell = theCellOfTheFirstCall(page);
  await expect(cell).toBeVisible();

  // The cell carries the place of the row and of the column, and it is the stop of the keyboard of
  // the navigation group of the table.
  await expect(cell).toHaveAttribute("data-cell", "0:0");
  await expect(cell).toHaveAttribute("tabindex", "0");

  // The trigger of the drawer is a real button that announces the window it opens, and it is not a
  // second stop of the keyboard inside the navigation group of the table (ADR-048, decision 2).
  const trigger = cell.getByRole("button");
  await expect(trigger).toHaveCount(1);
  await expect(trigger).toHaveAttribute("type", "button");
  await expect(trigger).toHaveAttribute("aria-haspopup", "dialog");
  await expect(trigger).toHaveAttribute("tabindex", "-1");

  // The accessible name of the button is the name of the tool followed by the number of the event,
  // and it contains the visible text of the button (WCAG 2.5.3).
  await expect(trigger).toHaveAccessibleName(`${FIRST_CALL_NAME} Event ${FIRST_CALL_EVENT}`);

  // The visitor reaches the cell with the Tab key, because the cell is in the order of the
  // keyboard.
  await tabUntilTheCellHasTheFocus(page, cell);
  expect((await readTheFocus(page))?.cell).toBe("0:0");
});

test("the Enter key on the cell of the row opens the drawer with the identity, the arguments and the result of the call", async ({
  page,
}) => {
  await openTheReplayWithItsCalls(page);

  const cell = theCellOfTheFirstCall(page);
  await tabUntilTheCellHasTheFocus(page, cell);
  await page.keyboard.press("Enter");

  const drawer = page.getByRole("dialog");
  await expect(drawer).toBeVisible();
  await expect(drawer).toHaveAccessibleName(`The call of ${FIRST_CALL_NAME}`);

  // The identity of the call: the name of the tool, the number of the event, the status and the
  // duration the capture measured.
  const identity = drawer.locator("dl");
  await expect(identity).toContainText(FIRST_CALL_NAME);
  await expect(identity).toContainText(FIRST_CALL_EVENT);
  await expect(identity).toContainText("Succeeded");
  await expect(identity).toContainText("12 ms");

  // The arguments of the call, as the recording wrote them.
  const argumentsText = await drawer.locator("pre").first().textContent();
  expect(argumentsText).toBe('{\n  "question": "FX rates applied to TX-2048"\n}');

  // The result of the call, as the recording wrote it. The amounts of the ledger are text, and
  // the case never sees a number that the core did not write.
  const resultText = (await drawer.locator("pre").nth(1).textContent()) ?? "";
  expect(resultText).toContain('"ok": true');
  expect(resultText).toContain('"row_count": 2');
  expect(resultText).toContain('"5.6679"');
});

test("the statement of the call is text in the pane of the SQL and its literal is never an element of the page", async ({
  page,
}) => {
  await openTheReplayWithItsCalls(page);

  const cell = theCellOfTheFirstCall(page);
  await cell.press("Enter");

  const drawer = page.getByRole("dialog");
  await expect(drawer).toBeVisible();

  const pane = drawer.getByRole("region", { name: `The statement of the call of ${FIRST_CALL_NAME}` });
  await expect(pane).toBeVisible();

  // The statement of the pane is the statement of the recording, character by character.
  expect(await pane.textContent()).toBe(RECORDED_SQL);

  // The literal of the recording is visible exactly as it was written: the browser never masks it,
  // because the rule about what a published recording may carry belongs to the Python core.
  expect(await pane.textContent()).toContain(RECORDED_LITERAL);

  // The statement is a text node and never markup, so a literal that carries a tag shows the tag
  // and never becomes an element of the page (ADR-048, decision 4).
  const shape = await pane.locator("code").evaluate((element) => ({
    children: element.childNodes.length,
    types: Array.from(element.childNodes).map((node) => node.nodeType),
    text: element.textContent ?? "",
  }));
  expect(shape.types).toEqual([TEXT_NODE]);
  expect(shape.children).toBe(1);
  expect(shape.text).toBe(RECORDED_SQL);

  // And the literal of the statement is not an element of the page.
  const elementsNamedByTheLiteral = await page.evaluate(() =>
    Array.from(document.querySelectorAll("*"))
      .map((element) => element.tagName.toLowerCase())
      .filter((tag) => tag.includes("tx-2048")),
  );
  expect(elementsNamedByTheLiteral).toEqual([]);
});

test("the Escape key closes the drawer and the focus goes back to the cell and not to the button inside it", async ({
  page,
}) => {
  await openTheReplayWithItsCalls(page);

  const cell = theCellOfTheFirstCall(page);
  await tabUntilTheCellHasTheFocus(page, cell);
  await page.keyboard.press("Enter");

  const drawer = page.getByRole("dialog");
  await expect(drawer).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(drawer).toHaveCount(0);

  // The focus goes back to the CELL that opened the drawer, because the cell is the stop of the
  // keyboard of the table and a focus on the button inside it would take the visitor out of the
  // navigation group (ADR-048, decision 7).
  const focus = await readTheFocus(page);
  expect(focus?.tag).toBe("TH");
  expect(focus?.cell).toBe("0:0");
  expect(focus?.isButton).toBe(false);
});

test("the drawer holds the call it was opened with while the recording moves to another event", async ({
  page,
}) => {
  // The clock of the playback runs only when the device asks for no less motion, so the case asks
  // for the ordinary motion of a device.
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await openTheReplay(page);
  await seekToPosition(page, POSITION_WITH_THE_FIRST_CALL);

  const position = page.getByLabel("Position of the recording");
  await page.getByRole("button", { name: "Play the recording" }).click();

  const cell = theCellOfTheFirstCall(page);
  await expect(cell).toBeVisible();
  await cell.press("Enter");

  const drawer = page.getByRole("dialog");
  await expect(drawer).toBeVisible();
  await expect(drawer).toContainText(FIRST_CALL_NAME);

  // The recording moves to another event while the drawer is open, because the drawer never
  // pauses the recording and never moves it (ADR-048, decision 3).
  const before = await position.inputValue();
  await expect.poll(async () => position.inputValue()).not.toBe(before);

  // The drawer still shows the call it was opened with, and the statement of that call.
  await expect(drawer).toContainText(FIRST_CALL_NAME);
  expect(await drawer.locator("pre").first().textContent()).toContain("FX rates applied to TX-2048");
  await expect(
    drawer.getByRole("region", { name: `The statement of the call of ${FIRST_CALL_NAME}` }),
  ).toBeVisible();
});

test("the focus moves to the status region once when the playback starts and the drawer never takes it", async ({
  page,
}) => {
  // The clock of the playback runs only when the device asks for no less motion, so the case asks
  // for the ordinary motion of a device.
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await openTheReplay(page);
  await seekToPosition(page, POSITION_WITH_THE_FIRST_CALL);

  // The page has exactly one polite region, the region of the reader of the replay, and the
  // drawer and the pane of the SQL announce nothing (ADR-048, decision 9). The assertive region of
  // the route of the framework of the site is not a region of the page of the repository.
  await expect(page.locator('[aria-live="polite"]')).toHaveCount(1);
  const status = page.getByRole("status");
  await expect(status).toBeVisible();

  await page.getByRole("button", { name: "Play the recording" }).click();

  // The focus moves to the status region once, when the playback starts (FR-032).
  await expect.poll(async () => readTheFocus(page)).toMatchObject({ role: "status" });

  // The recording moves and the focus stays in the region, because the region is pulled only once.
  const position = page.getByLabel("Position of the recording");
  const before = await position.inputValue();
  await expect.poll(async () => position.inputValue()).not.toBe(before);
  expect((await readTheFocus(page))?.role).toBe("status");

  // The drawer never takes the focus to the status region: the focus goes inside the window, and
  // it comes back to the cell that opened it (ADR-048, decision 7).
  const cell = theCellOfTheFirstCall(page);
  await cell.press("Enter");

  const drawer = page.getByRole("dialog");
  await expect(drawer).toBeVisible();

  // The drawer announces nothing: the dialog announces itself and the reader of the replay keeps
  // the one polite region of the page (ADR-048, decision 9).
  await expect(drawer.locator("[aria-live]")).toHaveCount(0);
  await expect(drawer.locator('[role="status"]')).toHaveCount(0);

  const focusIsInsideTheDrawer = await page.evaluate(() => {
    const active = document.activeElement;
    const dialog = document.querySelector('[role="dialog"]');
    return active !== null && dialog !== null && dialog.contains(active);
  });
  expect(focusIsInsideTheDrawer).toBe(true);

  await page.keyboard.press("Escape");
  await expect(drawer).toHaveCount(0);
  expect((await readTheFocus(page))?.cell).toBe("0:0");
});
