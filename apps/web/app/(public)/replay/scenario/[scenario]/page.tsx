/**
 * The route of a scenario of the recorded demo.
 *
 * Why this file exists: a scenario of the catalog is a place of the site, and a place has an
 * address. The route is `/replay/scenario/<id>`, with the identifier of the scenario in the path
 * and nothing else in the path, because the path is what a visitor can share and a query string
 * of a visitor is never a thing the site keeps (FR-004, ADR-043).
 *
 * Why the route is a server component: the site is a static export, and a static export of a
 * dynamic route needs the list of the parameters at build time. The page reads the catalog of the
 * site from the disk while the export is built, and it hands the card of the scenario to the
 * reader. An identifier that the catalog does not publish is the page of 404, never a guess at run
 * time.
 */

import { readFileSync } from "node:fs";
import path from "node:path";

import Link from "next/link";
import { notFound } from "next/navigation";

import { buttonClasses } from "@/components/ui/Button";
import { ReplayProvider } from "@/features/replay/ReplayProvider";
import { ReplayViewer } from "@/features/replay/ReplayViewer";
import type { ScenarioIndexEntry } from "@/lib/api/schemas";
import { validateScenarioIndex } from "@/lib/replay/validate";


/**
 * The catalog of the scenarios, as the build copies it into the site.
 *
 * Why the path is fixed: the artifacts of the site are copied into `public/replay` before the
 * build, and the page reads the very file the site serves (ADR-042).
 */
const CATALOG_PATH = path.join(process.cwd(), "public", "replay", "index.json");

/**
 * Reads the catalog of the scenarios from the disk.
 *
 * Why the catalog is validated here and not read as it is: the page hands the card of the
 * scenario to the reader, and a card that does not pass the contract of the published artifacts
 * is a card the reader cannot trust. A catalog that cannot be read at build time produces no
 * route at all, and the site then has no route for a scenario it never published.
 */
function readCatalog(): ScenarioIndexEntry[] {
  let raw: string;
  try {
    raw = readFileSync(CATALOG_PATH, "utf8");
  } catch {
    return [];
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return [];
  }

  const catalog = validateScenarioIndex(parsed);
  return catalog.ok ? catalog.value : [];
}

/**
 * The list of the scenarios the export holds a page for.
 *
 * Why the list is read from the disk: the export writes one HTML file per published scenario, so
 * the build has to know the identifiers before it writes them.
 */
export function generateStaticParams(): Array<{ scenario: string }> {
  return readCatalog().map((entry) => ({ scenario: entry.id }));
}

/**
 * Why no scenario is invented at run time.
 *
 * The export holds one page per published scenario, and an identifier that the catalog does not
 * publish is the page of 404. A route that guessed would show a run that was never recorded.
 */
export const dynamicParams = false;

/** The props of the route of a scenario. */
interface ReplayScenarioPageProps {
  /** The identifier of the scenario, as it is in the path. */
  readonly params: Promise<{ scenario: string }>;
}

/**
 * The route of a scenario of the recorded demo.
 *
 * The page reads the card of the scenario from the same file the export serves, and it hands it
 * to the provider of the replay, which reads the bundle of the scenario and hands the recording
 * to the reader.
 */
export default async function ReplayScenarioPage({ params }: ReplayScenarioPageProps) {
  const { scenario } = await params;
  const card = readCatalog().find((entry) => entry.id === scenario);

  if (!card) {
    notFound();
  }

  return (
    <div className="mx-auto flex w-full max-w-content flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-3">
        <h1 className="text-3xl font-semibold">Recorded demo</h1>
        <p className="max-w-2xl text-text-muted">
          The demo reads the published artifacts of a capture, played in the browser. It asks no
          provider, it needs no key and no network, and it runs the same way for every visitor.
        </p>
        <p className="text-sm text-text-subtle">
          <Link className={buttonClasses("ghost", "sm")} href="/replay">
            All the scenarios
          </Link>
        </p>
      </header>

      <section className="flex flex-col gap-4">
        <h2 className="text-lg font-semibold">
          {card.id} - {card.question}
        </h2>
        <ReplayProvider scenario={card}>
          <ReplayViewer scenario={card} />
        </ReplayProvider>
      </section>
    </div>
  );
}
