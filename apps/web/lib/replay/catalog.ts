/**
 * The reader of the published catalog of the scenarios.
 *
 * Why this file exists: the route of a scenario is a server component of a static export, so it has to know the
 * identifiers of the scenarios while the export is built. The repository publishes the catalog in one place only,
 * `site/replay`, and the build copies it into `apps/web/public/replay`, where the site serves it (ADR-042).
 *
 * Why the reader looks in two places: the copy is the file the site serves, so it is the first place to look, and the
 * published source is the fallback. A reader that only knows the copy depends on the order of the steps of the build:
 * a unit test that runs before the copy exists used to see a catalog with no scenario at all, and it failed with a
 * page of 404 in the middle of a test that had nothing to do with the 404.
 *
 * Why the failure is loud: a catalog that cannot be read, or that does not pass the contract of the published
 * artifacts, stops the build with a reason a reader can act on. It never becomes a catalog with no scenario, because a
 * catalog with no scenario produces an export with no page of a scenario, and a visitor who follows a card of the
 * catalog lands on nothing.
 */

import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

import type { ScenarioIndexEntry } from "@/lib/api/schemas";
import { validateScenarioIndex } from "@/lib/replay/validate";

/**
 * The places where the catalog of the scenarios can be, in the order they are looked for.
 *
 * Why the first place is the copy: the site serves that file, so the export has to be built from the very file that
 * the visitor will read.
 *
 * Why the second place is the published source: the repository publishes the catalog in `site/replay`, and the copy is
 * made from it. A reader that finds it there reads the same catalog the site serves.
 *
 * Why the root is a parameter: the reader is a function of the folder it works on, so a test can prove the order of
 * the two places with a folder of its own, outside the repository.
 */
export function catalogCandidates(root: string = process.cwd()): string[] {
  return [
    path.join(root, "public", "replay", "index.json"),
    path.join(root, "..", "..", "site", "replay", "index.json"),
  ];
}

/**
 * Finds the catalog of the scenarios on the disk.
 *
 * Why the first place that exists wins: the copy is what the site serves, and a copy that is older than the published
 * source is still the file the visitor reads.
 *
 * Why the first place is returned when none of them exists: the caller reads that file and fails with a reason that
 * names the place where the catalog was expected.
 */
export function resolveCatalogPath(root: string = process.cwd()): string {
  const candidates = catalogCandidates(root);
  for (const candidate of candidates) {
    if (existsSync(candidate)) {
      return candidate;
    }
  }
  return candidates[0] as string;
}

/**
 * Reads the catalog of the scenarios from the disk.
 *
 * Why the reader throws and never returns an empty catalog: an empty catalog is a valid answer to a question nobody
 * asked, and it builds a site with no page of a scenario. A reason a reader can act on is the answer.
 */
export function readPublishedCatalog(root: string = process.cwd()): ScenarioIndexEntry[] {
  const file = resolveCatalogPath(root);

  let raw: string;
  try {
    raw = readFileSync(file, "utf8");
  } catch {
    throw new Error(
      `the published catalog of the scenarios was not found: ${catalogCandidates(root).join(" or ")}`,
    );
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    throw new Error(`the published catalog of the scenarios is not a JSON document: ${file} (${reason})`);
  }

  const catalog = validateScenarioIndex(parsed);
  if (!catalog.ok) {
    throw new Error(
      `the published catalog of the scenarios does not pass the contract of the published artifacts: ${file} (${catalog.reasons.join("; ")})`,
    );
  }

  return catalog.value;
}

export const __all__ = ["catalogCandidates", "readPublishedCatalog", "resolveCatalogPath"] as const;
