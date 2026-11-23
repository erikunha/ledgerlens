/**
 * The skeleton of the design system: the placeholder of a thing that is still loading.
 *
 * Why this file exists: a panel that appears with nothing in it reads as a broken panel, and a
 * panel that shows a grey shape with the shape of the content reads as a panel that is loading.
 * The skeleton is that shape.
 *
 * Why the label is optional: a skeleton that stands for one known thing names itself, so a screen
 * reader says what is coming, and a skeleton that stands for a whole panel stays silent, because
 * the panel itself carries the name.
 */

import type { ReactElement } from "react";

import { cn } from "@/lib/design/cn";

/**
 * The props of the skeleton.
 *
 * Why the class name is open: the shape of a skeleton follows the shape of the thing it stands
 * for, and the caller knows that shape.
 */
export interface SkeletonProps {
  /** The class names of the shape. */
  readonly className?: string;
  /** The name of the thing that is loading, when the skeleton stands for one thing. */
  readonly label?: string;
}

/**
 * The skeleton of the design system.
 *
 * A skeleton with a label announces itself to a screen reader, and a skeleton without a label is
 * hidden from one, because the panel that is loading carries the name already.
 */
export function Skeleton(props: SkeletonProps): ReactElement {
  const label = props.label;

  return (
    <div
      className={cn("animate-pulse rounded bg-surface-muted", props.className)}
      role={label ? "status" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    />
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the primitive at once. */
export const __all__ = ["SkeletonProps", "Skeleton"] as const;
