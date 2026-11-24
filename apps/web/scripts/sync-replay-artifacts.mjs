/**
 * The copy of the published artifacts of the recorded demo into the tree of the frontend.
 *
 * Why this file exists: the site of the demo is a static export, so the recording has to be on the
 * disk before the export runs. The repository publishes the recording in one place only,
 * `site/replay`, and this script copies it into `apps/web/public/replay`, where the export of
 * Next.js picks it up. There is no second copy in the history of the repository, so there is no
 * second copy that can go stale (ADR-042).
 *
 * Why the copy fails loudly: a build that serves no recording is worse than a build that fails, so
 * a source that is missing or empty stops the build with a readable reason instead of leaving a
 * site with nothing to play.
 *
 * Why the copy takes files away: a scenario that left the set of the published artifacts must
 * leave the site too, otherwise the site keeps offering a recording the repository does not
 * publish.
 *
 * Why there are two catalogs: the site publishes the recordings of the scripted model and the
 * recordings of a real model, and each one has its own folder of published artifacts and its own
 * root in the export (ADR-075). Both catalogs are required: the route of a scenario of each one
 * reads the catalog of that route while the export is built, so a checkout without one of them has
 * no page for that catalog, and the copy fails with a readable reason.
 */

/* global process, console */

import { copyFileSync, existsSync, mkdirSync, readdirSync, rmSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

/** The folder of this script, which is inside the package of the frontend. */
const SCRIPT_FOLDER = dirname(fileURLToPath(import.meta.url));

/** The root of the repository: three folders above the script. */
const REPOSITORY_ROOT = resolve(SCRIPT_FOLDER, "../../..");

/** The folder the repository publishes: the only source of truth for the recorded artifacts. */
const DEFAULT_SOURCE = join(REPOSITORY_ROOT, "site", "replay");

/** The folder of the frontend the static export reads the artifacts from. */
const DEFAULT_DESTINATION = join(REPOSITORY_ROOT, "apps", "web", "public", "replay");

/**
 * The catalogs of the site and the folders of the published artifacts of each one.
 *
 * Why both catalogs are required: the site publishes two catalogs, and the route of a scenario of
 * each one reads the catalog of that route from the disk while the export is built. A checkout
 * without the catalog of a real model has no page for that catalog, and a build that serves half
 * the site is a build that lies about the site, so the copy fails with a readable reason (ADR-075).
 */
const CATALOGS = [
  {
    name: "replay",
    source: join(REPOSITORY_ROOT, "site", "replay"),
    destination: join(REPOSITORY_ROOT, "apps", "web", "public", "replay"),
  },
  {
    name: "replay-real",
    source: join(REPOSITORY_ROOT, "site", "replay-real"),
    destination: join(REPOSITORY_ROOT, "apps", "web", "public", "replay-real"),
  },
  {
    name: "proof",
    source: join(REPOSITORY_ROOT, "site", "proof"),
    destination: join(REPOSITORY_ROOT, "apps", "web", "public", "proof"),
  },
];

/**
 * Lists every file of a folder, with the paths relative to that folder.
 *
 * Why the paths are relative: the copy of one file is decided by the relative path, so a file of
 * the destination is known to be foreign by comparing the relative paths.
 */
function listFiles(root) {
  const found = [];
  const walk = (folder) => {
    for (const entry of readdirSync(folder, { withFileTypes: true })) {
      const full = join(folder, entry.name);
      if (entry.isDirectory()) {
        walk(full);
        continue;
      }
      found.push(relative(root, full));
    }
  };
  walk(root);
  return found.sort();
}

/**
 * Takes away the folders of the destination that hold no file.
 *
 * Why the empty folders go too: a scenario that left the set must not leave a folder behind, or
 * the tree of the frontend carries the shape of a scenario that does not exist.
 */
function removeEmptyFolders(root) {
  const folders = [];
  const walk = (folder) => {
    for (const entry of readdirSync(folder, { withFileTypes: true })) {
      if (entry.isDirectory()) {
        const full = join(folder, entry.name);
        folders.push(full);
        walk(full);
      }
    }
  };
  walk(root);
  for (const folder of folders.reverse()) {
    if (readdirSync(folder).length === 0) {
      rmSync(folder, { recursive: true, force: true });
    }
  }
}

/**
 * Copies the published artifacts into the tree of the frontend.
 *
 * Why it throws instead of returning a result: the caller of a build step has no way to show a
 * reason to the reader of a build, so the reason goes to the output of the process.
 */
export function syncReplayArtifacts({ source, destination }) {
  if (!existsSync(source)) {
    throw new Error(`the published artifacts are not there: ${source} does not exist`);
  }
  if (!statSync(source).isDirectory()) {
    throw new Error(`the published artifacts are not there: ${source} is not a folder`);
  }

  const sourceFiles = listFiles(source);
  if (sourceFiles.length === 0) {
    throw new Error(`the published artifacts are empty: ${source} holds no file`);
  }

  mkdirSync(destination, { recursive: true });

  const copied = [];
  for (const relativePath of sourceFiles) {
    const target = join(destination, relativePath);
    mkdirSync(dirname(target), { recursive: true });
    copyFileSync(join(source, relativePath), target);
    copied.push(relativePath);
  }

  const known = new Set(sourceFiles);
  const removed = [];
  for (const relativePath of listFiles(destination)) {
    if (known.has(relativePath)) {
      continue;
    }
    rmSync(join(destination, relativePath), { force: true });
    removed.push(relativePath);
  }
  removeEmptyFolders(destination);

  return { copied, removed };
}

/**
 * Reads the arguments of the command line.
 *
 * Why the source and the destination can be named: the test of the copy works in a temporary
 * folder, and it must never touch the artifacts the repository publishes.
 */
function parseArguments(argv) {
  const options = { source: DEFAULT_SOURCE, destination: DEFAULT_DESTINATION };
  for (let position = 0; position < argv.length; position += 1) {
    const argument = argv[position];
    if (argument === "--source") {
      position += 1;
      options.source = resolve(argv[position] ?? "");
      continue;
    }
    if (argument === "--destination") {
      position += 1;
      options.destination = resolve(argv[position] ?? "");
      continue;
    }
    throw new Error(`the argument ${argument} is not known`);
  }
  return options;
}

/**
 * Runs the copy and says what it did.
 *
 * Why the output names every file: the reader of a build has to be able to see which recording the
 * site is going to serve without opening the folder.
 */
function main(argv) {
  const options = parseArguments(argv);

  // A caller that names a source and a destination copies that one catalog and nothing else, and the
  // copy fails loudly when the source is not there.
  if (options.source !== DEFAULT_SOURCE || options.destination !== DEFAULT_DESTINATION) {
    report(options.source, options.destination, syncReplayArtifacts(options));
    return;
  }

  for (const catalog of CATALOGS) {
    if (!existsSync(catalog.source)) {
      throw new Error(`the published artifacts are not there: ${catalog.source} does not exist`);
    }
    report(catalog.source, catalog.destination, syncReplayArtifacts(catalog));
  }
}

/**
 * Says what the copy did, one line per file.
 *
 * Why the reader of a build has to see every file: the reader has to be able to see which recording
 * the site is going to serve without opening the folder.
 */
function report(source, destination, outcome) {
  console.log(`the published artifacts of ${source} are now in ${destination}`);
  for (const relativePath of outcome.copied) {
    console.log(`  copied ${relativePath}`);
  }
  for (const relativePath of outcome.removed) {
    console.log(`  removed ${relativePath}`);
  }
}

const invokedDirectly =
  process.argv[1] !== undefined && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url));

if (invokedDirectly) {
  try {
    main(process.argv.slice(2));
  } catch (error) {
    console.error(`sync-replay-artifacts: ${error instanceof Error ? error.message : String(error)}`);
    process.exitCode = 1;
  }
}
