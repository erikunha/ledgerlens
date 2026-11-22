"use client";

/**
 * The catalog of the scenarios of the recorded demo.
 *
 * Why this file exists: the recorded demo is the half of the demo that works with no key and no
 * network. The page shows the catalog of the scenarios from the static export of the site and it
 * links to the route of every scenario, so that a visitor picks a scenario and reads its
 * recording, and it makes no request to the backend of the demo at all: no provider, no exchange
 * rate service and no write endpoint.
 *
 * Why the page reads the catalog through the provider and not by itself: `lib/api/replay.ts` is
 * the ONE place that reads the static artifacts of the site, and the provider of the catalog is
 * the client of that client. The page calls no `fetch` of its own, so the rule that the recorded
 * demo calls nobody can be checked by reading the library alone (ADR-043).
 *
 * The catalog is read with the validator of the repository and with no mapping by hand, because
 * the catalog the repository publishes is a list of cards that carry `id` and a `data_origin` that
 * is a string. A catalog that does not pass the contract is refused with its reasons and shown
 * as no card at all, because a half read catalog is a catalog a reader cannot trust (ADR-042).
 *
 * The mode of what is shown is a property of what is shown: the reader of a recording shows the
 * mode of the manifest it read, and a recorded run is never presented as a live one (ADR-040).
 */

import Link from "next/link";

import { Badge } from "@/components/ui/Badge";
import { buttonClasses } from "@/components/ui/Button";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { loadScenarioCatalog } from "@/lib/api/replay";
import { ScenarioCatalogProvider, useScenarioCatalog } from "@/lib/api/provider";
import { scenarioPath } from "@/lib/state/urlState";

/**
 * The page of the recorded demo.
 *
 * The page is a client component because the artifacts are read in the browser: the site is a
 * static export and the files of the recording are served next to it.
 *
 * Why the provider is here and not in the layout: the catalog is the only thing this page needs,
 * and the provider reads it once, through the client of the artifacts.
 */
export default function ReplayPage() {
  return (
    <ScenarioCatalogProvider loader={loadScenarioCatalog}>
      <ReplayCatalog />
    </ScenarioCatalogProvider>
  );
}

/**
 * The catalog of the scenarios, as the provider of the catalog read it.
 *
 * Why the page shows the reason of a refusal and no card: a catalog that does not pass the
 * contract is a catalog a reader cannot trust, and a card of a broken catalog is a card that
 * points to a route that may not exist.
 */
function ReplayCatalog() {
  const { scenarios, error } = useScenarioCatalog();

  return (
    <div className="mx-auto flex w-full max-w-content flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge>mode: deterministic_sandbox</Badge>
        </div>
        <h1 className="text-3xl font-semibold">Recorded demo</h1>
        <p className="max-w-2xl text-text-muted">
          The demo reads the published artifacts of a capture, played in the browser. It asks no
          provider, it needs no key and no network, and it runs the same way for every visitor.
        </p>
        <p className="text-sm text-text-subtle">
          The live mode runs on the backend of the demo, with a key of your own:{" "}
          <Link className={buttonClasses("ghost", "sm")} href="/live">
            Open the live mode
          </Link>
        </p>
      </header>

      {error ? (
        <div role="alert" className="rounded-lg border border-danger/40 bg-danger-light p-4">
          <p className="text-sm text-danger-dark">{error}</p>
        </div>
      ) : null}

      {scenarios.length > 0 ? (
        <section className="flex flex-col gap-4" aria-labelledby="the-scenarios">
          <h2 id="the-scenarios" className="text-lg font-semibold">
            The scenarios
          </h2>
          <p className="text-sm text-text-muted">The cases the site published.</p>
          <ul className="flex flex-col gap-3">
            {scenarios.map((scenario) => (
              <li key={scenario.id}>
                <Card>
                  <CardHeader>
                    <h2 className="text-base font-semibold text-foreground">
                      {scenario.id} - {scenario.question}
                    </h2>
                  </CardHeader>
                  <CardContent>
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        className={buttonClasses("primary", "md")}
                        href={scenarioPath(scenario.id)}
                      >
                        {scenario.id} - {scenario.name}
                      </Link>
                      {scenario.data_origin ? (
                        <span className="text-xs text-text-subtle">data: {scenario.data_origin}</span>
                      ) : null}
                      {scenario.status ? <Badge>{scenario.status}</Badge> : null}
                    </div>
                  </CardContent>
                </Card>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
