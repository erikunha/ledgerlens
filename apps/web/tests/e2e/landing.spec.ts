import { expect, test, type Locator, type Page } from "@playwright/test";

/**
 * The end to end test of the landing page of the public site.
 *
 * Why this file exists: the home page is the door of the demo, and a visitor who opens it has to be able to tell the
 * three ways to see the demo apart before anything happens. The page shows the title of the site, it says out loud that
 * the money of the demo is simulated, and it offers the three rooms of the demo: the recorded demo, the sandbox of the
 * visitor and the live mode. Each card carries the mode it runs in, because a recorded run is never presented as a live
 * one and a live run is never presented as a recorded one (ADR-040, ADR-044).
 *
 * The test runs against the static export served as plain files, exactly as the files arrive in a browser. Every
 * assertion is about what the visitor sees and about where the visitor is taken.
 */

/**
 * The three rooms of the demo, each one with the badge of its mode and with the route of its room.
 *
 * Why the three of them live in one table: the badge of a card and the route of a card are one promise of the home page,
 * and a table keeps the two of them next to the room they belong to, so a card can never carry the badge of another
 * room.
 */
const ROOMS = [
  {
    title: "Recorded demo",
    mode: "mode: deterministic_sandbox",
    link: "Open the recorded demo",
    route: "/replay",
    heading: "Recorded demo",
  },
  {
    title: "Sandbox",
    mode: "mode: visitor_sandbox",
    link: "Open the sandbox",
    route: "/sandbox",
    heading: "The sandbox of the visitor",
  },
  {
    title: "Live mode",
    mode: "mode: live_agent",
    link: "Open the live mode",
    route: "/live",
    heading: "Live mode",
  },
] as const;

/**
 * The card of one of the rooms of the demo.
 *
 * Why the card is found from its title: the title is the name the visitor reads, and the card is the box that holds the
 * badge and the link of that room. The card of the design system is the box with the rounded border, so the walk up the
 * tree stops at the first ancestor that carries that border and the badge and the link of the room are the ones of that
 * card and of no other.
 */
function cardOf(page: Page, title: string): Locator {
  return page
    .getByRole("heading", { name: title })
    .locator("xpath=ancestor::div[contains(@class, 'rounded-lg')][1]");
}

/**
 * The six subsystems of the tour of the architecture, in the order of the run.
 *
 * Why the labels are written here: the tour is a room of the site, and a visitor who reaches it has
 * to find the six subsystems there. The labels are a fact of the repository, and the case has to
 * name them itself, the way the suite of the tour names them.
 */
const SUBSYSTEMS = [
  "Query guard",
  "Scoped ledger copy",
  "Decimal calculator",
  "Deterministic simulator",
  "Verifier",
  "Trace recorder",
] as const;

test("the home page shows the title of the site and says that the money of the demo is simulated", async ({
  page,
}) => {
  await page.goto("/");

  // The title of the site is the heading of the page, and the banner of the site carries the name of the site.
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Evidence-first payment investigation, with a trace you can read",
  );
  await expect(page.getByRole("banner", { name: "LedgerLens" })).toBeVisible();

  // The money of the demo is simulated, and the page says it out loud, because a visitor who reads a price on this site
  // has to know that no money of the world is behind it.
  await expect(page.getByText("All the money of the demo is simulated.")).toBeVisible();
});

test("the home page names the three ways to see the demo and shows the three cards", async ({ page }) => {
  await page.goto("/");

  // The section of the cards carries the name of the promise it holds.
  const rooms = page.getByRole("region", { name: "The three ways to see the demo" });
  await expect(rooms).toBeVisible();

  // The three rooms are on the screen, each one with its own title.
  for (const room of ROOMS) {
    await expect(rooms.getByRole("heading", { name: room.title })).toBeVisible();
  }

  // There are three cards and no more: a fourth card would be a room the repository does not publish.
  await expect(rooms.getByRole("heading")).toHaveCount(ROOMS.length);
});

test("each card of the demo carries the badge of the mode it runs in", async ({ page }) => {
  await page.goto("/");

  for (const room of ROOMS) {
    const card = cardOf(page, room.title);

    // The badge of the card names the mode of the room, and the badge of no other room is on that card.
    await expect(card.getByText(room.mode, { exact: true })).toBeVisible();
    for (const other of ROOMS) {
      if (other.mode === room.mode) {
        continue;
      }
      await expect(card.getByText(other.mode, { exact: true })).toHaveCount(0);
    }
  }
});

test("the link of each card of the demo goes to the room of that mode", async ({ page }) => {
  for (const room of ROOMS) {
    await page.goto("/");

    const link = cardOf(page, room.title).getByRole("link", { name: room.link });

    // The address of the room is in the link itself, so a reader of the page can see where the card leads.
    await expect(link).toHaveAttribute("href", room.route);

    // The visitor who presses the card lands in the room of the card.
    await link.click();
    await expect(page).toHaveURL(new RegExp(`${room.route}$`));
    await expect(page.getByRole("heading", { level: 1, name: room.heading })).toBeVisible();
  }
});

test("the home page offers the catalog of a real model", async ({ page }) => {
  // It proves that the door of the site names the second catalog of the recorded scenarios: a visitor who arrives
  // at the home page has to be able to find the recordings of a real model without knowing that they exist
  // (ADR-075).
  await page.goto("/");

  const link = cardOf(page, "Recorded demo").getByRole("link", { name: "Open the catalog of a real model" });

  await expect(link).toHaveAttribute("href", "/replay-real");

  // The visitor who presses the link lands in the catalog of a real model.
  await link.click();
  await expect(page).toHaveURL(/replay-real$/);
  await expect(page.getByRole("heading", { level: 1, name: "Recorded with a real model" })).toBeVisible();
});

test("the header leads the visitor to the tour of the architecture", async ({ page }) => {
  await page.goto("/");

  // The tour of the architecture is a room of the site, and the header of the site is the place
  // where every room is reachable from any page.
  const navigation = page.getByRole("navigation", { name: "The rooms of the demo" });
  const link = navigation.getByRole("link", { name: "Architecture" });
  await expect(link).toHaveAttribute("href", "/engineering");

  // The visitor who presses the link lands in the tour.
  await link.click();
  await expect(page).toHaveURL(new RegExp("/engineering$"));
  await expect(
    page.getByRole("heading", { level: 1, name: "The architecture of the recorded demo" }),
  ).toBeVisible();

  // The tour shows the six subsystems of the run, so the visitor finds what the room promises. The
  // tour shows them twice, once as the twin of the picture and once as the list of their code, so
  // the case looks for the first of the two and not for one of them.
  for (const subsystem of SUBSYSTEMS) {
    await expect(page.getByRole("heading", { name: subsystem }).first()).toBeVisible();
  }
});
