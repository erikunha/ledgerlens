import { expect, test, type Page } from "@playwright/test";

// The list of the pages of the site and the way of opening them live in one module, so that this
// suite walks exactly the pages the suite of the accessibility scans.
import { PAGES_UNDER_TEST, openThePage } from "./pages-under-test";

// The origin of the site comes from the module of the suite, so the origin this file answers to is
// the origin the configuration really serves.
import { SITE_ORIGIN } from "./site-origin";

/**
 * The end to end suite of the clean console of the public site.
 *
 * Why this file exists: a page that logs an error in the console tells the visitor nothing, and
 * the console is the place where the defects of the interface hide. The tour of the architecture
 * carried an invalid attribute of the SVG of its picture, and every visit of that page logged an
 * error in the console of the browser, and no suite of the repository said so. A defect of that
 * kind is invisible to a visitor and loud in the console, so the console is the layer that has to
 * be watched.
 *
 * Why the suite walks the pages of the list and not a list of its own: the pages of the site are
 * the ones the suite of the accessibility scans, and a second list of routes would be a second
 * truth about which pages exist. A page that no suite walks is a page that nobody checks.
 *
 * Why both the errors of the page and the messages of the console are watched: an exception that
 * the page recovers from never reaches the console of the browser, and the exception itself is the
 * worse defect of the two.
 *
 * Why only the errors are failures: the warnings and the notes of the browser are advice, and a
 * suite that fails on advice is a suite that nobody keeps.
 */

/**
 * One thing that the page logged that it should not have logged.
 *
 * Why the kind is kept: a reader of a red run has to know whether the page threw or whether the
 * page logged, because the two defects are fixed in two different places.
 */
interface ConsoleFailure {
  /** Where the failure came from. */
  readonly kind: "pageerror" | "console";
  /** The message of the failure, word for word. */
  readonly text: string;
}

/**
 * The model of the catalogue of the fake backend, in the shape the contract publishes.
 *
 * Why the fake exists: the live mode is the one room of the site that asks the backend of the
 * demo, and the static export of the site carries no backend. Without an answer the browser logs
 * the connection that never happened, and that message says nothing about the page: the page
 * answers that failure with its own alert. The gate gives the room a backend that answers the
 * catalogue of the models, the way the suite of the live path does, so that the console of the
 * page shows what the page itself does and nothing else.
 */
const MODEL = {
  profile_id: "openai-small",
  provider: "openai",
  model_id: "gpt-4o-mini",
  display_name: "A small model",
  capabilities: ["chat", "tool_calling"],
  status: "tested",
  enabled_in_public_demo: true,
  pricing: {
    source: "manual",
    last_verified: "2026-11-08",
    input_per_1m_usd: "0.40",
    output_per_1m_usd: "1.60",
  },
};

/**
 * The headers of the cross origin answers of the fake backend.
 *
 * Why the origin is exact and never a star: the calls of the browser carry the credentials, and a
 * star with credentials is illegal in the Fetch specification (ADR-040).
 */
function corsHeaders(): Record<string, string> {
  return {
    "Access-Control-Allow-Origin": SITE_ORIGIN,
    "Access-Control-Allow-Credentials": "true",
    "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Accept, X-LedgerLens-Schema-Version",
  };
}

/**
 * Installs the backend of the demo in front of the page.
 *
 * Why the interception is on the path and not on the origin: the origin of the backend is a build
 * variable of the site, and a test that pinned it would break the day the deployment changes it.
 * Every route of the live mode lives under `/v1`, and the static export publishes no route of that
 * name, so the path is enough to tell the calls of the backend from the files of the site.
 */
async function installTheBackendOfTheDemo(page: Page): Promise<void> {
  await page.route(
    (url) => url.pathname.startsWith("/v1/"),
    async (route) => {
      const request = route.request();
      const path = new URL(request.url()).pathname;

      // The browser asks for the permission of the cross origin call before it sends it.
      if (request.method() === "OPTIONS") {
        await route.fulfill({ status: 204, headers: corsHeaders() });
        return;
      }

      const json = async (status: number, payload: unknown): Promise<void> => {
        await route.fulfill({
          status,
          headers: { ...corsHeaders(), "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      };

      if (path === "/v1/sessions") {
        await json(200, { id: "session-1", expires_at: "2026-11-21T01:00:00+00:00", mode_capabilities: [] });
        return;
      }

      if (path === "/v1/models") {
        await json(200, { models: [MODEL] });
        return;
      }

      if (path.startsWith("/v1/models/")) {
        await json(200, {
          model: MODEL,
          price_known: true,
          price_note: "the price was verified on 2026-11-08 and comes from manual",
        });
        return;
      }

      await json(404, {
        code: "NOT_FOUND",
        message: "the route is not published",
        retryable: false,
        request_id: "request-0",
      });
    },
  );
}

for (const pageUnderTest of PAGES_UNDER_TEST) {
  test(`${pageUnderTest.name} logs no error in the console`, async ({ page }) => {
    const failures: ConsoleFailure[] = [];

    // The listeners are installed before the page is opened, so the first message of the page is
    // already watched.
    page.on("pageerror", (error: Error) => {
      failures.push({ kind: "pageerror", text: error.message });
    });
    page.on("console", (message) => {
      if (message.type() === "error") {
        failures.push({ kind: "console", text: message.text() });
      }
    });

    await installTheBackendOfTheDemo(page);
    await openThePage(page, pageUnderTest);

    expect(
      failures,
      `the page "${pageUnderTest.name}" logged ${failures.length} error(s) in the console:\n${failures
        .map((failure) => `      ${failure.kind}: ${failure.text}`)
        .join("\n")}`,
    ).toHaveLength(0);
  });
}
