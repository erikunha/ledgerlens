/**
 * The repository of LedgerLens and the commit that the site was built from.
 *
 * Why this file exists: the tour of the architecture links every node of the picture to the exact
 * module in the repository and to the record that explains why that module exists (ADR-046). A
 * link to a branch ages, and a link to a branch that does not hold the record answers 404, so
 * every link of the site is pinned to the full commit of the checkout the export was built from.
 *
 * Why the commit is read and never written: a commit that a human keeps in the source is a
 * constant that is wrong one day. The commit is read from the checkout while the export is built,
 * the same way `scripts/capture_replay.py` reads the `code_sha` of the capture.
 *
 * Why a checkout that cannot answer stops the build: a page whose links point at nothing is worse
 * than a build that fails, so a checkout without git, or an answer that is not a commit of forty
 * lowercase hexadecimal characters, stops the build with a reason a reader of the build can act on.
 *
 * Why the modules of node are asked for at run time and not imported: the drawer of the tour is a
 * client component and it renders the links of this module, so a static import of a module of node
 * would put `node:child_process` in the bundle of the browser, where it cannot be resolved.
 * `process.getBuiltinModule` asks the runtime for a module when the build asks for one, and the
 * browser never asks.
 *
 * Why this module reads no network and imports nothing of `lib/api/`: the page of the architecture
 * belongs to the recorded demo, and the recorded demo calls nobody (ADR-042, ADR-043).
 */

/** The address of the repository, the one every link of the site starts with. */
export const REPOSITORY_URL = "https://github.com/erikunha/ledgerlens";

/** The base of the links to a file of the repository: the commit and the path come after it. */
export const REPOSITORY_BLOB_BASE = `${REPOSITORY_URL}/blob`;

/**
 * What the build knows about the checkout the site was built from.
 *
 * Why the tree carries a flag: a commit names the tree of the release, and a working tree with
 * changes that are not committed is a tree that the commit does not name. The footer of the page
 * says so out loud, because a page that describes a tree it does not match is a page that lies.
 */
export interface RepositoryMeta {
  /** The full commit of the checkout, forty lowercase hexadecimal characters. */
  readonly commit: string;
  /** Whether the tree had changes that were not committed when the export was built. */
  readonly dirty: boolean;
}

/**
 * The part of the module of the child processes that this module uses.
 *
 * Why the shape is written here and not imported: the drawer of the tour is a client component and
 * it renders the links of this module, so a static import of a module of node would put
 * `node:child_process` in the bundle of the browser, where it cannot be resolved. The shape is
 * small, it is the whole of what this module asks of the runtime, and it never reaches the bundle
 * of the browser because it is a type and types are erased.
 */
interface ChildProcessRuntime {
  readonly execFileSync: (
    command: string,
    args: readonly string[],
    options: { readonly encoding: "utf8" },
  ) => string;
}

/**
 * The part of the module of the files that this module uses.
 *
 * Why the shape is written here: the reason is the one of the shape of the child processes, and
 * the module reads two things: whether a path exists.
 */
interface FileSystemRuntime {
  readonly existsSync: (path: string) => boolean;
}

/**
 * The part of the module of the paths that this module uses.
 *
 * Why the shape is written here: the reason is the one of the shape of the child processes, and
 * the module joins, resolves and takes the parent of a path.
 */
interface PathRuntime {
  readonly dirname: (path: string) => string;
  readonly join: (...parts: readonly string[]) => string;
  readonly resolve: (path: string) => string;
}

/**
 * The part of the module of the urls that this module uses.
 *
 * Why the shape is written here: the reason is the one of the shape of the child processes, and
 * the module turns the address of its own file into a path.
 */
interface UrlRuntime {
  readonly fileURLToPath: (url: string) => string;
}

/**
 * The modules of node that this module needs, and only when a build needs them.
 *
 * Why they are asked for and not imported: the drawer of the tour is a client component and it
 * renders the links of this module, so a static import of a module of node would put
 * `node:child_process` in the bundle of the browser, where it cannot be resolved. The runtime is
 * asked for only when a build asks, and the browser never asks.
 */
interface NodeRuntime {
  readonly childProcess: ChildProcessRuntime;
  readonly fs: FileSystemRuntime;
  readonly path: PathRuntime;
  readonly url: UrlRuntime;
}

/** The mark of the root of the repository: the folder that holds the records of the decisions. */
const ROOT_MARK = ["docs", "decisions"];

/** The second mark of the root of the repository: the folder of the web app. */
const WEB_MARK = ["apps", "web"];

/** The shape of a commit of git: forty lowercase hexadecimal characters. */
const COMMIT_PATTERN = /^[0-9a-f]{40}$/;

/** The runtime of node, kept after the first answer so that a build asks for it once. */
let runtime: NodeRuntime | undefined;

/**
 * The modules of node that this module needs.
 *
 * Why they are asked for and not imported: the drawer of the tour is a client component and it
 * renders the links of this module, so a static import of a module of node would put
 * `node:child_process` in the bundle of the browser, where it cannot be resolved. The runtime is
 * asked for only when a build asks, and the browser never asks.
 */
function nodeRuntime(): NodeRuntime {
  if (runtime !== undefined) {
    return runtime;
  }
  if (typeof process === "undefined" || typeof process.getBuiltinModule !== "function") {
    throw new Error(
      "the modules of node are not available in this runtime, so the commit of the repository cannot be read: the build needs node 22.3 or later, where process.getBuiltinModule exists",
    );
  }
  runtime = {
    childProcess: process.getBuiltinModule("node:child_process") as ChildProcessRuntime,
    fs: process.getBuiltinModule("node:fs") as FileSystemRuntime,
    path: process.getBuiltinModule("node:path") as PathRuntime,
    url: process.getBuiltinModule("node:url") as UrlRuntime,
  };
  return runtime;
}

/**
 * The folder that holds this file, when the runtime can say where it is.
 *
 * Why the file is asked and not the working folder: the build of the site can run in another
 * folder, and the working folder is not the root of the repository. The answer is a candidate and
 * not the answer, because the root is proved by the marks of the repository and not by a path.
 */
function folderOfThisFile(): string | undefined {
  const { path: paths, url: urls } = nodeRuntime();
  try {
    if (
      typeof import.meta !== "undefined" &&
      typeof import.meta.url === "string" &&
      import.meta.url.startsWith("file:")
    ) {
      return paths.dirname(urls.fileURLToPath(import.meta.url));
    }
  } catch {
    // The bundle of the browser has no file of its own, and the answer is the working folder.
  }
  if (typeof __dirname !== "undefined") {
    return __dirname;
  }
  return undefined;
}

/**
 * Says whether a folder is the root of the repository.
 *
 * Why two marks: the folder of the records is the mark of the repository, and the folder of the
 * web app is the mark of the layout that the ADR of the tour names. A folder that carries both is
 * the root, and nothing else is.
 */
function isRepositoryRoot(candidate: string): boolean {
  const { fs, path: paths } = nodeRuntime();
  return (
    fs.existsSync(paths.join(candidate, ...ROOT_MARK)) &&
    fs.existsSync(paths.join(candidate, ...WEB_MARK))
  );
}

/**
 * Finds the root of the repository.
 *
 * Why the search walks up: the answer is proved by the marks of the repository, so a candidate is
 * a candidate until a folder carries them. A search that stopped at the first answer could stop on
 * a copy of the tree.
 *
 * Why the folder given by the caller is proved too: a test asks for the metadata of a folder that
 * is not the repository, and the answer has to be a refusal and not a metadata of nowhere.
 */
function resolveRepositoryRoot(given?: string): string {
  const { path: paths } = nodeRuntime();

  if (given !== undefined) {
    const absolute = paths.resolve(given);
    if (!isRepositoryRoot(absolute)) {
      throw new Error(
        `the folder given to readRepositoryMeta is not the root of the repository: ${absolute} (the folder ${ROOT_MARK.join("/")} is the mark of the root)`,
      );
    }
    return absolute;
  }

  const starts: string[] = [];
  const own = folderOfThisFile();
  if (own !== undefined) {
    starts.push(own);
  }
  if (typeof process !== "undefined" && typeof process.cwd === "function") {
    starts.push(process.cwd());
  }

  const tried: string[] = [];
  for (const start of starts) {
    let current = paths.resolve(start);
    for (;;) {
      tried.push(current);
      if (isRepositoryRoot(current)) {
        return current;
      }
      const parent = paths.dirname(current);
      if (parent === current) {
        break;
      }
      current = parent;
    }
  }

  throw new Error(
    `the root of the repository was not found (looked at ${tried.join(", ")}): the folder ${ROOT_MARK.join("/")} is the mark of the root of the repository`,
  );
}

/**
 * Asks git a question about the repository.
 *
 * Why the root is given to git with `-C`: the build can run in another folder, and the question is
 * always about the repository and never about the folder the build happens to run in.
 *
 * Why the failure is loud: a question of git that cannot be answered has no default that is
 * right, and a commit that is invented opens links that point at nothing.
 */
function askGit(repositoryRoot: string, args: readonly string[]): string {
  const { childProcess } = nodeRuntime();
  try {
    return childProcess.execFileSync("git", ["-C", repositoryRoot, ...args], { encoding: "utf8" });
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    throw new Error(`git ${args.join(" ")} cannot answer in ${repositoryRoot}: ${reason}`);
  }
}

/**
 * Reads the commit of the checkout.
 *
 * Why the answer has to be a commit of forty lowercase hexadecimal characters: the links of the
 * site are built from it, and an answer of another shape is a link that opens nothing. The build
 * stops with a reason instead of publishing links that cannot be followed.
 */
function readCommit(repositoryRoot: string): string {
  const answer = askGit(repositoryRoot, ["rev-parse", "HEAD"]).trim();
  if (!COMMIT_PATTERN.test(answer)) {
    throw new Error(
      `the commit of the repository cannot be read in ${repositoryRoot}: git rev-parse HEAD answered "${answer}", and the links of the site need a commit of forty lowercase hexadecimal characters`,
    );
  }
  return answer;
}

/**
 * Says whether the tree had changes that were not committed.
 *
 * Why the whole porcelain output counts: a file that was added and a file that was changed are
 * both a tree that the commit does not name, and the footer of the page has to say so in both cases.
 */
function readDirtyTree(repositoryRoot: string): boolean {
  return askGit(repositoryRoot, ["status", "--porcelain"]).trim().length > 0;
}

/**
 * The path of a file, written the way the repository writes it.
 *
 * Why the path is cleaned: a path that starts with a slash or with a dot would build a link that
 * the base of the blob does not expect, and a link that answers 404 is a link that lies.
 */
function relativePathOf(path: string): string {
  return path.trim().replace(/^\.\//, "").replace(/^\/+/, "");
}

/**
 * The URL of a file of the repository at a commit.
 *
 * Why there is one builder and not two: a link of the picture and a link of the drawer that are
 * spelled two ways are two links that can drift apart, so the base and the shape of the path live
 * in this module and in no other place (ADR-046).
 */
function blobUrlOf(path: string, commit: string): string {
  const file = relativePathOf(path);
  const ref = commit.trim();
  if (file.length === 0 || ref.length === 0) {
    throw new Error(
      `a link to the repository needs a path and a commit, and it was given the path "${path}" and the commit "${commit}"`,
    );
  }
  return `${REPOSITORY_BLOB_BASE}/${ref}/${file}`;
}

/**
 * The URL of a module of the repository at a commit.
 *
 * Why the module and the record share the builder: the two links differ only in the path they
 * carry, and one base is the promise that they cannot be spelled two ways.
 */
export function sourceUrlOf(path: string, commit: string): string {
  return blobUrlOf(path, commit);
}

/**
 * The URL of a record of a decision at a commit.
 *
 * Why the record is not copied into the site: a copy is a second source that drifts, and the
 * record is a document of the repository, written for the reader of the repository (ADR-042).
 */
export function recordUrlOf(path: string, commit: string): string {
  return blobUrlOf(path, commit);
}

/**
 * Reads what the build has to know about the checkout the site is built from.
 *
 * Why this runs at build time and never at run time: the commit of the checkout is a fact of the
 * tree the export was built from, and the browser of the visitor has no checkout to ask. The page
 * carries the answer inside the export and asks for nothing.
 *
 * Why the root is an argument: the root is proved by the marks of the repository, and a test asks
 * for the metadata of a folder of its own to see the refusal.
 */
export function readRepositoryMeta(root?: string): RepositoryMeta {
  const repositoryRoot = resolveRepositoryRoot(root);
  return {
    commit: readCommit(repositoryRoot),
    dirty: readDirtyTree(repositoryRoot),
  };
}

/** Every symbol this module exports, so that a reader sees the whole surface at once. */
export const __all__ = [
  "REPOSITORY_URL",
  "REPOSITORY_BLOB_BASE",
  "RepositoryMeta",
  "readRepositoryMeta",
  "sourceUrlOf",
  "recordUrlOf",
] as const;
