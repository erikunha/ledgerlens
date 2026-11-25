/**
 * The sentence that says the answer comes from an AI agent is on the page of the live mode.
 *
 * Why this test exists: Article 50 of the EU AI Act has applied since 2 August 2026, and the surface of the
 * public site that answers a person has to say that the answer comes from an AI agent and that a person reviews
 * the cases that need a review. The live mode is that surface: it is the page where a run of the agent happens
 * and where the answer comes from.
 *
 * What it proves: the sentence reaches the rendered page, and not only the source of the page. The page is
 * rendered as the visitor receives it, with no key and no network, because the backend of the case is a fake
 * that answers the routes the page calls.
 *
 * Why the words are written here and not read from the file of the domain: a test that reads the expected words
 * from the very file it checks proves nothing about the words. The words of the domain are pinned on the Python
 * side, in `tests/test_ai_disclosure.py`, which also proves that the page reads that file.
 */

import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import LivePage from "@/app/(public)/live/page";

/**
 * The sentence the domain holds, written here on purpose.
 *
 * Why it is a literal and not an import: the point of the case is the words a person reads, so the case has to
 * say which words they are.
 */
const SENTENCE = "The answer is produced by an AI agent, and a person reviews the cases that need review.";

/**
 * Builds an answer of the fake backend, with the shape the transport of the browser expects.
 *
 * Why the fake exists: the page asks the catalog of the models when it opens, and a case that asks nobody
 * would prove nothing about a page that opens with a request.
 */
function answer(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => (body === null ? "" : JSON.stringify(body)),
    headers: new Headers(),
  } as unknown as Response;
}

/**
 * The fake backend of the page: it answers the routes the page calls and asks nobody.
 *
 * Why the catalog is empty: the case is about the sentence of the header, and a model in the catalog would
 * only add a second thing to the page that the case does not look at.
 */
function fakeBackend() {
  const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/v1/models")) {
      return answer(200, { models: [] });
    }
    return answer(200, { id: "session-1", expires_at: "", mode_capabilities: [] });
  });
  return fetchImpl as unknown as typeof fetch;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the disclosure of the AI agent", () => {
  it("shows the sentence on the page of the live mode", () => {
    vi.stubGlobal("fetch", fakeBackend());

    render(<LivePage />);

    expect(screen.getByText(SENTENCE)).toBeInTheDocument();
  });
});
