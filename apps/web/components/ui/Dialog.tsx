"use client";

/**
 * The dialog of the design system.
 *
 * Why this file exists: a modal window has to trap the focus, has to answer the Escape key and
 * has to carry a name, and writing that by hand is a way to write a window that a keyboard user
 * can leave behind. The primitive wraps `@radix-ui/react-dialog`, which the frontend already
 * depends on, so the milestone adds no dependency.
 *
 * Why the dialog is controlled: the caller decides when it is open, so the state of the visit can
 * live with the state of the page and not inside the primitive.
 */

import * as RadixDialog from "@radix-ui/react-dialog";
import type { ReactElement, ReactNode } from "react";

import { cn } from "@/lib/design/cn";

/**
 * The props of the dialog.
 *
 * Why the title is a string and not a node: a dialog without a name is a window a screen reader
 * cannot announce, and the name of a window is a sentence.
 */
export interface DialogProps {
  /** Whether the dialog is open. */
  readonly open: boolean;
  /** The function that is called with the state the visitor asked for. */
  readonly onOpenChange: (open: boolean) => void;
  /** The name of the dialog. */
  readonly title: string;
  /** What the dialog holds. */
  readonly children: ReactNode;
  /** The button that opens the dialog, when the caller wants one. */
  readonly trigger?: ReactNode;
}

/**
 * The dialog of the design system.
 *
 * The window is rendered in a portal, so it is never clipped by the column of the page, and the
 * overlay behind it holds the rest of the page still.
 */
export function Dialog(props: DialogProps): ReactElement {
  return (
    <RadixDialog.Root open={props.open} onOpenChange={props.onOpenChange}>
      {props.trigger ? (
        <RadixDialog.Trigger asChild>{props.trigger}</RadixDialog.Trigger>
      ) : null}
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 z-40 bg-neutral-900/40" />
        <RadixDialog.Content
          className={cn(
            "fixed left-1/2 top-1/2 z-50 w-[min(32rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2",
            "rounded-lg border border-line bg-background p-4 shadow-lg",
          )}
        >
          <RadixDialog.Title className="pr-8 text-base font-semibold">
            {props.title}
          </RadixDialog.Title>
          <RadixDialog.Close className="absolute right-3 top-3 rounded px-2 py-1 text-sm text-text-muted hover:bg-surface hover:text-foreground">
            Close
          </RadixDialog.Close>
          <div className="mt-3 flex flex-col gap-3">{props.children}</div>
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the primitive at once. */
export const __all__ = ["DialogProps", "Dialog"] as const;
