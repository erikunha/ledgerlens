"use client";

/**
 * The boundary of the root of the site.
 *
 * Why this file exists: the boundary of the segments lives inside the shell of the site, so an
 * exception thrown by the shell itself, by the header or by the root layout, would leave the
 * visitor in front of the default page of error of the framework. The boundary of the root catches
 * that last exception and shows the failure state of the site, in the words of the site
 * (ADR-043).
 *
 * Why the boundary draws its own document: the framework replaces the root layout when it shows
 * the boundary of the root, and the root layout is the owner of the tags of the document. The
 * boundary therefore writes the tags itself, with the language of the site, and it carries the
 * stylesheet of the site, because the root layout that carried it is gone.
 *
 * Why the failure state of the site is the one of the segments: the site has one look of failure,
 * and a visitor who sees two of them cannot tell that they are the same thing.
 */

import Link from "next/link";
import type { ReactElement } from "react";

import { Button, buttonClasses } from "@/components/ui/Button";

import { SiteFailure } from "./error";

import "./globals.css";

/**
 * The props of the boundary of the root, as the framework of Next.js hands them over.
 *
 * Why the error carries the digest: the framework adds it to the error of a server component, and
 * the type of the props has to say so, even though the boundary never shows it to the visitor.
 */
export interface SiteGlobalErrorProps {
  /** The error that was thrown. The boundary never shows it to the visitor. */
  readonly error: Error & { digest?: string };
  /** The reset that draws the site again. */
  readonly reset: () => void;
}

/**
 * The boundary of the root of the site.
 *
 * The boundary shows the failure state of the site with the actions of the visitor: the reset
 * draws the site again, and the catalog of the scenarios is one click away.
 */
export default function SiteGlobalError({ reset }: SiteGlobalErrorProps): ReactElement {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background text-foreground">
        <div className="mx-auto flex w-full max-w-content flex-col gap-8 px-6 py-12">
          <SiteFailure
            title="The page could not be shown"
            reason="The site hit a failure it did not expect while it drew this page."
            hint="Nothing of the recorded run is shown, because a reader cannot tell which parts of a half drawn run are true."
          >
            <Button variant="secondary" size="sm" onClick={() => reset()}>
              Try again
            </Button>
            <Link className={buttonClasses("ghost", "sm")} href="/replay">
              The catalog of the scenarios
            </Link>
          </SiteFailure>
        </div>
      </body>
    </html>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the boundary at once. */
export const __all__ = ["SiteGlobalErrorProps"] as const;
