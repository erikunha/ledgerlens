/**
 * The route of the tour of the architecture.
 *
 * Why this file exists: the tour of the architecture is a page of the site and not a section of
 * the replay, because the tour is about the repository and the repository does not change while
 * a recording plays. The URL of the page is `/engineering`, and the path of the page carries
 * nothing but itself: no key, no account, no login, no cookie and no query string (ADR-046).
 *
 * Why the route is a server component: the site is a static export, and the page reads the
 * content of the tour at build time. The commit of the checkout is read while the export is
 * built, with `readRepositoryMeta`, and the links of the page open the tree of that commit, so a
 * link keeps opening the file that the sentence of the node was written for. The page makes no
 * request of its own at run time and it calls nobody.
 *
 * Why the page shows the commit in its footer: a reader that follows a link and sees a file has
 * to know which tree the sentence was written for, and the commit in full is that answer. When
 * the tree carried changes that were not committed, the footer says so out loud, because a page
 * that describes a tree it does not match is a page that lies.
 *
 * Why the state of the visit lives in the tour and not in the path: the node the visitor chose is
 * a choice of the visitor and not a place of the site, and the path is what a visitor shares.
 * The tour holds the choice in the memory of the browser (ADR-046).
 */

import type { Metadata } from "next";
import type { ReactElement } from "react";

import { EngineeringTour } from "@/features/architecture/EngineeringDrawer";
import { readRepositoryMeta } from "@/lib/repository";

/**
 * The metadata of the route of the tour.
 *
 * Why the route carries a title and a description of its own: the tour is a place of the site,
 * and every place has a name that the browser, the search engine and the tab of the reader
 * show. The name says what the page is about, and the description promises only what the page
 * keeps: the page reads its content while the site is built and it asks no provider, no key and
 * no network.
 */
export function generateMetadata(): Metadata {
  return {
    title: "The architecture of the recorded demo",
    description:
      "The tour of the architecture of LedgerLens: the subsystems of the recorded demo, the module of each one in the repository and the record that explains why it exists. The page reads its content while the site is built and it calls nobody.",
  };
}

/**
 * The route of the tour of the architecture.
 *
 * The page reads the commit of the checkout while the export is built and hands it to the tour,
 * which draws the picture with its list, the nodes that open the engineering drawer and the
 * drawer itself.
 */
export default function EngineeringPage(): ReactElement {
  const meta = readRepositoryMeta();

  return (
    <div className="mx-auto flex w-full max-w-content flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-3">
        <h1 className="text-3xl font-semibold">The architecture of the recorded demo</h1>
        <p className="max-w-2xl text-text-muted">
          The tour of the subsystems of LedgerLens: the module of each one in the repository and the
          record that explains why it exists. The page reads its content while the site is built, it
          asks no provider and it calls nobody.
        </p>
      </header>

      <EngineeringTour commit={meta.commit} />

      <footer className="flex flex-col gap-2 border-t border-line pt-4">
        <p className="text-sm text-text-muted">
          This page describes the commit{" "}
          <span className="font-mono text-foreground">{meta.commit}</span> of the repository.
        </p>
        {meta.dirty ? (
          <p className="text-sm text-text-muted">
            The site was built from a working tree with changes that are not committed, so a file of
            this commit may differ from the file of the link.
          </p>
        ) : null}
      </footer>
    </div>
  );
}
