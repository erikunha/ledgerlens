#!/usr/bin/env python3
"""Cross checks the digests the site publishes against the canonical bundle of the repository.

Compare the files that Streamlit reads with the frozen recordings and their declared hashes.

What it proves, for the scenario it is given:

1. Every file the manifest of the canonical bundle declares exists in the published folder, and the
   sha256 of the published file is the digest the manifest declares.
2. The published file is the file of the canonical bundle, byte for byte, and not a file that looks
   like it.
3. The manifest the site publishes is the manifest of the canonical bundle, byte for byte. The digest
   of the bundle is the digest of that file, so a manifest that was re-serialized differently makes
   the digest that the panel of the provenance shows describe a file the site does not serve.
4. The provenance the site publishes carries the digest of the events and the digest of the manifest
   that this script recomputes, and its `bundle_digest` is the digest that the Python loader computes
   for the canonical bundle. That is the claim the panel of the provenance makes to the visitor
   (SC-012 of the specification).
5. The catalog of the site carries the digest of the bundle and the digest of the provenance file
   that the published files really have.
6. Nothing else is published beside the manifest. A file that neither the manifest nor the export
   accounts for is refused, because a file nobody can account for is a file nobody can check.
7. The file of the ledger is the frozen file, byte for byte, the provenance publishes the digest of
   the file that is really on the disk, and the catalog publishes the same digest under its own
   name. The artifact of the ledger is the one the recording read, so the chain of the digests of
   the scenario is closed: the events, the ledger, the provenance and the catalog.

The script reads the disk and nothing else: it never writes anything, it never opens a socket and it
never calls a model. The exit code is the answer. A missing file, a digest that does not match and a
file that is not accounted for are all a refusal with a readable reason, and the script prints one
line per file it checked.

Usage:

```bash
uv run python scripts/verify_replay_digests.py
uv run python scripts/verify_replay_digests.py --bundle data/eval/replay/s01 --published site/replay/s01
```

Exit code 0 when every check holds, 1 when one of them does not.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ledgerlens.replay.bundle import (  # noqa: E402  (the path is set up before the import)
    MANIFEST_FILE,
    BundleError,
    bundle_digest,
    load_bundle,
)
from ledgerlens.replay.ledger_artifact import LEDGER_FILE  # noqa: E402  (the path is set up before the import)
from ledgerlens.replay.site_export import (  # noqa: E402  (the path is set up before the import)
    INDEX_FILE,
    LEDGER_DIR_NAME,
    PROVENANCE_FILE,
    SCENARIO_ARTIFACT_NAMES,
)

__all__ = [
    "DEFAULT_BUNDLE",
    "DEFAULT_INDEX",
    "DEFAULT_PUBLISHED",
    "main",
    "sha256_of",
    "verify",
]

# The canonical bundle of the repository: the recording, as the capture sealed it.
DEFAULT_BUNDLE = ROOT / "data" / "eval" / "replay" / "s01"

# The artifacts the site publishes for that bundle, and the catalog that lists them.
DEFAULT_PUBLISHED = ROOT / "site" / "replay" / "s01"
DEFAULT_INDEX = ROOT / "site" / "replay" / INDEX_FILE

# A dotfile is metadata of the desktop and not content of the export, so it is exempt here too. The rule is the
# same one `load_bundle` of the core uses inside a bundle, for the same reason.
DOTFILE_PREFIX = "."


def sha256_of(path: Path) -> str:
    """The sha256 of a file, read from the disk.

    The bytes are read whole, because the digest of a file is the digest of its bytes and never of a
    part of them.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> object:
    """The JSON document of a file, read as it is on the disk.

    A file that is not a JSON document is a refusal and not a traceback, because the reader of the
    refusal is a person and not a stack trace.
    """
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_manifest(bundle_dir: Path, problems: list[str]) -> dict | None:
    """The manifest of the canonical bundle, after the core checked the hashes, the secret and the order.

    The loader of the core is the authority here: it refuses a bundle whose hash does not match, so a
    manifest that reaches the checks below is a manifest the repository itself vouches for.
    """
    try:
        manifest, _events = load_bundle(bundle_dir)
    except (BundleError, OSError, ValueError, KeyError, TypeError) as exc:
        problems.append(f"the canonical bundle does not hold up: {exc}")
        return None
    return manifest.to_dict()


def _check_declared_files(
    bundle_dir: Path,
    published_dir: Path,
    declared: dict[str, str],
    problems: list[str],
) -> None:
    """Every file the manifest declares exists in the published folder, with the digest the manifest declares.

    The canonical copy is compared as well: a published file that carries the right digest but is not the
    file of the canonical bundle would mean the two copies had drifted apart somewhere else.
    """
    for name in sorted(declared):
        published = published_dir / name
        if not published.is_file():
            problems.append(f"missing: the site does not publish {name}, which the manifest of the bundle declares")
            print(f"  missing  {name}")
            continue
        observed = sha256_of(published)
        if observed != declared[name]:
            problems.append(
                f"the digest of {name} does not match the manifest: expected {declared[name]}, observed {observed}"
            )
            print(f"  differs  {name}  {observed}")
            continue
        canonical = bundle_dir / name
        if canonical.is_file():
            expected = sha256_of(canonical)
            if expected != observed:
                problems.append(
                    f"the published {name} is not the file of the canonical bundle: the bundle has {expected}, "
                    f"the site has {observed}"
                )
                print(f"  differs  {name}  {observed}")
                continue
        print(f"  ok       {name}  {observed}")


def _check_published_manifest(bundle_dir: Path, published_dir: Path, problems: list[str]) -> None:
    """The manifest the site publishes is the manifest of the canonical bundle, byte for byte.

    The digest of the bundle is the digest of the manifest, so the panel of the provenance names the
    manifest of the canonical bundle and the site serves the manifest of the published folder. The two
    have to be the same file.
    """
    published = published_dir / MANIFEST_FILE
    canonical = bundle_dir / MANIFEST_FILE
    if not published.is_file():
        problems.append(f"missing: the site does not publish the {MANIFEST_FILE} of the bundle")
        print(f"  missing  {MANIFEST_FILE}")
        return
    observed = sha256_of(published)
    expected = sha256_of(canonical) if canonical.is_file() else ""
    if expected and observed != expected:
        problems.append(
            f"the {MANIFEST_FILE} the site publishes is not byte for byte the one of the canonical bundle: "
            f"the bundle has {expected}, the site has {observed}"
        )
        print(f"  differs  {MANIFEST_FILE}  {observed}")
        return
    try:
        published_data = _read_json(published)
        canonical_data = _read_json(canonical)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        problems.append(f"the {MANIFEST_FILE} of the site cannot be read as JSON: {exc}")
        print(f"  broken   {MANIFEST_FILE}")
        return
    if published_data != canonical_data:
        problems.append(f"the {MANIFEST_FILE} the site publishes does not carry the content of the canonical one")
        print(f"  differs  {MANIFEST_FILE}  {observed}")
        return
    print(f"  ok       {MANIFEST_FILE}  {observed}")


def _check_provenance(
    bundle_dir: Path,
    published_dir: Path,
    declared: dict[str, str],
    problems: list[str],
) -> None:
    """The provenance the site publishes carries the digests that this script recomputes.

    The panel of the provenance shows the digest of the bundle to the visitor, and that digest has to
    be the one the Python loader computes for the same artifact (SC-012). The file that carries it is
    the provenance, so the provenance is what is checked.
    """
    path = published_dir / PROVENANCE_FILE
    if not path.is_file():
        problems.append(f"missing: the site does not publish the {PROVENANCE_FILE} of the bundle")
        print(f"  missing  {PROVENANCE_FILE}")
        return
    try:
        payload = _read_json(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        problems.append(f"the {PROVENANCE_FILE} of the site cannot be read as JSON: {exc}")
        print(f"  broken   {PROVENANCE_FILE}")
        return
    if not isinstance(payload, dict):
        problems.append(f"the {PROVENANCE_FILE} of the site is not a JSON object")
        print(f"  broken   {PROVENANCE_FILE}")
        return

    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict):
        problems.append(f"the {PROVENANCE_FILE} of the site carries no map of artifacts")
        print(f"  broken   {PROVENANCE_FILE}")
        return

    # The digests of the artifacts of the bundle, recomputed from the files the site really serves.
    for name in sorted(declared):
        published = published_dir / name
        if not published.is_file():
            continue
        expected = artifacts.get(name)
        observed = sha256_of(published)
        if expected != observed:
            problems.append(
                f"the {PROVENANCE_FILE} publishes the digest {expected} of {name} and the file the site serves "
                f"has {observed}"
            )
            print(f"  differs  {PROVENANCE_FILE} ({name})")
            return
    manifest_path = published_dir / MANIFEST_FILE
    if manifest_path.is_file():
        expected = artifacts.get(MANIFEST_FILE)
        observed = sha256_of(manifest_path)
        if expected != observed:
            problems.append(
                f"the {PROVENANCE_FILE} publishes the digest {expected} of the {MANIFEST_FILE} and the file the "
                f"site serves has {observed}"
            )
            print(f"  differs  {PROVENANCE_FILE} ({MANIFEST_FILE})")
            return

    # The digest of the bundle: the one the Python loader computes for the canonical bundle.
    published_bundle_digest = payload.get("bundle_digest")
    computed = bundle_digest(bundle_dir)
    if published_bundle_digest != computed:
        problems.append(
            f"the {PROVENANCE_FILE} publishes the digest of the bundle {published_bundle_digest} and the loader "
            f"computes {computed}"
        )
        print(f"  differs  {PROVENANCE_FILE} (bundle_digest)")
        return
    # The label of the line names the file it is really about: the digest of the BUNDLE is the digest of
    # the manifest, and the digest of the provenance file is the one that the card of the catalog
    # publishes. Printing the digest of the bundle under the name of the provenance file says something
    # false about a file that is on the disk.
    print(f"  ok       {PROVENANCE_FILE}  the digest of the bundle is {published_bundle_digest}")


def _check_no_extra_files(published_dir: Path, declared: dict[str, str], problems: list[str]) -> None:
    """Nothing is published beside the manifest that neither the manifest nor the export accounts for.

    The export publishes three files per scenario: the files the manifest declares, the manifest itself
    and the provenance beside them. A fourth file is a file that no check of the repository covers, so
    it is refused.
    """
    allowed = set(declared) | set(SCENARIO_ARTIFACT_NAMES)
    if not published_dir.is_dir():
        problems.append(f"the published folder does not exist: {published_dir}")
        return
    for path in sorted(published_dir.rglob("*")):
        if not path.is_file():
            continue
        name = path.relative_to(published_dir).as_posix()
        if path.name.startswith(DOTFILE_PREFIX):
            continue
        if name not in allowed:
            problems.append(
                f"unexpected: the site publishes {name}, which the manifest does not declare and the export "
                f"does not produce"
            )
            print(f"  extra    {name}")


def _check_ledger(
    bundle_dir: Path,
    published_dir: Path,
    index_path: Path,
    ledger_path: Path,
    problems: list[str],
) -> None:
    """The file of the ledger is the frozen file, and the two published digests are the digest of that file.

    The artifact of the ledger is the ledger of the account of the recording, frozen beside the bundle by the
    producer. The site publishes a copy of it, and the provenance publishes the digest of the copy and the catalog
    publishes the same digest under a name of its own. The three have to be one file and one digest, or the chain of
    the scenario is open.

    A scenario whose provenance declares no file of the ledger owes the check nothing: the recording did not read a
    ledger, or the artifact was not produced yet.
    """
    provenance_path = published_dir / PROVENANCE_FILE
    if not provenance_path.is_file():
        return
    try:
        provenance = _read_json(provenance_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        # The provenance is checked by another check of this script, which names the reason.
        return
    if not isinstance(provenance, dict):
        return
    artifacts = provenance.get("artifacts")
    if not isinstance(artifacts, dict) or LEDGER_FILE not in artifacts:
        return

    published = published_dir / LEDGER_FILE
    if not published.is_file():
        problems.append(f"missing: the site does not publish the {LEDGER_FILE} that the provenance declares")
        print(f"  missing  {LEDGER_FILE}")
        return

    observed = sha256_of(published)
    declared = artifacts.get(LEDGER_FILE)
    if declared != observed:
        problems.append(
            f"the {PROVENANCE_FILE} publishes the digest {declared} of the {LEDGER_FILE} and the file the site serves "
            f"has {observed}"
        )
        print(f"  differs  {PROVENANCE_FILE} ({LEDGER_FILE})")
        return

    if not ledger_path.is_file():
        problems.append(f"missing: the frozen artifact of the ledger does not exist: {ledger_path}")
        print(f"  missing  {LEDGER_FILE} (frozen)")
        return
    if ledger_path.read_bytes() != published.read_bytes():
        frozen = sha256_of(ledger_path)
        problems.append(
            f"the published {LEDGER_FILE} is not the frozen artifact, byte for byte: the frozen file has {frozen} "
            f"and the site has {observed}"
        )
        print(f"  differs  {LEDGER_FILE}  {observed}")
        return

    card = _card_of(index_path, str(bundle_dir.name))
    if card is None:
        problems.append(f"the catalog of the site does not publish the scenario of {published_dir.name}")
        print(f"  missing  {index_path.name} ({LEDGER_FILE})")
        return
    if card.get("ledger_sha256") != observed:
        problems.append(
            f"the catalog of the site publishes the digest {card.get('ledger_sha256')} under the name "
            f"ledger_sha256 of the {LEDGER_FILE} and the published file has {observed}"
        )
        print(f"  differs  {index_path.name} (ledger_sha256)")
        return
    print(f"  ok       {LEDGER_FILE}  {observed}")


def _card_of(index_path: Path, scenario: str) -> dict | None:
    """The card of the catalog for the scenario, or None when the catalog does not publish it."""
    if not index_path.is_file():
        return None
    try:
        cards = _read_json(index_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(cards, list):
        return None
    for entry in cards:
        if isinstance(entry, dict) and str(entry.get("id", "")).upper() == scenario.upper():
            return entry
    return None


def _check_catalog(
    index_path: Path,
    published_dir: Path,
    scenario: str,
    computed_bundle_digest: str,
    problems: list[str],
) -> None:
    """The catalog of the site carries the digests of the bundle and of the provenance file.

    The catalog is what the visitor reads first, so a card that carries a digest the published files do
    not have is a card that lies to the visitor before the page opens.
    """
    if not index_path.is_file():
        problems.append(f"missing: the catalog of the site does not exist: {index_path}")
        print(f"  missing  {index_path.name}")
        return
    try:
        cards = _read_json(index_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        problems.append(f"the catalog of the site cannot be read as JSON: {exc}")
        print(f"  broken   {index_path.name}")
        return
    if not isinstance(cards, list):
        problems.append("the catalog of the site is not a list of scenarios")
        print(f"  broken   {index_path.name}")
        return

    card = next(
        (
            entry
            for entry in cards
            if isinstance(entry, dict) and str(entry.get("id", "")).upper() == scenario.upper()
        ),
        None,
    )
    if card is None:
        problems.append(f"the catalog of the site does not publish the scenario {scenario}")
        print(f"  missing  {scenario}")
        return
    if card.get("bundle_digest") != computed_bundle_digest:
        problems.append(
            f"the catalog of the site publishes the digest of the bundle {card.get('bundle_digest')} and the "
            f"loader computes {computed_bundle_digest}"
        )
        print(f"  differs  {index_path.name} (bundle_digest)")
        return
    provenance = published_dir / PROVENANCE_FILE
    if provenance.is_file():
        expected = sha256_of(provenance)
        if card.get("provenance_sha256") != expected:
            problems.append(
                f"the catalog of the site publishes the digest {card.get('provenance_sha256')} of the provenance "
                f"and the published file has {expected}"
            )
            print(f"  differs  {index_path.name} (provenance_sha256)")
            return
    print(f"  ok       {index_path.name}  {scenario}")


def verify(
    bundle_dir: Path,
    published_dir: Path,
    index_path: Path,
    ledger_path: Path | None = None,
) -> list[str]:
    """Runs every check and returns the problems it found. An empty list means the two copies agree.

    The checks are the ones the script promises in its docstring: the declared files, the published
    manifest, the provenance, the catalog, the file of the ledger and the absence of a file nobody
    accounts for.

    The frozen artifact of the ledger is the file beside the folder of the bundle, and the caller can name
    another one.
    """
    if ledger_path is None:
        ledger_path = bundle_dir.parent / LEDGER_DIR_NAME / f"{bundle_dir.name}.json"
    problems: list[str] = []
    manifest = _canonical_manifest(bundle_dir, problems)
    if manifest is None:
        return problems

    declared = {str(name): str(digest) for name, digest in (manifest.get("files") or {}).items()}
    if not declared:
        problems.append("the manifest of the canonical bundle declares no file, so there is nothing to compare")
        return problems

    scenario = str(manifest.get("scenario") or published_dir.name)
    print(f"canonical bundle: {bundle_dir}")
    print(f"published files: {published_dir}")
    print(f"scenario: {scenario}")
    print("files checked:")

    _check_declared_files(bundle_dir, published_dir, declared, problems)
    _check_published_manifest(bundle_dir, published_dir, problems)
    _check_provenance(bundle_dir, published_dir, declared, problems)
    _check_no_extra_files(published_dir, declared, problems)
    _check_catalog(index_path, published_dir, scenario, bundle_digest(bundle_dir), problems)
    _check_ledger(bundle_dir, published_dir, index_path, ledger_path, problems)
    return problems


def main(argv: Sequence[str] | None = None) -> int:
    """Runs the checks and returns the exit code of the answer."""
    parser = argparse.ArgumentParser(
        description="Cross checks the digests the site publishes against the canonical bundle."
    )
    parser.add_argument("--bundle", default=str(DEFAULT_BUNDLE), help="folder of the canonical bundle")
    parser.add_argument("--published", default=str(DEFAULT_PUBLISHED), help="folder of the published artifacts")
    parser.add_argument("--index", default=str(DEFAULT_INDEX), help="catalog of the published scenarios")
    parser.add_argument(
        "--ledger",
        default=None,
        help="frozen artifact of the ledger (by default, the file beside the folder of the bundle)",
    )
    args = parser.parse_args(argv)

    ledger = Path(args.ledger) if args.ledger else None
    problems = verify(Path(args.bundle), Path(args.published), Path(args.index), ledger)
    if problems:
        print("verify_replay_digests: the published artifacts do NOT match the canonical bundle:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    print("the published artifacts match the canonical bundle")
    return 0


if __name__ == "__main__":
    sys.exit(main())
