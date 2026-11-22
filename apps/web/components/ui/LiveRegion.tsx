"use client";

import type { ReactElement, ReactNode, Ref } from "react";

import { cn } from "@/lib/design/cn";

/**
 * The polite live region of the design system.
 *
 * Why this file exists: a page that shows a state the visitor cannot see has to announce it, and the markup of that
 * announcement is the same on every page of the site. The markup is a rule of the design system, so it lives here and
 * not in the feature that writes the sentence. The sentence itself belongs to the feature, because the sentence is
 * about the domain and the region is not.
 *
 * Why the region is polite and never assertive: a polite region never interrupts the visitor, and the reader of the
 * site decides when to listen. An assertive region talks over a visitor who is reading the panel they are in, and a
 * region that is a log is a region that is read as a stream of events nobody asked for.
 *
 * Why the region is atomic: the announcement is one sentence, and a reader of a screen reader has to hear it whole.
 *
 * Why the region takes the focus when the page asks for it: the reader of a recording moves the focus to the region
 * once, when the recording starts, so the visitor hears the summary of the state and knows where the focus is. The
 * region is never focused by itself.
 *
 * Why the primitive writes no word: the sentence that is announced is written by the caller, and a primitive that
 * wrote a sentence of its own would say something the recording does not carry.
 */

/** The props of the polite live region. */
export interface LiveRegionProps {
  /** The announcement. It is the whole content of the region. */
  readonly children: ReactNode;
  /** The element that takes the focus when the page asks the region to take it. */
  readonly ref?: Ref<HTMLParagraphElement>;
  /** The class names of the region, when the caller wants other ones than the ones of the design system. */
  readonly className?: string;
}

/**
 * The polite live region of the design system.
 *
 * The region renders exactly one paragraph, with the attributes of a polite region, and it renders the children it is
 * given without adding a word of its own. It never renders a second region, so a page that mounts it twice announces
 * two things for one action.
 */
export function LiveRegion({ children, ref, className }: LiveRegionProps): ReactElement {
  return (
    <p
      ref={ref}
      role="status"
      aria-live="polite"
      aria-atomic="true"
      tabIndex={-1}
      className={cn("text-sm font-medium text-foreground", className)}
    >
      {children}
    </p>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the region at once. */
export const __all__ = ["LiveRegionProps", "LiveRegion"] as const;
