import js from "@eslint/js";
import nextPlugin from "@next/eslint-plugin-next";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

/**
 * The lint configuration of the public site.
 *
 * The rules come in three groups: the correctness rules of the language and of TypeScript, the
 * rules of Next.js about the App Router, and the accessibility rules of the plugin
 * `jsx-a11y`, which are what the design package asks the interface to satisfy.
 *
 * The configuration is flat, so the file list is explicit. The build output and the installed
 * packages are never linted.
 */
export default tseslint.config(
  {
    // The build output, the installed packages and the file that Next.js generates are never linted. The generated
    // file carries a triple slash reference that the rule of TypeScript about it does not accept, and the file is not
    // part of the source.
    ignores: [
      ".next/**",
      "out/**",
      "node_modules/**",
      "coverage/**",
      "playwright-report/**",
      "test-results/**",
      "next-env.d.ts",
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
      },
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    plugins: {
      "@next/next": nextPlugin,
      react,
      "react-hooks": reactHooks,
    },
    settings: {
      react: { version: "detect" },
    },
    rules: {
      ...nextPlugin.configs.recommended.rules,
      ...nextPlugin.configs["core-web-vitals"].rules,
      ...react.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      "react/react-in-jsx-scope": "off",
      "react/prop-types": "off",
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
      "@typescript-eslint/consistent-type-imports": ["error", { prefer: "type-imports" }],
    },
  },
  {
    files: ["**/*.test.{ts,tsx}", "tests/**/*.{ts,tsx}"],
    rules: {
      // a test names its own cases, so the rule about the production code does not apply
      "@typescript-eslint/no-explicit-any": "off",
    },
  },
);
