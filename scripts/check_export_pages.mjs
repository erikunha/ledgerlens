/**
 * The check of the static export of the site of the replay.
 *
 * Why this file exists: the gate of the frontend has to prove that the build wrote one page per scenario of the
 * catalog, with the content of the scenario. A check that lives inside a shell script cannot be tested, so the check
 * lives in a script of its own, with no dependency at all, and the gate of the frontend calls it.
 *
 * Why the check reads the exported page as text: a route that answers 404 during the export still writes a file at
 * the path of the route, and that file is the body of the page of 404. A check that only proves that the file exists
 * passes a site where every visitor who follows the card of the catalog lands on the page of 404.
 *
 * Why the check names one problem per line: the reader of a build has to know which scenario is broken, and a message
 * that names the scenario and the file is a message a reader can act on.
 *
 * Why the script takes the folder of the export as its only argument: the test of the check builds a folder of its
 * own, outside the repository, and it must never look at the export of the repository.
 */

/* global process, console */

import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

/** The folder of this script. */
const SCRIPT_FOLDER = dirname(fileURLToPath(import.meta.url));

/** The root of the repository: one folder above the folder of the scripts. */
const REPOSITORY_ROOT = resolve(SCRIPT_FOLDER, "..");

/** The folder of the export, when the caller does not name one. */
const DEFAULT_EXPORT_FOLDER = join(REPOSITORY_ROOT, "apps", "web", "out");

/**
 * The marks of the body of the page of 404.
 *
 * Why there are two families: the first one is the document of error of Next.js, which is what a route that answers
 * 404 during the export writes at the path of the route. The second one is the body of the page of 404 of the site,
 * which is what a visitor reads when the page of 404 answers.
 */
const NOT_FOUND_MARKS_IN_THE_HTML = ['<html id="__next_error__"'];
const NOT_FOUND_MARKS_IN_THE_MARKUP = ["This page could not be found.", "next-error-h1"];

/**
 * The markup that the visitor sees, without the scripts.
 *
 * Why the scripts are removed: Next.js writes the data of the flight of the page inside the scripts, and those data
 * carry the text of the page of 404 in every page of the site. The check has to read what the visitor reads, and not
 * the payload that Next.js ships next to it.
 */
function visibleMarkup(html) {
  return html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, "");
}

/**
 * The text of a question as the browser reads it in the markup.
 */
function escapeHtml(text) {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

/**
 * A regular expression that matches a text literally.
 */
function escapeRegExp(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Finds the folder of the recorded demo inside the folder of the export.
 *
 * Why the folder is looked up: the export of the site holds the recorded demo in the folder `replay`, and the caller
 * can name either the export or the recorded demo itself. The folder that holds the catalog of the scenarios is the
 * one the check reads.
 *
 * Why the name of the catalog is an argument: the site publishes two catalogs, the recordings of the scripted model
 * and the recordings of a real model, and each one has its own folder and its own page (ADR-075).
 */
function resolveReplayFolder(folder, catalog) {
  if (existsSync(join(folder, "index.json"))) {
    return folder;
  }
  const nested = join(folder, catalog);
  if (existsSync(join(nested, "index.json"))) {
    return nested;
  }
  return folder;
}

/**
 * Finds the page of the catalog of the scenarios in the export.
 *
 * Why the two candidates: the caller can name the export itself, where the page of the catalog is `replay.html` at
 * the root of the export, or the recorded demo, where the page of the catalog is one folder above.
 *
 * Why the page of the catalog is checked at all: it is the first page a visitor lands on, and the end to end suite
 * that proves it runs in no job of the continuous integration, so the gate of the frontend is the only place that
 * can catch a catalog page that is missing or that is the page of 404.
 */
function findCatalogPage(folder, replayFolder, catalog) {
  const candidates = [join(folder, `${catalog}.html`)];
  candidates.push(join(dirname(replayFolder), `${catalog}.html`));
  for (const candidate of candidates) {
    if (existsSync(candidate)) {
      return candidate;
    }
  }
  return candidates[0];
}

/**
 * The six labels of the nodes of the picture of the architecture.
 *
 * Why the labels are written here: the page of the architecture shows six subsystems and the gate has to prove that
 * the build wrote the page with them. The labels are the words the visitor reads, and they are the words the typed
 * source of the nodes carries.
 */
const LABELS_OF_THE_NODES = [
  "Query guard",
  "Scoped ledger copy",
  "Decimal calculator",
  "Deterministic simulator",
  "Verifier",
  "Trace recorder",
];

/**
 * Finds the page of the architecture in the export.
 *
 * Why the two candidates: the caller can name the export itself, where the page of the architecture is
 * `engineering.html` at the root of the export, or the recorded demo, where the page of the architecture is one folder
 * above.
 */
function findEngineeringPage(folder, replayFolder) {
  const candidates = [join(folder, "engineering.html")];
  candidates.push(join(dirname(replayFolder), "engineering.html"));
  for (const candidate of candidates) {
    if (existsSync(candidate)) {
      return candidate;
    }
  }
  return candidates[0];
}

/**
 * Checks the page of the architecture and returns the problems it found.
 *
 * Why the page has to carry a heading: a page that carries no heading is not the page of the tour, whatever the file
 * is called.
 *
 * Why the page has to carry the six labels: the page is the tour of the six subsystems of the run, and a build that
 * writes the page without them writes a page that shows nothing the visitor came for.
 */
function checkEngineeringPage(folder, replayFolder) {
  const problems = [];
  const page = findEngineeringPage(folder, replayFolder);

  if (!existsSync(page)) {
    problems.push(`the export does not hold the page of the architecture: ${page} is missing`);
    return problems;
  }

  let html = null;
  try {
    html = readFileSync(page, "utf8");
  } catch (error) {
    problems.push(`the page of the architecture could not be read as text: ${page} (${error.message})`);
    return problems;
  }

  const visible = visibleMarkup(html);

  const markInHtml = NOT_FOUND_MARKS_IN_THE_HTML.find((candidate) => html.includes(candidate));
  if (markInHtml !== undefined) {
    problems.push(
      `the page of the architecture is the page of 404: ${page} carries the document of error of Next.js ('${markInHtml}')`,
    );
  }

  const markInMarkup = NOT_FOUND_MARKS_IN_THE_MARKUP.find((candidate) => visible.includes(candidate));
  if (markInMarkup !== undefined) {
    problems.push(
      `the page of the architecture is the page of 404: ${page} carries the body of the page of 404 ('${markInMarkup}')`,
    );
  }

  if (!/<h1\b/i.test(visible)) {
    problems.push(`the page of the architecture carries no heading: ${page}`);
  }

  for (const label of LABELS_OF_THE_NODES) {
    if (!visible.includes(label)) {
      problems.push(`the page of the architecture does not carry the label of the node "${label}": ${page}`);
    }
  }

  return problems;
}

/**
 * Checks the page of the catalog of the scenarios and returns the problems it found.
 *
 * Why the page has to carry a heading: a page that carries no heading is not the page of the catalog of the site,
 * whatever the file is called.
 */
function checkCatalogPage(folder, replayFolder, catalog) {
  const problems = [];
  const page = findCatalogPage(folder, replayFolder, catalog);

  if (!existsSync(page)) {
    problems.push(`the export does not hold the page of the catalog of the scenarios: ${page} is missing`);
    return problems;
  }

  let html = null;
  try {
    html = readFileSync(page, "utf8");
  } catch (error) {
    problems.push(`the page of the catalog of the scenarios could not be read as text: ${page} (${error.message})`);
    return problems;
  }

  const markInHtml = NOT_FOUND_MARKS_IN_THE_HTML.find((candidate) => html.includes(candidate));
  if (markInHtml !== undefined) {
    problems.push(
      `the page of the catalog of the scenarios is the page of 404: ${page} carries the document of error of Next.js ('${markInHtml}')`,
    );
  }

  const visible = visibleMarkup(html);
  const markInMarkup = NOT_FOUND_MARKS_IN_THE_MARKUP.find((candidate) => visible.includes(candidate));
  if (markInMarkup !== undefined) {
    problems.push(
      `the page of the catalog of the scenarios is the page of 404: ${page} carries the body of the page of 404 ('${markInMarkup}')`,
    );
  }

  if (!/<h1\b/i.test(visible)) {
    problems.push(`the page of the catalog of the scenarios carries no heading: ${page}`);
  }

  return problems;
}

/**
 * Checks the export of the site and returns the problems it found.
 *
 * Why the problems come back as a list and not as a boolean: the reader of a build has to know which scenario is
 * broken, and one line per problem is the shape of the output of the gate.
 *
 * Why the count of the scenarios comes back too: the message that says that the export is good names the number of
 * the scenarios that were checked.
 */
export function checkExportPages(folder, catalog = "replay") {
  const problems = [];
  let scenarioCount = 0;

  const replayFolder = resolveReplayFolder(folder, catalog);

  // The page of the architecture is checked first and it is checked on its own: the tour of the subsystems does not
  // depend on the recorded demo, and a build that loses the page of the tour has to fail whatever the catalog holds.
  problems.push(...checkEngineeringPage(folder, replayFolder));

  if (!existsSync(replayFolder)) {
    problems.push(`the export does not hold the recorded demo: ${replayFolder} does not exist`);
    return { problems, scenarioCount };
  }

  const catalogPath = join(replayFolder, "index.json");
  if (!existsSync(catalogPath)) {
    problems.push(`the export does not hold the catalog of the scenarios: ${catalogPath} is missing`);
    return { problems, scenarioCount };
  }

  let publishedCatalog = null;
  try {
    publishedCatalog = JSON.parse(readFileSync(catalogPath, "utf8"));
  } catch (error) {
    problems.push(`the catalog of the scenarios is not a JSON document: ${error.message}`);
  }

  if (publishedCatalog === null) {
    return { problems, scenarioCount };
  }

  if (!Array.isArray(publishedCatalog)) {
    problems.push(`the catalog of the scenarios is not a list: ${catalogPath}`);
    return { problems, scenarioCount };
  }

  if (publishedCatalog.length === 0) {
    problems.push(`the catalog of the scenarios is empty: ${catalogPath}`);
    return { problems, scenarioCount };
  }

  scenarioCount = publishedCatalog.length;

  problems.push(...checkCatalogPage(folder, replayFolder, catalog));

  for (const card of publishedCatalog) {
    const directory = card.bundle_path || String(card.id || "").toLowerCase();
    for (const file of ["manifest.json", "events.jsonl"]) {
      const artifact = join(replayFolder, directory, file);
      if (!existsSync(artifact)) {
        problems.push(`the export does not hold the artifact ${artifact}`);
      }
    }

    // The route of a scenario is a page of the export, one page per scenario of the catalog. A route that is
    // missing means that a visitor who follows the card of the catalog lands on nothing.
    const scenarioId = card.id ? String(card.id) : "";
    if (scenarioId === "") {
      problems.push(`the catalog of the scenarios holds a card without an identifier: ${catalogPath}`);
      continue;
    }

    const page = join(replayFolder, "scenario", `${scenarioId}.html`);
    if (!existsSync(page)) {
      problems.push(`the export does not hold the page of the scenario ${scenarioId}: ${page} is missing`);
      continue;
    }

    // The file has to exist AND to be the page of the scenario. A route that answers 404 during the build still
    // writes a file at the path of the route, and that file is the body of the page of 404, so the check reads the
    // file as text and proves what the visitor would read.
    let html = null;
    try {
      html = readFileSync(page, "utf8");
    } catch (error) {
      problems.push(`the page of the scenario ${scenarioId} could not be read as text: ${page} (${error.message})`);
      continue;
    }
    const visible = visibleMarkup(html);

    const question = card.question ? String(card.question) : "";
    if (question === "") {
      problems.push(`the catalog of the scenarios holds a card of ${scenarioId} without a question: ${catalogPath}`);
      continue;
    }
    if (!visible.includes(question) && !visible.includes(escapeHtml(question))) {
      problems.push(
        `the page of the scenario ${scenarioId} does not carry the question of the card: "${question}" is missing from ${page}`,
      );
    }
    if (!new RegExp(`\\b${escapeRegExp(scenarioId)}\\b`).test(visible)) {
      problems.push(
        `the page of the scenario ${scenarioId} does not carry the identifier of the scenario: "${scenarioId}" is missing from ${page}`,
      );
    }

    const markInHtml = NOT_FOUND_MARKS_IN_THE_HTML.find((candidate) => html.includes(candidate));
    if (markInHtml !== undefined) {
      problems.push(
        `the page of the scenario ${scenarioId} is the page of 404: ${page} carries the document of error of Next.js ('${markInHtml}')`,
      );
    }
    const markInMarkup = NOT_FOUND_MARKS_IN_THE_MARKUP.find((candidate) => visible.includes(candidate));
    if (markInMarkup !== undefined) {
      problems.push(
        `the page of the scenario ${scenarioId} is the page of 404: ${page} carries the body of the page of 404 ('${markInMarkup}')`,
      );
    }
  }

  return { problems, scenarioCount };
}

/**
 * Reads the arguments of the command line.
 *
 * Why the folder can be named: the test of the check works in a temporary folder, and it must never read the export
 * of the repository.
 *
 * Why the name of the catalog can be named: the site publishes two catalogs and the check proves one of them at a
 * time, so the gate calls it once for each one (ADR-075).
 */
function parseArguments(argv) {
  if (argv.length > 2) {
    throw new Error("the check takes the folder of the export and the name of a catalog");
  }
  if (argv.length === 0) {
    return { folder: DEFAULT_EXPORT_FOLDER, catalog: "replay" };
  }
  return { folder: resolve(argv[0]), catalog: argv[1] ?? "replay" };
}

/**
 * Runs the check and says what it found.
 *
 * Why the problems go to the error output: they are the reason the build did not pass, and the output of the gate
 * has to name them one per line.
 */
function main(argv) {
  const { folder, catalog } = parseArguments(argv);
  const { problems, scenarioCount } = checkExportPages(folder, catalog);

  if (problems.length > 0) {
    for (const problem of problems) {
      console.error(`gate_web: ${problem}`);
    }
    process.exitCode = 1;
    return;
  }

  console.log(
    `the build wrote the catalog of ${scenarioCount} scenario(s), the bundle of every one of them, the page of every one of them and the page of the architecture, with the six labels of its nodes`,
  );
}

const invokedDirectly =
  process.argv[1] !== undefined && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url));

if (invokedDirectly) {
  try {
    main(process.argv.slice(2));
  } catch (error) {
    console.error(`check_export_pages: ${error instanceof Error ? error.message : String(error)}`);
    process.exitCode = 1;
  }
}
