/**
 * The port and the origin of the static export that the end to end suite tests.
 *
 * Why this module exists: the suite needs the port of its server in three places, the base URL of
 * the browser, the command that serves the export and the URL it waits for, and the two specs of the
 * network guard have to assert that no request leaves the very origin the suite serves. When the port
 * was written by hand in each of those places, one edit could make the suite serve one origin and
 * assert another, and the proof of the network guard would become vacuous with no red test to show
 * it. One module makes the origin the suite serves and the origin the specs assert the same by
 * construction.
 *
 * Why the port comes from the environment: this machine runs several projects at the same time and
 * the popular ports are often taken by other work. The variable `LEDGERLENS_E2E_PORT` lets a second
 * copy of the suite of this repository run beside the first one without the two fighting for a port.
 *
 * Why the default is 3215: the default belongs to this project and not to a generic one, so it is
 * unlikely to be the port that another project of the machine happens to be serving.
 */

/**
 * The port the end to end suite serves the static export on when the environment says nothing.
 *
 * Why the number: the default is a port of this project, so the suite does not reach for one of the
 * popular ports that other projects of the machine tend to take.
 */
export const DEFAULT_E2E_PORT = 3215;

/**
 * The name of the environment variable that carries the port of the end to end suite.
 *
 * Why the name is public: the README of the site and the reader of a failing run both have to name
 * the same variable, and a constant keeps that name in one place.
 */
export const E2E_PORT_VARIABLE = "LEDGERLENS_E2E_PORT";

/**
 * Reads the port of the suite from the environment, and falls back to the default of the project.
 *
 * Why it refuses instead of guessing: a value that is not a port is a mistake of the reader and not
 * something to repair silently. A guess would put the suite on a port nobody expects, and the suite
 * would then either fail on a port of another project or, worse, be pointed at another project on
 * purpose. A readable error is the only safe answer.
 */
function readThePortFromTheEnvironment(): number {
  const raw = process.env[E2E_PORT_VARIABLE];
  if (raw === undefined || raw.trim() === "") {
    return DEFAULT_E2E_PORT;
  }

  const parsed = Number(raw.trim());
  if (!Number.isInteger(parsed) || parsed < 1 || parsed > 65535) {
    throw new Error(
      `${E2E_PORT_VARIABLE} must be a port between 1 and 65535, and it is "${raw}". ` +
        `Leave it unset to use the default port ${DEFAULT_E2E_PORT}.`,
    );
  }

  return parsed;
}

/**
 * The port the end to end suite serves the static export on.
 *
 * Why it is read once: the configuration and the specs of the suite have to agree on the port, and
 * two readings of the environment could disagree if the environment changed in between.
 */
export const E2E_PORT: number = readThePortFromTheEnvironment();

/**
 * The origin of the site that the end to end suite serves and that the specs of the network guard
 * assert.
 *
 * Why the loopback address: the suite serves the export on the machine that runs it, and the address
 * has to be the same on both sides of the assertion, so it is built here and nowhere else.
 */
export const SITE_ORIGIN: string = `http://127.0.0.1:${E2E_PORT}`;

/** Every symbol this module exports, so that a reader sees the whole surface of the module at once. */
export const __all__ = ["DEFAULT_E2E_PORT", "E2E_PORT", "E2E_PORT_VARIABLE", "SITE_ORIGIN"] as const;
