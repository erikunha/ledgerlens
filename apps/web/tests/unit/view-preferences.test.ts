/**
 * The test of the store of the preferences of the view.
 *
 * Why this test exists: the preferences of the view are the last thing a visitor of the site gives to the origin of
 * the site, and the rule of the repository is that the recorded demo never touches the identity of the session. The
 * store is therefore the `localStorage` of the origin of the site and never a cookie, and the payload it holds is the
 * two fields of the preferences and nothing else.
 *
 * Every case runs with no key and no network: the store is given a storage of its own and the cases of the repository
 * are published artifacts of the site.
 */

import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  VIEW_PREFERENCES_STORAGE_KEY,
  clearViewPreferences,
  loadViewPreferences,
  saveViewPreferences,
} from "@/lib/state/viewPreferences";
import { DEFAULT_VIEW_PREFERENCES } from "@/lib/state/urlState";

/**
 * A storage of the test, with the shape of the `Storage` of the browser.
 *
 * Why the case builds its own: the store must never write to the storage of a real visitor, and the case has to be
 * able to look at what was written.
 */
function fakeStorage(): Storage & { readonly written: Map<string, string> } {
  const written = new Map<string, string>();
  const values = new Map<string, string>();
  return {
    written,
    get length(): number {
      return values.size;
    },
    clear(): void {
      values.clear();
    },
    getItem(key: string): string | null {
      return values.has(key) ? (values.get(key) as string) : null;
    },
    key(index: number): string | null {
      return Array.from(values.keys())[index] ?? null;
    },
    removeItem(key: string): void {
      values.delete(key);
    },
    setItem(key: string, value: string): void {
      values.set(key, value);
      written.set(key, value);
    },
  } as Storage & { readonly written: Map<string, string> };
}

/** The writes the document received, so that the case can prove that no cookie was written. */
let cookieWrites: string[] = [];

beforeEach(() => {
  cookieWrites = [];
  Object.defineProperty(document, "cookie", {
    configurable: true,
    get: () => "",
    set: (value: string) => {
      cookieWrites.push(value);
    },
  });
});

afterEach(() => {
  localStorage.clear();
  delete (document as unknown as { cookie?: unknown }).cookie;
});

describe("the store of the preferences of the view", () => {
  it("uses the key of the contract", () => {
    // It proves that the key of the store is the one of the contract and not a name of its own.
    expect(VIEW_PREFERENCES_STORAGE_KEY).toBe("ledgerlens.view-preferences.v1");
  });

  it("gives the defaults back when the storage is empty", () => {
    // It proves that a visitor who arrives for the first time gets the defaults of the interface.
    expect(loadViewPreferences(fakeStorage())).toEqual(DEFAULT_VIEW_PREFERENCES);
  });

  it("gives the defaults back when the stored value does not parse", () => {
    // It proves that a broken payload never reaches the state of the interface.
    const storage = fakeStorage();
    storage.setItem(VIEW_PREFERENCES_STORAGE_KEY, "{not json");

    expect(loadViewPreferences(storage)).toEqual(DEFAULT_VIEW_PREFERENCES);
  });

  it("ignores a stored field that is not a legal value", () => {
    // It proves that a field the contract does not define falls back to its default.
    const storage = fakeStorage();
    storage.setItem(VIEW_PREFERENCES_STORAGE_KEY, JSON.stringify({ tab: "nonsense", speed: 9 }));

    expect(loadViewPreferences(storage)).toEqual(DEFAULT_VIEW_PREFERENCES);
  });

  it("keeps the stored fields that are legal", () => {
    // It proves that a visitor who chose a tab and a speed finds them again on the next visit.
    const storage = fakeStorage();
    storage.setItem(VIEW_PREFERENCES_STORAGE_KEY, JSON.stringify({ tab: "evidence", speed: 4 }));

    expect(loadViewPreferences(storage)).toEqual({ tab: "evidence", speed: 4 });
  });

  it("writes only the two fields of the preferences", () => {
    // It proves that the payload of the store holds the preferences and nothing else.
    const storage = fakeStorage();

    saveViewPreferences({ tab: "evidence", speed: 4 }, storage);

    const raw = storage.getItem(VIEW_PREFERENCES_STORAGE_KEY);
    expect(raw).not.toBeNull();
    expect(Object.keys(JSON.parse(raw as string)).sort()).toEqual(["speed", "tab"]);
  });

  it("never writes a cookie", () => {
    // It proves that the recorded demo never touches the identity of the session of the backend.
    const storage = fakeStorage();

    saveViewPreferences({ tab: "evidence", speed: 4 }, storage);
    loadViewPreferences(storage);
    clearViewPreferences(storage);

    expect(cookieWrites).toEqual([]);
  });

  it("writes to the localStorage of the origin when no storage is given", () => {
    // It proves that the store of the interface is the storage of the browser and not something of its own.
    saveViewPreferences({ tab: "decision", speed: 2 });

    expect(localStorage.getItem(VIEW_PREFERENCES_STORAGE_KEY)).not.toBeNull();
    expect(loadViewPreferences()).toEqual({ tab: "decision", speed: 2 });
    expect(cookieWrites).toEqual([]);
  });

  it("takes the value away when the preferences are cleared", () => {
    // It proves that a visitor who resets the view comes back to the defaults.
    const storage = fakeStorage();
    saveViewPreferences({ tab: "evidence", speed: 4 }, storage);

    clearViewPreferences(storage);

    expect(storage.getItem(VIEW_PREFERENCES_STORAGE_KEY)).toBeNull();
    expect(loadViewPreferences(storage)).toEqual(DEFAULT_VIEW_PREFERENCES);
  });
});
