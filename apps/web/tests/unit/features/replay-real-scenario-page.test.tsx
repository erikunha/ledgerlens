/**
 * The test of the route of a scenario recorded with a real model.
 *
 * Why this test exists: the route of a scenario is a page of the static export, so the export has to hold one page per
 * published scenario of that catalog and the page has to show the scenario that the catalog publishes. The site
 * publishes two catalogs, and the route of a scenario of one of them never reads the catalog of the other one: a route
 * that read the wrong catalog would publish the page of the wrong recording (ADR-075).
 *
 * Every case runs with no key and no network: the catalog of the case is the catalog the repository publishes, read
 * from the disk of the repository.
 */

import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { parseScenarioId, scenarioPath } from "@/lib/state/urlState";

/**
 * Finds the published catalog of the scenarios of a catalog on the disk.
 *
 * Why the search goes up from the working folder: the catalog is published in `site/<catalog>` at the root of the
 * repository and copied into `apps/web/public/<catalog>` by the build, and the test must find it in either place.
 */
function findPublishedCatalog(folder: string): Record<string, unknown>[] {
  const roots: string[] = [];
  let current = process.cwd();
  for (;;) {
    roots.push(current);
    const parent = dirname(current);
    if (parent === current) {
      break;
    }
    current = parent;
  }

  const candidates = [
    ...roots.map((root) => join(root, "public", folder, "index.json")),
    ...roots.map((root) => join(root, "site", folder, "index.json")),
  ];

  for (const catalog of candidates) {
    if (!existsSync(catalog)) {
      continue;
    }
    return JSON.parse(readFileSync(catalog, "utf8")) as Record<string, unknown>[];
  }
  throw new Error(
    `the published catalog of the scenarios of the catalog ${folder} was not found on the disk of the repository`,
  );
}

/** The published catalog of the scenarios of a real model, read from the disk of the repository. */
const CATALOG = findPublishedCatalog("replay-real");

/**
 * The module of the route of the scenario.
 *
 * Why the import is dynamic and relative: the route is a server component that carries the parameters of the export,
 * and it is read at the moment of the case. A route that is not there yet then fails the case that needs it with a
 * readable message, and it never breaks the whole suite at the moment of the import.
 */
async function readRoute(): Promise<RouteModule> {
  const specifier = "../../../app/(public)/replay-real/scenario/[scenario]/page";
  return (await import(specifier)) as unknown as RouteModule;
}

/**
 * The parameters of the route, in the shape of Next.js.
 *
 * Why the promise carries the values as well: the framework hands over a promise of the parameters, and a route that
 * reads them directly must find them there too.
 */
function paramsOf(scenarioId: string): Promise<{ scenario: string }> & { scenario: string } {
  return Object.assign(Promise.resolve({ scenario: scenarioId }), { scenario: scenarioId });
}

/** The shape of the module of the route of a scenario. */
interface RouteModule {
  default: (props: { params: unknown }) => unknown;
  generateStaticParams?: () => unknown;
  dynamicParams?: boolean;
}

describe("the route of a scenario of a real model", () => {
  it("publishes one page per scenario of the published catalog of a real model", async () => {
    // It proves that the export of the site holds a page for every scenario that the catalog of a real model
    // publishes, and that the parameter of the route is the identifier of the scenario (ADR-075).
    const route = await readRoute();

    expect(typeof route.generateStaticParams).toBe("function");
    const parameters = route.generateStaticParams?.() as { scenario: string }[] | undefined;
    expect(parameters).toHaveLength(CATALOG.length);
    expect(parameters?.map((parameter) => parameter.scenario)).toEqual(
      CATALOG.map((card) => card["id"] as string),
    );
  });

  it("never guesses a scenario at run time", async () => {
    // It proves that a scenario the catalog does not publish is the page of 404 and never a guess.
    const route = await readRoute();

    expect(route.dynamicParams).toBe(false);
  });

  it("shows the scenario that the catalog of a real model publishes", async () => {
    // It proves that the route shows the question of the scenario and the identifier that the catalog gave it.
    const route = await readRoute();
    const card = CATALOG[0];
    const scenarioId = card?.["id"] as string;
    const question = card?.["question"] as string;

    const element = await route.default({ params: paramsOf(scenarioId) });
    render(element as React.ReactElement);

    expect(
      await screen.findByRole("heading", { name: (name) => name.includes(question) }),
    ).toBeInTheDocument();
    expect(screen.getAllByText(new RegExp(scenarioId)).length).toBeGreaterThan(0);
  });

  it("reads the bundle of the scenario from the root of the catalog of a real model", async () => {
    // It proves that the route hands the provider of the replay the catalog of a real model, and that the provider
    // reads the bundle from the root of that catalog: a route that asked for the root of the other catalog would show
    // the recording of the scripted model under the name of a recording of a real model (ADR-075).
    const askedFor: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        askedFor.push(String(input));
        return { ok: false, status: 404, text: async () => "" } as unknown as Response;
      }),
    );

    const route = await readRoute();
    const card = CATALOG[0];
    const scenarioId = card?.["id"] as string;

    const element = await route.default({ params: paramsOf(scenarioId) });
    render(element as React.ReactElement);
    await screen.findByRole("heading", { name: (name) => name.includes(card?.["question"] as string) });

    expect(askedFor).toContain("/replay-real/s01/manifest.json");
    expect(askedFor).not.toContain("/replay/s01/manifest.json");

    vi.unstubAllGlobals();
  });

  it("carries the identifier of the scenario under the route of its own catalog", async () => {
    // It proves that the path of a scenario of a real model is the path of that catalog and never the path of the
    // sandbox, and that the reader of the path gives the identifier back for both catalogs (ADR-075).
    const route = await readRoute();
    const card = CATALOG[0];
    const scenarioId = card?.["id"] as string;
    const question = card?.["question"] as string;

    const element = await route.default({ params: paramsOf(scenarioId) });
    render(element as React.ReactElement);
    await screen.findByRole("heading", { name: (name) => name.includes(question) });

    expect(scenarioPath(scenarioId, "real")).toBe(`/replay-real/scenario/${scenarioId}`);
    expect(parseScenarioId(scenarioPath(scenarioId, "real"))).toBe(scenarioId);
    expect(parseScenarioId(scenarioPath(scenarioId))).toBe(scenarioId);
  });
});
