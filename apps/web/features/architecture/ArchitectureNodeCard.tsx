/**
 * The card of one node of the architecture of the recorded demo.
 *
 * Why this file exists: the tour of the architecture shows the same node in more than one place,
 * the picture, the list of the fallback and the drawer that opens with the node the visitor chose.
 * A visitor who reads the same subsystem twice must read the same sentence twice, and the only
 * way to guarantee that is one array that holds the words of the node and one component that
 * renders it (ADR-046).
 *
 * Why the card writes no sentence of its own: every word it shows comes from the node, and a
 * sentence written here would be a second source that drifts from the first one.
 *
 * Why the level of the title is a prop: the card sits under the h2 of a section of the page in
 * the list of the fallback and inside the drawer of the tour, and only the caller knows where the
 * card sits in the outline of the document. The rule of the repository is that the outline of the
 * headings never skips a level.
 *
 * Why the chosen node carries a mark that is not a tint: a reader with low vision and a reader in
 * the forced colours mode of the system do not see a tint of the background, so the chosen node
 * carries a word that says it is the chosen one and the attribute that says it to a reader of a
 * screen reader.
 */

import type { ReactElement } from "react";

import { CardSection, type CardTitleLevel } from "@/components/ui/Card";
import { AdrLink } from "@/features/architecture/AdrLink";
import type { ArchitectureNode } from "@/features/architecture/nodes";
import { SourceLink } from "@/features/architecture/SourceLink";

/**
 * The props of the card of one node.
 *
 * Why the card takes the commit and not the links: the commit is read once at build time and it
 * belongs to the build, and the builder of the URLs lives in the library of the repository, so a
 * link of the card, a link of the picture and a link of the drawer cannot be spelled two ways.
 */
export interface ArchitectureNodeCardProps {
  /** The node the card shows. */
  readonly node: ArchitectureNode;
  /** The commit of the checkout the links open. */
  readonly commit: string;
  /** The level of the heading of the title of the card. */
  readonly titleLevel?: CardTitleLevel;
  /** Whether this node is the node the visitor chose. */
  readonly selected?: boolean;
}

/**
 * The links of a node: the module it is written in and the records that explain why it exists.
 *
 * Why the links are built here and not in the caller: the module and the records are the two
 * things a node must always be able to reach, and the builder of the URLs is the library of the
 * repository, so every place that shows a node shows the same destinations.
 */
function NodeLinks({
  node,
  commit,
}: {
  readonly node: ArchitectureNode;
  readonly commit: string;
}): ReactElement {
  return (
    <ul className="flex flex-col gap-1 text-sm">
      <li>
        <SourceLink path={node.module} commit={commit} />
      </li>
      {node.records.map((record) => (
        <li key={`${record.number}-${record.path}`}>
          <AdrLink record={record} commit={commit} />
        </li>
      ))}
    </ul>
  );
}

/**
 * The card of one node of the architecture.
 *
 * The card shows the name of the subsystem, the sentence that explains it, the module it is
 * written in and the records that justify it. Every one of those words comes from the node.
 */
export function ArchitectureNodeCard({
  node,
  commit,
  titleLevel = "h3",
  selected = false,
}: ArchitectureNodeCardProps): ReactElement {
  return (
    <section
      aria-current={selected ? "true" : undefined}
      aria-label={node.label}
      data-architecture-card={node.id}
    >
      <CardSection title={node.label} description={node.summary} titleLevel={titleLevel}>
        {/*
          The mark of the chosen node is a word and not a colour: a tint of the background is
          invisible in the forced colours mode of the system, and the state of the visit has to
          survive that mode.
        */}
        {selected ? <p className="mb-2 text-xs font-semibold">The chosen node</p> : null}
        <NodeLinks node={node} commit={commit} />
      </CardSection>
    </section>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the card at once. */
export const __all__ = ["ArchitectureNodeCardProps", "ArchitectureNodeCard"] as const;
