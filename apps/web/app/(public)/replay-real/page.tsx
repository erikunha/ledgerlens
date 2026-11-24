"use client";

/**
 * The catalog of the scenarios recorded with a real model.
 *
 * Why this file exists: the site publishes two catalogs of recorded scenarios. This one holds the
 * recordings made with a real model: the agent read the ledger, asked the reference source and wrote
 * its own answer, and the repository published that run. It is a second thing to look at, and a
 * visitor who reads both sees the difference between a formula and a run (ADR-075).
 *
 * Why the page reads the catalog through the provider and not by itself: `lib/api/replay.ts` is the
 * ONE place that reads the static artifacts of the site, and the provider of the catalog is the
 * client of that client. The page calls no `fetch` of its own, so the rule that the recorded demo
 * calls nobody can be checked by reading the library alone (ADR-043).
 *
 * What the page says about the recordings, in words: they are the recording of a real run, they are
 * not reproducible byte for byte the way the recordings of the sandbox are, and the verdicts of the
 * claims were computed by the deterministic verifier of the repository, so that anybody can re-verify
 * them offline with the code of the repository and no model.
 */

import Link from "next/link";

import { Badge } from "@/components/ui/Badge";
import { buttonClasses } from "@/components/ui/Button";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { ScenarioCatalogProvider, useScenarioCatalog } from "@/lib/api/provider";
import { scenarioPath } from "@/lib/state/urlState";

/**
 * The page of the catalog of the recordings of a real model.
 *
 * The page is a client component because the artifacts are read in the browser: the site is a
 * static export and the files of the recording are served next to it.
 */
export default function ReplayRealPage() {
  return (
    <ScenarioCatalogProvider catalog="real">
      <ReplayRealCatalog />
    </ScenarioCatalogProvider>
  );
}

/**
 * The catalog of the recordings of a real model, as the provider of the catalog read it.
 *
 * Why the page shows the reason of a refusal and no card: a catalog that does not pass the
 * contract is a catalog a reader cannot trust, and a card of a broken catalog is a card that
 * points to a route that may not exist.
 */
function ReplayRealCatalog() {
  const { scenarios, error, status } = useScenarioCatalog();

  // The catalog is read in the browser, and the reading takes a moment. The placeholder of the
  // reading is on the screen while it lasts, because a title over nothing reads as a broken page.
  const isReading = status === "idle" || status === "loading";

  return (
    <div className="mx-auto flex w-full max-w-content flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge>mode: live_agent</Badge>
          <Badge>capture: real_model_recorded</Badge>
        </div>
        <h1 className="text-3xl font-semibold">Recorded with a real model</h1>
        <p className="max-w-2xl text-text-muted">
          These recordings are the recording of a real run: the agent read the ledger, asked the
          reference source for the exchange rate and wrote its own answer. The site plays them from
          the published artifacts, so it asks no provider and it needs no key.
        </p>
        <p className="max-w-2xl text-text-muted">
          A real run is not a formula: the same question asked twice does not give the same answer,
          so these recordings are not reproducible byte for byte the way the recordings of the
          sandbox are. The verdicts of the claims were computed by the deterministic verifier of the
          repository, the same judge the sandbox catalog uses, so that anybody can re-verify a
          bundle of either catalog offline.
        </p>
        <p className="text-sm text-text-subtle">
          The catalog of the recordings of the scripted model is here:{" "}
          <Link className={buttonClasses("ghost", "sm")} href="/replay">
            Open the sandbox catalog
          </Link>
        </p>
      </header>

      {error ? (
        <div role="alert" className="rounded-lg border border-danger/40 bg-danger-light p-4">
          <p className="text-sm text-danger-dark">{error}</p>
        </div>
      ) : null}

      {isReading ? (
        <section className="flex flex-col gap-4" aria-label="The scenarios being read">
          <Skeleton className="h-6 w-48" label="The catalog of the scenarios is being read" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </section>
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
                        href={scenarioPath(scenario.id, "real")}
                      >
                        {scenario.id} - {scenario.name}
                      </Link>
                      {scenario.data_origin ? (
                        <span className="text-xs text-text-subtle">data: {scenario.data_origin}</span>
                      ) : null}
                      {scenario.status ? <Badge>{scenario.status}</Badge> : null}
                    </div>
                    {/*
                      The concepts of the scenario are part of what the catalog publishes (FR-003),
                      and a card that throws them away hides what the scenario demonstrates. They are
                      words and not a tint, so a reader that does not see the badge reads the concept
                      all the same.
                    */}
                    {scenario.concepts && scenario.concepts.length > 0 ? (
                      <div className="mt-3 flex flex-wrap items-center gap-2">
                        <span className="text-xs text-text-subtle">concepts:</span>
                        {scenario.concepts.map((concept) => (
                          <Badge key={concept}>{concept}</Badge>
                        ))}
                      </div>
                    ) : null}
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
