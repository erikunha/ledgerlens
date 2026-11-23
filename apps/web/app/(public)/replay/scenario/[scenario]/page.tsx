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

import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

/**
 * The words of the disclosure of the AI agent, read from the domain of the product.
 *
 * Why this page carries the sentence: the recording shows the answer of an AI agent to a person,
 * and a person who reads it has to know that the answer was produced by a model and not by a
 * person (Article 50 of the EU AI Act, applied since 2 August 2026). The words come from the file
 * of the domain, so the demo application and this site cannot say different things.
 */
import aiDisclosure from "../../../../../../../ledgerlens/prompts/ai_disclosure.json";

import { buttonClasses } from "@/components/ui/Button";
import { ReplayProvider } from "@/features/replay/ReplayProvider";
import { ReplayViewer } from "@/features/replay/ReplayViewer";
import { readRepositoryMeta } from "@/lib/repository";
import { readPublishedCatalog } from "@/lib/replay/catalog";

/**
 * The list of the scenarios the export holds a page for.
 *
 * Why the list is read from the disk: the export writes one HTML file per published scenario, so the build has to
 * know the identifiers before it writes them.
 *
 * Why the reader is a module of its own: the catalog is the file the site serves, and the reader that finds it knows
 * both places where it can be, the copy the build makes and the source the repository publishes, and it refuses a
 * catalog that does not pass the contract of the published artifacts (ADR-042, ADR-043).
 */
export function generateStaticParams(): Array<{ scenario: string }> {
  return readPublishedCatalog().map((entry) => ({ scenario: entry.id }));
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
 * The metadata of the route of a scenario.
 *
 * Why the route carries a title and a description of its own: a scenario is a place of the site, and every place has a
 * name that the browser, the search engine and the tab of the reader show. The name is the identifier of the scenario
 * and the question of the catalog, because that is what the page is about.
 *
 * Why the description says what the page does: the description is what a visitor reads before the page opens, so it has
 * to promise only what the page keeps. The page reads the published artifacts of a capture, it asks no provider and it
 * needs no key and no network, and that is exactly what the description says.
 *
 * Why an identifier the catalog does not publish still gets a title: the metadata of a route is read before the page
 * decides that the scenario does not exist, so the route has to answer with words instead of with nothing.
 */
export async function generateMetadata({ params }: ReplayScenarioPageProps): Promise<Metadata> {
  const { scenario } = await params;
  const card = readPublishedCatalog().find((entry) => entry.id === scenario);

  if (!card) {
    return {
      title: "Scenario not found",
      description: `This site publishes no scenario with the identifier ${scenario}.`,
    };
  }

  return {
    title: `${card.id}: ${card.question}`,
    description: `The published recording of the scenario ${card.id}, played in the browser: it reads the published artifacts of the capture, it asks no provider, and it needs no key and no network.`,
  };
}

/**
 * The route of a scenario of the recorded demo.
 *
 * The page reads the card of the scenario from the same file the export serves, and it hands it
 * to the provider of the replay, which reads the bundle of the scenario and hands the recording
 * to the reader.
 *
 * Why the route reads the commit of the checkout: the reader opens the engineering drawer, and
 * the links of the drawer open the tree of that commit, so the drawer never points at a tree that
 * the site did not describe. The commit is read while the export is built, and the route asks for
 * nothing at run time (ADR-046).
 */
export default async function ReplayScenarioPage({ params }: ReplayScenarioPageProps) {
  const { scenario } = await params;
  const card = readPublishedCatalog().find((entry) => entry.id === scenario);

  if (!card) {
    notFound();
  }

  const meta = readRepositoryMeta();

  return (
    <div className="mx-auto flex w-full max-w-content flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-3">
        <h1 className="text-3xl font-semibold">Recorded demo</h1>
        <p className="max-w-2xl text-text-muted">{aiDisclosure.sentence}</p>
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
          <ReplayViewer scenario={card} commit={meta.commit} />
        </ReplayProvider>
      </section>
    </div>
  );
}
