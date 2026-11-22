import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/design/cn";

/**
 * The card of the design system: a bordered surface that groups one piece of content.
 *
 * The parts are separate components so the heading level stays the caller's choice, which keeps
 * the document outline correct on every page.
 */

export function Card({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-lg border border-line bg-background", className)} {...rest} />;
}

export function CardHeader({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex flex-col gap-1 border-b border-line px-4 py-3", className)} {...rest} />;
}

/**
 * The level of the title of a card.
 *
 * Why the list is closed: a heading is a level of the outline of the document, and a primitive that
 * accepts any tag lets a caller write a level that breaks the outline of the page it is put in.
 */
export type CardTitleLevel = "h2" | "h3" | "h4" | "h5";

/**
 * The props of the title of a card.
 *
 * Why the level is a prop and not a guess: the outline of the headings of a page is the caller's
 * decision, because only the caller knows where the card sits in the page. A card under the title
 * of the page is a `h2`, and a card inside a section is a `h3`.
 */
export interface CardTitleProps extends HTMLAttributes<HTMLHeadingElement> {
  /** The level of the heading of the title. */
  readonly level?: CardTitleLevel;
}

export function CardTitle({ className, level = "h3", ...rest }: CardTitleProps) {
  const Level = level;
  return <Level className={cn("text-base font-semibold text-foreground", className)} {...rest} />;
}

export function CardDescription({ className, ...rest }: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("text-sm text-text-muted", className)} {...rest} />;
}

export function CardContent({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-4 py-3", className)} {...rest} />;
}

export function CardFooter({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex items-center gap-2 border-t border-line px-4 py-3", className)} {...rest} />;
}

/**
 * The props of a card whose title and its description live in the header.
 *
 * Why the level is a prop: the title of the card is a heading of the page, and the level of that
 * heading belongs to the page and not to the primitive.
 */
export interface CardSectionProps {
  /** The title of the card. */
  readonly title: ReactNode;
  /** The description under the title. */
  readonly description?: ReactNode;
  /** The body of the card. */
  readonly children?: ReactNode;
  /** The level of the heading of the title. */
  readonly titleLevel?: CardTitleLevel;
}

/** A card whose title and its description live in the header. It is the common shape. */
export function CardSection({
  title,
  description,
  children,
  titleLevel = "h3",
}: CardSectionProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle level={titleLevel}>{title}</CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      {children ? <CardContent>{children}</CardContent> : null}
    </Card>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the primitive at once. */
export const __all__ = [
  "CardTitleLevel",
  "CardTitleProps",
  "CardSectionProps",
  "Card",
  "CardHeader",
  "CardTitle",
  "CardDescription",
  "CardContent",
  "CardFooter",
  "CardSection",
] as const;
