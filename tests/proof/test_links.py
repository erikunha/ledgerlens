"""The links of the artifact: every link resolves inside the commit the artifact names.

What they guarantee, and why: every link of the artifact resolves inside the commit that the artifact names,
and the recipe carries the command that reproduces the run, because a link that points at nothing is a link
that lies, and a recipe that does not reproduce the run is not a recipe.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from ledgerlens.proof.artifact import check_links, compose
from ledgerlens.proof.numbers import number_from_report


def _artifact(bundle, dataset, root):
    numbers = (
        number_from_report("heldout_accuracy", root / "data/eval/report_heldout.json", "accuracy.value", root=root),
    )
    return compose(bundle, catalog="replay", dataset_path=dataset, numbers=numbers, root=root)


def test_every_link_of_the_artifact_resolves_inside_the_commit_it_names(bundle_replay, dataset, root) -> None:
    """The links are the paths of the commit: the files of the bundle, the dataset and the reports."""
    artifact = _artifact(bundle_replay, dataset, root)

    assert artifact.links
    assert check_links(artifact, root) == []


def test_the_recipe_carries_the_command_that_reproduces_the_run(bundle_replay, dataset, root) -> None:
    """The recipe names the command of the capture of the catalog of the bundle."""
    artifact = _artifact(bundle_replay, dataset, root)

    assert "scripts/capture_replay.py" in artifact.recipe
    assert "--scenario S01" in artifact.recipe
