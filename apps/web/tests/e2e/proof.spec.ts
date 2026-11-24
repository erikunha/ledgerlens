import { expect, test } from "@playwright/test";

/**
 * The end to end test of the proof of work.
 *
 * Why this file exists: the proof of work is the page where a visitor checks what the repository did, which
 * commit did it and how to redo it. The page of the catalog has to list the artifacts, and the page of an
 * artifact has to show the provenance and the recipe, because a proof a visitor cannot read is a proof that
 * does not exist.
 *
 * The test runs against the static export served as plain files, exactly as the files arrive in a browser,
 * and every assertion is about what the visitor sees. The accessibility of the page of the proof is scanned
 * by the suite of the accessibility, which walks the page of the proof like every other page of the site.
 */

test("the page of the proof of work lists the artifacts with their status", async ({ page }) => {
  await page.goto("/proof");

  await expect(page.getByRole("heading", { level: 1, name: "Proof of work" })).toBeVisible();
  await expect(page.getByRole("link", { name: /S01 · replay/ }).first()).toBeVisible();
});

test("the page of an artifact shows the provenance and the recipe", async ({ page }) => {
  await page.goto("/proof");
  await page.getByRole("link", { name: /S01 · replay/ }).first().click();

  await expect(page).toHaveURL(/\/proof\/[a-f0-9]{64}$/);
  await expect(page.getByRole("heading", { level: 1, name: "Proof of S01" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "The provenance" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "The recipe that reproduces the run" })).toBeVisible();
  await expect(page.getByText("scripts/capture_replay.py", { exact: false })).toBeVisible();
});
