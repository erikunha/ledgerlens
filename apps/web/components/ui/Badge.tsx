import type { ReactNode } from "react";

import { cn } from "@/lib/design/cn";

/**
 * The badge of the design system: a small label that carries a piece of metadata.
 *
 * A badge never carries a meaning on its own. The colour only repeats what the text already
 * says, so a visitor who does not see the colour still reads the state. The semantic tones are
 * reserved for a real verification outcome.
 *
 * Why every tone paints its text with the dark step of its status: the text of a badge is 12
 * pixels, which is small text, so it needs a contrast of at least 4.5 to 1 against its own
 * background. The base step of the warning is #d97706, which is 3.19 to 1 on white and fails, so
 * the warning tone takes the dark step, #b45309, which keeps the label legible. The token of the
 * warning itself is never changed, because other components rely on it.
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
  // the dark step of the warning, because the base step fails the contrast of 12 pixel text
  warning: "bg-warning-light text-warning-dark border-warning/40",
  accent: "bg-surface text-foreground border-line-strong",
};

/**
 * The badge of the design system.
 *
 * The badge is a span, because a badge says something about the text next to it and it is not a
 * control. It carries the tone of the state and the words of the state, never the colour alone.
 */
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

/** Every symbol this module exports, so that a reader sees the whole surface of the badge at once. */
export const __all__ = ["BadgeTone", "BadgeProps", "Badge"] as const;
