import { forwardRef } from "react";
import type { ButtonHTMLAttributes, ReactNode, Ref } from "react";

import { cn } from "@/lib/design/cn";

/**
 * The button of the design system.
 *
 * It renders a real `button` element, so it is reachable with the keyboard, it takes part in
 * the form of the page and it fires on both the click and the Enter and Space keys without
 * any extra code.
 *
 * The `type` defaults to `button`, because a button that is not a submit button is the safe
 * default inside a form.
 */

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** The weight of the button. The primary one is the only filled one. */
  variant?: ButtonVariant;
  /** The size of the button. */
  size?: ButtonSize;
  /** The content of the button. */
  children: ReactNode;
}

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary:
    "bg-foreground text-background border border-foreground hover:bg-neutral-800 hover:border-neutral-800",
  secondary:
    "bg-background text-foreground border border-line-strong hover:bg-surface hover:border-neutral-400",
  ghost: "bg-transparent text-foreground border border-transparent hover:bg-surface",
  danger: "bg-danger text-background border border-danger hover:bg-danger-dark hover:border-danger-dark",
};

const SIZE_CLASSES: Record<ButtonSize, string> = {
  sm: "text-xs px-2 py-1 gap-1",
  md: "text-sm px-3 py-2 gap-2",
  lg: "text-base px-4 py-3 gap-2",
};

/** The class names of the button, exposed so a link can wear the same look. */
export function buttonClasses(
  variant: ButtonVariant = "primary",
  size: ButtonSize = "md",
  extra?: string,
): string {
  return cn(
    "inline-flex items-center justify-center rounded font-medium transition-colors",
    "disabled:opacity-50 disabled:pointer-events-none",
    VARIANT_CLASSES[variant],
    SIZE_CLASSES[size],
    extra,
  );
}

/**
 * The button of the design system.
 *
 * Why the button takes a reference to the element it draws: a button that opens a window has to
 * give the focus back to itself when the window closes, and the caller is the one that knows the
 * button. A button that cannot be referenced is a button whose caller cannot give the focus back
 * (ADR-046).
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", className, type, children, ...rest },
  ref: Ref<HTMLButtonElement>,
) {
  return (
    <button
      ref={ref}
      type={type ?? "button"}
      className={buttonClasses(variant, size, className)}
      {...rest}
    >
      {children}
    </button>
  );
});
