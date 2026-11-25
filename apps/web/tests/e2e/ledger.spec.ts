import { expect, test, type Locator, type Page } from "@playwright/test";

// The origin of the site comes from the module of the suite, so the origin this file asserts is the
// origin the configuration really serves, and the checks of the network cannot become vacuous.
import { SITE_ORIGIN } from "./site-origin";

/**
 * The end to end test of the tab of the ledger of the recorded demo.
 *
 * Why this file exists: the home page of the site promises the ledger rows the run read, and ADR-045
 * turned that promise into a published artifact of the site and into a fifth tab of the replay. The
 * tab is the place where a visitor reads that artifact: the movements of the account of the
 * recording, the movement that the run read and the reads that name it, the page the table is on,
 * and the state of the visit, which never reaches the address of the page.
 *
 * Why the facts of the recording are written down here: the artifact is a frozen file, and the test
 * asserts the values that file carries, the way a reader of the site reads them. The account of the
 * recording is `C-0412`, the movements are the transaction `TX-2048` and the refund `R-0731`, and
 * the recording made ONE read of the ledger, the read of the citation `sql:1` of the event 19, and
 * that read names `TX-2048`. So the transaction carries the words "Read by the run" and the refund
 * does not.
 *
 * The test runs against the static export served as plain files, exactly as the files arrive in a
 * browser. Every assertion is about what the visitor sees and about the address of the page.
 *
 * Why the last journey sorts and filters: ADR-049 gave the visitor the controls of the order and
 * of the filter of the recorded ledger, and the confirmation in a real browser belongs here, in
 * the journey that is NOT part of the gate of the Node.
 */

/**
 * The identifier of the account whose ledger the recording of `S01` read.
 *
 * Why the identifier is written here: the artifact of the scenario is a frozen file, and the name
 * of the account is a fact of that file, not a guess of the test.
 */
const ACCOUNT_ID = "C-0412";

/**
 * The name of the simulated customer of the account of the recording.
 *
 * Why the name is a fact of the test: the switcher of the accounts writes the identifier and the
 * name of the account, and the visitor has to be able to read which account the table is about.
 */
const ACCOUNT_NAME = "Mariana Albuquerque Costa";

/**
 * The requests the page made, and the ones that left the origin of the site.
 *
 * Why they are module state: the listener of the requests is installed before the navigation, so
 * the first request of the page is already watched.
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
 * Opens the route of the scenario and waits for the tab of the ledger to be on the screen.
 *
 * Why the panel is the wait: the panel of the ledger appears only when the bundle of the scenario
 * was read and the artifact of the ledger came with it, so it is the real sign that the ledger is
 * there. There is no sleep and no wait for a network that does not come.
 */
async function openTheLedgerFromTheAddress(page: Page): Promise<Locator> {
  await page.goto("/replay/scenario/S01?tab=ledger");

  const panel = page.getByRole("region", { name: `The ledger of the account ${ACCOUNT_ID}` });
  await expect(panel).toBeVisible();

  return panel;
}

/**
 * Fails when any request of the page left the origin of the site.
 *
 * Why the message names the URLs: a failure that only says that something escaped leaves the
 * reader to guess what, and the URL is the whole of the evidence.
 */
function expectEveryRequestStayedOnTheSite(): void {
  expect(
    requestsThatEscaped,
    `The recorded demo must not call any origin other than ${SITE_ORIGIN}. The requests that escaped are: ${
      requestsThatEscaped.join(", ") || "none"
    }`,
  ).toHaveLength(0);
}

test("the tab of the ledger opens from the address", async ({ page }) => {
  const panel = await openTheLedgerFromTheAddress(page);

  // The tab of the ledger is the open one, and it sits between the tab of the execution and the
  // tab of the evidence, because the order of the tabs is the order of the promise of the site and
  // the order of the work of the run.
  const tabs = page.getByRole("tab");
  await expect(tabs).toHaveCount(5);
  expect(await tabs.allInnerTexts()).toEqual([
    "Execution",
    "Ledger",
    "Evidence",
    "Decision",
    "Provenance",
  ]);
  await expect(page.getByRole("tab", { name: "Ledger" })).toHaveAttribute("aria-selected", "true");

  // The panel of the ledger names the account whose movements it shows.
  await expect(panel.getByRole("heading", { name: `The ledger of the account ${ACCOUNT_ID}` })).toBeVisible();

  expectEveryRequestStayedOnTheSite();
});

test("the tab of the ledger opens from the row of the tabs", async ({ page }) => {
  await page.goto("/replay/scenario/S01");
  await expect(page.getByRole("table", { name: "The calls of the tools of the recorded run" })).toBeVisible();

  // The visitor picks the tab of the ledger in the row of the tabs.
  await page.getByRole("tab", { name: "Ledger" }).click();

  const panel = page.getByRole("region", { name: `The ledger of the account ${ACCOUNT_ID}` });
  await expect(panel).toBeVisible();
  await expect(page.getByRole("tab", { name: "Ledger" })).toHaveAttribute("aria-selected", "true");

  // The address of the page carries the tab, because the tab is one of the two preferences the
  // contract allows.
  await expect.poll(() => new URL(page.url()).searchParams.get("tab")).toBe("ledger");

  expectEveryRequestStayedOnTheSite();
});

test("the table of the ledger shows the two movements of the account", async ({ page }) => {
  const panel = await openTheLedgerFromTheAddress(page);

  // The switcher of the accounts names the account of the recording, and the chosen account is the
  // pressed one. The recording read the ledger of one account, and the switcher says so in words.
  const switcher = panel.getByRole("group", { name: "The accounts of the recording" });
  await expect(switcher).toBeVisible();
  const account = switcher.getByRole("button", { name: new RegExp(ACCOUNT_ID) });
  await expect(account).toHaveAttribute("aria-pressed", "true");
  await expect(switcher.getByText(ACCOUNT_NAME)).toBeVisible();
  await expect(panel.getByText("The recording read the ledger of one account.")).toBeVisible();

  // The panel says in words how many rows the recording read, and it never shows a total.
  await expect(panel.getByText(/The recording read \d+ rows? of the ledger\./)).toBeVisible();

  // The table of the movements is named after the account whose movements it shows.
  const table = panel.getByRole("table", { name: `The movements of the account ${ACCOUNT_ID}` });
  await expect(table).toBeVisible();

  // There are two movements, and the table never draws a third row that would be a total.
  await expect(table.getByRole("row")).toHaveCount(3);
  await expect(table.getByRole("rowheader", { name: "TX-2048" })).toBeVisible();
  await expect(table.getByRole("rowheader", { name: "R-0731" })).toBeVisible();

  // The money of the table is the decimal text of the artifact, with the currency of the artifact.
  await expect(table.getByText("EUR 100.00")).toBeVisible();
  await expect(table.getByText("BRL 549.31")).toBeVisible();

  // The transaction carries the words that say that the run read it, and the refund does not,
  // because the recorded statement named the transaction and nothing else.
  const transaction = table.getByRole("row", { name: /TX-2048/ });
  const refund = table.getByRole("row", { name: /R-0731/ });
  await expect(transaction.getByText("Read by the run")).toBeVisible();
  await expect(refund.getByText("Read by the run")).toHaveCount(0);
  await expect(table.getByText("Read by the run")).toHaveCount(1);

  // The other fields of the row are the ones the artifact declares.
  await expect(transaction.getByText("transaction")).toBeVisible();
  await expect(transaction.getByText("2026-10-15T09:12:00Z")).toBeVisible();
  await expect(transaction.getByText("refunded")).toBeVisible();
  await expect(refund.getByText("refund")).toBeVisible();
  await expect(refund.getByText("2026-10-20T14:05:00Z")).toBeVisible();
  await expect(refund.getByText("paid")).toBeVisible();

  expectEveryRequestStayedOnTheSite();
});

test("the visitor opens a row and the detail shows the reads that name it", async ({ page }) => {
  const panel = await openTheLedgerFromTheAddress(page);
  const table = panel.getByRole("table", { name: `The movements of the account ${ACCOUNT_ID}` });

  // The visitor opens the transaction, and the detail of the movement is under the table.
  await table.getByRole("button", { name: "TX-2048" }).click();

  const detail = page.getByRole("heading", { name: "The movement TX-2048", level: 5 });
  await expect(detail).toBeVisible();

  // The row that is open carries the words of the state, because the state is never only a colour.
  await expect(table.getByRole("row", { name: /TX-2048/ }).getByText("Open")).toBeVisible();

  // The detail draws the six fields of the movement, one by one, with the names the artifact gives
  // them, and the money is the decimal text of the artifact.
  const section = page.getByRole("region", { name: "The movement TX-2048" });
  await expect(section.getByText("EUR 100.00")).toBeVisible();
  await expect(section.getByText("EUR", { exact: true })).toBeVisible();

  // The read that names the movement is drawn with its citation, the sequence number of the event
  // that closed it, the tool it called and the statement it ran.
  await expect(section.getByText("The read sql:1, the event 19, the tool query_ledger.")).toBeVisible();
  await expect(
    section.getByText("FROM fx_applied AS f JOIN transactions AS t"),
  ).toBeVisible();

  // The rows the run read are the two rates of the transaction, and the rate is not money: it
  // carries no currency at all.
  const read = section.getByRole("table", { name: "The rows the read sql:1 returned" });
  await expect(read).toBeVisible();
  await expect(read.getByRole("rowheader", { name: "charge" })).toBeVisible();
  await expect(read.getByRole("rowheader", { name: "refund" })).toBeVisible();
  await expect(read.getByText("5.6679")).toBeVisible();
  await expect(read.getByText("5.4931")).toBeVisible();
  await expect(read.getByText("EUR", { exact: true })).toHaveCount(0);
  await expect(read.getByText("BRL", { exact: true })).toHaveCount(0);

  // The visitor opens the refund, and the detail says in words that the recording read no record
  // of it, because no read of the recording names it.
  await table.getByRole("button", { name: "R-0731" }).click();
  await expect(page.getByRole("heading", { name: "The movement R-0731", level: 5 })).toBeVisible();
  await expect(
    page.getByRole("region", { name: "The movement R-0731" }).getByText(
      "The recording read no record of this movement.",
    ),
  ).toBeVisible();

  // The visitor closes the row, and the detail goes away.
  await table.getByRole("button", { name: "R-0731" }).click();
  await expect(page.getByRole("heading", { name: "The movement R-0731", level: 5 })).toHaveCount(0);

  expectEveryRequestStayedOnTheSite();
});

test("the control of the pagination says which page it is on", async ({ page }) => {
  const panel = await openTheLedgerFromTheAddress(page);

  // The account of the recording holds two movements and the page of the artifact holds fifty, so
  // the table is on the first page of one, and the control says so in words.
  await expect(panel.getByText("Page 1 of 1")).toBeVisible();

  // The controls are never disabled: the ones that would do nothing say so with
  // `aria-disabled` and with a sentence a reader can hear.
  const previous = panel.getByRole("button", { name: "Previous page" });
  const next = panel.getByRole("button", { name: "Next page" });
  await expect(previous).toHaveAttribute("aria-disabled", "true");
  await expect(next).toHaveAttribute("aria-disabled", "true");
  await expect(panel.getByText("This is the first page of the movements of the account.")).toBeVisible();
  await expect(panel.getByText("This is the last page of the movements of the account.")).toBeVisible();

  expectEveryRequestStayedOnTheSite();
});

test("the URL of the page holds the identifier, the tab and the speed, and nothing else", async ({ page }) => {
  await page.goto("/replay/scenario/S01");
  await expect(page.getByRole("table", { name: "The calls of the tools of the recorded run" })).toBeVisible();

  await page.getByRole("tab", { name: "Ledger" }).click();
  const panel = page.getByRole("region", { name: `The ledger of the account ${ACCOUNT_ID}` });
  await expect(panel).toBeVisible();

  // The path holds the identifier of the scenario and nothing else.
  const url = new URL(page.url());
  expect(url.pathname).toBe("/replay/scenario/S01");

  // The query string holds the tab and the speed, the two preferences of the contract.
  expect(url.searchParams.get("tab")).toBe("ledger");
  expect(url.searchParams.get("speed")).toBe("1");
  for (const key of url.searchParams.keys()) {
    expect(["tab", "speed"], `the address of the page must not carry the parameter ${key}`).toContain(key);
  }

  // The state of the visitor never goes in the URL: the account that is chosen and the row that is
  // open live in the memory of the panel, and the address does not move when the visitor opens a
  // movement.
  const table = panel.getByRole("table", { name: `The movements of the account ${ACCOUNT_ID}` });
  await table.getByRole("button", { name: "TX-2048" }).click();
  await expect(page.getByRole("heading", { name: "The movement TX-2048", level: 5 })).toBeVisible();

  const afterTheOpening = new URL(page.url());
  expect(afterTheOpening.pathname).toBe("/replay/scenario/S01");
  expect(afterTheOpening.searchParams.get("tab")).toBe("ledger");
  expect(afterTheOpening.searchParams.get("speed")).toBe("1");
  for (const key of afterTheOpening.searchParams.keys()) {
    expect(["tab", "speed"], `the address of the page must not carry the parameter ${key}`).toContain(key);
  }
  expect(afterTheOpening.search).not.toContain(ACCOUNT_ID);
  expect(afterTheOpening.search).not.toContain("TX-2048");
});

test("the tab of the ledger reads the artifact of the site and calls nobody", async ({ page }) => {
  await openTheLedgerFromTheAddress(page);

  // The artifact of the ledger is a file of the origin of the site, and the browser reads it from
  // there, exactly as it reads the manifest, the events and the provenance.
  expect(
    requestsMade.some((url) => url.includes("/replay/s01/ledger.json")),
    `the browser must read the artifact of the ledger from the origin of the site. The requests were: ${
      requestsMade.join(", ") || "none"
    }`,
  ).toBe(true);

  // Every request of the page went to the origin of the site.
  expect(requestsMade.length).toBeGreaterThan(0);
  for (const url of requestsMade) {
    expect(new URL(url).origin, `the request to ${url} must go to ${SITE_ORIGIN}`).toBe(SITE_ORIGIN);
  }

  expectEveryRequestStayedOnTheSite();
});

test("the visitor sorts and filters the movements of the ledger", async ({ page }) => {
  const panel = await openTheLedgerFromTheAddress(page);
  const table = panel.getByRole("table", { name: `The movements of the account ${ACCOUNT_ID}` });

  // The order on the screen is the order the artifact declares, and the table says so in words.
  await expect(panel.getByText("The order on the screen is the order the artifact declares.")).toBeVisible();
  await expect(panel.getByText("The table shows the 2 movements of the account.")).toBeVisible();

  // The visitor asks for the order of the amount, and the same control asked twice reverses it:
  // the refund of 549.31 comes before the transaction of 100.00.
  const amount = panel.getByRole("button", { name: "Sort by the amount" });
  await amount.click();
  await amount.click();

  await expect(table.getByRole("rowheader").first()).toHaveText("R-0731");
  await expect(
    panel.getByText(
      "The order on the screen is the order the visitor chose: by the amount, descending, and not the order the artifact declares.",
    ),
  ).toBeVisible();

  // The visitor filters by the state, and the panel says in words how many movements it kept: a
  // row that disappears is never dropped without a word.
  await panel.getByLabel("The state of the movement kept").selectOption("refunded");

  await expect(table.getByRole("rowheader")).toHaveCount(1);
  await expect(table.getByRole("rowheader", { name: "TX-2048" })).toBeVisible();
  await expect(panel.getByText("The table shows 1 of the 2 movements of the account.")).toBeVisible();

  // The visitor gets the order of the artifact back.
  await panel.getByRole("button", { name: "The order of the artifact" }).click();
  await expect(panel.getByText("The order on the screen is the order the artifact declares.")).toBeVisible();

  // The state of the visit never reaches the address of the page: the query string carries the tab
  // and the speed and nothing else.
  const url = new URL(page.url());
  expect(url.pathname).toBe("/replay/scenario/S01");
  expect(url.searchParams.get("tab")).toBe("ledger");
  for (const key of url.searchParams.keys()) {
    expect(["tab", "speed"], `the address of the page must not carry the parameter ${key}`).toContain(key);
  }

  expectEveryRequestStayedOnTheSite();
});
