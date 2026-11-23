/**
 * The link to one record of a decision.
 *
 * Why this file exists: the tour of the architecture links every subsystem to the record that
 * explains why it exists, and the link has to be spelled one way only (ADR-046). A record written
 * in three places is three records that can drift, and a link that points at a file that does not
 * exist is a link that lies.
 *
 * Why the link is built by the library of the repository: the base of the links and the commit live
 * in `apps/web/lib/repository.ts`, and this component only decides what the visitor reads.
 */

import type { ReactElement } from "react";

import type { ArchitectureRecord } from "@/features/architecture/nodes";
import { recordUrlOf } from "@/lib/repository";

/**
 * The props of the link to a record.
 *
 * Why the commit is a prop: the commit belongs to the build, and a commit written by hand in the
 * source is a constant that a release has to remember to update (ADR-046).
 */
export interface AdrLinkProps {
  /** The record the link opens. */
  readonly record: ArchitectureRecord;
  /** The commit of the checkout the link opens. */
  readonly commit: string;
  /** The class of the anchor, when the caller wants one. */
  readonly className?: string;
}

/**
 * The link to one record of a decision.
 *
 * The visitor reads the number and the title of the record, because a link that shows only a
 * number says nothing to a visitor who does not know what ADR-007 is.
 */
export function AdrLink({ record, commit, className }: AdrLinkProps): ReactElement {
  return (
    <a
      className={className ?? "underline"}
      href={recordUrlOf(record.path, commit)}
      rel="noreferrer"
      target="_blank"
      title={record.title}
    >
      {record.number} {record.title}
    </a>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the link at once. */
export const __all__ = ["AdrLinkProps", "AdrLink"] as const;
