"use client";

/**
 * The provider of the catalog of the scenarios.
 *
 * Why this file exists: the catalog of the site is a static file of the export, and the interface
 * has to read it in the browser. The provider is the static friendly client: it reads the catalog
 * once, it never reads it again when the window regains the focus, it never retries, and a
 * catalog that is not there is a refusal and not a retry. A site that answers a request twice for
 * the same file is a site that costs more and knows less.
 *
 * Why the loader can be injected: a unit test has to be able to answer with a catalog that is
 * broken, or with a catalog that never arrives, without a network and without a server.
 *
 * Why the reload is explicit: the visitor asks for a new reading when the visitor wants one, and
 * never because a window regained the focus.
 *
 * Why a provider that has a provider above it does not read the catalog again: the catalog is
 * read once, and a second request for the same file is a request the site does not need. The
 * provider above holds the catalog, and the provider below shows it.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactElement, ReactNode } from "react";

import { loadScenarioCatalog } from "@/lib/api/replay";
import type { ScenarioIndexEntry } from "@/lib/api/schemas";
import { DEFAULT_CATALOG } from "@/lib/replay/catalogs";
import type { ReplayCatalogId } from "@/lib/replay/catalogs";

/**
 * The function that reads the catalog of the scenarios.
 *
 * Why it is a type of its own: the provider reads the catalog through this function and through
 * nothing else, so a test can put a catalog of its own in its place.
 */
export type ScenarioCatalogLoader = () => Promise<ScenarioIndexEntry[] | { error: string }>;

/**
 * The state of the catalog of the scenarios.
 *
 * Why the status is one of four words: the catalog is either not read yet, being read, read or
 * refused, and the interface renders a different thing for each of them.
 */
export interface ScenarioCatalogState {
  /** Where the reading of the catalog stands. */
  readonly status: "idle" | "loading" | "ready" | "refused";
  /** The cards of the catalog, when it was read. */
  readonly scenarios: readonly ScenarioIndexEntry[];
  /** The reason of the refusal, when the catalog was refused. */
  readonly error: string | null;
  /** Reads the catalog again, on purpose. */
  readonly reload: () => void;
}

/**
 * The props of the provider of the catalog.
 *
 * Why the loader is optional: the provider reads the published catalog of the site when the
 * caller does not say otherwise.
 */
export interface ScenarioCatalogProviderProps {
  /** What the provider renders around the pages. */
  readonly children: ReactNode;
  /** The function that reads the catalog. The default reads the published one. */
  readonly loader?: ScenarioCatalogLoader;
  /**
   * The catalog of the scenarios the provider reads.
   *
   * Why the catalog is a prop: the site publishes two catalogs, the recordings of the scripted model and the
   * recordings of a real model, and each one has its own root of artifacts (ADR-075). The default is the sandbox,
   * the catalog that existed before the second one.
   */
  readonly catalog?: ReplayCatalogId;
}

/** The context that holds the state of the catalog. */
const ScenarioCatalogContext = createContext<ScenarioCatalogState | null>(null);

/**
 * The loader of the published catalog of a catalog of the site.
 *
 * Why it is a function of its own: the provider reads the catalog through it, and the reference
 * that holds it has to be a function and never nothing.
 */
function publishedCatalogLoader(catalog: ReplayCatalogId): ScenarioCatalogLoader {
  return () => loadScenarioCatalog({ catalog });
}

/**
 * The provider of the catalog of the scenarios.
 *
 * The reading happens once, when the provider appears, and again only when the visitor asks for
 * it with the reload.
 *
 * Why a provider that has a provider above it does not read: the catalog is read once, and a
 * provider above already read it, so this one shows that reading instead of asking the site for
 * the same file a second time.
 */
export function ScenarioCatalogProvider(props: ScenarioCatalogProviderProps): ReactElement {
  const { children, loader, catalog = DEFAULT_CATALOG } = props;

  // The state of the provider that is above this one, when there is one.
  const inherited = useContext(ScenarioCatalogContext);

  const [attempt, setAttempt] = useState(0);
  const [status, setStatus] = useState<ScenarioCatalogState["status"]>("idle");
  const [scenarios, setScenarios] = useState<readonly ScenarioIndexEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  // The loader is kept in a reference, so that a caller that hands over a new function does not
  // make the provider read the catalog again. The reading is decided by the attempt alone.
  //
  // Why the default loader is remembered: it closes over the catalog, and a function that is
  // built on every render would make the provider read the catalog again and again.
  const defaultLoader = useMemo(() => publishedCatalogLoader(catalog), [catalog]);
  const loaderRef = useRef<ScenarioCatalogLoader>(loader ?? defaultLoader);
  loaderRef.current = loader ?? defaultLoader;

  useEffect(() => {
    // The catalog is read once. When a provider above already read it, this provider shows that
    // reading instead of asking the site for the same file a second time.
    if (inherited !== null) {
      return;
    }

    let alive = true;
    setStatus("loading");
    setScenarios([]);
    setError(null);

    async function read(): Promise<void> {
      let result: ScenarioIndexEntry[] | { error: string };
      try {
        result = await loaderRef.current();
      } catch {
        result = { error: "the catalog of the scenarios could not be read: the site did not answer" };
      }
      if (!alive) {
        return;
      }
      if ("error" in result) {
        setStatus("refused");
        setScenarios([]);
        setError(result.error);
        return;
      }
      setStatus("ready");
      setScenarios(result);
      setError(null);
    }

    void read();

    return () => {
      alive = false;
    };
  }, [attempt, inherited]);

  const reload = useCallback(() => {
    setAttempt((current) => current + 1);
  }, []);

  const own = useMemo<ScenarioCatalogState>(
    () => ({ status, scenarios, error, reload }),
    [status, scenarios, error, reload],
  );

  // The catalog of the provider above wins, so that the catalog is read once and not twice.
  const value = useMemo<ScenarioCatalogState>(() => inherited ?? own, [inherited, own]);

  return (
    <ScenarioCatalogContext.Provider value={value}>{children}</ScenarioCatalogContext.Provider>
  );
}

/**
 * Reads the state of the catalog of the scenarios.
 *
 * Why it throws outside the provider: a page that asks for the catalog without the provider around
 * it has a bug, and a bug that reads a catalog of nothing is a bug that hides.
 */
export function useScenarioCatalog(): ScenarioCatalogState {
  const state = useContext(ScenarioCatalogContext);
  if (!state) {
    throw new Error("useScenarioCatalog has to be called inside a ScenarioCatalogProvider");
  }
  return state;
}

/** Every symbol this module exports, so that a reader sees the whole surface of the provider at once. */
export const __all__ = [
  "ScenarioCatalogLoader",
  "ScenarioCatalogState",
  "ScenarioCatalogProviderProps",
  "ScenarioCatalogProvider",
  "useScenarioCatalog",
] as const;
