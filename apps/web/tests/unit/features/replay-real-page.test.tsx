/**
 * The test of the page of the catalog of the scenarios recorded with a real model.
 *
 * Why this test exists: the site publishes two catalogs of recorded scenarios, the recordings of the scripted model
 * and the recordings of a real model, and each one has its own page (ADR-075). The page of the catalog of a real
 * model has to show the cards that the repository published for that catalog and has to link to the route of that
 * catalog, and never to the route of the other one: a card that leads to the recording of the other catalog is a card
 * that lies about what the visitor is about to read.
 *
 * Why the page is rendered WITHOUT a provider around it: the page brings its own provider, the one that reads the
 * catalog of a real model, and a provider around it would be inherited by that one, which would then never read
 * anything. A test that puts a provider around the page therefore proves nothing about which catalog the page reads,
 * and the page would read the catalog of the scripted model with the very same test green.
 *
 * Why the case proves the root that was asked for: the root of the artifacts is the difference between the two
 * catalogs, and a page that asked for the root of the other one would show the recordings of the other catalog under
 * the name of this one.
 *
 * Every case runs with no key and no network: the fetch of the runtime is a fake that answers with the catalog the
 * case decides.
 */

import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ReplayRealPage from "@/app/(public)/replay-real/page";

/** The card of the scenario in the published catalog of a real model. */
const PUBLISHED_CARD = {
  bundle_digest: "7302099601f0d8f63c539c94d58cb2e4616f9c6875af192bd8abb148fa0c3c2c",
  bundle_path: "s01",
  capture_kind: "real_model_recorded",
  code_sha: "9ffb3cbcfcb1a17883a63a56a7e5954a753322b1",
  concepts: ["read_only_ledger_query", "policy_retrieval"],
  data_origin: "UCI Online Retail II",
  id: "S01",
  name: "fx_markup_refund",
  provenance_sha256: "c879b10e32cc1f889cac717141da83da78bd3ac2497ebaf774a05090a73d06e5",
  question: "Why was the BRL refund for TX-2048 lower than the EUR payment?",
  status: "Recorded",
};

/** The URLs that the case asked for, so that the case can prove which root it read. */
const askedFor: string[] = [];

/**
 * Stubs the fetch of the runtime with the catalog the case decides.
 *
 * Why the stub answers the catalog and nothing else: the page reads the catalog of the scenarios and nothing more,
 * and a stub that answered anything else would hide a page that read something it should not.
 */
function stubCatalog(catalog: unknown): void {
  const body = JSON.stringify(catalog);
  askedFor.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      askedFor.push(url);
      return {
        ok: true,
        status: 200,
        text: async () => (url.endsWith("index.json") ? body : ""),
      } as unknown as Response;
    }),
  );
}

/** Renders the page of the catalog, with no provider around it. */
function renderPage(catalog: unknown): void {
  stubCatalog(catalog);
  render(<ReplayRealPage />);
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the page of the catalog of a real model", () => {
  it("reads the catalog of a real model from its own root", async () => {
    // It proves that the page reads the catalog of the catalog of a real model and not the root of the
    // scripted model: a page that asked for the other root would show the recordings of the other
    // catalog under the name of this one (ADR-075).
    renderPage([PUBLISHED_CARD]);

    await screen.findByRole("heading", { name: "The scenarios" });

    expect(askedFor).toContain("/replay-real/index.json");
    expect(askedFor).not.toContain("/replay/index.json");
  });

  it("says that the recordings were made with a real model", async () => {
    // It proves that the page tells the visitor what the catalog holds, because a recording of a real model and a
    // recording of a scripted model are two different things to read (ADR-075).
    renderPage([PUBLISHED_CARD]);

    expect(await screen.findByRole("heading", { name: "Recorded with a real model" })).toBeInTheDocument();
    expect(document.body.textContent ?? "").toContain("mode: live_agent");
    expect(document.body.textContent ?? "").toContain("capture: real_model_recorded");
  });

  it("says out loud that the recordings are not reproducible byte for byte", async () => {
    // It proves that the page is honest about the part of the recording that a reader cannot check: the same question
    // asked twice of a real model does not give the same answer, and the site says so (ADR-075).
    renderPage([PUBLISHED_CARD]);

    await screen.findByRole("heading", { name: "Recorded with a real model" });

    expect(document.body.textContent ?? "").toContain("not reproducible byte for byte");
    expect(document.body.textContent ?? "").toContain("the same judge");
  });

  it("shows the scenarios of the published catalog", async () => {
    // It proves that the catalog shows the card of the scenario exactly as the repository publishes it.
    renderPage([PUBLISHED_CARD]);

    expect(await screen.findByRole("heading", { name: "The scenarios" })).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: "S01 - Why was the BRL refund for TX-2048 lower than the EUR payment?",
      }),
    ).toBeInTheDocument();
  });

  it("links the card of the scenario to the route of the catalog of a real model", async () => {
    // It proves that the card leads to the route of its own catalog and never to the route of the other one: the same
    // identifier under the route of the sandbox would open the recording of the scripted model (ADR-075).
    renderPage([PUBLISHED_CARD]);

    const link = await screen.findByRole("link", { name: "S01 - fx_markup_refund" });
    expect(link).toHaveAttribute("href", "/replay-real/scenario/S01");
  });

  it("offers the catalog of the scripted model", async () => {
    // It proves that the two catalogs find each other, so that a visitor who reads one of them can reach the other.
    renderPage([PUBLISHED_CARD]);

    const link = await screen.findByRole("link", { name: "Open the sandbox catalog" });
    expect(link).toHaveAttribute("href", "/replay");
  });

  it("refuses a catalog that does not pass the contract", async () => {
    // It proves that a broken catalog is refused with a reason and that no card of it is shown, so that the visitor
    // never sees a half read list (ADR-042, ADR-043).
    renderPage({ scenarios: [PUBLISHED_CARD], schema_version: "1" });

    expect(await screen.findByText(/did not pass the contract/)).toBeInTheDocument();
    expect(screen.queryByText("S01 - fx_markup_refund")).toBeNull();
    expect(screen.queryByRole("link", { name: "S01 - fx_markup_refund" })).toBeNull();
  });
});
