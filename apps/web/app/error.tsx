"use client";

/**
 * The boundary of the segments of the site.
 *
 * Why this file exists: an exception thrown while the site draws a page leaves the visitor in
 * front of the default page of error of the framework, outside the shell of the site, without the
 * landmarks of the site and without its words. The boundary catches the exception and shows the
 * failure state of the site, in the look and in the language of the site (ADR-043).
 *
 * Why the boundary is a client component: the framework of Next.js hands the error and the reset
 * to a client component, and the reset is a function that only the browser can call.
 *
 * Why the boundary never shows the error itself: the message of an error of production carries the
 * digest of the server and the message of an error of development carries the name of an internal
 * module. The visitor is told that the page failed and what to do next, and nothing else.
 *
 * Why the failure state lives here and not in the folder of the features: the state of a failure
 * of the site is shown by the three boundaries of the site, and the folder of the features holds
 * the state of a refusal of the recording, which is a different failure with a different wording.
 * The look of the two is the same, so the site has one look of failure and not two.
 */

import Link from "next/link";
import type { ReactElement, ReactNode } from "react";

import { Button, buttonClasses } from "@/components/ui/Button";

/**
 * The props of the failure state of the site.
 *
 * Why the title and the reason are two fields: the title names the failure and the reason says
 * what happened, and a visitor reads the two in that order.
 *
 * Why the actions are children and not a field: the boundary of a segment offers a reset and the
 * page of 404 does not, and the caller of the state knows which actions it offers.
 */
export interface SiteFailureProps {
  /** The title of the failure. */
  readonly title: string;
  /** The reason the visitor reads. */
  readonly reason: string;
  /** The line that tells the visitor what the site does next. */
  readonly hint?: string;
  /** The actions the visitor can take. */
  readonly children?: ReactNode;
}

/**
 * The failure state of the site.
 *
 * The state is the panel of the site: the same border, the same colours and the same type scale
 * as the failure state of a refused recording, so a visitor sees one look of failure. The panel
 * is an alert, so a screen reader reads it when it appears.
 */
export function SiteFailure({ title, reason, hint, children }: SiteFailureProps): ReactElement {
  return (
    <div role="alert" className="rounded-lg border border-danger/40 bg-danger-light p-4">
      <h1 className="text-base font-semibold text-danger-dark">{title}</h1>
      <p className="text-sm text-danger-dark">{reason}</p>
      {hint ? <p className="mt-2 text-sm text-text-muted">{hint}</p> : null}
      {children ? <div className="mt-3 flex flex-wrap items-center gap-2">{children}</div> : null}
    </div>
  );
}

/**
 * The props of the boundary of the site, as the framework of Next.js hands them over.
 *
 * Why the error carries the digest: the framework adds it to the error of a server component, and
 * the type of the props has to say so, even though the boundary never shows it to the visitor.
 */
export interface SiteErrorBoundaryProps {
  /** The error that was thrown. The boundary never shows it to the visitor. */
  readonly error: Error & { digest?: string };
  /** The reset that draws the segment of the site again. */
  readonly reset: () => void;
}

/**
 * The boundary of the segments of the site.
 *
 * The boundary replaces the page that failed and shows the failure state of the site. The visitor
 * can draw the page again with the reset, and the catalog of the scenarios is always one click
 * away, because the recorded demo needs no key and no network.
 */
export default function SiteErrorBoundary({ reset }: SiteErrorBoundaryProps): ReactElement {
  return (
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
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the boundary at once. */
export const __all__ = ["SiteFailureProps", "SiteFailure", "SiteErrorBoundaryProps"] as const;
