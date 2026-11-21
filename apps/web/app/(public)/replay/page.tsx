"use client";

/**
 * The recorded demo, the page that plays the published artifacts.
 *
 * Why this file exists: the recorded demo is the half of the demo that works with no key and no
 * network. The page reads the catalog of the scenarios from the static export of the site and then
 * reads the bundle of the scenario the visitor picked, and it makes no request to the backend of
 * the demo at all: no provider, no exchange rate service and no write endpoint.
 *
 * The mode of what is shown is a property of what is shown: the reader shows the mode of the
 * manifest it read, and a recorded run is never presented as a live one (ADR-040).
 *
 * The catalog is read with the validator of the repository and with no mapping by hand, because
 * the catalog the repository publishes is a list of cards that carry `id` and a `data_origin` that
 * is a string. The artifacts of the site are the ones the repository publishes (ADR-042).
 */

import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button, buttonClasses } from "@/components/ui/Button";
import { CardSection } from "@/components/ui/Card";
import { ReplayViewer } from "@/features/replay/ReplayViewer";
import type { ScenarioIndexEntry } from "@/lib/api/schemas";
import { validateScenarioIndex } from "@/lib/replay/validate";

/**
 * The catalog of the scenarios, as the static export of the site publishes it.
 *
 * Why the path is fixed: the artifacts are part of the export, under `public/replay`, and the site
 * is served from the root of that export.
 */
const CATALOG_URL = "/replay/index.json";

/**
 * The page of the recorded demo.
 *
 * The page is a client component because the artifacts are read in the browser: the site is a
 * static export and the files of the recording are served next to it.
 */
export default function ReplayPage() {
  const [scenarios, setScenarios] = useState<ScenarioIndexEntry[]>([]);
  const [selected, setSelected] = useState<ScenarioIndexEntry | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;

    async function load(): Promise<void> {
      try {
        const response = await fetch(CATALOG_URL);
        if (!response.ok) {
          throw new Error(`the site answered ${response.status}`);
        }
        const catalog = validateScenarioIndex(JSON.parse(await response.text()));
        if (!alive) {
          return;
        }
        if (!catalog.ok) {
          setError(
            `The catalog of the scenarios did not pass the contract of the published artifacts: ${catalog.reasons.join("; ")}`,
          );
          return;
        }
        setScenarios(catalog.value);
        setSelected(catalog.value[0] ?? null);
        setError(null);
      } catch {
        if (!alive) {
          return;
        }
        setError("The catalog of the scenarios could not be read from the site.");
      }
    }

    void load();
    return () => {
      alive = false;
    };
  }, []);

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
        <CardSection title="The scenarios" description="The cases the site published.">
          <ul className="flex flex-col gap-2">
            {scenarios.map((scenario) => (
              <li key={scenario.id} className="flex flex-wrap items-center gap-2">
                <Button
                  variant={selected?.id === scenario.id ? "primary" : "secondary"}
                  onClick={() => setSelected(scenario)}
                >
                  {scenario.id} - {scenario.name}
                </Button>
                {scenario.data_origin ? (
                  <span className="text-xs text-text-subtle">data: {scenario.data_origin}</span>
                ) : null}
              </li>
            ))}
          </ul>
        </CardSection>
      ) : null}

      {selected ? (
        <section className="flex flex-col gap-4" aria-label="The recorded run">
          <h2 className="text-lg font-semibold">
            {selected.id} - {selected.question}
          </h2>
          <ReplayViewer scenario={selected} />
        </section>
      ) : null}
    </div>
  );
}
