"""The verifier's NLI model: loaded on demand, plus a deterministic stand-in for tests.

Why it exists: comparing a claim with the evidence (premise: evidence, hypothesis: claim) needs a natural
language inference model. The real model (`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`, about 740 MB,
English, three labels) lives in the optional `verify` extra (`transformers` and `torch`) and is imported only on
the first prediction. In offline mode (`LEDGERLENS_OFFLINE=1`) or without `transformers`, `get_nli` returns
`StubNli`, which decides by simple rules and always gives the same answer. Both have the same interface:
`predict(premise, hypothesis) -> {"entailment": p, "neutral": p, "contradiction": p}`.
"""

from __future__ import annotations

import importlib.util
import math
import os
import re
from collections.abc import Callable
from typing import Protocol

MODEL_ID = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
MAX_LENGTH = 512  # the model's limit, in tokens; the premise is truncated, the hypothesis is not

_NEGATIONS = {"not", "no", "never", "cannot", "without", "neither", "nor"}
# end of sentence, line break and the divisions of a JSON (braces, brackets and a comma before a new key)
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+|\n+|[{}\[\]]|,\s*(?=\")")
_STOPWORDS = {
    "the",
    "a",
    "an",
    "was",
    "were",
    "is",
    "are",
    "of",
    "to",
    "in",
    "on",
    "for",
    "by",
    "has",
    "have",
    "had",
    "with",
    "and",
    "or",
    "at",
    "as",
    "it",
    "its",
    "that",
    "this",
    "be",
    "been",
    "because",
    "after",
    "from",
    "which",
    "about",
}
# Word pairs that cannot both hold for the same thing.
_OPPOSITES = [
    ("approved", "rejected"),
    ("won", "lost"),
    ("paid", "unpaid"),
    ("paid", "scheduled"),
    ("captured", "failed"),
    ("opened", "closed"),
    ("refunded", "declined"),
    ("increase", "decrease"),
]
_ENTITY_OR_DATE = re.compile(r"\b[A-Z]{1,3}-\d+\b|\b\d{4}-\d{2}-\d{2}\b")
_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?\b")
_CURRENCY = re.compile(r"\b(?:BRL|USD|EUR|GBP)\b")
_WORD = re.compile(r"[\w-]+(?:\.\d+)*")
_ENTAILMENT_COVERAGE = 0.75


class Nli(Protocol):
    def predict(self, premise: str, hypothesis: str) -> dict[str, float]: ...


def _tokens(text: str) -> list[str]:
    """Lowercase words, with the contraction "n't" read as "not"."""
    return _WORD.findall(text.lower().replace("n't", " not").replace("n’t", " not"))


def _content_words(text: str) -> list[str]:
    words = []
    for token in _tokens(text):
        if token in _STOPWORDS or token in _NEGATIONS:
            continue
        # simple plural ("transactions" and "transaction" are the same word); ids and numbers stay as they are
        if len(token) > 3 and token.endswith("s") and not any(ch.isdigit() or ch == "-" for ch in token):
            token = token[:-1]
        words.append(token)
    return words


def _negated(tokens: set[str]) -> bool:
    return bool(tokens & _NEGATIONS)


def _closest_sentence(premise: str, hypothesis: str) -> str:
    """The premise sentence (or JSON field) that covers the most words of the hypothesis; the first one on a tie."""
    hyp_words = set(_content_words(hypothesis))
    sentences = [s for s in _SENTENCE_BREAK.split(premise) if s.strip()] or [premise]
    return max(sentences, key=lambda s: len(hyp_words & set(_content_words(s))))


class StubNli:
    """Deterministic stand-in: contradicts on a date, number, currency, negation or opposite word.

    It does not understand language: it only compares the facts that show up in both texts. It is there to test
    the verifier without downloading the model, not to measure the quality of the real model.
    """

    def predict(self, premise: str, hypothesis: str) -> dict[str, float]:
        prem_words, hyp_words = set(_content_words(premise)), _content_words(hypothesis)
        coverage = sum(w in prem_words for w in hyp_words) / len(hyp_words) if hyp_words else 0.0
        if self._conflicts(premise, hypothesis, coverage):
            return {"entailment": 0.02, "neutral": 0.05, "contradiction": 0.93}
        if coverage >= _ENTAILMENT_COVERAGE:
            entailment = round(0.88 + 0.1 * coverage, 4)  # above the support threshold in thresholds.json
            return {"entailment": entailment, "neutral": round(0.98 - entailment, 6), "contradiction": 0.02}
        entailment = round(0.3 * coverage, 4)
        return {"entailment": entailment, "neutral": round(0.95 - entailment, 6), "contradiction": 0.05}

    @staticmethod
    def _conflicts(premise: str, hypothesis: str, coverage: float) -> bool:
        def facts(pattern: re.Pattern[str], text: str) -> set[str]:
            return set(pattern.findall(_ENTITY_OR_DATE.sub(" ", text) if pattern is _NUMBER else text))

        for pattern in (_DATE, _NUMBER, _CURRENCY):
            hyp, prem = facts(pattern, hypothesis), facts(pattern, premise)
            if hyp and prem and not hyp <= prem:
                return True
        prem_tokens, hyp_tokens = set(_tokens(premise)), set(_tokens(hypothesis))
        for a, b in _OPPOSITES:
            for x, y in ((a, b), (b, a)):
                if x in hyp_tokens and y in prem_tokens and x not in prem_tokens:
                    return True
        if coverage < 0.6:
            return False
        # the premise's negation only counts in the sentence the hypothesis repeats: a "not" elsewhere does not count
        prem_tokens = set(_tokens(_closest_sentence(premise, hypothesis)))
        return _negated(hyp_tokens) != _negated(prem_tokens)


Backend = tuple[dict[int, str], Callable[[str, str], list[float]]]


class HuggingFaceNli:
    """The real model. Does not import `transformers` or `torch` until the first prediction."""

    def __init__(self, model_id: str = MODEL_ID, *, backend: Backend | None = None, max_length: int = MAX_LENGTH):
        self.model_id = model_id
        self.max_length = max_length
        self._backend = backend

    def _load(self) -> Backend:
        os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")  # lets the second `libomp` load (see below)
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer  # optional `verify` extra

        # faiss (policy index) and torch each bring their own `libomp`. In the same process the second load aborts,
        # and with the warning off a multithreaded prediction ends in a segmentation fault. With a single thread
        # the two runtimes compete for nothing and a prediction (one sentence at a time) still takes seconds.
        torch.set_num_threads(1)
        tokenizer = AutoTokenizer.from_pretrained(self.model_id)
        model = AutoModelForSequenceClassification.from_pretrained(self.model_id).to("cpu")  # CPU: no GPU here
        model.eval()

        def logits(premise: str, hypothesis: str) -> list[float]:
            # "only_first" truncates the premise (the evidence) and keeps the claim
            encoded = tokenizer(
                premise, hypothesis, truncation="only_first", max_length=self.max_length, return_tensors="pt"
            )
            with torch.no_grad():
                return model(**encoded).logits[0].tolist()

        return dict(model.config.id2label), logits

    def predict(self, premise: str, hypothesis: str) -> dict[str, float]:
        if self._backend is None:
            self._backend = self._load()
        id2label, logits_fn = self._backend
        logits = logits_fn(premise, hypothesis)
        peak = max(logits)
        exps = [math.exp(x - peak) for x in logits]
        total = sum(exps)
        scores: dict[str, float] = {}
        for index, exp in enumerate(exps):
            # the label order comes from the model configuration, never from the code
            name = str(id2label[index]).lower()
            canonical = next((c for c in ("entailment", "neutral", "contradiction") if name.startswith(c[:5])), None)
            if canonical is None:
                raise ValueError(f"unexpected NLI label {id2label[index]!r} in {self.model_id}")
            scores[canonical] = exp / total
        return scores


_cache: dict[str, HuggingFaceNli] = {}


def get_nli(offline: bool | None = None, *, require_real: bool = False) -> Nli:
    """The offline stand-in, or the one used without `transformers`/`torch`; else the real model, loaded once.

    With `require_real=True` (the online evaluation) a missing `transformers` or `torch` is an error, not a silent
    fallback to the stand-in, which would measure word rules instead of inference.
    """
    if offline is None:
        from ledgerlens.config import offline as offline_mode

        offline = offline_mode()
    missing = any(importlib.util.find_spec(name) is None for name in ("transformers", "torch"))
    if require_real and not offline and missing:
        raise RuntimeError(
            "the real NLI model needs `transformers` and `torch`: install the `verify` extra (uv sync --extra verify)"
        )
    if offline or missing:
        return StubNli()
    return _cache.setdefault(MODEL_ID, HuggingFaceNli(MODEL_ID))
