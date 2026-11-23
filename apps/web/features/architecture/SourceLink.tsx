/**
 * The link to one module of the repository.
 *
 * Why this file exists: the tour of the architecture links every subsystem to the exact module it
 * is written in, and the link has to be spelled one way only (ADR-046). A path written in three
 * places is three paths that can drift, and a link that points at a file that does not exist is a
 * link that lies.
 *
 * Why the link is built by the library of the repository: the base of the links and the commit live
 * in `apps/web/lib/repository.ts`, and this component only decides what the visitor reads.
 */

import type { ReactElement } from "react";

import { sourceUrlOf } from "@/lib/repository";

/**
 * The props of the link to a module.
 *
 * Why the commit is a prop: the commit belongs to the build, and a commit written by hand in the
 * source is a constant that a release has to remember to update (ADR-046).
 */
export interface SourceLinkProps {
  /** The path of the module, from the root of the repository. */
  readonly path: string;
  /** The commit of the checkout the link opens. */
  readonly commit: string;
  /** The class of the anchor, when the caller wants one. */
  readonly className?: string;
  /** The text of the link, when the caller wants another text than the path. */
  readonly children?: ReactElement | string;
}

/**
 * The link to one module of the repository.
 *
 * The visitor reads the path of the module, because the path is the thing he can find in his own
 * checkout, and it is what tells him which file of the repository he is about to open.
 */
export function SourceLink({
  path,
  commit,
  className,
  children,
}: SourceLinkProps): ReactElement {
  return (
    <a
      className={className ?? "underline"}
      href={sourceUrlOf(path, commit)}
      rel="noreferrer"
      target="_blank"
      title="The module in the repository"
    >
      {children ?? path}
    </a>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the link at once. */
export const __all__ = ["SourceLinkProps", "SourceLink"] as const;
