"""The NLI model: loaded on demand, a deterministic stand-in, and the label order read from the configuration."""

from __future__ import annotations

import importlib.util
import sys

import pytest

from ledgerlens.verify import nli
from ledgerlens.verify.nli import HuggingFaceNli, StubNli, get_nli

LABELS = {"entailment", "neutral", "contradiction"}


def test_the_stub_returns_probabilities_and_is_deterministic() -> None:
    stub = StubNli()
    first = stub.predict("Refund R-0412 was issued on 2026-10-05.", "Refund R-0412 was issued on 2026-10-05.")
    assert set(first) == LABELS
    assert sum(first.values()) == pytest.approx(1.0)
    assert first == stub.predict("Refund R-0412 was issued on 2026-10-05.", "Refund R-0412 was issued on 2026-10-05.")
    assert first["entailment"] > 0.5


def test_the_stub_flags_a_different_date_a_negation_and_an_opposite_word() -> None:
    stub = StubNli()
    assert (
        stub.predict("Refund R-0412 was issued on 2026-10-05.", "Refund R-0412 was issued on 2026-10-03.")[
            "contradiction"
        ]
        > 0.5
    )
    negated = stub.predict("Settlement ST-0044 has status paid.", "Settlement ST-0044 was not paid.")
    assert negated["contradiction"] > 0.5
    assert stub.predict("The refund was approved.", "The refund was rejected.")["contradiction"] > 0.5


def test_the_stub_calls_unrelated_text_neutral() -> None:
    scores = StubNli().predict("Refund R-0412 was issued.", "The customer prefers email.")
    assert scores["neutral"] > scores["entailment"] and scores["neutral"] > scores["contradiction"]


def test_offline_returns_the_stub_even_if_transformers_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda name, *a, **k: object())
    assert isinstance(get_nli(offline=True), StubNli)


def test_the_environment_flag_picks_the_stub_by_default() -> None:
    assert isinstance(get_nli(), StubNli)  # conftest sets LEDGERLENS_OFFLINE=1


def test_missing_transformers_falls_back_to_the_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda name, *a, **k: None)
    assert isinstance(get_nli(offline=False), StubNli)


def test_importing_the_package_does_not_load_the_heavy_libraries() -> None:
    assert "torch" not in sys.modules or "ledgerlens.verify.nli" in sys.modules
    assert not hasattr(nli, "torch") and not hasattr(nli, "transformers")


def test_the_real_wrapper_reads_the_label_order_from_the_model_config() -> None:
    # an order different from the published model's: the code cannot assume the order
    id2label = {0: "CONTRADICTION", 1: "Entailment", 2: "neutral"}

    def logits(premise: str, hypothesis: str) -> list[float]:
        return [0.0, 4.0, 0.0]

    model = HuggingFaceNli("any/model", backend=(id2label, logits))
    scores = model.predict("p", "h")
    assert set(scores) == LABELS
    assert scores["entailment"] > 0.9
    assert sum(scores.values()) == pytest.approx(1.0)


def test_the_real_wrapper_does_not_load_anything_until_it_predicts() -> None:
    model = HuggingFaceNli("any/model")
    assert model._backend is None


# ---- negation ------------------------------------------------------------------------------------

POLICY_SOURCE = (
    "The reference rate is the European Central Bank's daily rate, obtained through the Frankfurter service in the "
    "version that uses only that source. On weekends and holidays the rate of the previous business day applies. "
    "The reference rate is a market reference and not the rate the merchant applied: the applied rate lives on "
    "the conversion record."
)


def test_a_verbatim_sentence_is_not_contradicted_by_a_negation_elsewhere_in_the_chunk() -> None:
    sentence = (
        "The reference rate is the European Central Bank's daily rate, obtained through the Frankfurter service in "
        "the version that uses only that source"
    )
    scores = StubNli().predict(POLICY_SOURCE, sentence)
    assert scores["contradiction"] < 0.5 and scores["entailment"] > 0.7


def test_a_negation_in_the_matching_sentence_contradicts() -> None:
    premise = "The invoice was paid. The refund was approved by the merchant."
    assert StubNli().predict(premise, "The refund was not approved by the merchant.")["contradiction"] > 0.5
    negated = "The refund was not approved by the merchant."
    assert StubNli().predict(negated, "The refund was approved by the merchant.")["contradiction"] > 0.5


def test_no_is_a_negation() -> None:
    scores = StubNli().predict("The merchant has the refund on file.", "The merchant has no refund on file.")
    assert scores["contradiction"] > 0.5


def test_a_negation_in_another_field_of_a_json_premise_does_not_contradict_the_claim() -> None:
    premise = (
        '{"transaction": {"id": "TX-0138", "status": "refunded", "currency": "CAD"}, '
        '"refunds": [{"id": "R-0066", "status": "paid", "reason": "Charge not recognized by the customer"}]}'
    )
    scores = StubNli().predict(premise, "TX-0138 status refunded")
    assert scores["contradiction"] < 0.5 and scores["entailment"] > 0.7


@pytest.mark.parametrize("negation", ["never", "wasn't", "cannot be"])
def test_every_negation_form_contradicts(negation: str) -> None:
    hypothesis = f"The refund {negation} approved by the merchant."
    scores = StubNli().predict("The refund was approved by the merchant.", hypothesis)
    assert scores["contradiction"] > 0.5


def test_a_negation_with_little_overlap_is_neutral_not_contradicted() -> None:
    scores = StubNli().predict("The refund was approved by the merchant.", "The customer did not like the service.")
    assert scores["contradiction"] < 0.5


# ---- loading the real model: CPU and labels from the configuration -----------------------------------------


def test_requiring_the_real_model_refuses_the_stub_when_transformers_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda name, *a, **k: None)
    with pytest.raises(RuntimeError, match="verify"):
        get_nli(offline=False, require_real=True)


def test_the_real_model_is_loaded_once_and_moved_to_the_cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    import types

    moves: list[str] = []

    class FakeModel:
        config = types.SimpleNamespace(id2label={0: "entailment", 1: "neutral", 2: "contradiction"})

        def to(self, device: str) -> FakeModel:
            moves.append(device)
            return self

        def eval(self) -> None:
            pass

        def __call__(self, **encoded: object) -> object:
            return types.SimpleNamespace(logits=[types.SimpleNamespace(tolist=lambda: [3.0, 0.0, 0.0])])

    class FakeTokenizer:
        def __call__(self, premise: str, hypothesis: str, **kw: object) -> dict:
            return {}

    torch = types.ModuleType("torch")
    threads: list[int] = []
    torch.set_num_threads = threads.append  # type: ignore[attr-defined]
    torch.no_grad = lambda: __import__("contextlib").nullcontext()  # type: ignore[attr-defined]
    transformers = types.ModuleType("transformers")
    transformers.AutoTokenizer = types.SimpleNamespace(from_pretrained=lambda mid: FakeTokenizer())  # type: ignore[attr-defined]
    transformers.AutoModelForSequenceClassification = types.SimpleNamespace(  # type: ignore[attr-defined]
        from_pretrained=lambda mid: FakeModel()
    )
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    scores = HuggingFaceNli("any/model").predict("p", "h")
    assert moves == ["cpu"] and threads == [1]
    assert scores["entailment"] > 0.9


@pytest.mark.slow
@pytest.mark.skipif(importlib.util.find_spec("transformers") is None, reason="extra `verify` is not installed")
def test_the_real_model_runs_in_a_process_that_already_loaded_faiss() -> None:
    # The policy index loads faiss and the model loads torch; each brings its own `libomp`, and the
    # second load aborted the process ("OMP: Error #15"). Only a fresh process reproduces that.
    import subprocess

    code = (
        "import faiss, numpy as np\n"
        "faiss.IndexFlatL2(4).add(np.zeros((2, 4), dtype='float32'))\n"
        "from ledgerlens.verify.nli import get_nli\n"
        "scores = get_nli(offline=False, require_real=True).predict('Refund R-1 was paid.', 'Refund R-1 was paid.')\n"
        "print(round(scores['entailment']))\n"
    )
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    assert done.returncode == 0 and done.stdout.strip() == "1", done.stderr[-400:]
