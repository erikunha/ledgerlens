/**
 * The claims of the answer, with the verdict of the verifier about each one.
 *
 * Why this file exists: the answer of a recorded run is a list of claims, and a claim without its
 * verdict and without the note of the verifier is a claim the reader has to take on faith. The
 * list shows the identifier of the claim, the decision, the method that produced it, the note and
 * the evidence the decision cited (ADR-043).
 *
 * Why the text of the claim reads as not available: the published recording of the scenario
 * carries the identifier of the claim, the verdict and the note, and it does not carry the text of
 * the claim. A text of the claim that the interface invented would be a claim the recording never
 * made, so the field says that it is not available and the identifier and the note of the verdict
 * are shown instead.
 */

import type { ReactElement } from "react";

import { Badge } from "@/components/ui/Badge";
import { StatusPill, type StatusPillVerdict } from "@/components/ui/StatusPill";
import { formatVerdict, type StatusLabel } from "@/lib/format/status";
import type { VerdictSummary } from "@/lib/replay/selectors";


/**
 * The props of the list of the claims.
 *
 * Why the list takes the verdicts and not the claims: the recording carries no claim of its own.
 * The verdict of the verifier is what the recording published about the claim.
 */
export interface ClaimListProps {
  /** The verdicts the verifier produced, in the order it produced them. */
  readonly verdicts: readonly VerdictSummary[];
}

/** What the list shows when the recording carries nothing to show. */
const NOT_AVAILABLE = "Not available";

/** The verdicts the pill of the design system knows. */
const KNOWN_VERDICTS: readonly string[] = [
  "supported",
  "contradicted",
  "not_enough_evidence",
  "not_verified",
];

/**
 * Renders the verdict of one claim.
 *
 * Why the pill is used when the word is one the design system knows: the pill carries an icon and
 * the words, and a colour alone is not an accessible signal. A word the mapping does not know is
 * shown as it was read, with the neutral tone.
 */
function VerdictMark({ label, status }: { readonly label: string | null; readonly status: StatusLabel }) {
  if (label !== null && KNOWN_VERDICTS.includes(label)) {
    return <StatusPill verdict={label as StatusPillVerdict} label={status.label} />;
  }
  return <Badge tone={status.tone}>{status.label}</Badge>;
}

/**
 * The claims of the answer, with the verdict of the verifier about each one.
 *
 * The list says the verdict of every claim the recording published, and it says that the text of
 * the claim is not available when the recording carries no text of the claim.
 */
export function ClaimList({ verdicts }: ClaimListProps): ReactElement {
  return (
    <section aria-label="The claims of the answer" className="rounded-lg border border-line bg-background">
      <div className="flex flex-col gap-1 border-b border-line px-4 py-3">
        <h4 className="text-base font-semibold">The claims of the answer</h4>
        <p className="text-sm text-text-muted">
          The claims the verifier decided about, with the method of the verification and the note
          that came with the decision.
        </p>
      </div>

      {verdicts.length === 0 ? (
        <p className="px-4 py-3 text-sm text-text-muted">
          The recording carries no verdict yet.
        </p>
      ) : (
        <ul className="flex flex-col gap-3 px-4 py-3">
          {verdicts.map((verdict) => {
            const status = formatVerdict(verdict.label);

            return (
              <li key={verdict.claimId} className="flex flex-col gap-2 rounded border border-line p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-xs text-foreground">{verdict.claimId}</span>
                  <VerdictMark label={verdict.label} status={status} />
                </div>

                <dl className="grid gap-3 sm:grid-cols-2">
                  <div className="flex flex-col gap-1">
                    <dt className="text-xs font-medium text-text-subtle">Text of the claim</dt>
                    <dd className="text-sm text-foreground">{NOT_AVAILABLE}</dd>
                  </div>
                  <div className="flex flex-col gap-1">
                    <dt className="text-xs font-medium text-text-subtle">Method of the verification</dt>
                    <dd className="text-sm text-foreground">{verdict.method ?? NOT_AVAILABLE}</dd>
                  </div>
                  <div className="flex flex-col gap-1">
                    <dt className="text-xs font-medium text-text-subtle">Note of the verifier</dt>
                    <dd className="text-sm text-foreground">{verdict.note ?? NOT_AVAILABLE}</dd>
                  </div>
                  <div className="flex flex-col gap-1">
                    <dt className="text-xs font-medium text-text-subtle">Evidence the decision cited</dt>
                    <dd className="text-sm text-foreground">
                      {verdict.evidenceIds.length > 0
                        ? verdict.evidenceIds.join(", ")
                        : NOT_AVAILABLE}
                    </dd>
                  </div>
                </dl>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the list at once. */
export const __all__ = ["ClaimListProps", "ClaimList"] as const;
