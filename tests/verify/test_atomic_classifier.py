"""Protect the atomic classifier's evidence and decision contracts."""

import json

import pytest

from ledgerlens.offline import ScriptedChatModel
from ledgerlens.verify.atomic_classifier import AtomicEvidenceClassifier

EVIDENCE = "The transfer was approved. The transfer was rejected. The fee was $10."
CLAIM = "The transfer was approved and the fee was $5."
APPROVAL = "The transfer was approved."
REJECTION = "The transfer was rejected."
FEE = "The fee was $10."


def atom(claim, label, evidence_quote=None, conflicting_quote=None):
    return dict(claim=claim, label=label, evidence_quote=evidence_quote, conflicting_quote=conflicting_quote)


def classifier_for(*atoms):
    model = ScriptedChatModel(script=[json.dumps({"atoms": atoms})])
    return AtomicEvidenceClassifier(model), model


@pytest.mark.parametrize(
    ("atoms", "label"),
    [
        ([atom(APPROVAL, "entailment", APPROVAL)], "entailment"),
        ([atom(APPROVAL, "entailment", APPROVAL), atom("The fee was waived.", "neutral")], "neutral"),
        ([atom(APPROVAL, "neutral", APPROVAL, REJECTION)], "neutral"),
        (
            [atom(APPROVAL, "neutral", APPROVAL, REJECTION), atom("The fee was $5.", "contradiction", FEE)],
            "contradiction",
        ),
    ],
)
def test_predict_combines_atomic_labels(atoms, label):
    classifier, _ = classifier_for(*atoms)
    scores = classifier.predict(EVIDENCE, " and ".join(finding["claim"] for finding in atoms))
    assert scores == {name: float(name == label) for name in ("entailment", "contradiction", "neutral")}


def test_assess_sends_only_evidence_and_claim_and_explains_every_atom():
    atoms = [
        atom(APPROVAL, "neutral", APPROVAL, REJECTION),
        atom("The fee was $5.", "contradiction", FEE),
        atom("A receipt was sent.", "neutral"),
        atom(FEE, "entailment", FEE),
        atom("The transfer reached the recipient.", "neutral", APPROVAL),
    ]
    classifier, model = classifier_for(*atoms)
    result = classifier.assess(EVIDENCE, CLAIM)

    assert len(model.calls) == 1
    assert json.loads(model.calls[0][-1].content) == {"evidence": EVIDENCE, "claim": CLAIM}
    assert json.loads(json.dumps(result)) == result
    assert result["atoms"] == atoms
    assert result["label"] == "contradiction"
    assert result["answer"] == (
        'The evidence contradicts the claim.\n\n'
        '- “The transfer was approved.” The evidence conflicts. One passage says “The transfer was approved.” '
        'Another says “The transfer was rejected.”\n'
        '- “The fee was $5.” The evidence contradicts this part. It says “The fee was $10.”\n'
        '- “A receipt was sent.” The supplied evidence does not establish this part.\n'
        '- “The fee was $10.” The evidence supports this part. It says “The fee was $10.”\n'
        '- “The transfer reached the recipient.” The supplied evidence does not establish this part. '
        'The relevant passage says “The transfer was approved.”'
    )


def test_absent_evidence_returns_neutral_without_calling_the_model():
    classifier, model = classifier_for()
    result = classifier.assess(" \n", CLAIM)
    assert model.calls == []
    assert result == {
        "atoms": [atom(CLAIM, "neutral")],
        "label": "neutral",
        "answer": (
            "The evidence does not settle the claim.\n\n"
            "- “The transfer was approved and the fee was $5.” The supplied evidence does not establish this part."
        ),
    }


@pytest.mark.parametrize(
    ("payload", "error"),
    [
        ("not JSON", "Invalid JSON"),
        (json.dumps({"atoms": []}), "at least 1 item"),
        (json.dumps({"atoms": [atom(APPROVAL, "approved", APPROVAL)]}), "Input should be"),
        (json.dumps({"atoms": [atom("  ", "neutral")]}), "atom claim must not be blank"),
        (json.dumps({"atoms": [atom(APPROVAL, "entailment")]}), "requires an evidence quote"),
        (json.dumps({"atoms": [atom(APPROVAL, "neutral", " ")]}), "evidence quote must contain text"),
        (json.dumps({"atoms": [atom(APPROVAL, "entailment", "Transfer approved.")]}), "exact passage"),
        (json.dumps({"atoms": [atom(APPROVAL, "neutral", APPROVAL, "Transfer rejected.")]}), "exact passage"),
        (json.dumps({"atoms": [atom(APPROVAL, "neutral", None, REJECTION)]}), "different evidence quotes"),
        (json.dumps({"atoms": [atom(APPROVAL, "neutral", APPROVAL, APPROVAL)]}), "different evidence quotes"),
        (json.dumps({"atoms": [atom(APPROVAL, "entailment", APPROVAL, REJECTION)]}), "must be neutral"),
        (json.dumps({"atoms": [atom(APPROVAL, "neutral")], "label": "entailment"}), "Extra inputs"),
    ],
)
def test_assess_rejects_unusable_model_output(payload, error):
    classifier = AtomicEvidenceClassifier(ScriptedChatModel(script=[payload]))
    with pytest.raises(ValueError, match=error):
        classifier.assess(EVIDENCE, CLAIM)
