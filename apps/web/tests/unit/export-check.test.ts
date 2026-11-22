/**
 * The test of the check of the export of the site.
 *
 * Why this test exists: the gate of the frontend has to prove that the build wrote one page per scenario of the
 * catalog, with the content of the scenario. A check that lives inside a shell script cannot be tested, so the check
 * lives in a script of its own and this test drives that script.
 *
 * Why the check has to read the exported page as text: a route that answers 404 during the export still writes a file
 * at the path of the route, and that file is the body of the page of 404. A check that only proves that the file exists
 * passes a site where every visitor who follows the card of the catalog lands on the page of 404, and the gate of the
 * repository would say that the site is good.
 *
 * Why the folders of the case are built outside the repository: the test must never touch the export of the
 * repository, and it must never leave a file inside it.
 */

import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { afterEach, describe, expect, it } from "vitest";

/** The question of the card of the scenario of the case. */
const QUESTION = "Why was the BRL refund for TX-2048 lower than the EUR payment?";

/**
 * Finds the root of the repository, walking up from the folder of the test.
 *
 * Why the root is looked up: the script of the check and the gate of the frontend live at the root of the repository,
 * and the test has to run against the files of the repository, not against a copy of them.
 */
function findRepositoryRoot(): string {
  let current = dirname(fileURLToPath(import.meta.url));
  for (;;) {
    if (existsSync(join(current, "scripts", "check_export_pages.mjs"))) {
      return current;
    }
    const parent = dirname(current);
    if (parent === current) {
      throw new Error("the root of the repository was not found from the folder of the test");
    }
    current = parent;
  }
}

/** The root of the repository. */
const REPOSITORY_ROOT = findRepositoryRoot();

/** The script of the check of the export. */
const CHECK_SCRIPT = join(REPOSITORY_ROOT, "scripts", "check_export_pages.mjs");

/** The gate of the frontend. */
const GATE_SCRIPT = join(REPOSITORY_ROOT, "scripts", "gate_web.sh");

/** The folders of the case, removed at the end of every case. */
const temporaryFolders: string[] = [];

/**
 * Builds an export of the site with one scenario.
 *
 * Why the export has the shape of the real one: the export of Next.js holds the recorded demo in the folder `replay`,
 * with the catalog of the scenarios, the bundle of every scenario and the page of every scenario.
 */
function buildExport(options: {
  readonly page?: "good" | "not_found" | "missing";
  readonly catalogPage?: "good" | "not_found" | "missing";
}): string {
  const root = mkdtempSync(join(tmpdir(), "ledgerlens-export-check-"));
  temporaryFolders.push(root);

  const replay = join(root, "replay");
  mkdirSync(join(replay, "s01"), { recursive: true });
  mkdirSync(join(replay, "scenario"), { recursive: true });

  writeFileSync(
    join(replay, "index.json"),
    JSON.stringify([{ id: "S01", name: "fx_markup_refund", question: QUESTION, bundle_path: "s01" }]),
    "utf8",
  );
  writeFileSync(join(replay, "s01", "manifest.json"), "{}\n", "utf8");
  writeFileSync(join(replay, "s01", "events.jsonl"), "", "utf8");

  const page = options.page ?? "good";
  if (page !== "missing") {
    writeFileSync(join(replay, "scenario", "S01.html"), pageOfTheScenario(page), "utf8");
  }

  // The page of the catalog of the scenarios lives at the root of the export, next to the folder of the recorded
  // demo, and it is the first page a visitor lands on.
  const catalogPage = options.catalogPage ?? "good";
  if (catalogPage !== "missing") {
    writeFileSync(join(root, "replay.html"), pageOfTheCatalog(catalogPage), "utf8");
  }

  return root;
}

/**
 * The page of the catalog of the scenarios, as the export of the site writes it.
 *
 * Why the page of 404 carries a heading too: the check has to tell the page of 404 from a page that is not the
 * catalog by the marks of the error and not by the absence of a heading.
 */
function pageOfTheCatalog(page: "good" | "not_found"): string {
  const head = page === "not_found" ? '<html id="__next_error__" lang="en">' : '<html lang="en">';
  return [
    "<!DOCTYPE html>",
    head,
    "  <head>",
    "    <title>Recorded demo</title>",
    "  </head>",
    "  <body>",
    "    <main>",
    "      <h1>Recorded demo</h1>",
    "    </main>",
    "  </body>",
    "</html>",
    "",
  ].join("\n");
}

/**
 * The page of the scenario, as the export of the site writes it.
 *
 * Why the page of 404 carries the question and the identifier too: the case has to prove that the check tells the
 * page of the scenario and the page of 404 apart, and the only mark that tells them apart is the body of the error.
 */
function pageOfTheScenario(page: "good" | "not_found"): string {
  const head = page === "not_found" ? '<html id="__next_error__" lang="en">' : '<html lang="en">';
  return [
    "<!DOCTYPE html>",
    head,
    "  <head>",
    "    <title>S01</title>",
    "  </head>",
    "  <body>",
    "    <main>",
    `      <h1>${QUESTION}</h1>`,
    "      <p>S01</p>",
    "    </main>",
    "  </body>",
    "</html>",
    "",
  ].join("\n");
}

/**
 * Runs the script of the check and gives back what it said and the code it left.
 *
 * Why the code matters: the check has to fail the gate when the export is broken, and the exit code is what the gate
 * reads.
 */
function runCheck(folder: string): { readonly status: number | null; readonly output: string } {
  const result = spawnSync(process.execPath, [CHECK_SCRIPT, folder], { encoding: "utf8" });
  return {
    status: result.status,
    output: `${result.stdout ?? ""}${result.stderr ?? ""}`,
  };
}

afterEach(() => {
  for (const folder of temporaryFolders.splice(0)) {
    rmSync(folder, { recursive: true, force: true });
  }
});

describe("the check of the export of the site", () => {
  it("passes when the export holds the page of every scenario of the catalog", () => {
    // It proves that an export with one page per scenario, with the question and the identifier of the scenario, is
    // an export the gate accepts.
    const root = buildExport({ page: "good" });

    const { status, output } = runCheck(root);

    expect(status).toBe(0);
    expect(output).toContain("the build wrote the catalog of 1 scenario(s)");
  });

  it("fails and names the scenario when the export holds no page of the scenario", () => {
    // It proves that a card of the catalog whose page is missing is a failure of the gate, and that the message names
    // the scenario and not only the file.
    const root = buildExport({ page: "missing" });

    const { status, output } = runCheck(root);

    expect(status).toBe(1);
    expect(output).toContain("does not hold the page of the scenario S01");
  });

  it("fails when the page of the scenario is the page of 404", () => {
    // It proves that a route that answered 404 during the export is refused, even though the file of the page exists:
    // a visitor who follows the card of the catalog would land on the page of 404.
    const root = buildExport({ page: "not_found" });

    const { status, output } = runCheck(root);

    expect(status).toBe(1);
    expect(output).toContain("is the page of 404");
    expect(output).toContain("S01");
  });

  it("reads the folder of the recorded demo as well as the folder of the export", () => {
    // It proves that the gate can name the folder that holds the catalog, which is the folder the gate of the
    // frontend passes to the check.
    const root = buildExport({ page: "good" });

    const { status } = runCheck(join(root, "replay"));

    expect(status).toBe(0);
  });

  it("fails when the export holds no catalog of the scenarios", () => {
    // It proves that an export without the catalog is a failure of the gate and not a check that passes on nothing.
    const root = buildExport({ page: "good" });
    rmSync(join(root, "replay", "index.json"), { force: true });

    const { status, output } = runCheck(root);

    expect(status).toBe(1);
    expect(output).toContain("does not hold the catalog of the scenarios");
  });

  it("fails when the export holds no page of the catalog of the scenarios", () => {
    // It proves that a catalog page that is missing is a failure of the gate: it is the first page a visitor lands
    // on, and the end to end suite that proves it runs in no job of the continuous integration.
    const root = buildExport({ page: "good", catalogPage: "missing" });

    const { status, output } = runCheck(root);

    expect(status).toBe(1);
    expect(output).toContain("does not hold the page of the catalog of the scenarios");
  });

  it("fails when the page of the catalog of the scenarios is the page of 404", () => {
    // It proves that a catalog page that answered 404 during the export is refused, even though the file exists.
    const root = buildExport({ page: "good", catalogPage: "not_found" });

    const { status, output } = runCheck(root);

    expect(status).toBe(1);
    expect(output).toContain("the page of the catalog of the scenarios is the page of 404");
  });

  it("is called by the gate of the frontend", () => {
    // It proves that the gate of the frontend really runs the check of the export. A gate that stopped calling it
    // would pass a build whose pages are the page of 404, and nothing else would say so.
    const gate = readFileSync(GATE_SCRIPT, "utf8");

    expect(gate).toContain("check_export_pages.mjs");
    expect(gate).not.toContain("node <<'NODE'");
  });
});
