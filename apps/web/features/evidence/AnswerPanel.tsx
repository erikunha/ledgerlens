/**
 * The evidence of the answer of a recorded run.
 *
 * Why this file exists: the answer of a run is the thing a reader wants, and the answer is only
 * worth reading with the evidence behind it. The panel shows the text of the answer, the action
 * the run recommends, the flag of the human review, the summary of the run, the verdicts of the
 * verifier and the evidence the run cited (ADR-043).
 *
 * Why the panel shows no reasoning of the model: the recording carries no reasoning, and the panel
 * never claims that something is available when it is not.
 */

import type { ReactElement } from "react";

import { Badge } from "@/components/ui/Badge";
import { EvidenceCard } from "@/features/evidence/EvidenceCard";
import type { EvidenceSummary, FinalAnswer, VerdictSummary } from "@/lib/replay/selectors";


/**
 * The props of the panel of the evidence of the answer.
 *
 * Why the answer can be null: a recording that has not reached its answer yet has no answer, and
 * the panel says so instead of showing an answer of its own.
 */
export interface AnswerPanelProps {
  /** The answer of the run, when the recording carries one. */
  readonly answer: FinalAnswer | null;
  /** The verdicts the verifier produced. */
  readonly verdicts: readonly VerdictSummary[];
  /** The evidence the run gathered. */
  readonly evidence: readonly EvidenceSummary[];
}

/** What the panel shows when the recording carries nothing to show. */
const NOT_AVAILABLE = "Not available";

/**
 * The evidence of the answer of a recorded run.
 *
 * The panel shows the answer as the recording wrote it, with the facts the recording published
 * about it, and the evidence with the identifier, the tool that produced it and the content the
 * tool returned. The decisions of the verifier are shown with the claims of the answer, where
 * the identifier, the decision, the method and the note of every decision belong.
 */
export function AnswerPanel({ answer, verdicts, evidence }: AnswerPanelProps): ReactElement {
  return (
    <section
      aria-label="The evidence of the answer"
      className="rounded-lg border border-line bg-background"
    >
      <div className="flex flex-col gap-1 border-b border-line px-4 py-3">
        <h4 className="text-base font-semibold">The evidence of the answer</h4>
        <p className="text-sm text-text-muted">
          The answer of the run, with the evidence it cites and the decisions the verifier took
          about the claims.
        </p>
      </div>

      <div className="flex flex-col gap-4 px-4 py-4">
        {answer ? (
          <div className="flex flex-col gap-2">
            <p className="text-sm text-foreground">{answer.answer}</p>
            <dl className="grid gap-3 sm:grid-cols-2">
              <div className="flex flex-col gap-1">
                <dt className="text-xs font-medium text-text-subtle">Action the run recommends</dt>
                <dd className="text-sm text-foreground">
                  {answer.recommendedAction ? (
                    <Badge>{answer.recommendedAction}</Badge>
                  ) : (
                    NOT_AVAILABLE
                  )}
                </dd>
              </div>
              <div className="flex flex-col gap-1">
                <dt className="text-xs font-medium text-text-subtle">Human review</dt>
                <dd className="text-sm text-foreground">
                  {answer.requiresHumanReview === null
                    ? NOT_AVAILABLE
                    : answer.requiresHumanReview
                      ? "A human has to look at the case."
                      : "No human review is needed."}
                </dd>
              </div>
              <div className="flex flex-col gap-1">
                <dt className="text-xs font-medium text-text-subtle">Summary of the run</dt>
                <dd className="text-sm text-foreground">{answer.summary ?? NOT_AVAILABLE}</dd>
              </div>
            </dl>
          </div>
        ) : (
          <p className="text-sm text-text-muted">
            The recording carries no answer yet.
          </p>
        )}

        <div className="flex flex-col gap-2">
          <h5 className="text-sm font-semibold">The verdicts of the verification</h5>
          <p className="text-sm text-text-muted">
            The verifier produced {verdicts.length} decisions about the claims of the answer. They are
            shown with the claims, where the method and the note of every decision belong.
          </p>
        </div>

        <div className="flex flex-col gap-2">
          <h5 className="text-sm font-semibold">The evidence the run gathered</h5>
          {evidence.length === 0 ? (
            <p className="text-sm text-text-muted">The recording carries no evidence yet.</p>
          ) : (
            <ul className="flex flex-col gap-3">
              {evidence.map((item) => (
                <li key={item.evidenceId}>
                  <EvidenceCard evidence={item} />
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the panel at once. */
export const __all__ = ["AnswerPanelProps", "AnswerPanel"] as const;
