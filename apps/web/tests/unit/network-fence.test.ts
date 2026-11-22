/**
 * The fence of the network of the recorded demo.
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
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { extname, join } from "node:path";

import { describe, expect, it } from "vitest";

/** The folder of the web app, the root of the fence. */
const WEB_ROOT = process.cwd();

/** The folders of the web app that the fence walks. */
const WALKED = ["features", "components", "app"];

/**
 * The modules of the web app that are allowed to read the network.
 *
 * Why each one is allowed: `lib/api/replay.ts` reads the published artifacts of the recorded demo, and it is the ONE
 * place that does it. `lib/api/client.ts` and `lib/api/events.ts` read the origin of the backend for the live mode,
 * which is a different product by the decision of ADR-040.
 */
const ALLOWED = new Set([
  join("lib", "api", "replay.ts"),
  join("lib", "api", "client.ts"),
  join("lib", "api", "events.ts"),
]);

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

describe("the fence of the network of the recorded demo", () => {
  it("never reads the network outside the one module that is allowed to", () => {
    // It proves that the folder of the components and the folder of the pages never read the network: the recorded
    // demo reads the published artifacts through the one client of the artifacts and calls nobody else.
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

  it("lets only the named modules of the live mode read the origin of the backend", () => {
    // It proves that the exception of the live mode is a NAME and not a silence: a module that starts reading the
    // network has to be added to the list above, and the list is short on purpose.
    const readers: string[] = [];

    for (const path of sourceFiles(join(WEB_ROOT, "lib"))) {
      const relative = path.slice(WEB_ROOT.length + 1);
      if (ALLOWED.has(relative)) {
        readers.push(relative);
      }
    }

    expect(readers.sort()).toEqual([
      join("lib", "api", "client.ts"),
      join("lib", "api", "events.ts"),
      join("lib", "api", "replay.ts"),
    ]);
  });
});
