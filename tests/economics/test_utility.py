"""The expected loss of a policy, with the classes kept apart and the unknowns named.

What they guarantee, and why: (a) the expected loss of a policy is the sum of the loss of each class times its
count, and the false accept and the false reject never share a number; (b) two classes that overlap are refused
before the sum, because a case that is in both of them would be counted twice; (c) a probability that was never
calibrated is published as unknown and never as a point; (d) a loss that nobody knows leaves the total unknown and
names the class that is missing; (e) the module publishes no return; (f) the curve of the risk and the coverage is
drawn over the labels that carry a probability.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ledgerlens.economics.utility import (
    CLASS_FALSE_ACCEPT,
    CLASS_FALSE_REJECT,
    ErrorClass,
    compare_policies,
    expected_loss_of,
    risk_coverage_curve,
)

# The fixture of four classes with known counts and known losses, so that the expected loss of the fixture is
# computed by hand: the two correct outcomes cost nothing and the two errors cost 1 * 500 + 2 * 50 = 600.
TRUE_ACCEPT = ErrorClass(name="true_accept", count=3, loss_usd=Decimal("0"), probability=Decimal("1"))
FALSE_ACCEPT = ErrorClass(name=CLASS_FALSE_ACCEPT, count=1, loss_usd=Decimal("500"), probability=Decimal("1"))
FALSE_REJECT = ErrorClass(name=CLASS_FALSE_REJECT, count=2, loss_usd=Decimal("50"), probability=Decimal("1"))
TRUE_REJECT = ErrorClass(name="true_reject", count=4, loss_usd=Decimal("0"), probability=Decimal("1"))


def test_the_expected_loss_is_the_sum_of_the_loss_of_each_class_times_its_count() -> None:
    """The number is the sum of the four classes, computed by hand over the fixture."""
    loss = expected_loss_of((TRUE_ACCEPT, FALSE_ACCEPT, FALSE_REJECT, TRUE_REJECT))

    assert loss.total_usd == Decimal("600")
    # The count multiplies the loss of the class: the false rejects are two cases of fifty.
    assert loss.by_class[CLASS_FALSE_REJECT] == Decimal("100")


def test_the_false_accept_and_the_false_reject_never_share_a_number() -> None:
    """The two classes of the error are published apart, because they cost different things.

    Why it matters: a system that accepts a case it should reject and a system that rejects a case it should accept
    do not lose the same money, and a number that merged them would hide which one hurt.
    """
    loss = expected_loss_of((TRUE_ACCEPT, FALSE_ACCEPT, FALSE_REJECT, TRUE_REJECT))

    assert loss.by_class[CLASS_FALSE_ACCEPT] == Decimal("500")
    assert loss.by_class[CLASS_FALSE_REJECT] == Decimal("100")
    assert loss.by_class[CLASS_FALSE_ACCEPT] != loss.by_class[CLASS_FALSE_REJECT]


def test_two_classes_that_overlap_are_refused_before_the_sum() -> None:
    """A case that is in two classes of the error would be counted twice, and the module refuses the sum.

    Why it matters: the classes of the error have to be mutually exclusive, and a sum over classes that overlap is
    a number that overstates the loss.
    """
    overlapping = ErrorClass(name="case_both", count=1, loss_usd=Decimal("100"), probability=Decimal("1"))
    other = ErrorClass(name="case_other", count=1, loss_usd=Decimal("100"), probability=Decimal("1"))
    overlap = ErrorClass(
        name="case_other",
        count=1,
        loss_usd=Decimal("100"),
        probability=Decimal("1"),
        overlaps_with=("case_both",),
    )

    with pytest.raises(ValueError, match="overlap"):
        expected_loss_of((overlapping, other, overlap))


def test_an_uncalibrated_probability_is_published_as_unknown_and_not_as_a_point() -> None:
    """A probability that nobody calibrated is not a probability, and the module says so.

    Why it matters: an uncalibrated confidence read as a probability turns a guess into a number of money.
    """
    uncalibrated = ErrorClass(name="uncalibrated", count=2, loss_usd=Decimal("100"), probability=None)

    loss = expected_loss_of((uncalibrated,))

    assert loss.total_usd is None
    assert loss.unknown_classes() == ("uncalibrated",)
    assert any("calibrated" in reason for reason in loss.unknown_reasons)


def test_a_loss_that_nobody_knows_leaves_the_total_unknown_and_names_the_class() -> None:
    """A class with no known loss leaves the total unknown, and the class is named.

    Why it matters: a missing loss treated as a zero would say that the error was free.
    """
    unknown_loss = ErrorClass(name="no_loss", count=2, loss_usd=None, probability=Decimal("1"))

    loss = expected_loss_of((unknown_loss,))

    assert loss.total_usd is None
    assert loss.unknown_classes() == ("no_loss",)


def test_the_module_publishes_no_return() -> None:
    """The module publishes the loss and the coverage and never a return.

    Why it matters: a return is a claim about the future, and the module computes over the runs that already
    happened.
    """
    loss = expected_loss_of((TRUE_ACCEPT, FALSE_ACCEPT, FALSE_REJECT, TRUE_REJECT))

    published = loss.to_dict()

    assert "return" not in published
    assert "roi" not in published
    assert published["total_usd"] == "600"


def test_the_loss_of_a_policy_carries_the_assumptions_that_produced_it() -> None:
    """A result of the utility names the assumptions it used."""
    loss = expected_loss_of((TRUE_ACCEPT, FALSE_ACCEPT, FALSE_REJECT, TRUE_REJECT))

    published = loss.to_dict()

    assert published["assumptions"]["review"]["source"] == "unstated"


def test_the_result_names_the_source_of_the_probabilities() -> None:
    """The source of the probability of each class is published, because a probability has to come from somewhere.

    Why it matters: a probability that nobody calibrated is a confidence, and a reader has to know which of the
    classes of the loss rests on a measurement and which rests on an assumption.
    """
    measured = ErrorClass(
        name="measured",
        count=2,
        loss_usd=Decimal("100"),
        probability=Decimal("1"),
        source="the cohort of the evaluation",
    )
    assumed = ErrorClass(name="assumed", count=1, loss_usd=Decimal("100"), probability=Decimal("1"), source="manual")

    published = expected_loss_of((measured, assumed)).to_dict()

    assert published["sources"]["measured"] == "the cohort of the evaluation"
    assert published["sources"]["assumed"] == "manual"


def test_the_comparison_of_the_three_policies_is_over_the_same_mix_of_cases() -> None:
    """The automatic resolution, the review and the abstention are compared over the same cohort.

    Why it matters: the three policies pay for different things, and a comparison over different mixes of cases
    would measure the mixes and not the policies.
    """
    comparison = compare_policies(
        (TRUE_ACCEPT, FALSE_ACCEPT, FALSE_REJECT, TRUE_REJECT),
        review_cost_usd=Decimal("15.00"),
        abstained_count=1,
    )

    # The automatic resolution pays for the errors it made on its own: 500 + 100.
    assert comparison.automatic.total_usd == Decimal("600")
    # The review of every case pays for the review and makes no error of its own.
    assert comparison.review.total_usd == Decimal("150.00")
    # The abstention reviews only the uncertain case and pays for it.
    assert comparison.abstention.total_usd == Decimal("15.00")
    assert comparison.to_dict()["cases"] == 10


def test_the_curve_of_the_risk_and_the_coverage_is_drawn_over_the_labels_that_carry_a_probability() -> None:
    """The curve has one point per label with a probability, and it names the labels it left out.

    Why it matters: a curve drawn over a label with no probability would draw a point nobody measured.
    """
    curve = risk_coverage_curve(
        (
            ErrorClass(name="certain", count=2, loss_usd=Decimal("100"), probability=Decimal("1.0")),
            ErrorClass(name="unsure", count=1, loss_usd=Decimal("100"), probability=Decimal("0.5")),
            ErrorClass(name="unmeasured", count=1, loss_usd=Decimal("100"), probability=None),
        )
    )

    assert len(curve.points) == 2
    assert curve.points[0].label == "certain"
    assert curve.points[0].coverage == Decimal("2")
    assert curve.left_out == ("unmeasured",)
