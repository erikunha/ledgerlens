/**
 * The reader of the published catalog of the proofs of work.
 *
 * Why this file exists: the route of the proof of work is a server component of a static export, so it has to
 * read the catalog of the artifacts while the export is built. The repository publishes the catalog in one
 * place only, `site/proof`, and the build copies it into `apps/web/public/proof`, where the site serves it.
 *
 * Why the reader looks in two places: the copy is the file the site serves, so it is the first place to look,
 * and the published source is the fallback. A reader that only knows the copy depends on the order of the
 * steps of the build, and a unit test that runs before the copy exists would see no catalog at all.
 *
 * Why the failure is loud: a catalog that cannot be read stops the build with a reason a reader can act on.
 * It never becomes a catalog with no artifact, because a catalog with no artifact produces an export with no
 * page of an artifact, and a visitor who follows a link of the catalog lands on nothing.
 */

import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

/** One number of the artifact, with the report it came from and the digest of that report. */
export interface ProofNumber {
  readonly name: string;
  readonly value: string;
  readonly report_path: string;
  readonly report_digest: string;
}

/** One artifact of the catalog of the proofs, as the export of the repository publishes it. */
export interface ProofCatalogEntry {
  readonly artifact_id: string;
  readonly scenario_id: string;
  readonly catalog: string;
  readonly capture_kind: string;
  readonly status: string;
  readonly missing: readonly string[];
  readonly git_commit: string;
  readonly claim: string;
  readonly evidence_refs: readonly string[];
  readonly verdict_summary: string;
  readonly numbers: readonly ProofNumber[];
  readonly recipe: string;
  readonly links: readonly string[];
  readonly media: string | null;
  readonly transcript: string;
  readonly media_dropped: boolean;
  readonly known_limitations: readonly string[];
  readonly cost_usd: string | null;
  readonly cost_provenance: string;
}

/**
 * The places where the catalog of the proofs can be, in the order they are looked for.
 *
 * Why the first place is the copy: the site serves that file, so the export has to be built from the very
 * file that the visitor will read. Why the second place is the published source: the repository publishes the
 * catalog in `site/proof`, and the copy is made from it.
 */
export function proofCatalogCandidates(root: string = process.cwd()): string[] {
  return [
    path.join(root, "public", "proof", "index.json"),
    path.join(root, "..", "..", "site", "proof", "index.json"),
  ];
}

/**
 * The catalog of the proofs, read from the disk.
 *
 * The reader refuses a catalog that is not there and a catalog whose shape is not the shape of the export,
 * because a catalog a reader cannot trust is a catalog that stops the build, and never a page with no
 * artifact.
 */
export function readProofCatalog(root: string = process.cwd()): ProofCatalogEntry[] {
  for (const candidate of proofCatalogCandidates(root)) {
    if (!existsSync(candidate)) {
      continue;
    }
    const data = JSON.parse(readFileSync(candidate, "utf8")) as { artifacts?: unknown };
    if (!Array.isArray(data.artifacts)) {
      throw new Error(`the catalog of the proofs at ${candidate} holds no list of artifacts`);
    }
    return data.artifacts as ProofCatalogEntry[];
  }
  throw new Error("the published catalog of the proofs was not found on the disk of the repository");
}
