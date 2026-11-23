/**
 * The indicator of the mode of the site.
 *
 * Why this file exists: the site shows two kinds of investigation, one that plays a recording and
 * one that talks to a provider, and a visitor has to know which one is on the screen before they
 * read a word of it. The indicator says so, and it says it with the label of the mode.
 *
 * Why the label never says live for a recording: the site publishes only the deterministic
 * sandbox, and a recorded run is never presented as a live one (ADR-043). The raw mode of the
 * artifact stays visible in the panel of the run, where it belongs.
 */

import type { ReactElement } from "react";

import { Badge } from "@/components/ui/Badge";
import type { TraceMode } from "@/lib/api/schemas";
import { modeLabel } from "@/lib/replay/provenance";

/**
 * The props of the indicator of the mode.
 *
 * Why the mode can be missing: a page that does not show a recording has no mode to announce, and
 * the indicator then says nothing at all rather than guessing one.
 */
export interface ModeIndicatorProps {
  /** The mode of what is shown. */
  readonly mode: TraceMode | null | undefined;
}

/**
 * The indicator of the mode of the site.
 *
 * The indicator carries the label of the mode, and it carries nothing else, so a recorded bundle
 * is never announced as a live one.
 */
export function ModeIndicator(props: ModeIndicatorProps): ReactElement {
  const mode = props.mode;

  if (!mode) {
    return <></>;
  }

  return (
    <Badge tone="accent" className="tracking-wide">
      {modeLabel(mode)}
    </Badge>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the indicator at once. */
export const __all__ = ["ModeIndicatorProps", "ModeIndicator"] as const;
