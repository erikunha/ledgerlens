import { expect, test, type Locator, type Page } from "@playwright/test";

// The origin of the site comes from the module of the suite, so the origin this file asserts is the
// origin the configuration really serves.
import { SITE_ORIGIN } from "./site-origin";

/**
 * The end to end suite of the tour of the architecture.
 *
 * Why this file exists: the tour of the architecture is the part of the site that turns a visitor
 * into a reader of the code. The page `/engineering` draws the six subsystems of the system, every
 * node of the picture links to the exact module of the repository and to the record that explains
 * why the module exists, and the engineering drawer of the replay explains the guard, the
 * arithmetic and the verification in plain language. ADR-046 decided the shape of the page and of
 * the drawer, and this suite is the proof that the shape holds in the browser.
 *
 * Why the cases below are the four cases of the plan: the specification of the user story 5 asks
 * for four things, a link that opens the exact module of the guard and the record of the
 * allowlist, a drawer that explains three subsystems in plain language and links to each module, a
 * diagram that the keyboard reaches, that it activates and that names every subsystem in words, and
 * a diagram that stays a static picture when the visitor prefers reduced motion.
 *
 * Why the commit of the repository is read from the page and never written here: the links of the
 * page are pinned to the commit of the checkout the site was built from, and that commit moves
 * with every commit of the repository. A commit written in the test would be wrong the day after
 * it was written and the test would prove nothing. The footer of the page carries the commit in
 * full, so the suite reads it there and compares the links of the page with it.
 *
 * Why the suite runs against the static export: the export is what a visitor receives, and the
 * links of the page are part of it. The configuration of Playwright starts its own server and
 * never reuses a server that is already running, because this machine runs other projects in
 * parallel.
 */

/**
 * The base of the links to the code of the repository, as ADR-046 fixed it.
 */
const REPOSITORY_BLOB_BASE = "https://github.com/erikunha/ledgerlens/blob";

/**
 * The module of the guard of the read only queries.
 */
const GUARD_MODULE = "ledgerlens/tools/sql_guard.py";

/**
 * The module of the arithmetic of the money.
 */
const CALCULATOR_MODULE = "ledgerlens/tools/calculator.py";

/**
 * The module of the verification of the claims of the answer.
 */
const VERIFIER_MODULE = "ledgerlens/verify/checks.py";

/**
 * The record that describes the allowlist of the guard.
 */
const ALLOWLIST_RECORD = "ADR-005";

/**
 * The six subsystems of the tour, in the order of the run, as the table of ADR-046 fixed them.
 *
 * Why the modules are named here: the suite compares the links of the page with the path of the
 * module, and the path is a fact of the repository that the table of the record fixed before the
 * page was written.
 */
const NODES: ReadonlyArray<{ readonly label: string; readonly module: string }> = [
  { label: "Query guard", module: GUARD_MODULE },
  { label: "Scoped ledger copy", module: "ledgerlens/api/accounts.py" },
  { label: "Decimal calculator", module: CALCULATOR_MODULE },
  { label: "Deterministic simulator", module: "ledgerlens/sim/pipeline.py" },
  { label: "Verifier", module: VERIFIER_MODULE },
  { label: "Trace recorder", module: "ledgerlens/observability/trace.py" },
];

/**
 * The names that the control that opens the engineering drawer may carry.
 *
 * Why the list and not one name: ADR-046 fixes that the replay opens the drawer from the section
 * of the calls of the tools, and it does not fix the words of the control that opens it. The suite
 * tries the names the contract allows and fails with a readable reason when it finds none, instead
 * of naming a button that the implementation may have spelled in another way.
 */
const NAMES_OF_THE_CONTROL_OF_THE_DRAWER: ReadonlyArray<RegExp> = [
  /engineering/i,
  /architecture/i,
  /how .*(built|works|made)/i,
  /subsystem/i,
];

/**
 * The requests that left the origin of the site.
 *
 * Why they are module state: the listener of the requests is installed before the navigation, so
 * the first request of the page is already watched.
 */
let requestsThatEscaped: string[] = [];

test.beforeEach(async ({ page }) => {
  requestsThatEscaped = [];

  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.origin !== SITE_ORIGIN) {
      requestsThatEscaped.push(request.url());
    }
  });
});

/**
 * Fails when any request of the page left the origin of the site.
 *
 * Why the message names the URLs: a failure that only says that something escaped leaves the
 * reader to guess what, and the URL is the whole of the evidence.
 */
function expectEveryRequestStayedOnTheSite(): void {
  expect(
    requestsThatEscaped,
    `The tour of the architecture must not call any origin other than ${SITE_ORIGIN}. The requests that escaped are: ${
      requestsThatEscaped.join(", ") || "none"
    }`,
  ).toHaveLength(0);
}

/**
 * Opens the page of the tour and waits for its heading.
 *
 * Why the heading is the wait: the page is static and it is written at build time, so the heading
 * is on the screen as soon as the file arrives. There is no sleep and no wait for a network that
 * does not come.
 */
async function openTheTour(page: Page): Promise<void> {
  await page.goto("/engineering");
  await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
}

/**
 * Reads the commit of the checkout that the page describes.
 *
 * Why the footer is read first: ADR-046 says that the footer of the page carries the commit in
 * full, and the footer is the place where the promise of the links is written down. The body of
 * the page is the fallback, for the case where the page shows the commit somewhere else.
 *
 * Why a commit of forty hexadecimal characters: that is the shape of a commit of git, and the
 * build of the site refuses to write a page whose commit is not of that shape.
 */
async function readTheCommitOfTheCheckout(page: Page): Promise<string> {
  const footers = await page.locator("footer").allInnerTexts();
  const body = await page.locator("body").innerText();

  for (const source of [...footers, body]) {
    const found = source.match(/\b[0-9a-f]{40}\b/g);
    if (found !== null && found.length > 0) {
      return found[0];
    }
  }

  throw new Error(
    "the page of the architecture does not carry the commit of the checkout, so the links of the page cannot be checked",
  );
}

/**
 * Gives back the anchor of the picture that opens the module of a node.
 *
 * Why the anchor is looked up inside the picture: the accessible list carries the same modules,
 * and the suite is about the picture here. The anchor of the picture is an anchor of the SVG with
 * an href, as ADR-046 decided.
 */
function pictureAnchor(page: Page, modulePath: string): Locator {
  return page
    .locator(`svg a[href*="${modulePath}"]`)
    .filter({ visible: true })
    .first();
}

/**
 * Gives back the picture of the diagram, which is the SVG that holds the anchors of the nodes.
 *
 * Why the picture is found by its own mark and not by walking up from an anchor: the anchor is an
 * element of the SVG, and the way up from an element of an SVG is not the same in every engine of
 * the suite, so a locator that walks up proves the picture in one engine and not in another. The
 * picture carries a mark of its own, and the mark is the same everywhere.
 */
function pictureOfTheDiagram(page: Page): Locator {
  return page.locator("[data-architecture-picture]");
}

/**
 * Moves the focus with the Tab key until the element is the one that holds it.
 *
 * Why the keyboard and not a call of the focus: a visitor does not call the focus of an element, the
 * visitor presses the Tab key until the browser reaches it. A test that calls the focus would prove
 * that the element can hold the focus and not that it is in the order of the keyboard.
 */
async function tabUntilFocused(page: Page, target: Locator): Promise<void> {
  for (let step = 0; step < 150; step += 1) {
    const focused = await target
      .evaluate((element) => element === document.activeElement)
      .catch(() => false);
    if (focused) {
      return;
    }
    await page.keyboard.press("Tab");
  }

  throw new Error("the node of the diagram was not reachable with the Tab key");
}

/**
 * Reads a duration of the CSS and gives it back in seconds.
 *
 * Why it reads the milliseconds: the rule of the reduced motion of the site writes the duration as
 * `0.01ms`, and a duration that is not read in seconds would look like a duration that runs.
 */
function durationInSeconds(value: string): number {
  let total = 0;

  for (const part of value.split(",").map((entry) => entry.trim())) {
    if (part.endsWith("ms")) {
      total += Number(part.slice(0, -2)) / 1000;
    } else if (part.endsWith("s")) {
      total += Number(part.slice(0, -1));
    } else {
      total += Number(part);
    }
  }

  return total;
}

/**
 * Escapes the characters that have a meaning in a regular expression.
 */
function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Reads every href of the page.
 *
 * Why the list and not a locator per link: the suite compares the address of the link with the
 * address that the commit and the path of the module produce, and a link that is not the one the
 * suite looked for has to be counted, not to be guessed.
 */
async function readEveryHrefOfThePage(page: Page): Promise<string[]> {
  return page
    .locator("a")
    .evaluateAll((anchors) => anchors.map((anchor) => anchor.getAttribute("href") ?? ""));
}

/**
 * Opens the route of the scenario and waits for the calls of the tools of the recording.
 *
 * Why the table is the wait: the table of the calls of the tools appears only when the bundle of
 * the scenario was read and accepted, so it is the real sign that the recording is there.
 */
async function openTheReplayWithItsCalls(page: Page): Promise<void> {
  await page.goto("/replay/scenario/S01");

  const calls = page.getByRole("table", { name: "The calls of the tools of the recorded run" });
  await expect(calls).toBeVisible();

  // The visitor moves the slider of the recording to its last position, the way a visitor does, so
  // that the calls of the tools are on the screen.
  const position = page.getByLabel("Position of the recording");
  const last = await position.getAttribute("max");
  expect(last, "the slider of the recording must name the last position").not.toBeNull();

  await position.focus();
  await position.press("End");
  if ((await position.inputValue()) !== last) {
    for (let step = 0; step < 60 && (await position.inputValue()) !== last; step += 1) {
      await position.press("ArrowRight");
    }
  }
  await expect(position).toHaveValue(last as string);

  await expect(calls.getByRole("rowheader", { name: "query_ledger" })).toBeVisible();
}

/**
 * Opens the engineering drawer from the replay.
 *
 * Why the control is looked up and not named: the drawer of the engineering tour is opened from
 * the section of the calls of the tools, and the words of the control are the choice of the
 * implementation. The control that carries the promise of the drawer is a button of the dialog, and
 * a button that names the engineering is the second choice.
 */
async function openTheEngineeringDrawer(page: Page): Promise<void> {
  const candidates = [
    page.locator('[aria-haspopup="dialog"]').filter({ visible: true }).first(),
    ...NAMES_OF_THE_CONTROL_OF_THE_DRAWER.flatMap((pattern) => [
      page.getByRole("button", { name: pattern }).filter({ visible: true }).first(),
      page.getByRole("link", { name: pattern }).filter({ visible: true }).first(),
    ]),
  ];

  for (const candidate of candidates) {
    const appeared = await candidate
      .waitFor({ state: "visible", timeout: 2_000 })
      .then(() => true)
      .catch(() => false);
    if (!appeared) {
      continue;
    }
    await candidate.click();
    return;
  }

  throw new Error(
    "the replay holds no control that opens the engineering drawer, and the drawer of the user story 5 is opened from the section of the calls of the tools",
  );
}

/**
 * Waits for the effect of the activation of a node with the keyboard.
 *
 * Why there are two outcomes: ADR-046 says that the node of the picture carries an href that opens
 * the module of the repository, and it says that the page opens the drawer with the node the
 * visitor chose. The suite accepts the two shapes the contract allows and refuses the one where
 * the activation does nothing.
 */
async function waitForTheActivationOfTheNode(page: Page): Promise<"drawer" | "link"> {
  for (let step = 0; step < 100; step += 1) {
    if ((await page.getByRole("dialog").count()) > 0) {
      return "drawer";
    }
    if (page.context().pages().length > 1) {
      return "link";
    }
    if (page.url().startsWith(REPOSITORY_BLOB_BASE)) {
      return "link";
    }
    await page.waitForTimeout(100);
  }

  throw new Error("the activation of the node with the keyboard did nothing at all");
}

test("the node of the query guard opens the exact module of the guard and the record of the allowlist", async ({
  page,
}) => {
  await openTheTour(page);

  // The commit of the checkout is read from the page, because the page is the one that promises
  // which tree the sentences of the nodes were written for.
  const commit = await readTheCommitOfTheCheckout(page);
  expect(commit, "the commit of the checkout must be forty hexadecimal characters").toMatch(
    /^[0-9a-f]{40}$/,
  );

  // The link of the module of the guard is exactly the URL that the commit and the path of the
  // module produce, and the suite compares it with the whole address and not with a part of it.
  const moduleUrl = `${REPOSITORY_BLOB_BASE}/${commit}/${GUARD_MODULE}`;
  const moduleLink = page.locator(`a[href="${moduleUrl}"]`).filter({ visible: true }).first();
  await expect(moduleLink).toBeVisible();
  await expect(moduleLink).toHaveAttribute("href", moduleUrl);

  // The record of the allowlist is reached with the same kind of URL: the base of the blob, the
  // commit and the path of the file of the record.
  const recordPattern = new RegExp(
    `^${escapeRegExp(REPOSITORY_BLOB_BASE)}/${commit}/docs/decisions/${ALLOWLIST_RECORD}-[^/]+\\.md$`,
  );
  const hrefs = await readEveryHrefOfThePage(page);
  const recordLinks = hrefs.filter((href) => recordPattern.test(href));

  expect(
    recordLinks,
    `the node of the guard must link the record that describes the allowlist, and the page carries these links: ${hrefs.join(", ")}`,
  ).not.toHaveLength(0);

  const recordLink = page
    .locator(`a[href^="${REPOSITORY_BLOB_BASE}/${commit}/docs/decisions/${ALLOWLIST_RECORD}-"]`)
    .filter({ visible: true })
    .first();
  await expect(recordLink).toBeVisible();
  await expect(recordLink).toContainText(ALLOWLIST_RECORD);

  expectEveryRequestStayedOnTheSite();
});

test("the engineering drawer of the replay explains the guard, the arithmetic and the verification", async ({
  page,
}) => {
  await openTheReplayWithItsCalls(page);
  await openTheEngineeringDrawer(page);

  const drawer = page.getByRole("dialog");
  await expect(drawer).toBeVisible();

  // The drawer names the three subsystems of the plan in plain language, the way a visitor reads
  // them and not the way the array of the nodes names them.
  const text = await drawer.innerText();
  expect(text, "the drawer must explain the guard of the read only queries").toMatch(/guard/i);
  expect(text, "the drawer must explain the arithmetic of the money with decimal numbers").toMatch(
    /decimal/i,
  );
  expect(text, "the drawer must explain the step of the verification").toMatch(/verif|verdict/i);

  // Every one of the three subsystems carries a link to its module, and the link is the URL of the
  // repository with the commit of the checkout and the path of the module.
  for (const modulePath of [GUARD_MODULE, CALCULATOR_MODULE, VERIFIER_MODULE]) {
    const pattern = new RegExp(
      `^${escapeRegExp(REPOSITORY_BLOB_BASE)}/[0-9a-f]{40}/${escapeRegExp(modulePath)}$`,
    );
    const links = await drawer.locator("a").evaluateAll((anchors) =>
      anchors.map((anchor) => anchor.getAttribute("href") ?? ""),
    );

    expect(
      links.filter((href) => pattern.test(href)),
      `the drawer must link the module ${modulePath}, and it carries these links: ${links.join(", ") || "none"}`,
    ).not.toHaveLength(0);
  }
});

test("every node of the diagram is reachable with the keyboard and names its subsystem in words", async ({
  page,
}) => {
  await openTheTour(page);

  for (const node of NODES) {
    const anchor = pictureAnchor(page, node.module);

    // The node of the picture is an anchor with an href, so the keyboard reaches it.
    await tabUntilFocused(page, anchor);
    await expect(anchor).toBeVisible();

    // The node carries a visible text that names the subsystem, and it is not a title that only a
    // screen reader hears.
    await expect(anchor).toContainText(node.label);
    const box = await anchor.boundingBox();
    expect(box, `the node ${node.label} must be drawn on the picture`).not.toBeNull();
    expect(box?.width ?? 0).toBeGreaterThan(0);
    expect(box?.height ?? 0).toBeGreaterThan(0);
  }

  expectEveryRequestStayedOnTheSite();
});

test("a node of the diagram is activated with the keyboard", async ({ page }) => {
  // The repository is stubbed, because the suite must not depend on the network of the machine and
  // the activation of a node may follow the link to the module.
  await page.route("https://github.com/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/html",
      body: "<!DOCTYPE html><html lang=\"en\"><head><title>The repository</title></head><body><p>The stub of the repository</p></body></html>",
    }),
  );

  await openTheTour(page);
  const commit = await readTheCommitOfTheCheckout(page);

  const anchor = pictureAnchor(page, GUARD_MODULE);
  await tabUntilFocused(page, anchor);

  // The visitor activates the node with the Enter key, and the suite proves that something happened.
  await page.keyboard.press("Enter");
  const outcome = await waitForTheActivationOfTheNode(page);

  if (outcome === "drawer") {
    // The page opened the drawer with the node the visitor chose.
    await expect(page.getByRole("dialog")).toBeVisible();
  } else {
    // The node opened the module of the guard in the repository, at the commit of the checkout.
    expect(page.url()).toBe(`${REPOSITORY_BLOB_BASE}/${commit}/${GUARD_MODULE}`);
  }
});

test("the accessible list is the twin of the picture", async ({ page }) => {
  await openTheTour(page);

  // The list is always on the page and it is never behind a toggle, so the visitor reads the six
  // subsystems as headings even when the picture is not read at all.
  const headings = await page.getByRole("heading").allInnerTexts();
  for (const node of NODES) {
    expect(headings, `the list must name the subsystem ${node.label}`).toContain(node.label);
  }

  expectEveryRequestStayedOnTheSite();
});

test("the diagram is a static picture when the visitor prefers reduced motion", async ({ page }) => {
  // The preference is set on the page and not on the context, because the preference of the context
  // does not reach the page in every engine of the suite.
  await page.emulateMedia({ reducedMotion: "reduce" });

  await openTheTour(page);
  const picture = pictureOfTheDiagram(page);
  await expect(picture).toBeVisible();

  // The picture is legible as a static picture: it is on the screen and it has a size.
  const before = await picture.boundingBox();
  expect(before, "the picture of the diagram must be drawn on the page").not.toBeNull();
  expect(before?.width ?? 0).toBeGreaterThan(0);
  expect(before?.height ?? 0).toBeGreaterThan(0);

  // No animation of the layout runs: the size of the picture does not move while the page waits.
  await page.waitForTimeout(400);
  const after = await picture.boundingBox();
  expect(after?.width).toBe(before?.width);
  expect(after?.height).toBe(before?.height);

  // No animation runs inside the picture, and the picture declares no animation of its own.
  const running = await picture.evaluate((element) => {
    const animations = typeof document.getAnimations === "function" ? document.getAnimations() : [];
    return animations.filter((animation) => {
      if (animation.playState !== "running") {
        return false;
      }
      const effect = animation.effect;
      const target = effect instanceof KeyframeEffect ? effect.target : null;
      return target instanceof Node && element.contains(target);
    }).length;
  });
  expect(running, "no animation may run inside the picture of the diagram").toBe(0);

  const declared = await picture.evaluate((element) => {
    const style = getComputedStyle(element);
    const anchor = element.querySelector("a");
    const anchorStyle = anchor === null ? null : getComputedStyle(anchor);
    return {
      animation: style.animationName,
      transition: style.transitionDuration,
      anchorAnimation: anchorStyle?.animationName ?? "none",
      anchorTransition: anchorStyle?.transitionDuration ?? "0s",
    };
  });
  expect(declared.animation, "the picture must not declare an animation of its own").toBe("none");
  expect(declared.anchorAnimation, "a node of the picture must not declare an animation").toBe("none");
  expect(
    durationInSeconds(declared.transition),
    "the picture must not run a transition of the layout under the preference for reduced motion",
  ).toBeLessThanOrEqual(0.01);
  expect(
    durationInSeconds(declared.anchorTransition),
    "a node of the picture must not run a transition of the layout under the preference for reduced motion",
  ).toBeLessThanOrEqual(0.01);

  // The words of the nodes are still on the screen, so the visitor reads the diagram as a picture.
  const anchor = pictureAnchor(page, GUARD_MODULE);
  await expect(anchor).toBeVisible();
  await expect(anchor).toContainText("Query guard");

  expectEveryRequestStayedOnTheSite();
});
