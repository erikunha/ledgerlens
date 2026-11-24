/**
 * The test of the reader of the published catalog of the scenarios.
 *
 * Why this test exists: the route of a scenario is a server component of a static export, so it reads the catalog
 * from the disk while the export is built. The repository publishes the catalog in one place only and the build copies
 * it into the tree of the frontend, so the reader has to find the catalog in either place, and it has to fail loudly
 * when it finds none of them: a catalog with no scenario builds a site with no page of a scenario, and a visitor who
 * follows a card of the catalog lands on nothing.
 *
 * Why the cases that need a catalog of their own work in a temporary folder: the artifacts the repository publishes
 * must never be written to by a test, and a folder of its own proves the order of the two places the reader looks for.
 */

import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";

import { afterEach, describe, expect, it } from "vitest";

import { catalogCandidates, readPublishedCatalog, resolveCatalogPath } from "@/lib/replay/catalog";

/** The folders the test created, so that every case can clean up after itself. */
const temporaryFolders: string[] = [];

/**
 * Creates a folder for one case of the test.
 *
 * Why a folder of its own for every case: the cases must not see the files of each other, and the artifacts of the
 * repository must never be written to.
 */
function temporaryFolder(): string {
  const folder = mkdtempSync(join(tmpdir(), "ledgerlens-catalog-"));
  temporaryFolders.push(folder);
  return folder;
}

/**
 * Writes a catalog of the test, creating the folders above it.
 *
 * Why the helper writes a card that passes the contract: the cases that break the contract break it on purpose, and
 * the other cases need a catalog the reader accepts.
 */
function writeCatalog(root: string, relativePath: string, content: string): void {
  const target = join(root, relativePath);
  mkdirSync(dirname(target), { recursive: true });
  writeFileSync(target, content);
}

/** A card that passes the contract of the published artifacts. */
const VALID_CARD = { id: "S01", name: "fx_markup_refund", question: "Why was the refund lower?" };

afterEach(() => {
  while (temporaryFolders.length > 0) {
    const folder = temporaryFolders.pop();
    if (folder) {
      rmSync(folder, { recursive: true, force: true });
    }
  }
});

describe("the reader of the published catalog of the scenarios", () => {
  it("reads the catalog that the repository publishes", () => {
    // It proves that the reader finds the catalog of the repository in a checkout that never built the frontend, which
    // is the shape of the continuous integration and the shape of a fresh clone.
    const catalog = readPublishedCatalog();

    expect(catalog.length).toBeGreaterThan(0);
    for (const card of catalog) {
      expect(card.id).toMatch(/^S[0-9]{2}$/);
      expect(card.question.length).toBeGreaterThan(0);
    }
  });

  it("reads the catalog of a real model from the folder of that catalog", () => {
    // It proves that the two catalogs live in two folders of their own, and that the reader of the catalog of a real
    // model never reads the folder of the sandbox: a route that read the other catalog would publish the pages of the
    // wrong recordings (ADR-075).
    const sandbox = catalogCandidates(process.cwd());
    const real = catalogCandidates(process.cwd(), "real");

    expect(sandbox[0]).toContain(join("public", "replay"));
    expect(real[0]).toContain(join("public", "replay-real"));
    expect(real[1]).toContain(join("site", "replay-real"));

    const catalog = readPublishedCatalog(process.cwd(), "real");
    expect(catalog.length).toBeGreaterThan(0);
    for (const card of catalog) {
      expect(card.capture_kind).toBe("real_model_recorded");
    }
  });

  it("fails loudly when the catalog of a real model is not there", () => {
    // It proves that the reader refuses a missing catalog with a reason that names the places where it was expected,
    // and that it never builds an export with no page of a scenario (ADR-075).
    const root = temporaryFolder();

    expect(() => readPublishedCatalog(join(root, "apps", "web"), "real")).toThrow(
      /published catalog of the scenarios/,
    );
    expect(() => readPublishedCatalog(join(root, "apps", "web"), "real")).toThrow(/replay-real/);
  });

  it("looks for the copy that the site serves first, and for the published source second", () => {
    // It proves the order of the two places: the copy is the file the visitor reads, so it wins over the source.
    const root = temporaryFolder();
    const served = join(root, "apps", "web", "public", "replay", "index.json");
    const published = join(root, "site", "replay", "index.json");

    expect(catalogCandidates(join(root, "apps", "web"))).toEqual([served, published]);

    writeCatalog(root, "apps/web/public/replay/index.json", JSON.stringify([VALID_CARD]));
    writeCatalog(root, "site/replay/index.json", JSON.stringify([{ ...VALID_CARD, id: "S02" }]));

    expect(resolveCatalogPath(join(root, "apps", "web"))).toBe(served);
    expect(readPublishedCatalog(join(root, "apps", "web")).map((card) => card.id)).toEqual(["S01"]);
  });

  it("reads the published source when the copy that the site serves is not there yet", () => {
    // It proves that the reader does not depend on the order of the steps of the build: a unit test that runs before
    // the copy exists still finds the catalog of the repository.
    const root = temporaryFolder();
    writeCatalog(root, "site/replay/index.json", JSON.stringify([VALID_CARD]));

    expect(resolveCatalogPath(join(root, "apps", "web"))).toBe(join(root, "site", "replay", "index.json"));
    expect(readPublishedCatalog(join(root, "apps", "web")).map((card) => card.id)).toEqual(["S01"]);
  });

  it("fails loudly when the catalog is not there", () => {
    // It proves that a missing catalog stops the build with a reason, and that the reason names the places where the
    // catalog was expected.
    const root = temporaryFolder();

    expect(() => readPublishedCatalog(join(root, "apps", "web"))).toThrow(/published catalog of the scenarios/);
    expect(() => readPublishedCatalog(join(root, "apps", "web"))).toThrow(/site/);
  });

  it("refuses a catalog whose card does not pass the contract", () => {
    // It proves that a broken card is a refusal with a reason, and never a catalog with no scenario.
    const root = temporaryFolder();
    writeCatalog(root, "site/replay/index.json", JSON.stringify([{ id: "not-a-scenario" }]));

    expect(() => readPublishedCatalog(join(root, "apps", "web"))).toThrow(/does not pass the contract/);
  });

  it("refuses a catalog that is not a JSON document", () => {
    // It proves that a file that cannot be parsed is a refusal with a reason and not a traceback.
    const root = temporaryFolder();
    writeCatalog(root, "site/replay/index.json", "{not json");

    expect(() => readPublishedCatalog(join(root, "apps", "web"))).toThrow(/not a JSON document/);
  });
});
