/**
 * The test of the lengths of the SVG of the frontend.
 *
 * Why this test exists: the picture of the architecture of the recorded demo carried the attribute
 * `height="auto"`, and that is not a length that the browser accepts, so every visit of the page
 * logged an error in the console of the browser. No visitor sees that error and no suite of the
 * repository said so, because a console error is not a page that breaks. The test walks the source
 * of the frontend and refuses the length that no browser accepts, so the next one is caught the day
 * it lands and not the day a visitor complains.
 *
 * Why the test reads the files and not the pages: the pages of the site are the export, and the
 * export is built from the source. A test that reads the export proves something about a build
 * that may be old, and the defect is in the source, in the file that the next build reads.
 *
 * Every case runs with no key and no network.
 */

import { readFileSync, readdirSync } from "node:fs";
import { dirname, extname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

/**
 * The folders of the frontend that carry the source of the interface.
 *
 * Why the folders are named here and not walked blindly: the folder of the build and the folder of
 * the dependencies hold files that nobody of this repository wrote, and a test that reads them
 * would report the problems of another project.
 */
const SOURCE_FOLDERS = ["app", "components", "features", "lib"] as const;

/**
 * The root of the frontend, which is the folder that holds the package of the site.
 *
 * Why the root is looked up and not written: the folder of the test is at a known depth today, and
 * a test that breaks when a file moves is a test that gets ignored.
 */
const FRONTEND_ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));

/**
 * The pattern of an attribute of a length that no browser accepts.
 *
 * Why the pattern is written and not searched as a plain text: the attribute may be written with
 * single quotes or without spaces around the sign, and the test has to catch every spelling of the
 * defect and not only the one that happened today.
 */
const INVALID_LENGTH = /height\s*=\s*["']auto["']/;

/**
 * Every file of the source of the frontend that carries the extension of the interface.
 *
 * Why the walk is recursive and by extension: the source of a page is spread over folders, and a
 * file without the extension of the interface holds no attribute of an SVG.
 */
function sourceFilesOf(folder: string): string[] {
  const found: string[] = [];

  for (const entry of readdirSync(folder, { withFileTypes: true })) {
    const path = join(folder, entry.name);

    if (entry.isDirectory()) {
      found.push(...sourceFilesOf(path));
      continue;
    }
    if (extname(entry.name) !== ".ts" && extname(entry.name) !== ".tsx") {
      continue;
    }
    found.push(path);
  }

  return found;
}

describe("the lengths of the SVG of the frontend", () => {
  it("carries no length that no browser accepts", () => {
    // It proves that no file of the frontend asks an SVG for a height that the browser refuses to
    // parse, because that refusal is an error in the console of every visit of the page.
    const offenders: string[] = [];

    for (const folder of SOURCE_FOLDERS) {
      for (const file of sourceFilesOf(join(FRONTEND_ROOT, folder))) {
        const source = readFileSync(file, "utf8");
        if (!INVALID_LENGTH.test(source)) {
          continue;
        }
        offenders.push(file.replace(`${FRONTEND_ROOT}/`, ""));
      }
    }

    expect(
      offenders,
      `these files of the frontend carry a height that no browser accepts: ${offenders.join(", ")}`,
    ).toEqual([]);
  });
});
