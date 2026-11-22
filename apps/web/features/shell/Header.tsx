/**
 * The header of the shell.
 *
 * Why this file exists: every page of the site needs the same answer to the same question, which
 * question is on the screen, and the header is where that answer sits. It carries the name of the
 * site and the indicator of the mode, and nothing else, so a header never competes with the
 * content of the page for the attention of the reader.
 *
 * Why the raw mode of the artifact is not here: the raw mode belongs to the panel of the run,
 * which is where the artifact is read (ADR-043). The header carries the label, and the label of a
 * recorded bundle never says live.
 */

import Link from "next/link";
import type { ReactElement } from "react";

import type { TraceMode } from "@/lib/api/schemas";

import { ModeIndicator } from "./ModeIndicator";

/**
 * The props of the header.
 *
 * Why the mode is optional: a page that shows no recording has no mode to announce.
 */
export interface HeaderProps {
  /** The mode of what the page shows. */
  readonly mode?: TraceMode | null;
}

/**
 * The header of the shell.
 *
 * The header is the landmark of the banner of the page, so a screen reader can jump to it and
 * back to the content.
 *
 * Why the banner carries a name: a reader who jumps between the landmarks of a page hears the
 * name of the banner as "banner" when it has none, and a name that says which site it is tells
 * the reader that the jump reached the right page.
 */
export function Header(props: HeaderProps): ReactElement {
  return (
    <header aria-label="LedgerLens" className="border-b border-line bg-surface">
      <div className="mx-auto flex w-full max-w-content flex-wrap items-center justify-between gap-3 px-6 py-4">
        <Link href="/" className="text-base font-semibold text-foreground">
          LedgerLens
        </Link>
        <ModeIndicator mode={props.mode ?? null} />
      </div>
    </header>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the header at once. */
export const __all__ = ["HeaderProps", "Header"] as const;
