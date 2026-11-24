"""The provenance of the artifact: the commit and the digests of the run it describes.

Why the provenance of the artifact is the provenance of the bundle: the bundle already names the commit it was
produced from and carries the digest of every file, and the artifact adds nothing to that and takes nothing
away. The digest of a file in the artifact is the digest of that file on the disk, so a reader can open the
bundle and check the artifact against the bytes.

Why the identifier of the artifact is the digest of the bundle: the digest of the bundle is unguessable by
construction, and no private artifact exists, because every artifact is built from a published bundle of the
two catalogs. Two artifacts of two commits have two identifiers, because two bundles have two digests.

Why the source commit of the artifact is the sha256 of the git commit: the schema of the package pins the
field to sixty four hexadecimal characters, and the git commit of the bundle is forty. The artifact carries
the sha256 of the commit, and the page of the proof names the commit itself, so the reader sees the commit
and the schema holds.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from ledgerlens.replay.bundle import MANIFEST_FILE, bundle_digest

__all__ = ["CATALOGS", "Provenance", "provenance_of", "source_commit_of"]

CATALOGS = ("replay", "replay-real")

# The mode of the bundle, mapped into the vocabulary of the schema of the package: the recording of a real
# model is a live provider run that was recorded, and the schema has no live_agent of its own.
_MODE_BY_BUNDLE_MODE = {
    "deterministic_sandbox": "deterministic_sandbox",
    "live_agent": "live_provider",
}


@dataclass(frozen=True)
class Provenance:
    """The provenance of one artifact: the bundle it was built from, and every digest of it.

    The digests of the files are read from the disk at the moment of the composition, and never copied from
    the manifest, because the manifest could be the thing that moved. The dataset digest pins the world the
    run read, and the catalog says which of the two published catalogs the bundle belongs to.
    """

    artifact_id: str
    bundle: str
    catalog: str
    scenario_id: str
    capture_kind: str
    model_profiles: dict[str, str]
    git_commit: str
    source_commit: str
    snapshot_hash: str
    dataset_path: str
    dataset_digest: str
    file_digests: dict[str, str]
    mode: str


def source_commit_of(git_commit: str) -> str:
    """The source commit of the artifact: the sha256 of the git commit, because the schema pins sixty four hex."""
    return hashlib.sha256(git_commit.encode("utf-8")).hexdigest()


def provenance_of(bundle_dir: Path, *, catalog: str, dataset_path: Path, root: Path) -> Provenance:
    """The provenance of the bundle, read from the manifest of the bundle and from the disk.

    Every digest of a file of the bundle is the digest of the file on the disk, and the digest of the dataset
    is the digest of the dataset file on the disk. The identifier of the artifact is the digest of the bundle.
    """
    if catalog not in CATALOGS:
        raise ValueError(f"the catalog is {catalog!r} and the catalogs are {CATALOGS}")
    manifest = json.loads((bundle_dir / MANIFEST_FILE).read_text(encoding="utf-8"))
    git_commit = str(manifest["code_sha"])
    file_digests = {
        name: hashlib.sha256((bundle_dir / name).read_bytes()).hexdigest() for name in manifest["files"]
    }
    profiles = manifest.get("model_profiles") or {"agent": str(manifest.get("model_profile", ""))}
    return Provenance(
        artifact_id=bundle_digest(bundle_dir),
        bundle=str(bundle_dir.relative_to(root)),
        catalog=catalog,
        scenario_id=str(manifest["scenario"]),
        capture_kind=str(manifest["capture_kind"]),
        model_profiles={str(role): str(profile) for role, profile in profiles.items()},
        git_commit=git_commit,
        source_commit=source_commit_of(git_commit),
        snapshot_hash=str(manifest["snapshot_sha256"]),
        dataset_path=str(dataset_path.relative_to(root)),
        dataset_digest=hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        file_digests=file_digests,
        mode=_MODE_BY_BUNDLE_MODE.get(str(manifest["mode"]), "recorded_replay"),
    )
