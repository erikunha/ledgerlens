"""The shared fixtures of the proof tests: the bundles of the two published catalogs.

Why the tests read the published bundles: the artifact is a claim about the code of the repository over the
published catalogs, and a test over a fixture bundle would prove the composition over a bundle nobody
published. The two bundles of the fixtures are the s01 of each catalog, and the dataset of the run is the
file of the scenarios of the repository.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BUNDLE_REPLAY = ROOT / "data" / "eval" / "replay" / "s01"
BUNDLE_REPLAY_REAL = ROOT / "data" / "eval" / "replay-real" / "s01"
DATASET = ROOT / "data" / "scenarios.json"


@pytest.fixture
def root() -> Path:
    """The root of the repository, for the paths the artifact names."""
    return ROOT


@pytest.fixture
def bundle_replay() -> Path:
    """The bundle s01 of the catalog of the scripted model."""
    return BUNDLE_REPLAY


@pytest.fixture
def bundle_replay_real() -> Path:
    """The bundle s01 of the catalog of a real model."""
    return BUNDLE_REPLAY_REAL


@pytest.fixture
def dataset() -> Path:
    """The dataset of the run: the file of the scenarios of the repository."""
    return DATASET
