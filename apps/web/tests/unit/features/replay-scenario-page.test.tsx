/**
 * The test of the route of a scenario of the recorded demo.
 *
 * Why this test exists: the route of a scenario is a page of the static export, so the export has to hold one page per
 * published scenario and the page has to show the scenario that the catalog publishes. The route is a server component
 * because a static export of a dynamic route needs the list of the parameters at build time, and the identifier of the
 * scenario lives in the path and never in the query string (ADR-043).
 *
 * Every case runs with no key and no network: the catalog of the case is the catalog the repository publishes, read
 * from the disk of the repository.
 */

import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { parseScenarioId, scenarioPath } from "@/lib/state/urlState";

/**
 * Finds the published catalog of the scenarios on the disk.
 *
 * Why the search goes up from the working folder: the catalog is published in `site/replay` at the root of the
 * repository and copied into `apps/web/public/replay` by the build, and the test must find it in either place.
 */
function findPublishedCatalog(): Record<string, unknown>[] {
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
    ...roots.map((root) => join(root, "public", "replay", "index.json")),
    ...roots.map((root) => join(root, "site", "replay", "index.json")),
  ];

  for (const catalog of candidates) {
    if (!existsSync(catalog)) {
      continue;
    }
    return JSON.parse(readFileSync(catalog, "utf8")) as Record<string, unknown>[];
  }
  throw new Error("the published catalog of the scenarios was not found on the disk of the repository");
}

/** The published catalog of the scenarios, read from the disk of the repository. */
const CATALOG = findPublishedCatalog();

/**
 * The module of the route of the scenario.
 *
 * Why the import is dynamic and relative: the route is a server component that carries the parameters of the export,
 * and it is read at the moment of the case. A route that is not there yet then fails the case that needs it with a
 * readable message, and it never breaks the whole suite at the moment of the import.
 */
async function readRoute(): Promise<RouteModule> {
  const specifier = "../../../app/(public)/replay/scenario/[scenario]/page";
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

describe("the route of a scenario", () => {
  it("publishes one page per scenario of the published catalog", async () => {
    // It proves that the export of the site holds a page for every scenario that the catalog publishes, and that the
    // parameter of the route is the identifier of the scenario.
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

  it("shows the scenario that the catalog publishes", async () => {
    // It proves that the route shows the question of the scenario and the identifier that the catalog gave it.
    const route = await readRoute();
    const card = CATALOG[0];
    const scenarioId = card?.["id"] as string;
    const question = card?.["question"] as string;

    const element = await route.default({ params: paramsOf(scenarioId) });
    render(element as React.ReactElement);

    // The heading of the route carries the identifier and the question of the card of the catalog.
    expect(
      await screen.findByRole("heading", { name: (name) => name.includes(question) }),
    ).toBeInTheDocument();
    expect(screen.getAllByText(new RegExp(scenarioId)).length).toBeGreaterThan(0);
  });

  it("carries the identifier of the scenario in the path and only the preferences in the query string", async () => {
    // It proves that the path of a scenario holds the identifier and nothing else, and that the query string of the
    // interface holds the two preferences of the contract and nothing else.
    const route = await readRoute();
    const card = CATALOG[0];
    const scenarioId = card?.["id"] as string;
    const question = card?.["question"] as string;

    const element = await route.default({ params: paramsOf(scenarioId) });
    render(element as React.ReactElement);
    await screen.findByRole("heading", { name: (name) => name.includes(question) });

    expect(scenarioPath(scenarioId)).toBe(`/replay/scenario/${scenarioId}`);
    expect(parseScenarioId(scenarioPath(scenarioId))).toBe(scenarioId);

    for (const anchor of Array.from(document.querySelectorAll("a"))) {
      const href = anchor.getAttribute("href") ?? "";
      const url = new URL(href, "http://site.test");
      for (const key of url.searchParams.keys()) {
        expect(["tab", "speed"], `the link ${href} must not carry the parameter ${key}`).toContain(key);
      }
    }
  });
});
