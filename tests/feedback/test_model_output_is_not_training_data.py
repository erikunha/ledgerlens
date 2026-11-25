"""The red line of ADR-P007 expressed as a test: an output of a model is not training data.

What they guarantee, and why: a record whose only support is an output of a model, whether the answer of the
agent, the label of the NLI model or a correction proposed from a suggestion of the model, stays below the
tier `gold` and the training set does not carry it, because a loop without the deterministic gate would be a
machine that trains a model on the agreement of another model.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from ledgerlens.feedback.gate import verdict_of
from ledgerlens.feedback.tiers import GOLD, tier_of
from ledgerlens.feedback.training_set import build_training_set


def test_a_record_supported_only_by_the_answer_of_the_agent_stays_below_gold(record_factory) -> None:
    """The answer of the agent is an output of a model, and it is not evidence."""
    only_answer = record_factory(evidence_refs=(), model_suggested=True)

    assert tier_of(only_answer, verdict_of(only_answer), second_reader="ana") != GOLD


def test_a_record_supported_only_by_the_label_of_the_nli_model_stays_below_gold(record_factory) -> None:
    """The label of the NLI model is a proposal, and a proposal is not evidence."""
    only_nli = record_factory(evidence_refs=(), nli_label="supported")

    assert tier_of(only_nli, verdict_of(only_nli), second_reader="ana") != GOLD


def test_a_correction_proposed_from_a_suggestion_of_the_model_stays_below_gold_without_evidence(
    record_factory,
) -> None:
    """A correction the model suggested is a suggestion, and the evidence is what the gate reads."""
    suggested = record_factory(evidence_refs=(), model_suggested=True, nli_label="supported")

    assert tier_of(suggested, verdict_of(suggested), second_reader="ana") != GOLD


def test_the_training_set_does_not_carry_a_record_whose_only_support_is_a_model(record_factory) -> None:
    """The door of the training set has two conditions, and the support of a model passes neither."""
    only_model = record_factory(evidence_refs=(), model_suggested=True, nli_label="supported")
    tier = tier_of(only_model, verdict_of(only_model), second_reader="ana")

    training_set = build_training_set([only_model], tiers={only_model.record_id: tier})

    assert only_model.record_id not in {record.record_id for record in training_set.records}
