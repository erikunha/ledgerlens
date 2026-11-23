/**
 * The URL contract of the browser.
 *
 * Why this file exists: the site is a static export and the live mode of the demo talks to the
 * backend on the origin of the backend (ADR-040). The origin is a public build variable, because
 * a static export has no server to read a variable at runtime, and the default is the origin of
 * the local demo.
 *
 * The value is an origin and nothing else: no path, no query string, no trailing slash. A value
 * that is not an origin is refused instead of being repaired, because a repaired origin is a
 * guess, and a guess sends the visitor of the site to a host nobody owns.
 */

/**
 * The name of the public build variable that holds the origin of the backend.
 *
 * The `NEXT_PUBLIC_` prefix is the convention of Next.js for a value that is inlined in the
 * bundle of the browser, and it says out loud that the value is public. The variable never holds
 * a secret.
 */
export const API_BASE_URL_VARIABLE = "NEXT_PUBLIC_LEDGERLENS_API_BASE_URL";

/**
 * The origin of the backend when the variable is absent.
 *
 * Why `localhost` and not `127.0.0.1`: the cookie of the session is `SameSite=Lax`, so the
 * backend has to answer on the same site as the interface. `localhost` and `localhost` are the
 * same site, and `127.0.0.1` is another host, so the browser would not send the cookie from one
 * to the other.
 */
export const DEFAULT_API_BASE_URL = "http://localhost:8010";

/**
 * Turns a configured value into the origin it names, or refuses it.
 *
 * The value is refused when it is absent, when it is not an absolute URL, when it carries a
 * scheme other than HTTP or HTTPS, or when it carries a path, a query string or a fragment: the
 * contract of the deployment is an origin, and anything more is a deployment that has to be
 * fixed rather than a value the interface can repair.
 */
export function normalizeBaseUrl(raw: string | undefined | null): string | null {
  if (typeof raw !== "string") {
    return null;
  }
  const trimmed = raw.trim();
  if (trimmed === "") {
    return null;
  }

  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    return null;
  }

  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    return null;
  }
  if (parsed.hostname === "") {
    return null;
  }
  if (parsed.pathname.replace(/\/+$/, "") !== "") {
    return null;
  }
  if (parsed.search !== "" || parsed.hash !== "") {
    return null;
  }
  if (parsed.username !== "" || parsed.password !== "") {
    return null;
  }

  return `${parsed.protocol}//${parsed.host}`;
}

/**
 * The origin the browser talks to.
 *
 * Why the default and not a failure: the recorded demo is the offline half of the demo and it
 * makes no request to the backend at all, so a deployment with a broken variable still shows the
 * site. The live section reports the origin it tried, so the misconfiguration is visible where
 * it happens.
 */
export function apiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_LEDGERLENS_API_BASE_URL;
  return normalizeBaseUrl(configured) ?? DEFAULT_API_BASE_URL;
}

/**
 * Joins a path of the backend with the origin, with exactly one slash between the two.
 *
 * Why the origin is normalized again here: the caller may hand over a base with a trailing
 * slash, and the routes of the backend are published without one.
 */
export function apiUrl(path: string, base?: string): string {
  const origin = normalizeBaseUrl(base ?? undefined) ?? apiBaseUrl();
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${origin}${suffix}`;
}
