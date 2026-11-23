/**
 * The design tokens of the public site: the single source of truth for the visual language.
 *
 * Why this file exists: the design package asks for a calm, credible surface with a neutral
 * palette, a legible sans font with a monospace companion, a 4 pixel spacing scale and semantic
 * colours reserved for real verification statuses. If every component carried its own hex value,
 * the site would drift and the contrast could not be checked in one place.
 *
 * The tokens live here as a typed object so a wrong key or a wrong type is a compile error.
 * `app/globals.css` declares the same values as CSS custom properties, and the unit test
 * `tests/unit/tokens.test.ts` reads that stylesheet and fails when the two disagree. The
 * stylesheet stays a plain CSS file because Tailwind reads it directly, and the test is what
 * keeps the duplication honest.
 *
 * The colours are named for what they mean, never for how they look. A status colour is only
 * allowed to appear next to a text label, so no meaning ever depends on seeing a hue.
 */

/** A spacing step of the 4 pixel scale. The key is the Tailwind step, the value is the size. */
export const spacing = {
  0: "0px",
  1: "4px",
  2: "8px",
  3: "12px",
  4: "16px",
  5: "20px",
  6: "24px",
  8: "32px",
  10: "40px",
  12: "48px",
  16: "64px",
  20: "80px",
  24: "96px",
} as const;

/**
 * The neutral palette. Every surface, border and text colour of the site comes from here.
 * The names are steps, not meanings, because no step is reserved for a status.
 */
export const neutral = {
  0: "#ffffff",
  50: "#f8fafc",
  100: "#f1f5f9",
  200: "#e2e8f0",
  300: "#cbd5e1",
  400: "#94a3b8",
  500: "#64748b",
  600: "#475569",
  700: "#334155",
  800: "#1e293b",
  900: "#0f172a",
} as const;

/**
 * The semantic statuses. These are the only saturated colours of the interface and they are
 * reserved for a real verification outcome.
 *
 * The dark step is the one used for text and for icons on the light step, so that the label
 * keeps a contrast of at least 4.5 to 1 against its own background.
 */
export const success = {
  light: "#dcfce7",
  base: "#15803d",
  dark: "#166534",
} as const;

export const danger = {
  light: "#fee2e2",
  base: "#dc2626",
  dark: "#b91c1c",
} as const;

export const warning = {
  light: "#fef3c7",
  base: "#d97706",
  dark: "#b45309",
} as const;

/** The palette of the interface, with the meaning in the name. */
export const colors = {
  background: neutral[0],
  surface: neutral[50],
  surfaceMuted: neutral[100],
  border: neutral[200],
  borderStrong: neutral[300],
  text: neutral[900],
  textMuted: neutral[600],
  textSubtle: neutral[500],
  successLight: success.light,
  success: success.base,
  successDark: success.dark,
  dangerLight: danger.light,
  danger: danger.base,
  dangerDark: danger.dark,
  warningLight: warning.light,
  warning: warning.base,
  warningDark: warning.dark,
} as const;

/**
 * The typefaces.
 *
 * The stacks are the ones of the platform, not a downloaded file. A web font would make the
 * build depend on a network call and would add a request to a page that is otherwise static,
 * and the constitution asks the site to work with no credential and no network.
 */
export const fonts = {
  sans: [
    "ui-sans-serif",
    "system-ui",
    "-apple-system",
    "Segoe UI",
    "Roboto",
    "Helvetica Neue",
    "Arial",
    "sans-serif",
  ].join(", "),
  mono: [
    "ui-monospace",
    "SFMono-Regular",
    "SF Mono",
    "Menlo",
    "Consolas",
    "Liberation Mono",
    "monospace",
  ].join(", "),
} as const;

/** The type scale, in pixels, with the line height that goes with each size. */
export const fontSizes = {
  xs: { size: "12px", lineHeight: "16px" },
  sm: { size: "14px", lineHeight: "20px" },
  base: { size: "16px", lineHeight: "24px" },
  lg: { size: "18px", lineHeight: "28px" },
  xl: { size: "20px", lineHeight: "28px" },
  "2xl": { size: "24px", lineHeight: "32px" },
  "3xl": { size: "30px", lineHeight: "38px" },
  "4xl": { size: "36px", lineHeight: "44px" },
} as const;

/** The corner radii. They are small on purpose: the interface is dense and technical. */
export const radii = {
  none: "0px",
  sm: "2px",
  DEFAULT: "4px",
  md: "6px",
  lg: "8px",
  full: "9999px",
} as const;

/**
 * The responsive breakpoints, in pixels.
 *
 * The names follow the design package: a single column under 768, two panes from 768 to 1439
 * and the wide layout with the side drawer at 1440.
 */
export const breakpoints = {
  sm: "640px",
  md: "768px",
  lg: "1024px",
  xl: "1280px",
  "2xl": "1440px",
} as const;

/** The shadow of the surfaces that float above the page, such as a dialog or a drawer. */
export const shadows = {
  sm: "0 1px 2px rgba(15, 23, 42, 0.06)",
  md: "0 4px 12px rgba(15, 23, 42, 0.08)",
  lg: "0 12px 32px rgba(15, 23, 42, 0.12)",
} as const;

/** The whole token set, gathered so a consumer can iterate over it in one place. */
export const tokens = {
  spacing,
  neutral,
  colors,
  fonts,
  fontSizes,
  radii,
  breakpoints,
  shadows,
  success,
  danger,
  warning,
} as const;

export type Tokens = typeof tokens;
export type SpacingKey = keyof typeof spacing;
export type ColorKey = keyof typeof colors;

/**
 * The CSS custom properties that `app/globals.css` declares, computed from the tokens.
 *
 * The function exists so the unit test can rebuild the expected list from the tokens and
 * compare it with the stylesheet, instead of the two being maintained by hand and drifting.
 * The names follow the convention `--ll-<group>-<name>`.
 */
export function cssVariables(source: Tokens = tokens): Record<string, string> {
  const variables: Record<string, string> = {};

  for (const [key, value] of Object.entries(source.spacing)) {
    variables[`--ll-space-${key}`] = value;
  }

  for (const [key, value] of Object.entries(source.neutral)) {
    variables[`--ll-neutral-${key}`] = value;
  }

  for (const [key, value] of Object.entries(source.colors)) {
    variables[`--ll-color-${kebab(key)}`] = value;
  }

  variables["--ll-font-sans"] = source.fonts.sans;
  variables["--ll-font-mono"] = source.fonts.mono;

  for (const [key, value] of Object.entries(source.fontSizes)) {
    variables[`--ll-text-${key}`] = value.size;
    variables[`--ll-leading-${key}`] = value.lineHeight;
  }

  for (const [key, value] of Object.entries(source.radii)) {
    variables[`--ll-radius-${key.toLowerCase()}`] = value;
  }

  for (const [key, value] of Object.entries(source.breakpoints)) {
    variables[`--ll-breakpoint-${key}`] = value;
  }

  for (const [key, value] of Object.entries(source.shadows)) {
    variables[`--ll-shadow-${key}`] = value;
  }

  return variables;
}

/** Turns a camel case token name into the kebab case used in the CSS custom property name. */
function kebab(value: string): string {
  return value.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`);
}
