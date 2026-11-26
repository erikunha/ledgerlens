"""The export of the proofs: the artifacts of the two published catalogs, under `site/proof/`.

Why the export reads the published catalogs and never a session: the artifacts are built from the bundles of
`data/eval/replay/` and `data/eval/replay-real/`, which are the recordings the repository publishes, and a run
of a visitor is not published and therefore has no artifact. The export writes only under `site/proof/`, and
the two catalogs are read and never written.

Why the export is reproducible: every byte of the export comes from the bundles and from the reports of the
repository, and nothing comes from the clock, so running the export twice leaves the same bytes on the disk,
and the check of the gate compares the published artifacts with the rebuilt ones.
"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import validate

from ledgerlens.proof.artifact import compose, to_schema_dict
from ledgerlens.proof.media import attach_media
from ledgerlens.proof.numbers import number_from_report
from ledgerlens.proof.redact import scan_artifact
from ledgerlens.replay.site_export import discover_bundles

__all__ = ["ProofExportError", "build_proof_export", "check_proof_export", "write_proof_export"]

SCHEMA_PATH = Path("docs/design/contracts/schemas/v3-portfolio-proof.schema.json")
CATALOG_DIRS = {"replay": Path("data/eval/replay"), "replay-real": Path("data/eval/replay-real")}
DATASET_PATH = Path("data/scenarios.json")
HELDOUT_REPORT = Path("data/eval/report_heldout.json")


class ProofExportError(ValueError):
    """The export of the proofs cannot be built, and the message says why."""


def _schema(root: Path) -> dict:
    """The schema of the package, read from the frozen contract of the repository."""
    return json.loads((root / SCHEMA_PATH).read_text(encoding="utf-8"))


def build_proof_export(root: Path) -> dict[str, bytes]:
    """The files of the export of the proofs: one artifact per bundle, and the index of the catalog.

    Every artifact is validated against the schema of the package and scanned by the redaction before it is
    written, and the scan is the last wall: an artifact that carries a secret like string refuses the export
    with the name of the file, and nothing is written.
    """
    schema = _schema(root)
    dataset_path = root / DATASET_PATH
    numbers = (
        number_from_report("heldout_accuracy", root / HELDOUT_REPORT, "accuracy.value", root=root),
    )
    files: dict[str, bytes] = {}
    catalog: list[dict] = []
    for catalog_name, catalog_dir in CATALOG_DIRS.items():
        for bundle_dir in discover_bundles(root / catalog_dir):
            artifact = compose(
                bundle_dir,
                catalog=catalog_name,
                dataset_path=dataset_path,
                numbers=numbers,
                root=root,
            )
            core = to_schema_dict(artifact)
            validate(instance=core, schema=schema)
            name = f"{artifact.provenance.artifact_id}.json"
            text = json.dumps(core, indent=2, sort_keys=True) + "\n"
            scan_artifact(text, name=name)
            files[name] = text.encode("utf-8")
            media = attach_media(bundle_dir, artifact.transcript)
            media_path = str(Path(media.media).relative_to(root)) if media.media is not None else None
            catalog.append(
                {
                    "artifact_id": artifact.provenance.artifact_id,
                    "scenario_id": artifact.provenance.scenario_id,
                    "catalog": artifact.provenance.catalog,
                    "capture_kind": artifact.provenance.capture_kind,
                    "status": artifact.status.value,
                    "missing": list(artifact.status.missing),
                    "git_commit": artifact.provenance.git_commit,
                    "claim": artifact.claim,
                    "evidence_refs": list(artifact.evidence_refs),
                    "verdict_summary": artifact.verdict_summary,
                    "numbers": [
                        {
                            "name": number.name,
                            "value": str(number.value),
                            "report_path": number.report_path,
                            "report_digest": number.report_digest,
                        }
                        for number in artifact.numbers
                    ],
                    "recipe": artifact.recipe,
                    "links": list(artifact.links),
                    "media": media_path,
                    "transcript": media.transcript,
                    "media_dropped": media.dropped,
                    "known_limitations": list(artifact.known_limitations),
                    "cost_usd": str(artifact.cost_usd) if artifact.cost_usd is not None else None,
                    "cost_provenance": artifact.cost_provenance,
                }
            )
    catalog.sort(key=lambda entry: (entry["catalog"], entry["scenario_id"]))
    index = json.dumps({"artifacts": catalog}, indent=2, sort_keys=True) + "\n"
    scan_artifact(index, name="index.json")
    files["index.json"] = index.encode("utf-8")
    return files


def write_proof_export(files: dict[str, bytes], out_dir: Path) -> None:
    """The write of the export, after the scan of every file: the last wall is behind."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (out_dir / name).write_bytes(content)


def check_proof_export(files: dict[str, bytes], out_dir: Path) -> list[str]:
    """The differences between the rebuilt export and the published one, one line each.

    The check writes nothing: a published proof that does not match its bundle is a proof that drifted, and
    the gate refuses it with the name of the file.
    """
    problems: list[str] = []
    for name, content in sorted(files.items()):
        published = out_dir / name
        if not published.is_file():
            problems.append(f"the published proof {name} is not on the disk")
        elif published.read_bytes() != content:
            problems.append(f"the published proof {name} does not match its bundle")
    for published in sorted(out_dir.glob("*.json")):
        if published.name not in files:
            problems.append(f"the published proof {published.name} has no bundle it was built from")
    return problems
