/**
 * The skip link of the shell.
 *
 * Why this file exists: the first thing a keyboard user meets on a page is the header, and a
 * header with several buttons can take a long time to walk past. The skip link is the first thing
 * in the tab order of the page, and it jumps straight to the content.
 *
 * Why the link stays out of the way until it is focused: the stylesheet of the site moves it out
 * of the screen until the keyboard reaches it, so it never covers the content of a page for a
 * visitor who reads with the mouse.
 */

import type { ReactElement } from "react";

/**
 * The props of the skip link.
 *
 * Why the target is optional: the content of the page lives under the identifier `main` in every
 * page of the site, so the common case needs no argument.
 */
export interface SkipLinkProps {
  /** The identifier of the element the link jumps to. */
  readonly target?: string;
}

/**
 * The skip link of the shell.
 *
 * The link is the first element of the page, so the keyboard reaches it before anything else.
 */
export function SkipLink(props: SkipLinkProps): ReactElement {
  return (
    <a className="ll-skip-link" href={props.target ?? "#main"}>
      Skip to the main content
    </a>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the link at once. */
export const __all__ = ["SkipLinkProps", "SkipLink"] as const;
