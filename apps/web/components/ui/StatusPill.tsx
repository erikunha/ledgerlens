import type { ReactNode } from "react";

import { cn } from "@/lib/design/cn";

/**
 * The status pill: the verdict of a claim, with an icon and with the words.
 *
 * Why it always carries words: a colour alone is not an accessible signal, and a visitor who
 * does not distinguish the hues would read a wrong meaning out of a green pill. The icon is
 * decorative for a screen reader, because the text next to it already says everything.
 *
 * The allowed labels are the ones the verifier produces in Python: `supported`,
 * `contradicted` and `not_enough_evidence`, plus `not_verified` for the case where the
 * verifier itself was unavailable. The last one is deliberately not a verdict: it says the
 * claim was not checked, which is a different thing from being checked and found weak.
 */

export type StatusPillVerdict = "supported" | "contradicted" | "not_enough_evidence" | "not_verified";

export interface StatusPillProps {
  /** The verdict to show. */
  verdict: StatusPillVerdict;
  /** Extra class names. */
  className?: string;
  /** Replaces the default label, for the case where the wording of the page needs it. */
  label?: ReactNode;
}

interface StatusDefinition {
  /** The words the visitor reads. */
  label: string;
  /** The classes of the pill. */
  className: string;
  /** The icon of the pill. */
  icon: ReactNode;
}

/** A check mark: the claim holds against the evidence. */
function CheckIcon() {
  return (
    <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true" focusable="false">
      <path
        d="M3 8.5l3.2 3.2L13 5"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** A cross: the evidence contradicts the claim. */
function CrossIcon() {
  return (
    <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true" focusable="false">
      <path
        d="M4 4l8 8M12 4l-8 8"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

/** A question mark: there was not enough evidence to decide. */
function QuestionIcon() {
  return (
    <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true" focusable="false">
      <path
        d="M6 6a2 2 0 113 1.7c-.6.4-1 .8-1 1.6"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <circle cx="8" cy="12" r="1" fill="currentColor" />
    </svg>
  );
}

/** A dash: the verifier was unavailable, so nothing was decided. */
function DashIcon() {
  return (
    <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true" focusable="false">
      <path d="M4 8h8" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

const DEFINITIONS: Record<StatusPillVerdict, StatusDefinition> = {
  supported: {
    label: "Supported",
    className: "bg-success-light text-success-dark border-success/40",
    icon: <CheckIcon />,
  },
  contradicted: {
    label: "Contradicted",
    className: "bg-danger-light text-danger-dark border-danger/40",
    icon: <CrossIcon />,
  },
  not_enough_evidence: {
    label: "Not enough evidence",
    className: "bg-warning-light text-warning-dark border-warning/40",
    icon: <QuestionIcon />,
  },
  not_verified: {
    label: "Not verified",
    className: "bg-surface-muted text-text-muted border-line-strong",
    icon: <DashIcon />,
  },
};

export function StatusPill({ verdict, className, label }: StatusPillProps) {
  const definition = DEFINITIONS[verdict];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        definition.className,
        className,
      )}
    >
      {definition.icon}
      {label ?? definition.label}
    </span>
  );
}

/** The label of a verdict, for the places that need the words without the pill. */
export function statusLabel(verdict: StatusPillVerdict): string {
  return DEFINITIONS[verdict].label;
}
