/**
 * The two catalogs of recorded scenarios that the site publishes.
 *
 * Why this file exists: the site publishes the recordings of the scripted model and the recordings of a real
 * model, and every layer of the site has to know which one it is reading: the client of the published artifacts,
 * the reader of the catalog on the disk, the URL of a scenario and the page that shows it. The table lives here so
 * that the layers cannot drift apart on the root of the artifacts, on the mode of the bundles and on the route of
 * the catalog (ADR-075).
 *
 * Why a catalog is one mode: the bundles of a catalog all carry the same mode, and the browser refuses a bundle
 * whose mode is not the mode of the catalog it was asked for. A recording of a real model published under the
 * label of the sandbox would be a lie, and a lie in a manifest is worse than a missing file.
 */

import type { TraceMode } from "@/lib/api/schemas";

/**
 * The identifier of a catalog of recorded scenarios.
 *
 * Why two and not one: the site publishes the recordings of the scripted model and the recordings of a real model,
 * and the two are different things: the first is a formula and the second is a run.
 */
export type ReplayCatalogId = "sandbox" | "real";

/**
 * What a catalog of recorded scenarios is: where its artifacts live, what its bundles declare and where its
 * pages are.
 */
export interface ReplayCatalog {
  /** The identifier of the catalog. */
  readonly id: ReplayCatalogId;
  /** The root of the published artifacts, which the browser reads. */
  readonly root: string;
  /** The mode every bundle of the catalog declares. */
  readonly mode: TraceMode;
  /** The route of the page of the catalog, and the prefix of the route of a scenario. */
  readonly route: string;
  /**
   * The name of the folder of the published artifacts.
   *
   * Why the folder has a name of its own: the browser reads the artifacts under a root, and the build reads them
   * from a folder of the repository, and the two are not the same string.
   */
  readonly folder: string;
}

/**
 * The two catalogs of the site.
 *
 * Why the mode of the sandbox is `deterministic_sandbox` and the mode of the real one is `live_agent`: the bundles
 * declare that mode, and the browser refuses a bundle of the mode of the other catalog.
 */
export const REPLAY_CATALOGS: Readonly<Record<ReplayCatalogId, ReplayCatalog>> = {
  sandbox: {
    id: "sandbox",
    root: "/replay",
    mode: "deterministic_sandbox",
    route: "/replay",
    folder: "replay",
  },
  real: {
    id: "real",
    root: "/replay-real",
    mode: "live_agent",
    route: "/replay-real",
    folder: "replay-real",
  },
};

/**
 * The catalog that a caller that names none reads.
 *
 * Why the sandbox is the default: it is the catalog that existed before the second one, and a caller that names
 * no catalog is a caller of the recorded demo of the sandbox.
 */
export const DEFAULT_CATALOG: ReplayCatalogId = "sandbox";

/**
 * The catalog of an identifier.
 *
 * Why the function and not a lookup: a caller that names a catalog it does not know has to be told, and the
 * lookup of a record would answer `undefined` instead of a reason.
 */
export function catalogOf(id: ReplayCatalogId): ReplayCatalog {
  const catalog = (REPLAY_CATALOGS as Readonly<Record<string, ReplayCatalog | undefined>>)[id];
  if (!catalog) {
    throw new Error(
      `the catalog ${String(id)} is not one of the catalogs of the site: ${Object.keys(REPLAY_CATALOGS).join(", ")}`,
    );
  }
  return catalog;
}

/**
 * Says whether a value is the identifier of one of the catalogs of the site.
 *
 * Why the function exists: the loaders of the artifacts never throw at the caller, so a caller that names a
 * catalog it does not know has to be refused with a reason and not with a crash. The check of the identifier
 * is what lets the loader refuse it before it reads a single file.
 */
export function isReplayCatalogId(value: unknown): value is ReplayCatalogId {
  return (
    typeof value === "string" &&
    Object.prototype.hasOwnProperty.call(REPLAY_CATALOGS, value)
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the catalogs at once. */
export const __all__ = [
  "ReplayCatalogId",
  "ReplayCatalog",
  "REPLAY_CATALOGS",
  "DEFAULT_CATALOG",
  "catalogOf",
  "isReplayCatalogId",
] as const;
