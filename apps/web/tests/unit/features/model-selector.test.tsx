/**
 * The test of the picker of the model.
 *
 * Why this test exists: the picker is the only place where the visitor chooses what the live run
 * thinks with, so the catalog of the server has to be filtered before it is shown. A profile that
 * is not tested, or that the public demo does not enable, must never be offered.
 *
 * Every case runs with no key and no network: the profiles are given to the component directly.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ModelSelector } from "@/features/models/ModelSelector";
import type { ModelProfile } from "@/lib/api/live";

/** One profile of the catalog, with the fields a case wants to change. */
function profile(overrides: Partial<ModelProfile>): ModelProfile {
  return {
    profile_id: "openai-gpt-4.1-mini",
    provider: "openai",
    model_id: "gpt-4.1-mini",
    display_name: "GPT-4.1 mini",
    capabilities: ["chat", "tool_calling"],
    status: "tested",
    enabled_in_public_demo: true,
    pricing: { source: "provider", last_verified: null, input_per_1m_usd: null, output_per_1m_usd: null },
    ...overrides,
  };
}

describe("the picker of the model", () => {
  it("offers only the profiles that are tested and enabled in the public demo", () => {
    render(
      <ModelSelector
        profiles={[
          profile({}),
          profile({ profile_id: "experimental", display_name: "Experimental model", status: "experimental" }),
          profile({
            profile_id: "disabled-in-demo",
            display_name: "Model out of the demo",
            enabled_in_public_demo: false,
          }),
        ]}
        selectedProfileId={null}
        onSelect={() => {}}
      />,
    );

    expect(screen.getByRole("radio", { name: /GPT-4\.1 mini/ })).toBeInTheDocument();
    expect(screen.queryByRole("radio", { name: /Experimental model/ })).toBeNull();
    expect(screen.queryByRole("radio", { name: /Model out of the demo/ })).toBeNull();
  });

  it("shows the status and the capabilities of the profile", () => {
    render(
      <ModelSelector profiles={[profile({})]} selectedProfileId={null} onSelect={() => {}} />,
    );

    expect(screen.getByText("status: tested")).toBeInTheDocument();
    expect(screen.getByText("chat")).toBeInTheDocument();
    expect(screen.getByText("tool_calling")).toBeInTheDocument();
  });

  it("reports the profile the visitor chose", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <ModelSelector profiles={[profile({})]} selectedProfileId={null} onSelect={onSelect} />,
    );

    await user.click(screen.getByRole("radio", { name: /GPT-4\.1 mini/ }));

    expect(onSelect).toHaveBeenCalledWith("openai-gpt-4.1-mini");
  });

  it("says that the price is unknown when the server does not know it", () => {
    render(
      <ModelSelector
        profiles={[profile({})]}
        selectedProfileId={null}
        onSelect={() => {}}
        priceKnown={false}
        priceNote="the price of this model was never verified"
      />,
    );

    expect(screen.getByText(/price of the model is unknown/i)).toBeInTheDocument();
    expect(screen.getByText("the price of this model was never verified")).toBeInTheDocument();
  });
});
