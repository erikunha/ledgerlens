import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// The origin of the site comes from the module of the suite, so the origin this file asserts is the
// origin the configuration really serves, and the checks of the network cannot become vacuous.
import { SITE_ORIGIN } from "./site-origin";

/**
 * The end to end test of the live path.
 *
 * Why this file exists: the live mode is the half of the demo that asks the backend for a run with
 * the key of the visitor, and the only proof that the path works is a browser that walks it: the
 * visitor types the key, ticks the consent, picks a model, runs the case and reads what the run
 * cost. The unit tests of the page prove the rules of the page with a fake of the transport; this
 * suite proves the same path in a real browser, against the static export served as plain files.
 *
 * Why the backend of the demo is a fake and not the real one: the suite must never call a provider
 * and never spend the money of anybody. The fake is the backend of the demo wired with the fake
 * adapter of the domain (`FakeProviderAdapter` in `ledgerlens/byok/adapter.py`): it answers what
 * the scripted model answers, it counts the tokens the fake counted, and it opens no socket. The
 * answers of the fake are the shapes the routes of `ledgerlens/api/byok.py` publish, so the page
 * reads the same contract it reads in a deployment.
 *
 * Why the answers of the fake carry the headers of the cross origin: the browser of the visitor
 * calls the backend on another origin, so the browser asks for a permission before it accepts the
 * answer. The fake answers the permission the way the deployment does (ADR-040).
 *
 * Why the suite never switches a rule of axe off: a rule that is off hides a real problem from the
 * people who read the site, so the suite would rather be red than quiet.
 */

/** The identifier of the run of the cases of this suite. */
const RUN_ID = "run_0123456789abcdef";

/** The key the visitor types in the cases of this suite. It is not a key of any provider. */
const VISITOR_KEY = "sk-test-key-not-real";

/** The model of the catalogue of the fake backend, in the shape the contract publishes. */
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
    "Access-Control-Expose-Headers":
      "X-LedgerLens-Billing-Disclosure, X-LedgerLens-Key-Storage, X-LedgerLens-Key-Erasure",
  };
}

/**
 * The report of the cost of the run, as the route of the cost answers it.
 *
 * Why the amounts are the texts of the server: the money of a run is never a binary float, and the
 * frontend renders the texts it receives and computes nothing (FR-010, FR-011).
 */
const COST_REPORT = {
  run_id: RUN_ID,
  status: "completed",
  model_calls: 1,
  tool_calls: 0,
  calls_by_model: { "gpt-4o-mini": 1 },
  input_tokens: 120,
  output_tokens: 30,
  elapsed_seconds: 1.5,
  observed_cost_usd: "0.000096",
  estimated_cost_usd: "0.000048",
  price_known: true,
  money_cap_authoritative: false,
  cut_by: null,
  usage_without_reservation: [],
  note:
    "the observed cost and the estimated cost are two numbers: the first is what the provider reported and the second is what the run planned",
};

/**
 * The frames of the stream of the events of the run.
 *
 * Why the frames are the ones the backend writes: the backend writes the name of the event and the
 * JSON of the trace event, and a named event never reaches the generic listener of the browser
 * (ADR-040).
 */
function frame(eventType: string, payload: Record<string, unknown>, seq: number): string {
  const event = {
    schema_version: "1",
    run_id: RUN_ID,
    seq,
    at: "2026-11-21T17:00:00+00:00",
    event_type: eventType,
    payload,
    mode: "live_agent",
  };
  return `event: ${eventType}\ndata: ${JSON.stringify(event)}\n\n`;
}

/** What the fake backend saw while the page was talking to it. */
interface FakeBackend {
  /** The urls of the calls the page made. */
  readonly urls: string[];
  /** The bodies of the calls the page made. */
  readonly bodies: string[];
}

/**
 * Installs the backend of the demo, wired with the fake adapter, in front of the page.
 *
 * Why the interception is on the path and not on the origin: the origin of the backend is a build
 * variable of the site, and a test that pinned it would break the day the deployment changes it.
 * Every route of the live mode lives under `/v1`, and the static export publishes no route of that
 * name, so the path is enough to tell the calls of the backend from the files of the site.
 *
 * Why the stream of the run waits for the cancellation when the case asks for it: the run of the
 * visitor has to be going while the visitor presses the button that stops it, and a stream that
 * ended at once would let the visitor stop a run that is already over.
 */
async function installTheFakeBackend(
  page: Page,
  options: { waitForTheCancellation?: boolean } = {},
): Promise<FakeBackend> {
  const urls: string[] = [];
  const bodies: string[] = [];
  let streamRequests = 0;
  let releaseTheStream: (() => void) | null = null;
  const theStreamWaits = new Promise<void>((resolve) => {
    releaseTheStream = resolve;
  });

  await page.route(
    (url) => url.pathname.startsWith("/v1/"),
    async (route) => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      const method = request.method();
      const body = request.postData() ?? "";

      urls.push(request.url());
      if (body !== "") {
        bodies.push(body);
      }

      // The browser asks for the permission of the cross origin call before it sends it.
      if (method === "OPTIONS") {
        await route.fulfill({ status: 204, headers: corsHeaders() });
        return;
      }

      const json = (status: number, payload: unknown): Promise<void> =>
        route.fulfill({
          status,
          headers: { ...corsHeaders(), "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

      if (path === "/v1/sessions") {
        await json(200, { id: "session-1", expires_at: "2026-11-21T01:00:00+00:00", mode_capabilities: [] });
        return;
      }

      if (path === `/v1/models/${MODEL.profile_id}`) {
        await json(200, {
          model: MODEL,
          price_known: true,
          price_note: "the price was verified on 2026-11-08 and comes from manual",
        });
        return;
      }

      if (path === "/v1/models") {
        await json(200, { models: [MODEL] });
        return;
      }

      if (path === "/v1/credentials") {
        await route.fulfill({
          status: 200,
          headers: {
            ...corsHeaders(),
            "Content-Type": "application/json",
            "X-LedgerLens-Billing-Disclosure": "your provider may charge you for the calls of this run",
            "X-LedgerLens-Key-Storage": "the key is not stored: it lives in the memory of the server",
            "X-LedgerLens-Key-Erasure": "the erasure of the memory cannot be guaranteed",
          },
          body: JSON.stringify({
            handle: "handle-1",
            provider: "openai",
            created_at: "2026-11-21T00:00:00+00:00",
            expires_at: "2026-11-21T01:00:00+00:00",
          }),
        });
        return;
      }

      if (path === "/v1/sandboxes") {
        await json(200, {
          id: "sbx-1",
          base_snapshot_id: "snap-1",
          snapshot_sha256: "hash-of-the-base",
          revision: 0,
          expires_at: "2026-11-21T01:00:00+00:00",
        });
        return;
      }

      if (path.endsWith("/cancel")) {
        // The run was going, so the server answers that the cancellation is a best effort: a call
        // was already at the provider (FR-019).
        await json(200, {
          run_id: RUN_ID,
          status: "cancelling",
          best_effort: true,
          message:
            "the run was cancelled; the cancellation of a call that was already at the provider is a best effort and is not a guarantee",
        });
        if (releaseTheStream !== null) {
          releaseTheStream();
        }
        return;
      }

      if (path.endsWith("/events")) {
        streamRequests += 1;
        if (streamRequests > 1) {
          // A browser that reconnects would receive the whole stream of the run again, so the
          // second answer carries nothing and the browser stops there.
          await route.fulfill({ status: 204, headers: corsHeaders() });
          return;
        }
        if (options.waitForTheCancellation === true) {
          await theStreamWaits;
        }
        const cancelled = options.waitForTheCancellation === true;
        const body = cancelled
          ? frame("run.cancelled", { status: "cancelled", best_effort: true }, 1)
          : [
              frame("run.started", { provider: "openai", model_id: MODEL.model_id }, 1),
              frame(
                "run.status",
                { model_calls: 1, tool_calls: 0, input_tokens: 120, output_tokens: 30, elapsed_seconds: 1.5 },
                2,
              ),
              frame("run.completed", { status: "completed", best_effort: false }, 3),
            ].join("");
        await route.fulfill({
          status: 200,
          headers: { ...corsHeaders(), "Content-Type": "text/event-stream" },
          body,
        });
        return;
      }

      if (path.endsWith("/cost")) {
        await json(200, { ...COST_REPORT, status: options.waitForTheCancellation ? "cancelled" : "completed" });
        return;
      }

      if (path === "/v1/live-runs") {
        await json(201, { run_id: RUN_ID, status: "running", mode: "live_agent" });
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

  return {
    urls,
    bodies,
  };
}

/**
 * Walks the live path with the visitor: the key, the consent, the model and the run.
 *
 * Why the four acts: the dialog is closed until the visitor asks for it, the send waits for the
 * tick of the consent, the run needs a model of the catalogue, and the run needs a key.
 */
async function runTheCase(page: Page): Promise<void> {
  await page.getByRole("button", { name: /use your own key/i }).click();
  await page.getByLabel(/the key of your provider/i).fill(VISITOR_KEY);
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: /send the key/i }).click();

  await expect(page.getByText(/the server accepted the key of your provider/i)).toBeVisible();

  await page.getByRole("radio", { name: /a small model/i }).check();
  await page.getByRole("button", { name: /run the case/i }).click();
}

test("the visitor runs a case with a key of their own and reads what the run cost", async ({ page }) => {
  const backend = await installTheFakeBackend(page);

  await page.goto("/live");
  await expect(page.getByRole("heading", { level: 1, name: "Live mode" })).toBeVisible();
  await expect(page.getByRole("radio", { name: /a small model/i })).toBeVisible();

  await runTheCase(page);

  // The run is on the screen, with the identifier the server gave it.
  await expect(page.getByRole("heading", { name: "The run", exact: true })).toBeVisible();
  await expect(page.getByText(RUN_ID)).toBeVisible();

  // The cost panel shows the two amounts of the server, apart, and computes nothing.
  const cost = page.getByRole("region", { name: /the cost of the run/i });
  await expect(cost.getByText("0.000096")).toBeVisible();
  await expect(cost.getByText("0.000048")).toBeVisible();

  // The key travelled in the body of the credential and in no url of the page.
  expect(backend.bodies.some((body) => body.includes(VISITOR_KEY))).toBe(true);
  expect(backend.urls.some((url) => url.includes(VISITOR_KEY))).toBe(false);
  expect(backend.urls.some((url) => url.includes("handle-1"))).toBe(false);
});

test("the visitor stops a run and the page says that the cancellation is a best effort", async ({ page }) => {
  await installTheFakeBackend(page, { waitForTheCancellation: true });

  await page.goto("/live");
  await expect(page.getByRole("heading", { level: 1, name: "Live mode" })).toBeVisible();

  await runTheCase(page);

  // The control that stops the run is there while the run is going, and it says what it does.
  const stop = page.getByRole("button", { name: /stop the run/i });
  await expect(stop).toBeVisible();
  await expect(page.getByText(/stopping a run ends it/i)).toBeVisible();

  await stop.click();

  // The server flagged the cancellation as a best effort, and the page says so. The notice is an
  // alert, so a reader of a screen reader hears it when it appears.
  const notice = page.getByRole("alert");
  await expect(notice.getByText(/the cancellation was a best effort/i)).toBeVisible();
  await expect(
    notice.getByText(/a call of the provider was already in flight when you stopped the run/i),
  ).toBeVisible();
  await expect(notice.getByText(/it may finish anyway/i)).toBeVisible();
  await expect(notice.getByText(/the trace keeps the events that already happened/i)).toBeVisible();
});

test("the live page has no accessibility violation", async ({ page }) => {
  await installTheFakeBackend(page);

  await page.goto("/live");
  await expect(page.getByRole("heading", { level: 1, name: "Live mode" })).toBeVisible();
  await expect(page.getByRole("radio", { name: /a small model/i })).toBeVisible();

  const results = await new AxeBuilder({ page }).analyze();

  expect(
    results.violations,
    `the live page has ${results.violations.length} accessibility violation(s) found by axe:\n${results.violations
      .map((violation) => `    rule: ${violation.id}\n    help: ${violation.help}`)
      .join("\n")}`,
  ).toHaveLength(0);
});
