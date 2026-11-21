import type { ReactNode } from "react";

import { cn } from "@/lib/design/cn";

/**
 * The badge of the design system: a small label that carries a piece of metadata.
 *
 * A badge never carries a meaning on its own. The colour only repeats what the text already
 * says, so a visitor who does not see the colour still reads the state. The semantic tones are
 * reserved for a real verification outcome.
 */

export type BadgeTone = "neutral" | "success" | "danger" | "warning" | "accent";

export interface BadgeProps {
  /** The tone of the badge. It repeats the text, it never replaces it. */
  tone?: BadgeTone;
  /** The content of the badge. It is always a text. */
  children: ReactNode;
  /** Extra class names. */
  className?: string;
}

const TONE_CLASSES: Record<BadgeTone, string> = {
  neutral: "bg-surface-muted text-text-muted border-line",
  success: "bg-success-light text-success-dark border-success/40",
  danger: "bg-danger-light text-danger-dark border-danger/40",
  warning: "bg-warning-light text-warning-dark border-warning/40",
  accent: "bg-surface text-foreground border-line-strong",
};

export function Badge({ tone = "neutral", children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        TONE_CLASSES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
