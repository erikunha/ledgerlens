"""The scope of the claim: the artifact names the code, the commit and the digests, and never a person.

What they guarantee, and why: the artifact names the code, the commit and the digests, and no sentence of it
is about an employer or a hiring decision, because the artifact is a claim about the code of the repository
and never a proof of a person or of an employer.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import re

from ledgerlens.proof.artifact import compose, to_schema_dict
from ledgerlens.proof.numbers import number_from_report

FORBIDDEN = re.compile(r"\bemployer\b|\bhiring\b|\bproof of employment\b|\brecruiter\b|\bcandidate\b", re.IGNORECASE)


def _artifact(bundle, dataset, root):
    numbers = (
        number_from_report("heldout_accuracy", root / "data/eval/report_heldout.json", "accuracy.value", root=root),
    )
    return compose(bundle, catalog="replay", dataset_path=dataset, numbers=numbers, root=root)


def test_the_artifact_names_the_code_the_commit_and_the_digests(bundle_replay, dataset, root) -> None:
    """The claim of the artifact is about the code of the repository, with the commit and the digests."""
    artifact = _artifact(bundle_replay, dataset, root)
    core = to_schema_dict(artifact)

    assert "the run of the scenario S01 of the repository" in artifact.claim
    assert core["source_commit"]
    assert core["snapshot_hash"]
    assert artifact.provenance.git_commit


def test_no_sentence_of_the_artifact_is_about_an_employer_or_a_hiring_decision(bundle_replay, dataset, root) -> None:
    """The artifact attests to a claim about the code and never about a person."""
    artifact = _artifact(bundle_replay, dataset, root)
    text = "\n".join(
        [artifact.claim, artifact.verdict_summary, artifact.transcript, *artifact.known_limitations]
    )

    assert not FORBIDDEN.search(text)
