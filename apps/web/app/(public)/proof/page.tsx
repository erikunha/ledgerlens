/**
 * The catalog of the proofs of work of the repository.
 *
 * Why this file exists: the proof of work of the repository is a set of artifacts, one per bundle of the two
 * published catalogs, and a visitor who opens the site has to find them. The page lists the artifacts with
 * the scenario, the catalog and the status of each one, and it links to the page of every artifact, where the
 * provenance, the claim, the evidence, the verdicts, the recipe and the links of the artifact live.
 *
 * Why the page is a server component: the site is a static export, and the catalog of the proofs is a file of
 * the repository, so the page reads it from the disk while the export is built. The page asks no backend, it
 * needs no key and no network, and it runs the same way for every visitor.
 *
 * Why the status is a badge with the word and not only a colour: a badge never carries a meaning on its own,
 * and the status of an artifact is `verified` only when the evidence is all there. A `draft` artifact names
 * what is missing on its own page, and no person promotes an artifact by hand.
 */

import Link from "next/link";

import { Badge } from "@/components/ui/Badge";
import { readProofCatalog } from "@/lib/proof/catalog";

export const metadata = {
  title: "Proof of work",
  description:
    "The artifacts of the proof of work of the repository: the claim, the evidence, the provenance and the recipe of every published run.",
};

/**
 * The page of the catalog of the proofs.
 *
 * The page reads the catalog from the disk while the export is built, and every card of the catalog links to
 * the page of the artifact, with the identifier of the artifact in the path.
 */
export default function ProofCatalogPage() {
  const artifacts = readProofCatalog(process.cwd());

  return (
    <div className="mx-auto flex w-full max-w-content flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-3">
        <h1 className="text-3xl font-semibold">Proof of work</h1>
        <p className="max-w-2xl text-text-muted">
          Every artifact of this page is a claim about the code of the repository: it names the commit, the
          digests, the evidence and the recipe that reproduces the run, and it says nothing about a person.
          An artifact is verified only when the evidence is all there, and a draft names what is missing.
        </p>
      </header>
      <ul className="flex flex-col gap-4">
        {artifacts.map((artifact) => (
          <li key={artifact.artifact_id}>
            <Link
              className="flex flex-col gap-2 rounded-lg border border-border p-4 hover:bg-surface-muted"
              href={`/proof/${artifact.artifact_id}`}
            >
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-semibold">
                  {artifact.scenario_id} · {artifact.catalog}
                </span>
                <Badge tone={artifact.status === "verified" ? "success" : "warning"}>
                  {artifact.status}
                </Badge>
              </span>
              <span className="text-sm text-text-muted">{artifact.claim}</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
