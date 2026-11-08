"""Long-term memory: what a verified investigation teaches the following sessions (CoALA).

In the CoALA taxonomy, this module handles the project's two long-term memories:

- **Episodic**: what was investigated and what was concluded, with the date and the evidence (case `CASE-0001`).
- **Semantic**: a lasting fact about a merchant, with an optional validity (M-17's markup).

Why it exists: short-term memory (`ledgerlens/memory/history.py`) dies with the session. A customer who
comes back the next week and asks again about M-17 should not get the same explanation from scratch, but
a lead: "this was seen before, in CASE-0001, on such a date". The lead is not a proof: the agent
must confirm it in the ledger before claiming anything about today.

Two rules the code makes visible:

1. **Only what was verified gets in.** `write_case` refuses an investigation with any verdict that is not
   `supported`, or with broken coherence. An unverified conclusion would become memory and come back as a
   claim in the next session.
2. **The entity filter comes before the cut.** Merchant or customer filters are applied to the set
   of candidates before picking the best `k`, so a case from another merchant never
   "fits" the answer just for being semantically closer.

Where it lives: the `cases.jsonl` file in the runtime folder and the FAISS index `cases_index/`. The seeded file
`data/seed/cases.jsonl` is the source of the first case (`CASE-0001`, scenario S12) and is loaded while the
runtime file does not exist yet.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from ledgerlens.config import PROJECT_ROOT, get_embeddings
from ledgerlens.embeddings import embedding_id

SEED_PATH = PROJECT_ROOT / "data" / "seed" / "cases.jsonl"
RUNTIME_FILE = "cases.jsonl"
INDEX_DIR = "cases_index"
META_FILE = "index_meta.json"
METRIC = "l2 on unit vectors"

# The id prefix says which kind of entity it is.
_KINDS_BY_PREFIX = {
    "TX": "transaction_ids",
    "CB": "chargeback_ids",
    "ST": "settlement_ids",
    "R": "refund_ids",
    "M": "merchant_ids",
    "C": "customer_ids",
}


class CaseIndexUnavailable(RuntimeError):
    """The case index does not exist (or cannot be read). Memory is optional, so the tool degrades."""


class CaseIndexMismatch(RuntimeError):
    """The case index was built with another embedding, so the neighbors would be wrong."""


class CaseMemory:
    """The project's cases: verified writes, a FAISS index and search with an entity filter."""

    def __init__(
        self,
        runtime_dir: Path | str,
        *,
        embeddings: Embeddings | None = None,
        seed_path: Path | str = SEED_PATH,
    ) -> None:
        self.runtime_dir = Path(runtime_dir)
        self.runtime_file = self.runtime_dir / RUNTIME_FILE
        self.index_dir = self.runtime_dir / INDEX_DIR
        self._embeddings = embeddings
        self._seed_path = Path(seed_path)
        self._index: FAISS | None = None

    # --- leitura ----------------------------------------------------------------------------

    def records(self) -> list[dict[str, Any]]:
        """Every case: from the runtime file when it exists, from the seeded file while it does not."""
        source = self.runtime_file if self.runtime_file.is_file() else self._seed_path
        if not source.is_file():
            return []
        records = []
        for line in source.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
        return records

    def recall(
        self,
        query: str,
        entity_ids: dict[str, list[str]] | list[str] | str | None = None,
        k: int = 3,
        kind: str = "any",
    ) -> list[dict[str, Any]]:
        """The `k` cases closest to `query`, after applying the entity, kind and validity filters."""
        store = self._store()
        if store is None:
            return []
        records = {str(record["case_id"]): record for record in self.records()}
        hits = store.similarity_search_with_score(query, k=max(int(store.index.ntotal), 1))
        results: list[dict[str, Any]] = []
        for document, score in hits:
            record = records.get(str(document.metadata.get("case_id", "")))
            if record is None:
                continue
            if kind != "any" and record.get("kind") != kind:
                continue
            if not _matches(record, entity_ids):
                continue
            if _is_expired(record):
                continue
            results.append(
                {
                    "case_id": record["case_id"],
                    "kind": record.get("kind", "episodic"),
                    "finding": record.get("finding", ""),
                    "created_at": record.get("created_at", ""),
                    "confidence": record.get("confidence", "medium"),
                    "entities": record.get("entities") or {},
                    "score": float(score),
                }
            )
            if len(results) >= k:
                break
        return results

    # --- escrita ----------------------------------------------------------------------------

    def write_case(
        self,
        result: Any,
        *,
        kind: str = "episodic",
        confidence: str = "high",
        valid_until: date | None = None,
        source_result_id: str | None = None,
    ) -> dict[str, Any]:
        """Saves the case of an investigation, but only when every verdict was supported.

        Returns `{"written": False, "reason": ...}` when the investigation cannot become memory, and
        `{"written": True, "case_id": ...}` when it saved.
        """
        reason = _refusal_reason(result)
        if reason is not None:
            return {"written": False, "reason": reason}

        record = {
            "case_id": _next_case_id(self.records()),
            "kind": kind,
            "session_id": result.session_id,
            "created_at": datetime.now(UTC).isoformat(),
            "entities": _entities_of(result),
            "finding": _finding_of(result),
            "evidence_refs": [evidence.id for evidence in result.evidence],
            "confidence": confidence,
            "valid_until": valid_until.isoformat() if valid_until else None,
            "source_result_id": source_result_id or result.session_id,
        }
        self._append(record)
        self._add_to_index(record)
        return {
            "written": True,
            "case_id": record["case_id"],
            "kind": record["kind"],
            "finding": record["finding"],
        }

    # --- index ------------------------------------------------------------------------------

    def _active_embeddings(self) -> Embeddings:
        return self._embeddings if self._embeddings is not None else get_embeddings()

    def _store(self) -> FAISS | None:
        """The ready index, or a new index built from the saved cases."""
        if self._index is not None:
            return self._index
        embeddings = self._active_embeddings()
        records = self.records()
        meta = self._read_meta()
        if meta is not None:
            built_with = str(meta.get("embedding", ""))
            if built_with and built_with != embedding_id(embeddings):
                raise CaseIndexMismatch(
                    f"the case index was built with '{built_with}' but the active embedding is "
                    f"'{embedding_id(embeddings)}'; rebuild it with the active embedding"
                )
            if int(meta.get("cases", -1)) == len(records) and self._index_files_exist():
                self._index = FAISS.load_local(
                    str(self.index_dir), embeddings, allow_dangerous_deserialization=True, normalize_L2=True
                )
                return self._index
        self._index = self._build(embeddings, records)
        return self._index

    def _build(self, embeddings: Embeddings, records: list[dict[str, Any]]) -> FAISS | None:
        if not records:
            return None
        documents = [Document(page_content=record["finding"], metadata=_metadata(record)) for record in records]
        store = FAISS.from_documents(
            documents, embeddings, ids=[str(record["case_id"]) for record in records], normalize_L2=True
        )
        self._save(store)
        return store

    def _save(self, store: FAISS) -> None:
        self.index_dir.mkdir(parents=True, exist_ok=True)
        store.save_local(str(self.index_dir))
        meta = {
            "embedding": embedding_id(self._active_embeddings()),
            "dimension": int(store.index.d),
            "cases": int(store.index.ntotal),
            "metric": METRIC,
            "built_on": datetime.now(UTC).date().isoformat(),
        }
        (self.index_dir / META_FILE).write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def _read_meta(self) -> dict[str, Any] | None:
        meta_file = self.index_dir / META_FILE
        if not meta_file.is_file():
            return None
        try:
            return json.loads(meta_file.read_text(encoding="utf-8"))
        except ValueError:
            return None

    def _index_files_exist(self) -> bool:
        return all((self.index_dir / name).is_file() for name in ("index.faiss", "index.pkl", META_FILE))

    def _append(self, record: dict[str, Any]) -> None:
        """Appends the case to the runtime file, materializing the seeded file first."""
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        if not self.runtime_file.is_file() and self._seed_path.is_file():
            shutil.copyfile(self._seed_path, self.runtime_file)
        with self.runtime_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _add_to_index(self, record: dict[str, Any]) -> None:
        if self._index is None:
            return  # with no index loaded, the next read rebuilds it from the file
        document = Document(page_content=record["finding"], metadata=_metadata(record))
        try:
            self._index.add_documents([document], ids=[str(record["case_id"])])
            self._save(self._index)
        except Exception:  # pragma: no cover - the index is rebuilt on the next read
            self._index = None


# --- helpers ---------------------------------------------------------------------------------


def _refusal_reason(result: Any) -> str | None:
    """Why the investigation cannot become memory (`None` when it can)."""
    verdicts = list(getattr(result, "verdicts", []) or [])
    if not verdicts:
        return "no_verdicts"
    if any(verdict.label != "supported" for verdict in verdicts):
        return "verdict_not_supported"
    coherence = getattr(result, "coherence", None)
    if coherence is not None and not coherence.passed:
        return "coherence_failed"
    return None


def _entities_of(result: Any) -> dict[str, Any]:
    triage = getattr(result, "triage", None)
    if triage is None:
        return {}
    return triage.entities.model_dump(mode="json")


def _finding_of(result: Any) -> str:
    """The conclusion in one or two sentences: this is the text that goes into the vector index."""
    text = " ".join(str(getattr(result, "answer", "")).split())
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(sentences[:2]).strip()


def _next_case_id(records: list[dict[str, Any]]) -> str:
    highest = 0
    for record in records:
        match = re.fullmatch(r"CASE-(\d{4})", str(record.get("case_id", "")))
        if match:
            highest = max(highest, int(match.group(1)))
    return f"CASE-{highest + 1:04d}"


def _metadata(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": record.get("case_id", ""),
        "kind": record.get("kind", "episodic"),
        "created_at": record.get("created_at", ""),
        "confidence": record.get("confidence", "medium"),
        "entities": record.get("entities") or {},
        "valid_until": record.get("valid_until"),
        "session_id": record.get("session_id", ""),
    }


def _entity_kind(value: str) -> str | None:
    """The entity kind by the id prefix (`M-17` is a merchant, `TX-2048` is a transaction)."""
    prefix = value.split("-", 1)[0].upper()
    return _KINDS_BY_PREFIX.get(prefix)


def _normalize_entities(entity_ids: dict[str, list[str]] | list[str] | str | None) -> dict[str, list[str]]:
    """Accepts the entity dictionary, a list of ids or a single id and returns the dictionary."""
    if not entity_ids:
        return {}
    if isinstance(entity_ids, str):
        entity_ids = [entity_ids]
    if isinstance(entity_ids, dict):
        wanted: dict[str, list[str]] = {}
        for key, values in entity_ids.items():
            kind = key if key.endswith("_ids") else f"{key}s" if key.endswith("_id") else key
            ids = [values] if isinstance(values, str) else list(values)
            if ids:
                wanted[kind] = [str(value) for value in ids]
        return wanted
    wanted = {}
    for value in entity_ids:
        kind = _entity_kind(str(value))
        if kind is not None:
            wanted.setdefault(kind, []).append(str(value))
    return wanted


def _matches(record: dict[str, Any], entity_ids: dict[str, list[str]] | list[str] | str | None) -> bool:
    """Does the case match the filter? Each kind asked for must have at least one id in common."""
    wanted = _normalize_entities(entity_ids)
    if not wanted:
        return True
    case_entities = record.get("entities") or {}
    for kind, ids in wanted.items():
        have = {str(value) for value in (case_entities.get(kind) or [])}
        if not have & set(ids):
            return False
    return True


def _is_expired(record: dict[str, Any]) -> bool:
    """A semantic fact past its validity does not go into the search."""
    valid_until = record.get("valid_until")
    if not valid_until:
        return False
    try:
        return date.fromisoformat(str(valid_until)) < date.today()
    except ValueError:
        return False
