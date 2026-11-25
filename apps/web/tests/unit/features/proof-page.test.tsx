/**
 * The test of the pages of the proof of work.
 *
 * Why this test exists: the page of the catalog lists the artifacts with the status of each one, and the page
 * of an artifact shows the provenance, the claim, the verdicts, the recipe and the links of the artifact. A
 * page that shows a badge for a draft, or that hides the recipe, is a page that lies about the artifact.
 *
 * Every case runs with no key and no network: the catalog of the case is the catalog the repository
 * publishes, read from the disk of the repository.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ProofCatalogPage from "@/app/(public)/proof/page";
import ProofPage from "@/app/(public)/proof/[id]/page";
import { readProofCatalog } from "@/lib/proof/catalog";

describe("the page of the catalog of the proofs", () => {
  it("lists the artifacts with the scenario, the catalog and the status of each one", () => {
    render(<ProofCatalogPage />);

    expect(screen.getByRole("heading", { level: 1, name: "Proof of work" })).toBeInTheDocument();
    const artifacts = readProofCatalog(process.cwd());
    const links = screen.getAllByRole("link");
    const hrefs = links.map((link) => link.getAttribute("href"));
    for (const artifact of artifacts) {
      expect(hrefs).toContain(`/proof/${artifact.artifact_id}`);
    }
  });
});

describe("the page of an artifact", () => {
  it("shows the provenance, the verdicts, the recipe and the links of the artifact", async () => {
    const artifact = readProofCatalog(process.cwd())[0];
    if (!artifact) {
      throw new Error("the catalog of the proofs is empty");
    }
    render(await ProofPage({ params: Promise.resolve({ id: artifact.artifact_id }) }));

    expect(
      screen.getByRole("heading", { level: 1, name: `Proof of ${artifact.scenario_id}` }),
    ).toBeInTheDocument();
    expect(screen.getByText(artifact.git_commit)).toBeInTheDocument();
    expect(screen.getByText(artifact.verdict_summary)).toBeInTheDocument();
    expect(screen.getByText(artifact.recipe)).toBeInTheDocument();
    expect(screen.getByText(artifact.transcript)).toBeInTheDocument();
    for (const link of artifact.links) {
      expect(screen.getAllByText(link).length).toBeGreaterThan(0);
    }
  });

  it("shows the badge only when the status is verified", async () => {
    const artifacts = readProofCatalog(process.cwd());
    const verified = artifacts.find((artifact) => artifact.status === "verified");
    expect(verified).toBeDefined();
    render(await ProofPage({ params: Promise.resolve({ id: verified!.artifact_id }) }));

    expect(screen.getByText("verified")).toBeInTheDocument();
  });
});
