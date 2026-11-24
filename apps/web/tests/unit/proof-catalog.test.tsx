/**
 * The test of the reader of the published catalog of the proofs.
 *
 * Why this test exists: the route of the proof of work is a server component of a static export, so the
 * catalog of the proofs has to be on the disk while the export is built, and the reader has to find it and to
 * refuse a catalog that is not there. A catalog with no artifact would produce an export with no page of an
 * artifact, and a visitor who follows a link of the catalog would land on nothing.
 *
 * Every case runs with no key and no network: the catalog of the case is the catalog the repository
 * publishes, read from the disk of the repository.
 */

import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { proofCatalogCandidates, readProofCatalog } from "@/lib/proof/catalog";

describe("the reader of the catalog of the proofs", () => {
  it("finds the catalog the repository publishes", () => {
    const artifacts = readProofCatalog(process.cwd());

    expect(artifacts.length).toBeGreaterThan(0);
    for (const artifact of artifacts) {
      expect(artifact.artifact_id).toMatch(/^[a-f0-9]{64}$/);
      expect(artifact.scenario_id).toBeTruthy();
      expect(["replay", "replay-real"]).toContain(artifact.catalog);
      expect(["verified", "draft"]).toContain(artifact.status);
      expect(artifact.git_commit).toMatch(/^[a-f0-9]{40}$/);
      expect(artifact.recipe).toContain("scripts/");
      expect(artifact.transcript).toBeTruthy();
      expect(artifact.known_limitations.length).toBeGreaterThan(0);
    }
  });

  it("looks in the copy of the build first and in the published source after", () => {
    const candidates = proofCatalogCandidates(process.cwd());

    expect(candidates[0]).toContain(join("public", "proof", "index.json"));
    expect(candidates[1]).toContain(join("site", "proof", "index.json"));
  });

  it("refuses a root with no catalog, and never becomes a catalog with no artifact", () => {
    const empty = mkdtempSync(join(tmpdir(), "proof-catalog-"));

    expect(() => readProofCatalog(empty)).toThrow(/not found/);
  });
});
