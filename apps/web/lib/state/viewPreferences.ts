/**
 * The store of the preferences of the view.
 *
 * Why this file exists: a visitor who comes back to the replay expects the tab and the speed they chose to still be
 * there. The preferences are kept in the `localStorage` of the origin of the site, under one key, and never in a
 * cookie: the cookie of the origin of the backend is the identity of the session of the visitor, and the recorded demo
 * must never touch it.
 *
 * Only the two fields of the preferences are stored. A stored value that does not parse falls back to the defaults,
 * and a stored field that carries a value the contract does not define is ignored. The store is never allowed to throw:
 * a server render has no storage at all, and a browser that refuses the storage still has to show the replay.
 */

import {
  DEFAULT_VIEW_PREFERENCES,
  isPlaybackSpeed,
  isReplayTab,
  type ViewPreferences,
} from "@/lib/state/urlState";

/** The key of the preferences in the storage of the origin of the site. */
export const VIEW_PREFERENCES_STORAGE_KEY = "ledgerlens.view-preferences.v1";

/**
 * Finds the storage the preferences live in.
 *
 * A caller may pass a storage of its own, which is how a test passes a fake one. Without one the storage of the
 * browser is used, and a render without a browser has no storage at all.
 */
function resolveStorage(storage?: Storage): Storage | null {
  if (storage) {
    return storage;
  }
  try {
    if (typeof window === "undefined") {
      return null;
    }
    return window.localStorage;
  } catch {
    // A browser that refuses the storage of the origin leaves the interface with no storage, which is not an error.
    return null;
  }
}

/**
 * Reads the preferences of the view out of the storage.
 *
 * A storage that holds nothing, a payload that does not parse and a field that carries an illegal value all fall back
 * to the defaults of that field.
 */
export function loadViewPreferences(storage?: Storage): ViewPreferences {
  const target = resolveStorage(storage);
  if (!target) {
    return { ...DEFAULT_VIEW_PREFERENCES };
  }

  let raw: string | null = null;
  try {
    raw = target.getItem(VIEW_PREFERENCES_STORAGE_KEY);
  } catch {
    return { ...DEFAULT_VIEW_PREFERENCES };
  }
  if (raw === null || raw === "") {
    return { ...DEFAULT_VIEW_PREFERENCES };
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    // A payload that does not parse is a payload that says nothing, so the defaults stand.
    return { ...DEFAULT_VIEW_PREFERENCES };
  }
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    return { ...DEFAULT_VIEW_PREFERENCES };
  }

  const record = parsed as Record<string, unknown>;
  const tab = record.tab;
  const speed = record.speed;
  return {
    tab: typeof tab === "string" && isReplayTab(tab) ? tab : DEFAULT_VIEW_PREFERENCES.tab,
    speed: typeof speed === "number" && isPlaybackSpeed(speed) ? speed : DEFAULT_VIEW_PREFERENCES.speed,
  };
}

/**
 * Writes the preferences of the view into the storage.
 *
 * Only the two fields of the preferences are written, and a storage that refuses the write leaves the interface
 * working with the preferences it already has.
 */
export function saveViewPreferences(preferences: ViewPreferences, storage?: Storage): void {
  const target = resolveStorage(storage);
  if (!target) {
    return;
  }
  try {
    target.setItem(
      VIEW_PREFERENCES_STORAGE_KEY,
      JSON.stringify({ tab: preferences.tab, speed: preferences.speed }),
    );
  } catch {
    // The storage refused the write, so the preferences of this visit stay in the URL and nothing else breaks.
  }
}

/**
 * Removes the preferences of the view from the storage.
 */
export function clearViewPreferences(storage?: Storage): void {
  const target = resolveStorage(storage);
  if (!target) {
    return;
  }
  try {
    target.removeItem(VIEW_PREFERENCES_STORAGE_KEY);
  } catch {
    // The storage refused the removal, so the preferences stay where they were.
  }
}

/** Every symbol this module exports, so that a reader sees the whole surface of the store at once. */
export const __all__ = [
  "VIEW_PREFERENCES_STORAGE_KEY",
  "loadViewPreferences",
  "saveViewPreferences",
  "clearViewPreferences",
] as const;
