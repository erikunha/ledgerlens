/**
 * The test of the page of the recorded demo.
 *
 * Why this test exists: the page reads the catalog of the scenarios from the static export and it
 * has to read it exactly as the repository publishes it, a list of cards that carry `id` and a
 * `data_origin` that is a string. The page validates the catalog with the validator of the
 * repository and with no mapping by hand, so a catalog that does not pass the contract is refused
 * with a reason and not shown as a half read list (ADR-042).
 *
 * Every case runs with no key and no network: the fetch of the case is a fake that answers with
 * the artifacts the repository publishes.
 */

import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ReplayPage from "@/app/(public)/replay/page";

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

/** The manifest of the published bundle, as `site/replay/s01/manifest.json` holds it. */
const PUBLISHED_MANIFEST = {
  bundle_schema_version: "1",
  capture_kind: "scripted_fixture",
  code_sha: "9dc3af946b223496c7ed2e897b1e4152bbf9234f",
  created_at: "2026-11-14T11:00:14+00:00",
  events: 1,
  files: { "events.jsonl": "577939e532327f3af1a3897612f622d96edc27a620646437fb02c5fa5318de13" },
  mode: "deterministic_sandbox",
  model_profile: "scripted-fixture",
  note: "Deterministic execution of the scenario S01, account C-0412, with the scripted model and the recorded exchange rate. This is not a live execution and it calls no model.",
  policy_version: "policies-v1",
  recorded_at: "2026-11-14T11:00:14+00:00",
  run_id: "replay-s01",
  scenario: "S01",
  snapshot_sha256: "26849ada6f60c63fa30a0b085fd1ff473508d18a5892498cade13b7dc436ee2f",
};

/** One event of the recording, with the shape the contract publishes. */
const PUBLISHED_EVENT = {
  schema_version: "1",
  run_id: "replay-s01",
  seq: 1,
  at: "2026-11-14T11:00:13.128+00:00",
  event_type: "run.started",
  payload: { question: PUBLISHED_CARD.question },
  snapshot_sha256: "26849ada6f60c63fa30a0b085fd1ff473508d18a5892498cade13b7dc436ee2f",
  mode: "deterministic_sandbox",
};

/**
 * The fetch of the case: it answers with the catalog, the manifest and the events.
 *
 * Why the catalog is a parameter: the case that proves the refusal needs a catalog that does not
 * pass the contract, and every other answer is the published one.
 */
function fakeFetch(catalog: unknown): typeof fetch {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    const body = url.endsWith("index.json")
      ? JSON.stringify(catalog)
      : url.endsWith("manifest.json")
        ? JSON.stringify(PUBLISHED_MANIFEST)
        : url.endsWith("events.jsonl")
          ? `${JSON.stringify(PUBLISHED_EVENT)}\n`
          : "";
    return { ok: true, status: 200, text: async () => body } as unknown as Response;
  }) as unknown as typeof fetch;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the page of the recorded demo", () => {
  it("shows the scenarios of the published catalog", async () => {
    vi.stubGlobal("fetch", fakeFetch([PUBLISHED_CARD]));

    render(<ReplayPage />);

    expect(await screen.findByText("S01 - fx_markup_refund")).toBeInTheDocument();
    expect(screen.getByText("data: UCI Online Retail II")).toBeInTheDocument();
  });

  it("refuses a catalog that does not pass the contract", async () => {
    vi.stubGlobal("fetch", fakeFetch({ scenarios: [PUBLISHED_CARD], schema_version: "1" }));

    render(<ReplayPage />);

    expect(await screen.findByText(/did not pass the contract/)).toBeInTheDocument();
    expect(screen.queryByText("S01 - fx_markup_refund")).toBeNull();
  });
});
