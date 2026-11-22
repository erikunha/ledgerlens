/**
 * One piece of evidence of the answer.
 *
 * Why this file exists: a claim of the answer is only as good as the source behind it, so the
 * reader has to be able to see the identifier of the source, the tool that produced it, the
 * reference of its origin and the content the tool returned (ADR-043).
 *
 * Why the card shows what the recording carried and nothing else: the published recording of the
 * scenario carries the evidence inside the outputs of the tools, and a source the recording does
 * not carry is shown as not available, never as a piece of text the interface invented.
 */

import type { ReactElement } from "react";

import { Badge } from "@/components/ui/Badge";
import type { EvidenceSummary } from "@/lib/replay/selectors";


/**
 * The props of the card of one piece of evidence.
 *
 * Why the card takes the summary and not the raw output: the summary is what the library of the
 * projections read, and the card only shows it.
 */
export interface EvidenceCardProps {
  /** The evidence, as the outputs of the tools reported it. */
  readonly evidence: EvidenceSummary;
}

/** What the card shows when the recording carries nothing to show. */
const NOT_AVAILABLE = "Not available";

/**
 * One piece of evidence of the answer.
 *
 * The content of the source is shown as it was published, in a pane that scrolls sideways on its
 * own, so that a long statement never makes the page scroll sideways.
 */
export function EvidenceCard({ evidence }: EvidenceCardProps): ReactElement {
  return (
    <article className="flex flex-col gap-2 rounded-lg border border-line bg-surface p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-xs text-foreground">{evidence.evidenceId}</span>
        <Badge>{evidence.tool}</Badge>
      </div>

      <dl className="flex flex-col gap-2">
        <div className="flex flex-col gap-1">
          <dt className="text-xs font-medium text-text-subtle">Origin of the source</dt>
          <dd className="break-all font-mono text-xs text-foreground">
            {evidence.ref ?? NOT_AVAILABLE}
          </dd>
        </div>
        <div className="flex flex-col gap-1">
          <dt className="text-xs font-medium text-text-subtle">Content of the source</dt>
          <dd className="ll-code-pane rounded border border-line bg-background p-2 font-mono text-xs text-foreground">
            {evidence.content ?? NOT_AVAILABLE}
          </dd>
        </div>
      </dl>
    </article>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the card at once. */
export const __all__ = ["EvidenceCardProps", "EvidenceCard"] as const;
