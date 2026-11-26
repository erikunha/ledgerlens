"""Read experiment records without silently overwriting duplicate fields."""

import json
from pathlib import Path


def _unique_keys(entries: list[tuple[str, object]]) -> dict[str, object]:
    value = dict(entries)
    if len(value) != len(entries):
        raise ValueError("duplicate key in input JSON")
    return value


def read_experiment_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
