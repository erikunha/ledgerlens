"""Retrieval: splits the policies into excerpts, builds the index of the policies and loads the ready index.

Why it exists: the agent answers rule questions ("how many days to ask for a refund?") by finding the right
policy excerpts instead of memorizing them. This module owns the index of the POLICIES, and it talks to the
vector library only through the protocol of `ledgerlens/vectorstore.py`: the case memory keeps its own
vectors (`ledgerlens/memory/long_term.py`) over the same protocol, and ADR-056 decides the two vector sites
and the protocol they share.

Two separate moments, on purpose
-------------------------------------
::

    BUILD (scripts/build_index.py, once)              LOAD (the search_policies tool, always)
    data/policies/*.md                               data/index/policies_<embedding>/
      -> load_policy_documents (excerpts + metadata)   -> checks index_meta.json against the active embedding
      -> embeddings.embed_documents                    -> and against the corpus of the policies
      -> the index + index_meta.json on disk           -> the protocol loads the index
                                                       -> the protocol searches the index

The tool never rebuilds the index: if it does not exist, it says how to build it.

Excerpts: each `##` or `###` heading opens a section; the heading carries an anchor `{#anchor}` and the excerpt id
is `<document>#<anchor>` (stable between rebuilds). A section longer than 800 characters
is split with an overlap of 100, and the following parts get `-2`, `-3`. Every excerpt starts with the
section heading, so the excerpt explains itself when read outside the document.

Distance: vectors are normalized (length 1) when they go into the index and into the query, so
the L2 distance orders the same as cosine similarity. Lower is closer.

Compatibility: each index carries `index_meta.json` with the embedding name, the dimension and the digest of
the corpus it was built from. The loader refuses an index from another embedding, because neighbors from
another vector space would be wrong without warning, and it refuses an index from another corpus, because
the text it would answer with is the text of a version of the policies that is not on the disk. Both
refusals happen before the store is opened.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ledgerlens.config import PROJECT_ROOT
from ledgerlens.embeddings import embedding_id
from ledgerlens.vectorstore import VectorStore, add_to_index, load_index, search_index

POLICIES_DIR = PROJECT_ROOT / "data" / "policies"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
META_FILE = "index_meta.json"

# The marker of the fiction: every chunk of the index and every result of the tool carries it, so an
# excerpt says that the company is fictional even when it is read out of its file (gap 10 of the audit).
FICTION_MARKER = "Acme Payments is a fictional company, created only for this project"
INDEX_FILES = ("index.faiss", "index.pkl", META_FILE)
METRIC = "l2 on unit vectors"
BUILD_HINT = "run `uv run python scripts/build_index.py` to build it"

__all__ = [
    "BUILD_HINT",
    "CHUNK_OVERLAP",
    "CHUNK_SIZE",
    "INDEX_FILES",
    "META_FILE",
    "METRIC",
    "POLICIES_DIR",
    "IndexMismatch",
    "IndexStale",
    "IndexUnavailable",
    "build_policy_index",
    "corpus_digest",
    "index_dir_for",
    "load_policy_documents",
    "load_policy_index",
    "search_policy_index",
]

_HEADING = re.compile(r"^(#{2,3})\s+(.*?)\s*(?:\{#([A-Za-z0-9_-]+)\})?\s*$")
_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


class IndexUnavailable(RuntimeError):
    """The index files do not exist (or cannot be read). The message says how to build it."""


class IndexMismatch(RuntimeError):
    """The index was built with another embedding (or another dimension) than the active one."""


class IndexStale(RuntimeError):
    """The index was built from another corpus, or it does not say which corpus it was built from."""


def _front_matter(text: str, source: Path) -> tuple[dict[str, str], str]:
    match = _FRONT_MATTER.match(text)
    if match is None:
        raise ValueError(f"{source.name}: the document must start with a front matter block between '---' lines")
    meta = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    missing = {"document", "topic", "version", "language"} - meta.keys()
    if missing:
        raise ValueError(f"{source.name}: front matter lacks {', '.join(sorted(missing))}")
    return meta, text[match.end() :]


def _sections(body: str, source: Path) -> list[tuple[str, str, str]]:
    """(heading, anchor, text) of each `##` or `###` section. The `#` heading and what comes before it are ignored."""
    sections: list[tuple[str, str, list[str]]] = []
    for line in body.splitlines():
        heading = _HEADING.match(line) if line.startswith("##") else None
        if heading is not None:
            title, anchor = heading.group(2), heading.group(3)
            if not anchor:
                raise ValueError(f"{source.name}: the heading '{title}' has no {{#anchor}}")
            sections.append((title, anchor, []))
        elif sections:
            sections[-1][2].append(line)
    return [(title, anchor, "\n".join(lines).strip()) for title, anchor, lines in sections]


def load_policy_documents(policies_dir: Path | str = POLICIES_DIR) -> list[Document]:
    """The excerpts of every policy, with the metadata `chunk_id`, `document`, `section`, `topic`,
    `version`, `language` and `order` (the excerpt's position in the document, starting at 1)."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    documents: list[Document] = []
    for path in sorted(Path(policies_dir).glob("*.md")):
        meta, body = _front_matter(path.read_text(encoding="utf-8"), path)
        for order, (title, anchor, text) in enumerate(_chunks(_sections(body, path), splitter), start=1):
            documents.append(
                Document(
                    page_content=f"{title}\n{text}",
                    metadata={
                        "chunk_id": f"{meta['document']}#{anchor}",
                        "document": meta["document"],
                        "section": title,
                        "topic": meta["topic"],
                        "version": meta["version"],
                        "language": meta["language"],
                        "order": order,
                        "fiction": FICTION_MARKER,
                    },
                )
            )
    ids = [d.metadata["chunk_id"] for d in documents]
    if len(ids) != len(set(ids)):
        repeated = sorted({i for i in ids if ids.count(i) > 1})
        raise ValueError(f"chunk ids must be unique; repeated: {', '.join(repeated)}")
    return documents


def _chunks(sections: list[tuple[str, str, str]], splitter: RecursiveCharacterTextSplitter):
    """A short section becomes one excerpt; a long one becomes several, whose id gets `-2`, `-3`..."""
    for title, anchor, text in sections:
        pieces = splitter.split_text(text) or [""]
        for number, piece in enumerate(pieces, start=1):
            yield title, anchor if number == 1 else f"{anchor}-{number}", piece


def index_dir_for(index_root: Path | str, embeddings: Embeddings) -> Path:
    """The policy index folder for this embedding: `<root>/policies_<provider>`."""
    provider = embedding_id(embeddings).split(":", 1)[0]
    return Path(index_root) / f"policies_{provider}"


def corpus_digest(policies_dir: Path | str = POLICIES_DIR) -> str:
    """The sha256 of the corpus of the policies: the value the meta of the index carries as `corpus_sha256`.

    What goes into it, so that a reader can reproduce it by hand:

    - the files are the `*.md` files of the folder and nothing else (no subfolder, no other extension);
    - they are taken in the order of their name, never in the order the disk lists them;
    - the bytes of a file are the bytes on the disk, read as they are (no translation of the line endings);
    - one line per file: the name of the file, a colon, the sha256 of its bytes, and a line feed;
    - the digest is the sha256 of that text, read as UTF-8.

    The name of the file is in the text, so a rename moves the digest as well as an edit. The bytes are in
    the text, and not the parsed excerpts, so a change of the splitter does not move the digest (the chunk
    size and the overlap are in the meta already). The same corpus gives the same digest on every platform,
    because the text is built from the names, from the bytes and from a line feed.
    """
    folder = Path(policies_dir)
    lines = [
        f"{path.name}:{hashlib.sha256(path.read_bytes()).hexdigest()}"
        for path in sorted(folder.glob("*.md"), key=lambda path: path.name)
    ]
    canonical = "".join(f"{line}\n" for line in lines)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_policy_index(
    documents: list[Document],
    embeddings: Embeddings,
    index_dir: Path | str,
    *,
    policies_dir: Path | str = POLICIES_DIR,
) -> dict[str, Any]:
    """Generates the vectors, writes the index and `index_meta.json` in `index_dir`. Returns the meta.

    Only `scripts/build_index.py` calls this. The FAISS ids are the `chunk_id`s, so rebuilding with the
    same vectors gives the same bytes (no random uuid in `index.pkl`).

    `policies_dir` is the folder the documents were read from: the meta carries the digest of that corpus,
    so the loader can refuse an index that describes another corpus. The default is the folder of the
    repository, which is the corpus every caller of this function reads today.
    """
    store = add_to_index(documents, embeddings, ids=[d.metadata["chunk_id"] for d in documents])
    folder = Path(index_dir)
    folder.mkdir(parents=True, exist_ok=True)
    store.save_local(str(folder))
    meta = {
        "embedding": embedding_id(embeddings),
        "dimension": store.dimension,
        "chunks": store.count,
        "metric": METRIC,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "built_on": datetime.now(UTC).date().isoformat(),
        "corpus_sha256": corpus_digest(policies_dir),
    }
    (folder / META_FILE).write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return meta


def load_policy_index(
    index_dir: Path | str,
    embeddings: Embeddings,
    *,
    policies_dir: Path | str = POLICIES_DIR,
) -> VectorStore:
    """Loads the ready index. Raises `IndexUnavailable`, `IndexMismatch` or `IndexStale`; never builds anything.

    The corpus is compared before the store is opened: an index built from another corpus answers with the
    text of a version of the policies that is not on the disk, so it refuses instead of answering.
    """
    folder = Path(index_dir)
    absent = [name for name in INDEX_FILES if not (folder / name).is_file()]
    if absent:
        raise IndexUnavailable(f"policy index files missing in {folder} ({', '.join(absent)}); {BUILD_HINT}")
    try:
        meta = json.loads((folder / META_FILE).read_text(encoding="utf-8"))
        built_with, dimension = str(meta["embedding"]), int(meta["dimension"])
    except (ValueError, KeyError, TypeError):
        raise IndexUnavailable(f"{META_FILE} in {folder} is unreadable; {BUILD_HINT}") from None

    built_digest = meta.get("corpus_sha256") if isinstance(meta, dict) else None
    if not isinstance(built_digest, str) or not built_digest:
        raise IndexStale(
            f"the policy index in {folder} does not carry the digest of the corpus it was built from; "
            f"rebuild it ({BUILD_HINT})"
        )
    current_digest = corpus_digest(policies_dir)
    if built_digest != current_digest:
        raise IndexStale(
            f"the policy index in {folder} was built from another corpus: the index says '{built_digest}' "
            f"and the policies in {policies_dir} hash to '{current_digest}'; rebuild it ({BUILD_HINT})"
        )

    active = embedding_id(embeddings)
    if built_with != active:
        raise IndexMismatch(
            f"the policy index was built with '{built_with}' but the active embedding is '{active}'; "
            f"rebuild it with the active embedding ({BUILD_HINT})"
        )
    store = load_index(folder, embeddings)
    if store.dimension != dimension:
        raise IndexMismatch(f"the index has {store.dimension} dimensions but {META_FILE} says {dimension}")
    return store


def search_policy_index(store: VectorStore, query: str, k: int = 4) -> list[dict[str, Any]]:
    """The `k` closest excerpts to `query`, from closest to farthest, with the L2 distance."""
    results = []
    for hit in search_index(store, query, k=k):
        meta = hit.document.metadata
        results.append(
            {
                "chunk_id": meta["chunk_id"],
                "document": meta["document"],
                "section": meta["section"],
                "topic": meta["topic"],
                "version": meta["version"],
                "language": meta["language"],
                "text": hit.document.page_content,
                "score": hit.distance,
                "fiction": meta.get("fiction", FICTION_MARKER),
            }
        )
    return results
