import type { Config } from "tailwindcss";

import { breakpoints, colors, fontSizes, neutral, radii, shadows, spacing } from "./lib/design/tokens";

/**
 * The Tailwind configuration of the public site.
 *
 * The theme is built from the design tokens in `lib/design/tokens.ts`, so a colour or a spacing
 * step exists in exactly one place. The colour names are the neutral scale plus the semantic
 * statuses, which keeps the saturated colours reserved for a real verification outcome.
 *
 * The names are written for the class, not for the token: `text-foreground` reads better in a
 * component than `text-text`, and `border-line` reads better than `border-border`.
 */
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./features/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    // the design tokens replace the defaults, so a spacing step is always a 4 pixel step
    spacing,
    colors: {
      background: colors.background,
      foreground: colors.text,
      surface: colors.surface,
      "surface-muted": colors.surfaceMuted,
      line: colors.border,
      "line-strong": colors.borderStrong,
      "text-muted": colors.textMuted,
      "text-subtle": colors.textSubtle,
      "success-light": colors.successLight,
      success: colors.success,
      "success-dark": colors.successDark,
      "danger-light": colors.dangerLight,
      danger: colors.danger,
      "danger-dark": colors.dangerDark,
      "warning-light": colors.warningLight,
      warning: colors.warning,
      "warning-dark": colors.warningDark,
      neutral,
      transparent: "transparent",
      current: "currentColor",
      inherit: "inherit",
    },
    fontFamily: {
      sans: ["var(--ll-font-sans)"],
      mono: ["var(--ll-font-mono)"],
    },
    fontSize: Object.fromEntries(
      Object.entries(fontSizes).map(([key, value]) => [key, [value.size, { lineHeight: value.lineHeight }]]),
    ),
    borderRadius: {
      none: radii.none,
      sm: radii.sm,
      DEFAULT: radii.DEFAULT,
      md: radii.md,
      lg: radii.lg,
      full: radii.full,
    },
    boxShadow: {
      none: "none",
      sm: shadows.sm,
      md: shadows.md,
      lg: shadows.lg,
    },
    screens: {
      sm: breakpoints.sm,
      md: breakpoints.md,
      lg: breakpoints.lg,
      xl: breakpoints.xl,
      "2xl": breakpoints["2xl"],
    },
    extend: {
      maxWidth: {
        content: "80rem",
      },
    },
  },
  plugins: [],
};

export default config;
