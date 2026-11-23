import { expect, test } from "@playwright/test";

/**
 * The end to end test of the catalog of the scenarios.
 *
 * Why this file exists: the catalog is the door of the recorded demo. A visitor who opens the site has to find the
 * scenarios that the repository published, and the card of a scenario has to lead to the route of that scenario, with
 * the identifier of the scenario in the path and nothing else.
 *
 * The test runs against the static export served as plain files, exactly as the files arrive in a browser, and every
 * assertion is about what the visitor sees and about where the visitor is taken.
 */

test("the catalog lists the published scenarios", async ({ page }) => {
  await page.goto("/replay");

  // The catalog has its own heading and the card of the scenario the repository published.
  await expect(page.getByRole("heading", { name: "The scenarios" })).toBeVisible();
  await expect(page.getByRole("link", { name: "S01 - fx_markup_refund" })).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "S01 - Why was the BRL refund for TX-2048 lower than the EUR payment?",
    }),
  ).toBeVisible();
});

test("the link of a card carries the identifier of the scenario in the path", async ({ page }) => {
  await page.goto("/replay");

  const card = page.getByRole("link", { name: "S01 - fx_markup_refund" });

  // The path of the route holds the identifier of the scenario and nothing else.
  await expect(card).toHaveAttribute("href", "/replay/scenario/S01");

  await card.click();

  await expect(page).toHaveURL(/\/replay\/scenario\/S01$/);
  await expect(page.getByRole("region", { name: "The recorded run" })).toBeVisible();
});
