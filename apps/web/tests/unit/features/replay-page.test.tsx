/**
 * The test of the page of the catalog of the scenarios.
 *
 * Why this test exists: the catalog of the site is the way a visitor finds a recording, and it has to show exactly the
 * scenarios that the repository publishes and to link to the route of each one of them. A catalog that does not pass
 * the contract is refused with a reason and never shown as a half read list (ADR-042, ADR-043).
 *
 * Every case runs with no key and no network: the loader of the case is a function of the test, and the fetch of the
 * runtime is a fake that answers with the same catalog, so the page reads the published artifacts either way.
 */

import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ReplayPage from "@/app/(public)/replay/page";
import { ScenarioCatalogProvider } from "@/lib/api/provider";

/** The card of the scenario in the published catalog, as `site/replay/index.json` holds it. */
const PUBLISHED_CARD = {
  bundle_digest: "bbbe1e54fcae712df66a3a6096838ab5b7f8c938e2e47b7ef6681e43cafa84ac",
  bundle_path: "s01",
  capture_kind: "scripted_fixture",
  code_sha: "9dc3af946b223496c7ed2e897b1e4152bbf9234f",
  concepts: ["read_only_ledger_query", "policy_retrieval"],
  data_origin: "UCI Online Retail II",
  data_origin_detail: {
    dataset: "UCI Online Retail II",
    kind: "public-derived",
    license: "CC BY 4.0",
    reference: "https://doi.org/10.24432/C5CG6D",
    seed: 42,
  },
  id: "S01",
  name: "fx_markup_refund",
  provenance_sha256: "c879b10e32cc1f889cac717141da83da78bd3ac2497ebaf774a05090a73d06e5",
  question: "Why was the BRL refund for TX-2048 lower than the EUR payment?",
  status: "Recorded",
};

/**
 * The loader of the case: it answers with the catalog that the case decides.
 *
 * Why the loader and the fetch are both given the same answer: the page reads the catalog through the provider of the
 * catalog, and the provider reads it through the loader of the case. The fetch of the runtime is stubbed with the same
 * answer, so the case proves the same thing whichever of the two the page uses.
 */
function stubCatalog(catalog: unknown): void {
  const body = JSON.stringify(catalog);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      return {
        ok: true,
        status: 200,
        text: async () => (url.endsWith("index.json") ? body : ""),
      } as unknown as Response;
    }),
  );
}

/** Renders the page of the catalog with a loader of the case. */
function renderPage(catalog: unknown): void {
  stubCatalog(catalog);
  const loader = vi.fn(async () => {
    try {
      const parsed = JSON.parse(JSON.stringify(catalog)) as unknown;
      if (!Array.isArray(parsed)) {
        return { error: "the catalog of the scenarios did not pass the contract of the published artifacts" };
      }
      return parsed as never;
    } catch {
      return { error: "the catalog of the scenarios is not a JSON document" };
    }
  });

  render(
    <ScenarioCatalogProvider loader={loader}>
      <ReplayPage />
    </ScenarioCatalogProvider>,
  );
}

/**
 * Renders the page of the catalog while the catalog is still being read.
 *
 * Why the loader never answers: the case has to see the page in the state that the visitor sees
 * between the first drawing and the answer of the reading, and the only way to hold that state is a
 * reading that never finishes.
 */
function renderPageWhileTheCatalogIsBeingRead(): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      () =>
        new Promise<Response>(() => {
          // the reading of the catalog never finishes
        }),
    ),
  );

  const loader = vi.fn(
    () =>
      new Promise<never>(() => {
        // the reading of the catalog never finishes
      }),
  );

  render(
    <ScenarioCatalogProvider loader={loader}>
      <ReplayPage />
    </ScenarioCatalogProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the page of the catalog of the scenarios", () => {
  it("shows the scenarios of the published catalog", async () => {
    // It proves that the catalog shows the card of the scenario exactly as the repository publishes it.
    renderPage([PUBLISHED_CARD]);

    expect(await screen.findByRole("heading", { name: "The scenarios" })).toBeInTheDocument();
    expect(document.body.textContent ?? "").toContain("UCI Online Retail II");
    expect(
      screen.getByRole("heading", {
        name: "S01 - Why was the BRL refund for TX-2048 lower than the EUR payment?",
      }),
    ).toBeInTheDocument();
  });

  it("links the card of the scenario to the route of the scenario", async () => {
    // It proves that the card of the catalog leads to the route of the scenario and not to a guess at run time.
    renderPage([PUBLISHED_CARD]);

    const link = await screen.findByRole("link", { name: "S01 - fx_markup_refund" });
    expect(link).toHaveAttribute("href", "/replay/scenario/S01");
  });

  it("refuses a catalog that does not pass the contract", async () => {
    // It proves that a broken catalog is refused with a reason and that no card of it is shown, so that the visitor
    // never sees a half read list.
    renderPage({ scenarios: [PUBLISHED_CARD], schema_version: "1" });

    expect(await screen.findByText(/did not pass the contract/)).toBeInTheDocument();
    expect(screen.queryByText("S01 - fx_markup_refund")).toBeNull();
    expect(screen.queryByRole("link", { name: "S01 - fx_markup_refund" })).toBeNull();
  });

  it("shows the concepts that the scenario demonstrates", async () => {
    // It proves that the card shows the concepts of the scenario, because the concepts are part of
    // what the catalog publishes and a card that throws them away is a card that hides what the
    // scenario demonstrates.
    renderPage([PUBLISHED_CARD]);

    await screen.findByRole("heading", { name: "The scenarios" });

    expect(screen.getByText("read_only_ledger_query")).toBeInTheDocument();
    expect(screen.getByText("policy_retrieval")).toBeInTheDocument();
  });

  it("shows a skeleton while the catalog is being read", async () => {
    // It proves that the page says that it is loading while it loads, because a page that shows a
    // title over nothing reads as a broken page.
    renderPageWhileTheCatalogIsBeingRead();

    const skeleton = await screen.findByRole("status", {
      name: "The catalog of the scenarios is being read",
    });
    expect(skeleton).toBeInTheDocument();
  });

  it("shows no skeleton once the catalog is read", async () => {
    // It proves that the placeholder of the reading goes away when the cards of the scenarios are
    // on the screen, so the visitor never reads a page that is half drawn.
    renderPage([PUBLISHED_CARD]);

    await screen.findByRole("heading", { name: "The scenarios" });

    expect(screen.queryByRole("status", { name: "The catalog of the scenarios is being read" })).toBeNull();
  });
});
