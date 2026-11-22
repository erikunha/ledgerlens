"use client";

/**
 * The sheet of the design system: the dialog that comes from the side of the screen.
 *
 * Why this file exists: a panel that slides in from the edge of the screen is the same window as
 * the dialog, only anchored somewhere else, so it is the same package with a different place. The
 * primitive wraps `@radix-ui/react-dialog`, which the frontend already depends on, so the
 * milestone adds no dependency and the lock file of the repository does not move.
 *
 * Why the sheet traps the focus like the dialog: a panel that leaves the keyboard behind it is a
 * panel a keyboard user can leave behind.
 */

import * as RadixDialog from "@radix-ui/react-dialog";
import type { ReactElement, ReactNode, RefObject } from "react";

import { cn } from "@/lib/design/cn";

/**
 * The props of the sheet.
 *
 * Why the side has a default: the side on the right is the side a drawer is opened from in the
 * rest of the interface, and a caller that says nothing gets the common case.
 */
export interface SheetProps {
  /** Whether the sheet is open. */
  readonly open: boolean;
  /** The function that is called with the state the visitor asked for. */
  readonly onOpenChange: (open: boolean) => void;
  /** The name of the sheet. */
  readonly title: string;
  /** What the sheet holds. */
  readonly children: ReactNode;
  /** The edge of the screen the sheet comes from. */
  readonly side?: "top" | "bottom" | "left" | "right";
  /**
   * The element that takes the focus back when the sheet closes.
   *
   * Why the sheet needs it: the sheet is controlled by its caller and it is opened by a control
   * that lives outside of it, so the primitive of the dialog does not know which control opened
   * it and the focus lands on the body of the page when the sheet closes. A visitor who opened a
   * window with the keyboard and closed it with the Escape key has to find his way back to the
   * control from scratch, and the rule of the repository is that the focus returns to the control
   * that opened the drawer.
   */
  readonly returnFocusTo?: RefObject<HTMLElement | null>;
}

/** The place of the sheet on the screen, for every side of the edge. */
const SIDE_CLASSES: Record<NonNullable<SheetProps["side"]>, string> = {
  right: "right-0 top-0 h-full w-[min(24rem,90vw)] border-l",
  left: "left-0 top-0 h-full w-[min(24rem,90vw)] border-r",
  top: "inset-x-0 top-0 w-full max-h-[85vh] border-b",
  bottom: "inset-x-0 bottom-0 w-full max-h-[85vh] border-t",
};

/**
 * The sheet of the design system.
 *
 * The sheet is rendered in a portal, so it is never clipped by the column of the page, and the
 * overlay behind it holds the rest of the page still.
 */
export function Sheet(props: SheetProps): ReactElement {
  const side = props.side ?? "right";

  /**
   * Gives the focus back to the control that opened the sheet.
   *
   * Why the event is prevented: the primitive of the dialog returns the focus to the element it
   * knows, and the sheet is opened by a control that lives outside of it, so the primitive would
   * return the focus to the body of the page after this handler ran. Preventing the default stops
   * that, and the sheet is the one that knows the control, so the sheet gives the focus back.
   */
  const handleCloseAutoFocus = (event: Event): void => {
    event.preventDefault();
    props.returnFocusTo?.current?.focus();
  };

  return (
    <RadixDialog.Root open={props.open} onOpenChange={props.onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 z-40 bg-neutral-900/40" />
        <RadixDialog.Content
          className={cn(
            "fixed z-50 overflow-y-auto border-line bg-background p-4 shadow-lg",
            SIDE_CLASSES[side],
          )}
          onCloseAutoFocus={handleCloseAutoFocus}
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
export const __all__ = ["SheetProps", "Sheet"] as const;
