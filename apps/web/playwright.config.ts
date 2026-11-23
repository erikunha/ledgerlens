import { defineConfig, devices } from "@playwright/test";

import { E2E_PORT, SITE_ORIGIN } from "./tests/e2e/site-origin";

/**
 * The configuration of the end to end tests.
 *
 * The suite runs against the static export, served as plain files, because that is exactly what
 * a visitor receives. The command builds the export first and serves it, so the test never
 * depends on a development server.
 *
 * The viewports are the ones of the design package: 390 pixels for the phone and 1440 pixels
 * for the wide layout. Both are checked in the two engines the package names.
 *
 * Why the port has one source: the base URL, the command of the server and the URL the suite waits
 * for all read `E2E_PORT` from `tests/e2e/site-origin`, and the specs of the network guard read
 * the origin of that same module. The origin the suite serves and the origin the specs assert are
 * therefore the same by construction, and no edit of one place can make the proof vacuous.
 *
 * Why `reuseExistingServer` is always false: the suite must test the export of this repository and
 * nothing else. Outside the CI it used to reuse whatever server already answered on the port, and
 * this machine runs other projects in parallel, so a green run could have tested a site that is not
 * LedgerLens. A green run against the wrong server is worse than a red one. The suite now always
 * starts its own server, and when the port is busy it fails loudly with a readable reason instead
 * of quietly testing somebody else's server. When two copies of this repository have to run at the
 * same time, give one of them its own port with `LEDGERLENS_E2E_PORT`.
 */
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "list" : [["html", { open: "never" }]],
  use: {
    baseURL: SITE_ORIGIN,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium-390",
      use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 } },
    },
    {
      name: "chromium-1440",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
    {
      name: "webkit-390",
      use: { ...devices["Desktop Safari"], viewport: { width: 390, height: 844 } },
    },
    {
      name: "webkit-1440",
      use: { ...devices["Desktop Safari"], viewport: { width: 1440, height: 900 } },
    },
  ],
  webServer: {
    command: `npm run build && npx serve out -l ${E2E_PORT}`,
    url: SITE_ORIGIN,
    // Always false, on purpose: the suite starts its own server, and a busy port is a loud failure
    // instead of a green run against the server of another project.
    reuseExistingServer: false,
    timeout: 180_000,
  },
});
