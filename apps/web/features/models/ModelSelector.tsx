"use client";

/**
 * The picker of the model of the live run.
 *
 * Why this file exists: the visitor chooses what the live run thinks with, and the catalog of the
 * server is the only source of that choice. The picker therefore shows what the server published
 * and nothing else: a profile that is not tested, or that the public demo does not enable, is never
 * offered, because offering it would promise a run the demo does not make.
 *
 * The price of the model is shown before the first call, read from the route of the price, so the
 * visitor reads where the price comes from before the run and not after it.
 */

import { Badge } from "@/components/ui/Badge";
import type { ModelProfile } from "@/lib/api/live";

/**
 * The props of the picker.
 *
 * Why the price is optional: the catalog of the server does not carry the note of the price, and
 * the note only arrives when the visitor asks for the price of the profile they chose.
 */
export interface ModelSelectorProps {
  /** The catalog of the server, with every profile it published. */
  profiles: ModelProfile[];
  /** The profile the visitor chose, or `null` while the choice is not made. */
  selectedProfileId: string | null;
  /** Called with the profile the visitor chose. */
  onSelect: (profileId: string) => void;
  /** What the server says about the price of the chosen profile. */
  priceNote?: string | null;
  /** Whether the price of the chosen profile was verified. */
  priceKnown?: boolean | null;
}

/**
 * The picker of the model.
 *
 * The options are radio buttons inside a fieldset, so a keyboard visitor reaches them with the
 * arrow keys and a screen reader announces the group with its legend.
 */
export function ModelSelector({
  profiles,
  selectedProfileId,
  onSelect,
  priceNote,
  priceKnown,
}: ModelSelectorProps) {
  const offered = profiles.filter((profile) => profile.enabled_in_public_demo && profile.status === "tested");

  return (
    <fieldset className="flex flex-col gap-3">
      <legend className="text-sm font-semibold">Model of the run</legend>

      {offered.length === 0 ? (
        <p className="text-sm text-text-muted">
          The catalog of the server offers no model for the public demo right now.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {offered.map((profile) => (
            <li key={profile.profile_id}>
              <label className="flex flex-wrap items-center gap-2 rounded border border-line p-3">
                <input
                  type="radio"
                  name="ledgerlens-model"
                  className="h-4 w-4"
                  value={profile.profile_id}
                  checked={selectedProfileId === profile.profile_id}
                  onChange={() => onSelect(profile.profile_id)}
                />
                <span className="text-sm font-medium">{profile.display_name}</span>
                <Badge>{profile.provider}</Badge>
                <Badge>status: {profile.status}</Badge>
                {profile.capabilities.map((capability) => (
                  <Badge key={capability}>{capability}</Badge>
                ))}
              </label>
            </li>
          ))}
        </ul>
      )}

      {priceKnown === false ? (
        <p className="text-sm text-text-muted">
          The price of the model is unknown: the server has no verified price for it, so no amount of
          money is shown for the run.
        </p>
      ) : null}
      {priceNote ? <p className="text-sm text-text-subtle">{priceNote}</p> : null}
    </fieldset>
  );
}
