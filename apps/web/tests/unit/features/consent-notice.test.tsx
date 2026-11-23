/**
 * The test of the consent of T036.
 *
 * Why this test exists: the visitor sends a key of their own, so the page has to say the three
 * things that matter before the send is enabled: the provider may charge the visitor, the key is
 * not stored, and the memory of the machine cannot be guaranteed to be erased. After the credential
 * is accepted, the page shows the words of the server and never a disclosure of its own.
 *
 * Every case runs with no key and no network: the consent never talks to the backend by itself.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApiKeyDialog } from "@/features/models/ApiKeyDialog";
import { CONSENT_SENTENCES, ConsentNotice, ConsentSummary } from "@/features/consent/ConsentNotice";

describe("the consent of the visitor", () => {
  it("shows the three sentences of the consent", () => {
    render(<ConsentNotice checked={false} onCheckedChange={() => {}} />);

    expect(CONSENT_SENTENCES).toHaveLength(3);
    for (const sentence of CONSENT_SENTENCES) {
      expect(screen.getByText(sentence)).toBeInTheDocument();
    }
  });

  it("reports the tick of the box", async () => {
    const user = userEvent.setup();
    const onCheckedChange = vi.fn();
    render(<ConsentNotice checked={false} onCheckedChange={onCheckedChange} />);

    await user.click(screen.getByRole("checkbox"));

    expect(onCheckedChange).toHaveBeenCalledWith(true);
  });

  it("keeps the send of the key disabled until the box is ticked", async () => {
    const user = userEvent.setup();
    render(<ApiKeyDialog open providers={["openai"]} onSubmit={() => {}} onClose={() => {}} />);

    const send = screen.getByRole("button", { name: /send the key/i });
    expect(send).toBeDisabled();

    await user.click(screen.getByRole("checkbox"));

    expect(send).toBeEnabled();
  });

  it("shows the words of the server when the answer arrives", () => {
    render(
      <ConsentNotice
        checked={true}
        onCheckedChange={() => {}}
        disclosure={{
          billing: "the provider of the visitor may charge the visitor",
          keyStorage: "the key lives in the memory of the server and dies with the session",
          keyErasure: "the key is dropped when the credential ends",
        }}
      />,
    );

    expect(screen.getByText(/the provider of the visitor may charge the visitor/)).toBeInTheDocument();
    expect(screen.getByText(/the key lives in the memory of the server/)).toBeInTheDocument();
    expect(screen.getByText(/the key is dropped when the credential ends/)).toBeInTheDocument();
  });

  it("invents no disclosure when the server sent none", () => {
    render(
      <ConsentNotice
        checked={true}
        onCheckedChange={() => {}}
        disclosure={{ billing: null, keyStorage: null, keyErasure: null }}
      />,
    );

    expect(screen.queryByText(/the server says about the billing/i)).toBeNull();
  });

  it("shows the sentences and the words of the server with no control at all", () => {
    render(
      <ConsentSummary
        disclosure={{
          billing: "the provider of the visitor may charge the visitor",
          keyStorage: "the key lives in the memory of the server and dies with the session",
          keyErasure: "the key is dropped when the credential ends",
        }}
      />,
    );

    for (const sentence of CONSENT_SENTENCES) {
      expect(screen.getByText(sentence)).toBeInTheDocument();
    }
    expect(screen.getByText(/the provider of the visitor may charge the visitor/)).toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).toBeNull();
  });
});
