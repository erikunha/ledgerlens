#!/usr/bin/env python3
"""Builds the FAISS index of the policies in data/index/policies_<embedding>/.

Run it like this, from the project root: uv run python scripts/build_index.py [--policies DIR] [--out DIR]

Why it is a separate script: building the index costs time (and, with OpenAI, money), so it happens
once, here. The agent only loads the result (`ledgerlens/tools/policies.py`) and never rebuilds it.

What it does, in order:
  1. reads the documents in data/policies/*.md and splits them into excerpts (`ledgerlens.retrieval`);
  2. generates the vectors with the active embedding: the local fastembed model offline (`LEDGERLENS_OFFLINE=1`
     or default) or OpenAI (`LEDGERLENS_EMBEDDINGS=openai`, needs a key);
  3. writes index.faiss, index.pkl and index_meta.json in the embedding's folder.

Running it again replaces the files in the same folder. The default target folder comes from LEDGERLENS_INDEX_DIR
(default data/index/). Exit code 0 on success, 1 if the policies do not exist or are empty.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from ledgerlens.config import ConfigError, get_embeddings, get_settings
from ledgerlens.retrieval import POLICIES_DIR, build_policy_index, index_dir_for, load_policy_documents


def build(policies_dir: Path, index_root: Path) -> tuple[Path, dict]:
    """Builds the index and returns (folder, meta)."""
    documents = load_policy_documents(policies_dir)
    if not documents:
        raise FileNotFoundError(f"no policy documents (*.md) in {policies_dir}")
    embeddings = get_embeddings()
    folder = index_dir_for(index_root, embeddings)
    return folder, build_policy_index(documents, embeddings, folder)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the FAISS index of the policy documents.")
    parser.add_argument("--policies", type=Path, default=POLICIES_DIR, help="folder with the policy .md files")
    parser.add_argument("--out", type=Path, default=None, help="index root (default: LEDGERLENS_INDEX_DIR, data/index)")
    args = parser.parse_args(argv)

    try:
        folder, meta = build(args.policies, args.out or get_settings().index_dir)
    except (FileNotFoundError, ValueError, ConfigError) as exc:
        print(f"build_index: {exc}", file=sys.stderr)
        return 1
    print(f"{folder}: {meta['chunks']} chunks, {meta['dimension']} dimensions, embedding {meta['embedding']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
