"use client";

/**
 * The shell of the public site.
 *
 * Why this file exists: the landmarks of a page, the header, the skip link and the column of the
 * content are the same on every page of the site, and a page that writes them for itself writes
 * them differently every time. The shell owns them, and the layout of the site renders the shell.
 *
 * Why the shell is thin: the layout of the content belongs to the page, because the catalog, the
 * reader of a recording and the live mode do not look the same. The shell only guarantees that
 * the page has a banner, a main region, a footer and a way to skip the banner.
 *
 * Why the shell is a client component: the skip link has to move the focus to the main, and a
 * browser does not do that on its own. Chromium moves the focus to a fragment target that can
 * take the focus, and WebKit does not, so the shell listens to the hash of the location and gives
 * the focus to the main itself (FR-031, SC-014).
 */

import Link from "next/link";
import { useEffect, useRef } from "react";
import type { ReactElement, ReactNode } from "react";

import type { TraceMode } from "@/lib/api/schemas";

import { Header } from "./Header";
import { SkipLink } from "./SkipLink";

/**
 * The props of the shell.
 *
 * Why the mode is optional: the mode is the mode of the page that is being shown, and a page
 * that shows no recording has none.
 */
export interface AppShellProps {
  /** The content of the page. */
  readonly children: ReactNode;
  /** The mode of what the page shows. */
  readonly mode?: TraceMode | null;
}

/**
 * The shell of the public site.
 *
 * The skip link comes first, so the keyboard reaches it before the header, and the main region
 * carries the identifier `main`, which is where the skip link jumps to. The main takes the focus
 * when the hash of the location changes to it, so the visitor lands on the content and not on the
 * header again.
 *
 * The footer is the landmark of the content information of the page. It says what the site
 * publishes and what it does not do, because a site that shows the artifacts of a recorded run
 * and nothing else has to say so.
 */
export function AppShell(props: AppShellProps): ReactElement {
  const mainRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const focusMain = (): void => {
      if (window.location.hash !== "#main") {
        return;
      }
      mainRef.current?.focus();
    };

    // the hash changes when the skip link is activated, and the focus follows the jump
    window.addEventListener("hashchange", focusMain);
    focusMain();

    return () => {
      window.removeEventListener("hashchange", focusMain);
    };
  }, []);

  return (
    <div className="flex min-h-screen flex-col">
      <SkipLink />
      <Header mode={props.mode ?? null} />
      <main id="main" ref={mainRef} tabIndex={-1} className="flex-1">
        {props.children}
      </main>
      <footer className="border-t border-line bg-surface">
        <div className="mx-auto flex w-full max-w-content flex-wrap items-center justify-between gap-3 px-6 py-4">
          <p className="text-sm text-text-subtle">
            LedgerLens publishes the artifacts of a recorded run and nothing else. It asks no
            provider, it needs no key and it calls nobody.
          </p>
          <Link
            href="/replay"
            className="text-sm font-medium text-foreground underline underline-offset-2 hover:text-text-muted"
          >
            The catalog of the scenarios
          </Link>
        </div>
      </footer>
    </div>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the shell at once. */
export const __all__ = ["AppShellProps", "AppShell"] as const;
