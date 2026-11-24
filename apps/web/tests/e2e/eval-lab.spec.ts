import { expect, test } from "@playwright/test";

/**
 * The end to end test of the Eval Lab.
 *
 * Why this file exists: the Eval Lab is the page where a visitor reads the numbers of the verification and of
 * the evaluation with the dataset each one comes from and the restriction that applies to it. The page has to
 * show the numbers, the confusion matrix with its denominator and the cases that failed, because a number a
 * visitor cannot check is a number that does not exist.
 *
 * The test runs against the static export served as plain files, exactly as the files arrive in a browser,
 * and every assertion is about what the visitor sees. The accessibility of the page is scanned by the suite
 * of the accessibility, which walks the page of the Eval Lab like every other page of the site.
 */

test("the eval lab shows the numbers with the dataset and the restriction", async ({ page }) => {
  await page.goto("/eval-lab");

  await expect(page.getByRole("heading", { level: 1, name: "Eval Lab" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "The verification" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "The evaluation of the agent" })).toBeVisible();
  await expect(page.getByText(/accuracy of the verifier over/)).toBeVisible();
  await expect(page.getByText(/correctness of the agent over/)).toBeVisible();
});

test("the eval lab shows the confusion matrix with its denominator and the failed cases", async ({ page }) => {
  await page.goto("/eval-lab");

  await expect(page.getByRole("heading", { name: "The confusion matrix of the verifier" })).toBeVisible();
  await expect(page.getByText(/A missing model is not a pass/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "The cases that failed" })).toBeVisible();

  const firstCase = page.locator("details").first();
  await firstCase.locator("summary").click();
  await expect(firstCase.getByText("The claim")).toBeVisible();
  await expect(firstCase.getByText("The verdict that came out")).toBeVisible();
});
