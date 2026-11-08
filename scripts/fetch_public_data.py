#!/usr/bin/env python3
"""Download the public raw files into data/raw/ and record their checksums in data/sources.lock.json.

Run as: uv run python scripts/fetch_public_data.py [--only NAME ...] [--update-lock] [--force]

Sources (no key, account or login):
  uci_online_retail_ii   UCI Online Retail II, CC BY 4.0
  bin_list               BIN list (venelinkochev/bin-list-data), CC BY 4.0
  ecb_eurofxref_hist     ECB euro foreign exchange reference rates, full history

Rules:
  * A file already in data/raw/ is checked against the lock and not downloaded again.
  * A download whose SHA-256 differs from the lock is deleted and refused. `--update-lock`
    accepts the new checksum on purpose.
  * The lock is rewritten only when a file was downloaded; it is sorted and has no timestamps
    other than `fetched_at` of the entry that changed.
  * data/raw/ is ignored by git. Only the lock and derived samples are committed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_DIR = ROOT / "data" / "raw"
DEFAULT_LOCK = ROOT / "data" / "sources.lock.json"
LOCK_SCHEMA_VERSION = "1"
CHUNK = 1 << 20


class FetchError(RuntimeError):
    """A download failed. The message names the source and the reason."""


class ChecksumMismatch(FetchError):
    """A file does not match the checksum recorded in the lock."""


@dataclass(frozen=True)
class Source:
    name: str
    url: str
    filename: str
    license: str
    redistributable: bool
    attribution: str


@dataclass(frozen=True)
class FetchResult:
    name: str
    path: Path
    status: str  # "downloaded" or "verified"
    bytes: int
    sha256: str


SOURCES: tuple[Source, ...] = (
    Source(
        name="uci_online_retail_ii",
        url="https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip",
        filename="online_retail_ii.zip",
        license="CC BY 4.0",
        redistributable=True,
        attribution="Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository. "
        "https://doi.org/10.24432/C5CG6D",
    ),
    Source(
        name="bin_list",
        url="https://raw.githubusercontent.com/venelinkochev/bin-list-data/master/bin-list-data.csv",
        filename="bin-list-data.csv",
        license="CC BY 4.0",
        redistributable=True,
        attribution="venelinkochev/bin-list-data, https://github.com/venelinkochev/bin-list-data",
    ),
    Source(
        name="ecb_eurofxref_hist",
        url="https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip",
        filename="eurofxref-hist.zip",
        license="ECB reuse with source acknowledged",
        redistributable=True,
        attribution="European Central Bank, euro foreign exchange reference rates, https://www.ecb.europa.eu",
    ),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def read_lock(lock_path: Path) -> dict:
    if not lock_path.exists():
        return {"schema_version": LOCK_SCHEMA_VERSION, "sources": {}}
    return json.loads(lock_path.read_text(encoding="utf-8"))


def write_lock(lock_path: Path, lock: dict) -> None:
    lock["sources"] = dict(sorted(lock["sources"].items()))
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps(lock, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _download(source: Source, target: Path, *, timeout: float, retries: int) -> tuple[int, str]:
    """Stream the URL into `target` and return (bytes, sha256). Retries 5xx and connection errors."""
    last_error = "unknown error"
    for attempt in range(1, retries + 1):
        digest = hashlib.sha256()
        size = 0
        try:
            with httpx.stream("GET", source.url, follow_redirects=True, timeout=timeout) as response:
                if response.status_code >= 400:
                    last_error = f"HTTP {response.status_code}"
                    if response.status_code < 500:
                        break
                    raise httpx.HTTPError(last_error)
                with target.open("wb") as handle:
                    for chunk in response.iter_bytes(CHUNK):
                        handle.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
            return size, digest.hexdigest()
        except httpx.HTTPError as error:
            last_error = last_error if last_error.startswith("HTTP") else f"{type(error).__name__}: {error}"
            if attempt < retries:
                time.sleep(min(2.0 * attempt, 6.0))
    target.unlink(missing_ok=True)
    raise FetchError(f"{source.name}: download of {source.url} failed ({last_error})")


def _entry(source: Source, size: int, digest: str) -> dict:
    return {
        "url": source.url,
        "filename": source.filename,
        "bytes": size,
        "sha256": digest,
        "license": source.license,
        "redistributable": source.redistributable,
        "attribution": source.attribution,
        "fetched_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def fetch_sources(
    sources: Iterable[Source],
    *,
    raw_dir: Path = DEFAULT_RAW_DIR,
    lock_path: Path = DEFAULT_LOCK,
    update_lock: bool = False,
    force: bool = False,
    timeout: float = 120.0,
    retries: int = 3,
) -> list[FetchResult]:
    """Download or verify each source. Raises ChecksumMismatch or FetchError on the first problem."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    lock = read_lock(lock_path)
    results: list[FetchResult] = []
    for source in sources:
        target = raw_dir / source.filename
        locked = lock["sources"].get(source.name)
        if target.exists() and not force:
            digest = sha256_file(target)
            if locked is None:
                lock["sources"][source.name] = _entry(source, target.stat().st_size, digest)
                write_lock(lock_path, lock)
                results.append(FetchResult(source.name, target, "downloaded", target.stat().st_size, digest))
                continue
            if digest != locked["sha256"] and not update_lock:
                raise ChecksumMismatch(
                    f"{source.name}: {target} has sha256 {digest}, the lock has {locked['sha256']}. "
                    "Delete the file to download it again, or pass --update-lock to accept it."
                )
            if digest == locked["sha256"]:
                results.append(FetchResult(source.name, target, "verified", target.stat().st_size, digest))
                continue
        partial = target.with_suffix(target.suffix + ".part")
        size, digest = _download(source, partial, timeout=timeout, retries=retries)
        if locked is not None and digest != locked["sha256"] and not update_lock:
            partial.unlink(missing_ok=True)
            raise ChecksumMismatch(
                f"{source.name}: {source.url} now has sha256 {digest}, the lock has {locked['sha256']}. "
                "The upstream file changed. Review it, then pass --update-lock to accept it."
            )
        partial.replace(target)
        lock["sources"][source.name] = _entry(source, size, digest)
        write_lock(lock_path, lock)
        results.append(FetchResult(source.name, target, "downloaded", size, digest))
    return results


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", nargs="+", metavar="NAME", help="fetch only these sources")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--update-lock", action="store_true", help="accept a changed checksum")
    parser.add_argument("--force", action="store_true", help="download again even if the file exists")
    args = parser.parse_args(argv)

    wanted = [source for source in SOURCES if not args.only or source.name in args.only]
    unknown = set(args.only or ()) - {source.name for source in SOURCES}
    if unknown:
        print(f"unknown source(s): {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2
    try:
        results = fetch_sources(
            wanted, raw_dir=args.raw_dir, lock_path=args.lock, update_lock=args.update_lock, force=args.force
        )
    except FetchError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    for result in results:
        print(f"{result.status:10} {result.name}  {result.bytes} bytes  sha256 {result.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
