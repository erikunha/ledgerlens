import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

/**
 * The configuration of the unit tests.
 *
 * The unit tests cover the pure parts of the interface: the design tokens, the accessible
 * primitives and the components that need a browser to be tested at all. The end to end
 * journeys live in `tests/e2e` and run with Playwright, against the static export.
 *
 * The environment is jsdom, because the primitives are React components that need a document.
 */
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL(".", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/unit/setup.ts"],
    include: ["tests/unit/**/*.test.{ts,tsx}"],
    css: false,
    restoreMocks: true,
  },
});
