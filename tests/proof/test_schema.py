"""The artifact against the schema of the package: the validation passes, and a broken artifact is refused.

What they guarantee, and why: the artifact validates against `docs/v3/contracts/schemas/v3-portfolio-proof.schema.json`
with `jsonschema`, and an artifact that breaks the schema is refused. The schema is versioned in the frozen
package and it is read, never edited.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import json

import pytest
from jsonschema import ValidationError, validate

from ledgerlens.proof.artifact import compose, to_schema_dict
from ledgerlens.proof.export import SCHEMA_PATH
from ledgerlens.proof.numbers import number_from_report


def _schema(root):
    return json.loads((root / SCHEMA_PATH).read_text(encoding="utf-8"))


def _artifact(bundle, catalog, dataset, root):
    numbers = (
        number_from_report("heldout_accuracy", root / "data/eval/report_heldout.json", "accuracy.value", root=root),
    )
    return compose(bundle, catalog=catalog, dataset_path=dataset, numbers=numbers, root=root)


def test_the_artifact_of_each_catalog_validates_against_the_schema(
    bundle_replay, bundle_replay_real, dataset, root
) -> None:
    """The projection of the artifact into the schema holds for the two catalogs."""
    schema = _schema(root)
    for bundle, catalog in ((bundle_replay, "replay"), (bundle_replay_real, "replay-real")):
        artifact = _artifact(bundle, catalog, dataset, root)
        validate(instance=to_schema_dict(artifact), schema=schema)


def test_an_artifact_that_breaks_the_schema_is_refused(bundle_replay, dataset, root) -> None:
    """A field the schema does not know is a field the artifact may not carry."""
    schema = _schema(root)
    artifact = _artifact(bundle_replay, "replay", dataset, root)
    broken = dict(to_schema_dict(artifact), employer="someone")

    with pytest.raises(ValidationError):
        validate(instance=broken, schema=schema)
