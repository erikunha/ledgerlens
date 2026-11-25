"""The published result of the economics: the export, its hash and the digest of its cohort.

What they guarantee, and why: (a) the export of a result is byte identical when it runs twice, so a published
number is a number and not a rendering that drifts; (b) the artifact carries the hash of its content and the digest
of the cohort it was computed over, so a reader can check what it was computed from; (c) the export copies, hashes
and labels and never changes the recorded content; (d) a cohort whose digest moved is refused.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ledgerlens.economics.assumptions import Assumptions, PriceSnapshot, ReviewAssumption
from ledgerlens.economics.cost import CATEGORY_MODEL, CaseCost, CohortCost, CostCategory
from ledgerlens.economics.publish import export_economics, published_bytes

PRICE = PriceSnapshot(
    source="manual",
    last_verified=date(2026, 11, 8),
    input_per_1m_usd=Decimal("0.40"),
    output_per_1m_usd=Decimal("1.60"),
)
ASSUMPTIONS = Assumptions(
    review=ReviewAssumption(minutes=Decimal("15"), hourly_rate_usd=Decimal("60.00"), source="manual"),
    prices=(("gpt-4.1-mini", PRICE),),
)


def _cohort(digest: str = "digest-a") -> CohortCost:
    """A cohort of two cases, one of them resolved."""
    return CohortCost(
        cohort_id="cohort-1",
        cases=(
            CaseCost(
                case_id="EC-01",
                categories=(CostCategory(name=CATEGORY_MODEL, usd=Decimal("0.010"), known=True),),
                resolved=True,
                went_to_person=False,
            ),
            CaseCost(
                case_id="EC-02",
                categories=(
                    CostCategory(name=CATEGORY_MODEL, usd=Decimal("0.020"), known=True),
                    CostCategory(name="review", usd=Decimal("15.00"), known=True),
                ),
                resolved=False,
                went_to_person=True,
            ),
        ),
        assumptions=ASSUMPTIONS,
        cohort_digest=digest,
    )


def test_the_export_of_a_result_is_byte_identical_when_it_runs_twice() -> None:
    """The same result exported twice is the same bytes, so a published number does not drift.

    Why it matters: an artifact that changes every time it is written is an artifact nobody can compare with the
    one of the day before.
    """
    first = published_bytes(_cohort())
    second = published_bytes(_cohort())

    assert first == second


def test_the_artifact_carries_the_hash_of_its_content() -> None:
    """The artifact carries the hash of what it holds, so a reader can check that it did not change."""
    payload = published_bytes(_cohort())

    assert payload["sha256"]
    assert len(payload["sha256"]) == 64


def test_the_artifact_carries_the_digest_of_the_cohort_it_was_computed_over() -> None:
    """The artifact names the cohort it was computed over, and a reader can check it."""
    payload = published_bytes(_cohort(digest="digest-a"))

    assert payload["cohort_digest"] == "digest-a"


def test_the_export_copies_the_content_and_never_changes_it() -> None:
    """The numbers of the cohort are the numbers of the artifact, and the export adds no amount of its own."""
    payload = published_bytes(_cohort())

    assert payload["cohort"]["total_usd"] == "15.030"
    assert payload["cohort"]["resolved_cases"] == 1
    assert payload["cohort"]["cost_per_resolved_usd"] == "15.030"


def test_a_cohort_whose_digest_moved_is_refused() -> None:
    """An artifact over a cohort that is not the one that was measured is refused.

    Why it matters: a result computed over one cohort and published over another is a result that describes nothing.
    """
    with pytest.raises(ValueError, match="digest"):
        export_economics(_cohort(digest="digest-a"), expected_digest="digest-b", out_dir=Path("/tmp/never-written"))


def test_the_export_writes_the_file_and_names_it(tmp_path: Path) -> None:
    """The export writes the artifact and returns where it wrote it."""
    path = export_economics(_cohort(), expected_digest="digest-a", out_dir=tmp_path)

    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["cohort"]["cohort_id"] == "cohort-1"


def test_the_published_assumptions_carry_the_price_of_the_model_whose_money_is_published() -> None:
    """The price that the money of the cohort was computed with travels with the cohort.

    Why it matters: a reader has to be able to recompute the published money from the published assumptions. A
    price that the registry carries under a bare identifier and the report carries under the name of the deployment
    would not match, and the artifact would publish an unstated price next to a money computed with a verified one.
    """
    snapshot = PriceSnapshot(
        source="manual",
        last_verified=date(2026, 11, 8),
        input_per_1m_usd=Decimal("0.40"),
        output_per_1m_usd=Decimal("1.60"),
    )
    assumptions = Assumptions(review=ReviewAssumption(minutes=Decimal("15")), prices=(("gpt-4.1-mini", snapshot),))
    cohort = CohortCost(
        cohort_id="cohort-1",
        cases=(
            CaseCost(
                case_id="EC-01",
                categories=(CostCategory(name=CATEGORY_MODEL, usd=Decimal("0.010"), known=True),),
                resolved=True,
                went_to_person=False,
            ),
        ),
        assumptions=assumptions,
        cohort_digest="digest-a",
    )

    published = published_bytes(cohort)

    assert published["cohort"]["assumptions"]["prices"]["gpt-4.1-mini"]["verified"]
    assert published["cohort"]["assumptions"]["prices"]["gpt-4.1-mini"]["last_verified"] == "2026-11-08"
