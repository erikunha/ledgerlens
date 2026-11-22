/**
 * The fence of the network of the frontend.
 *
 * Why this file exists: the contract of the milestone says that `apps/web/lib/api/replay.ts` is the ONE place that
 * reads the published artifacts, and that the folder of the components never reads the network. A reviewer of the
 * milestone added a `fetch` to the reader of the replay and the whole suite of 231 tests stayed green, so the rule
 * was real and nothing held it.
 *
 * Why the fence reads the source and does not run the code: the rule is about WHERE the network is read, and no
 * runtime observation of a single case can tell that a module never reads the network. The fence walks the source of
 * the web app and looks for the calls that read it.
 *
 * Why the live mode is excluded: the live mode lives on the origin of the backend and reads it on purpose, by the
 * decision of ADR-040. The fence names the modules that carry that exception, so an exception is always a name and
 * never a silence.
 *
 * Why the sandbox is named and not excluded: the sandbox is the third mode of the demo and it calls the origin of the
 * backend, exactly like the live mode does, by the decision of ADR-044. Its client is the ONE module of the folder
 * `features/` that reads the network, so the first case of this file names it, and the name carries the reason it
 * is allowed. Every other module of the frontend reads nothing.
 *
 * Why the folder `lib/` is walked by a case of its own: the folder holds the three modules that are allowed to read
 * the network and the many that read nothing, and a module that starts reading it has to be NAMED before it does.
 * The second case walks the folder the way the first one walks `features/`, so a module of `lib/` that the list of
 * that folder does not name and that reads the network fails the fence instead of passing in silence.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { extname, join } from "node:path";

import { describe, expect, it } from "vitest";

/** The folder of the web app, the root of the fence. */
const WEB_ROOT = process.cwd();

/** The folders of the web app that the fence walks. */
const WALKED = ["features", "components", "app"];

/**
 * The modules of the folder `lib/` that are allowed to read the network.
 *
 * Why each one is allowed: `lib/api/replay.ts` reads the published artifacts of the recorded demo, and it is the ONE
 * place that does it. `lib/api/client.ts` and `lib/api/events.ts` read the origin of the backend for the live mode,
 * which is a different product by the decision of ADR-040.
 *
 * Why the list is short on purpose: every other module of the folder `lib/` reads nothing, and the second case of
 * this file fails when one of them reads the network, so a new reader of the folder has to be NAMED here first.
 */
const ALLOWED_IN_LIB = new Set([
  join("lib", "api", "replay.ts"),
  join("lib", "api", "client.ts"),
  join("lib", "api", "events.ts"),
]);

/**
 * The modules of the frontend OUTSIDE the folder `lib/` that are allowed to read the network.
 *
 * Why the client of the sandbox is allowed: the sandbox of the visitor lives on the origin of the backend and calls
 * it on purpose, exactly like the live mode, by the decision of ADR-044. The client of the sandbox is the ONE module
 * of the folder `features/` that reads the network, and it is named here so that the exception is always a name and
 * never a silence.
 */
const ALLOWED_OUTSIDE_LIB = new Set([join("features", "sandbox", "api", "sandboxClient.ts")]);

/**
 * Every module of the web app that is allowed to read the network, wherever it lives.
 *
 * Why the two lists are joined: the first case of this file walks the folders of the frontend that live outside
 * `lib/`, and the second case walks the folder `lib/` alone and answers for the three modules of `lib/` only.
 */
const ALLOWED = new Set([...ALLOWED_IN_LIB, ...ALLOWED_OUTSIDE_LIB]);

/** The calls that read the network, with the reason each one is a read. */
const READS_OF_THE_NETWORK: readonly { readonly needle: string; readonly why: string }[] = [
  { needle: "fetch(", why: "the fetch of the runtime" },
  { needle: "XMLHttpRequest", why: "the request of the XML" },
  { needle: "EventSource", why: "the stream of the events" },
  { needle: "WebSocket", why: "the socket of the web" },
  { needle: "sendBeacon", why: "the beacon of the page" },
];

/** The extensions of the files the fence reads. */
const SOURCE_EXTENSIONS = new Set([".ts", ".tsx"]);

/**
 * Lists every source file of a folder, recursively.
 *
 * Why the walk is explicit: the fence has to know every file of the web app, and a glob that the runner expands
 * would hide the folders it skips.
 */
function sourceFiles(folder: string): string[] {
  const found: string[] = [];
  for (const entry of readdirSync(folder)) {
    const path = join(folder, entry);
    if (statSync(path).isDirectory()) {
      found.push(...sourceFiles(path));
      continue;
    }
    if (SOURCE_EXTENSIONS.has(extname(path))) {
      found.push(path);
    }
  }
  return found;
}

describe("the fence of the network of the frontend", () => {
  it("never reads the network outside the modules that are named", () => {
    // It proves that the folder of the components and the folder of the pages never read the network: the recorded
    // demo reads the published artifacts through the one client of the artifacts and calls nobody else, and the
    // sandbox reads the origin of the backend through the one client of the branch.
    const offenders: string[] = [];

    for (const walked of WALKED) {
      for (const path of sourceFiles(join(WEB_ROOT, walked))) {
        const relative = path.slice(WEB_ROOT.length + 1);
        if (ALLOWED.has(relative)) {
          continue;
        }
        const source = readFileSync(path, "utf8");
        for (const read of READS_OF_THE_NETWORK) {
          if (source.includes(read.needle)) {
            offenders.push(`${relative} reads the network with ${read.why}`);
          }
        }
      }
    }

    expect(offenders).toEqual([]);
  });

  it("lets only the named modules of `lib/` read the network", () => {
    // It proves that the exception of the live mode is a NAME and not a silence: a module of the folder `lib/` that
    // starts reading the network has to be added to the list of that folder, and the list is short on purpose. The
    // client of the sandbox is not one of them, because it does not live in the folder `lib/`.
    const offenders: string[] = [];
    const readers: string[] = [];

    for (const path of sourceFiles(join(WEB_ROOT, "lib"))) {
      const relative = path.slice(WEB_ROOT.length + 1);
      if (ALLOWED_IN_LIB.has(relative)) {
        readers.push(relative);
        continue;
      }
      // Why the modules that the list does not name are read too: a module of `lib/` that is not named and that reads
      // the network is an OFFENDER, exactly like a module of `features/` that is not named in the first case.
      const source = readFileSync(path, "utf8");
      for (const read of READS_OF_THE_NETWORK) {
        if (source.includes(read.needle)) {
          offenders.push(`${relative} reads the network with ${read.why}`);
        }
      }
    }

    expect(offenders).toEqual([]);
    expect(readers.sort()).toEqual([
      join("lib", "api", "client.ts"),
      join("lib", "api", "events.ts"),
      join("lib", "api", "replay.ts"),
    ]);
  });
});
