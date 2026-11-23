/**
 * The tests of the URL contract of the browser.
 *
 * Why this file exists: the site is a static export and the live mode talks to the backend on
 * another origin, so the browser has to know that origin before it can call anything. The
 * origin comes from a public build variable, and a wrong value has to be refused rather than
 * guessed, because a guessed origin sends a visitor to a host nobody owns.
 *
 * Every case runs with no key and no network: the function under test only builds strings.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  API_BASE_URL_VARIABLE,
  DEFAULT_API_BASE_URL,
  apiBaseUrl,
  apiUrl,
  normalizeBaseUrl,
} from "@/lib/api/config";

describe("the URL contract", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("defaults to the origin of the demo", () => {
    expect(DEFAULT_API_BASE_URL).toBe("http://localhost:8010");
    expect(apiBaseUrl()).toBe("http://localhost:8010");
  });

  it("reads the origin from the public build variable", () => {
    vi.stubEnv(API_BASE_URL_VARIABLE, "https://api.example.com");
    expect(apiBaseUrl()).toBe("https://api.example.com");
  });

  it("normalizes a value that carries a trailing slash", () => {
    expect(normalizeBaseUrl("http://localhost:8010/")).toBe("http://localhost:8010");
    expect(normalizeBaseUrl("http://localhost:8010///")).toBe("http://localhost:8010");
    expect(normalizeBaseUrl("  http://localhost:8010  ")).toBe("http://localhost:8010");
  });

  it("refuses a value that is not an origin", () => {
    expect(normalizeBaseUrl("not-an-origin")).toBeNull();
    expect(normalizeBaseUrl("http://localhost:8010/v1")).toBeNull();
    expect(normalizeBaseUrl("http://localhost:8010?key=secret")).toBeNull();
    expect(normalizeBaseUrl("ftp://localhost:8010")).toBeNull();
    expect(normalizeBaseUrl("")).toBeNull();
    expect(normalizeBaseUrl(undefined)).toBeNull();
    expect(normalizeBaseUrl(null)).toBeNull();
  });

  it("joins the path with exactly one slash", () => {
    expect(apiUrl("/v1/sessions")).toBe("http://localhost:8010/v1/sessions");
    expect(apiUrl("v1/sessions")).toBe("http://localhost:8010/v1/sessions");
    expect(apiUrl("/v1/sessions", "https://api.example.com/")).toBe("https://api.example.com/v1/sessions");
    expect(apiUrl("/v1/sessions", "https://api.example.com")).toBe("https://api.example.com/v1/sessions");
  });
});
