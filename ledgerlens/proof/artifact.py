"""The composition of the artifact: every section comes from a file of the repository.

Why every section of the artifact has a source: the claim is the question of the bundle, the evidence is the
evidence of the claims of the run, the verdicts are the verdicts of the deterministic verifier re-verified
offline, the provenance is the manifest of the bundle and the disk, the numbers are the reports of the
repository, the recipe is the command of the capture, and the links are the paths of the commit the artifact
names. A section without a source would be a sentence a reader cannot check.

Why the artifact is a claim about the code and never about a person: the artifact names the code, the commit
and the digests, and it attests to a claim about the code of the repository. The repository does not issue
proof of employment and publishes nothing about a person, and no sentence of the artifact is about an employer
or a hiring decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from ledgerlens.proof.numbers import Number
from ledgerlens.proof.provenance import Provenance, provenance_of
from ledgerlens.proof.status import Status, status_of
from ledgerlens.proof.verification import reverification_passes, verdict_summary_of
from ledgerlens.replay.verdict import published_result

__all__ = ["ProofArtifact", "check_links", "compose", "to_schema_dict"]

# The command of the capture of each catalog, the recipe that reproduces the run of the bundle.
_RECIPE_BY_CATALOG = {
    "replay": "LEDGERLENS_OFFLINE=1 uv run python scripts/capture_replay.py --scenario {scenario}",
    "replay-real": "uv run python scripts/capture_live_replay.py --scenario {scenario}",
}

# The limitations of the artifact of each catalog: the catalog of a real model is not reproducible byte for
# byte, under ADR-075, and the artifact says so.
_LIMITATIONS_BY_CATALOG = {
    "replay": (
        "the run is the recording of the scripted model, and it reproduces the run of the capture byte for byte",
        "the artifact attests to a claim about the code of the repository and says nothing about a person",
    ),
    "replay-real": (
        "the run is the recording of one run of a real model, and it is not reproducible byte for byte",
        "the artifact attests to a claim about the code of the repository and says nothing about a person",
    ),
}

# The cost of the run of each catalog: the scripted run costs nothing to replay, and the bundle of a real
# model does not carry the cost of the provider run, so the artifact says the cost is unknown.
_COST_BY_CATALOG = {
    "replay": (None, "replayed"),
    "replay-real": (None, "unknown"),
}


@dataclass(frozen=True)
class ProofArtifact:
    """The artifact of one bundle: the claim, the evidence, the provenance, the status and the recipe.

    The artifact is the composition of the sections, and every section names its source. The schema of the
    package is the projection of the artifact, and the page of the proof renders the composition.
    """

    provenance: Provenance
    claim: str
    evidence_refs: tuple[str, ...]
    verdict_summary: str
    status: Status
    numbers: tuple[Number, ...]
    recipe: str
    links: tuple[str, ...]
    transcript: str
    cost_usd: Decimal | None
    cost_provenance: str
    known_limitations: tuple[str, ...]
    privacy_reviewed: bool


def compose(
    bundle_dir: Path,
    *,
    catalog: str,
    dataset_path: Path,
    numbers: tuple[Number, ...],
    root: Path,
) -> ProofArtifact:
    """The artifact of one bundle of a published catalog, composed from the bundle and the disk.

    The status is computed over the provenance and the offline re-verification, and the recipe is the command
    of the capture of the catalog of the bundle. The links are the paths of the commit the artifact names:
    the files of the bundle, the dataset and the reports of the numbers.
    """
    provenance = provenance_of(bundle_dir, catalog=catalog, dataset_path=dataset_path, root=root)
    result = published_result(bundle_dir)
    status = status_of(provenance, reverified=reverification_passes(bundle_dir), root=root)
    recipe = _RECIPE_BY_CATALOG[catalog].format(scenario=provenance.scenario_id)
    links = tuple(
        [f"{provenance.bundle}/{name}" for name in provenance.file_digests]
        + [provenance.dataset_path]
        + [number.report_path for number in numbers]
    )
    claim = f"the run of the scenario {provenance.scenario_id} of the repository: {result.question}"
    verdict_summary = verdict_summary_of(bundle_dir)
    transcript = (
        f"the run of the scenario {provenance.scenario_id} of the repository, "
        f"over the ledger of the dataset {provenance.dataset_path}. "
        f"The question of the run: {result.question} "
        f"The verdicts of the deterministic verifier: {verdict_summary}."
    )
    cost_usd, cost_provenance = _COST_BY_CATALOG[catalog]
    return ProofArtifact(
        provenance=provenance,
        claim=claim,
        evidence_refs=tuple(evidence.id for evidence in result.evidence),
        verdict_summary=verdict_summary,
        status=status,
        numbers=numbers,
        recipe=recipe,
        links=links,
        transcript=transcript,
        cost_usd=cost_usd,
        cost_provenance=cost_provenance,
        known_limitations=_LIMITATIONS_BY_CATALOG[catalog],
        privacy_reviewed=True,
    )


def check_links(artifact: ProofArtifact, root: Path) -> list[str]:
    """The links of the artifact that do not resolve inside the commit the artifact names.

    A link of the artifact is a path of the commit, and the commit is the checkout the export was built from:
    a link that does not resolve on the disk is a link that points at nothing, and the check names it.
    """
    return [link for link in artifact.links if not (root / link).is_file()]


def to_schema_dict(artifact: ProofArtifact) -> dict:
    """The projection of the artifact into the schema of the package, for the validation and the export."""
    return {
        "schema_version": "3",
        "artifact_id": artifact.provenance.artifact_id,
        "mode": artifact.provenance.mode,
        "source_commit": artifact.provenance.source_commit,
        "scenario_id": artifact.provenance.scenario_id,
        "snapshot_hash": artifact.provenance.snapshot_hash,
        "trace_refs": [f"{artifact.provenance.bundle}/{name}" for name in artifact.provenance.file_digests],
        "claim_evidence_refs": list(artifact.evidence_refs),
        "verdict_summary": artifact.verdict_summary,
        "cost_usd": str(artifact.cost_usd) if artifact.cost_usd is not None else None,
        "cost_provenance": artifact.cost_provenance,
        "known_limitations": list(artifact.known_limitations),
        "privacy_reviewed": artifact.privacy_reviewed,
    }
