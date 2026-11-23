/**
 * The class name joiner of the design system.
 *
 * Why it exists: every primitive takes optional class names from the caller and joins them
 * with its own. A plain join would put an undefined in the middle of the attribute, and a
 * library would be one more dependency for three lines of code.
 */

/** Joins the class names and drops the empty ones, so a conditional class is a plain argument. */
export function cn(...values: Array<string | false | null | undefined>): string {
  return values.filter((value): value is string => Boolean(value)).join(" ");
}
