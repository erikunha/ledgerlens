"""Retrieval: splits the policies into excerpts, builds the FAISS index and loads the ready index.

Why it exists: the agent answers rule questions ("how many days to ask for a refund?") by finding the right
policy excerpts instead of memorizing them. This is the only place in the project that talks to FAISS, so
switching vector libraries touches one file.

Two separate moments, on purpose
-------------------------------------
::

    BUILD (scripts/build_index.py, once)              LOAD (the search_policies tool, always)
    data/policies/*.md                               data/index/policies_<embedding>/
      -> load_policy_documents (excerpts + metadata)   -> checks index_meta.json against the active embedding
      -> embeddings.embed_documents                    -> FAISS.load_local
      -> FAISS + index_meta.json on disk               -> similarity_search_with_score

The tool never rebuilds the index: if it does not exist, it says how to build it.

Excerpts: each `##` or `###` heading opens a section; the heading carries an anchor `{#anchor}` and the excerpt id
is `<document>#<anchor>` (stable between rebuilds). A section longer than 800 characters
is split with an overlap of 100, and the following parts get `-2`, `-3`. Every excerpt starts with the
section heading, so the excerpt explains itself when read outside the document.

Distance: vectors are normalized (length 1) when they go into the index and into the query, so
FAISS L2 distance orders the same as cosine similarity. Lower is closer.

Compatibility: each index carries `index_meta.json` with the embedding name and the dimension. The loader
refuses an index from another embedding, because neighbors from another vector space would be wrong without warning.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ledgerlens.config import PROJECT_ROOT
from ledgerlens.embeddings import embedding_id

POLICIES_DIR = PROJECT_ROOT / "data" / "policies"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
META_FILE = "index_meta.json"
INDEX_FILES = ("index.faiss", "index.pkl", META_FILE)
METRIC = "l2 on unit vectors"
BUILD_HINT = "run `uv run python scripts/build_index.py` to build it"

_HEADING = re.compile(r"^(#{2,3})\s+(.*?)\s*(?:\{#([A-Za-z0-9_-]+)\})?\s*$")
_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


class IndexUnavailable(RuntimeError):
    """The index files do not exist (or cannot be read). The message says how to build it."""


class IndexMismatch(RuntimeError):
    """The index was built with another embedding (or another dimension) than the active one."""


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


def build_policy_index(documents: list[Document], embeddings: Embeddings, index_dir: Path | str) -> dict[str, Any]:
    """Generates the vectors, writes the FAISS index and `index_meta.json` in `index_dir`. Returns the meta.

    Only `scripts/build_index.py` calls this. The FAISS ids are the `chunk_id`s, so rebuilding with the
    same vectors gives the same bytes (no random uuid in `index.pkl`).
    """
    store = FAISS.from_documents(
        documents, embeddings, ids=[d.metadata["chunk_id"] for d in documents], normalize_L2=True
    )
    folder = Path(index_dir)
    folder.mkdir(parents=True, exist_ok=True)
    store.save_local(str(folder))
    meta = {
        "embedding": embedding_id(embeddings),
        "dimension": int(store.index.d),
        "chunks": int(store.index.ntotal),
        "metric": METRIC,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "built_on": datetime.now(UTC).date().isoformat(),
    }
    (folder / META_FILE).write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return meta


def load_policy_index(index_dir: Path | str, embeddings: Embeddings) -> FAISS:
    """Loads the ready index. Raises `IndexUnavailable` or `IndexMismatch`; never builds anything."""
    folder = Path(index_dir)
    absent = [name for name in INDEX_FILES if not (folder / name).is_file()]
    if absent:
        raise IndexUnavailable(f"policy index files missing in {folder} ({', '.join(absent)}); {BUILD_HINT}")
    try:
        meta = json.loads((folder / META_FILE).read_text(encoding="utf-8"))
        built_with, dimension = str(meta["embedding"]), int(meta["dimension"])
    except (ValueError, KeyError, TypeError):
        raise IndexUnavailable(f"{META_FILE} in {folder} is unreadable; {BUILD_HINT}") from None

    active = embedding_id(embeddings)
    if built_with != active:
        raise IndexMismatch(
            f"the policy index was built with '{built_with}' but the active embedding is '{active}'; "
            f"rebuild it with the active embedding ({BUILD_HINT})"
        )
    # The index is ours: it was written by `build_policy_index` and is only read from `data/index/`. FAISS keeps
    # the excerpt text in a pickle, and LangChain requires this consent to open it. This is the only
    # place in the project that gives it; never point this function at an outside file.
    store = FAISS.load_local(str(folder), embeddings, allow_dangerous_deserialization=True, normalize_L2=True)
    if store.index.d != dimension:
        raise IndexMismatch(f"the index has {store.index.d} dimensions but {META_FILE} says {dimension}")
    return store


def search_policy_index(store: FAISS, query: str, k: int = 4) -> list[dict[str, Any]]:
    """The `k` closest excerpts to `query`, from closest to farthest, with the L2 distance."""
    results = []
    for document, distance in store.similarity_search_with_score(query, k=k):
        meta = document.metadata
        results.append(
            {
                "chunk_id": meta["chunk_id"],
                "document": meta["document"],
                "section": meta["section"],
                "topic": meta["topic"],
                "version": meta["version"],
                "language": meta["language"],
                "text": document.page_content,
                "score": float(distance),
            }
        )
    return results
