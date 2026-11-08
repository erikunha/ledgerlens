"""Online path of the evaluation, tested only with doubles: no network, no real key, no model.

What they guarantee, and why: (a) `run_online` runs the variants through the `evaluate` it receives, with
the model and client swapped, and builds an `online` report with the judge score, the tokens and the cost per
variant; (b) the experiment URLs come back in the return value but not in the written report; (c) the
LangSmith environment is set with the key from the settings and goes back to what it was on exit; (d) a
failed case scores 0 with the error, instead of stopping the run; (e) the cost comes from the list price and
is `None` for a model off the list; (f) an invalid `--variants` is refused before any call; (g) the committed
online report carries no key, LangSmith URL or machine path.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from ledgerlens.config import get_settings
from ledgerlens.eval import run as eval_run
from ledgerlens.eval.dataset import load_cases, load_verification_cases
from ledgerlens.retrieval import build_policy_index, index_dir_for, load_policy_documents
from ledgerlens.verify.nli import StubNli

ONLINE_METRICS = [*eval_run.METRICS, "explanation"]
ONLINE_REPORT = Path(__file__).resolve().parents[2] / "data" / "eval" / "report_online.json"
FAKE_KEY = "ls-test-key-123"


class AnswerModel(BaseChatModel):
    """Always answers the same sentence, in the shape ReAct and the integrator accept, without calling a tool."""

    @property
    def _llm_type(self) -> str:
        return "answer-model"

    def bind_tools(self, tools: Any, **kwargs: Any) -> AnswerModel:  # type: ignore[override]
        return self

    def _generate(self, messages: list[BaseMessage], stop: Any = None, run_manager: Any = None, **kw: Any):
        text = "Thought: I now know the final answer\nFinal Answer: I could not confirm it."
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])


class FakeClient:
    def __init__(self, examples: list[Any]) -> None:
        self.examples = examples
        self.verification_examples = [eval_run._verification_example(c) for c in load_verification_cases()]
        self.created = False
        self.asked: list[str] = []

    def has_dataset(self, *, dataset_name: str) -> bool:
        return True

    def read_dataset(self, *, dataset_name: str) -> Any:
        return SimpleNamespace(id="dataset-id")

    def update_examples(self, **kwargs: Any) -> None:
        self.updated = kwargs

    def list_examples(self, *, dataset_name: str) -> list[Any]:
        self.asked.append(dataset_name)
        return self.verification_examples if dataset_name == eval_run.VERIFICATION_DATASET else self.examples


class FakeResults(list):
    experiment_name = "ledgerlens-X-abc"
    url = "https://example.invalid/experiment"


def fake_evaluate(target, *, data, evaluators, **kwargs: Any) -> FakeResults:
    """Does what `evaluate` does: runs the target on each example, applies the evaluators, returns the rows."""
    results = FakeResults()
    results.experiment_name = f"{kwargs['experiment_prefix']}-abc"
    for example in data:
        try:
            outputs, error = target(example.inputs), None
        except Exception as exc:  # the real `evaluate` records the error and goes on
            outputs, error = None, str(exc)
        scores = []
        if outputs is not None:
            for evaluator in evaluators:
                scores.append(
                    SimpleNamespace(
                        **{
                            "comment": None,
                            **evaluator(inputs=example.inputs, outputs=outputs, reference_outputs=example.outputs),
                        }
                    )
                )
        run = SimpleNamespace(outputs=outputs, error=error)
        results.append({"example": example, "run": run, "evaluation_results": {"results": scores}})
    return results


@pytest.fixture
def online_settings(tmp_path: Path):
    embeddings = eval_run.OfflineEmbeddings()
    index_root = tmp_path / "index"
    build_policy_index(load_policy_documents(), embeddings, index_dir_for(index_root, embeddings))
    return get_settings(
        env={
            "LEDGERLENS_OFFLINE": "0",
            "LEDGERLENS_MODEL": "gpt-4.1-mini",
            "LANGSMITH_API_KEY": FAKE_KEY,
            "LANGSMITH_PROJECT": "ledgerlens",
            "LEDGERLENS_INDEX_DIR": str(index_root),
            "LEDGERLENS_ENV_FILE": str(tmp_path / "no-such.env"),
        }
    )


@pytest.fixture
def patched(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(eval_run, "ingestion_refusal", lambda settings: None)
    monkeypatch.setattr(eval_run, "get_embeddings", lambda settings=None: eval_run.OfflineEmbeddings())
    monkeypatch.setattr(eval_run, "get_nli", lambda offline=None, **kw: StubNli())
    monkeypatch.setattr(eval_run, "_online_model", lambda: AnswerModel())
    monkeypatch.setattr(
        eval_run, "explanation_judge", lambda model: _named(lambda **_: {"key": "explanation", "score": 0.5})
    )


def _named(fn):
    fn.__name__ = "explanation"
    return fn


def test_the_online_run_builds_a_report_with_the_judge_tokens_and_cost(
    online_settings: Any, patched: None, tmp_path: Path
) -> None:
    cases = load_cases()[:2]
    client = FakeClient([eval_run._example(c) for c in cases])
    report = eval_run.run_online(
        cases,
        settings=online_settings,
        client=client,
        evaluate_fn=fake_evaluate,
        work_dir=tmp_path / "w",
        model=AnswerModel(),
    )
    assert report["mode"] == "online" and report["cases"] == 2 and report["model"] == "gpt-4.1-mini"
    assert len(report["per_case"]) == 6
    for variant, summary in report["variants"].items():
        assert list(summary["metrics"]) == ONLINE_METRICS
        assert summary["metrics"]["explanation"] == 0.5
        assert summary["experiment"] == f"ledgerlens-{variant}-abc"
        assert set(summary["usage"]) == {"input_tokens", "output_tokens", "total_tokens", "cost_usd"}
    assert report["experiments"]["C"]["url"] == "https://example.invalid/experiment"
    assert "experiments" not in eval_run._public(report)
    assert FAKE_KEY not in json.dumps(report)
    assert "(online)" in eval_run.render_markdown(report) and "Tokens and cost" in eval_run.render_markdown(report)


def test_a_failed_case_scores_zero_and_keeps_the_error(online_settings: Any, patched: None, tmp_path: Path) -> None:
    class Failing(AnswerModel):
        def _generate(self, *args: Any, **kwargs: Any):
            raise RuntimeError("provider failure\nsecond line with details")

    cases = load_cases()[:1]
    client = FakeClient([eval_run._example(c) for c in cases])
    report = eval_run.run_online(
        cases,
        variants=("A",),
        settings=online_settings,
        client=client,
        evaluate_fn=fake_evaluate,
        work_dir=tmp_path / "w",
        model=Failing(),
    )
    (row,) = report["per_case"]
    assert row["scores"] == dict.fromkeys(ONLINE_METRICS, 0.0)
    assert row["error"] == "provider failure"


def test_the_langsmith_environment_is_set_for_the_run_and_restored(online_settings: Any) -> None:
    os.environ.pop("LANGSMITH_API_KEY", None)
    os.environ["LANGSMITH_PROJECT"] = "other"
    with eval_run._langsmith_env(online_settings):
        assert os.environ["LANGSMITH_API_KEY"] == FAKE_KEY
        assert os.environ["LANGSMITH_TRACING"] == "true" and os.environ["LANGSMITH_PROJECT"] == "ledgerlens"
    assert "LANGSMITH_API_KEY" not in os.environ and os.environ["LANGSMITH_PROJECT"] == "other"
    assert os.environ["LANGSMITH_TRACING"] == "false"  # the test's value, restored


def test_the_cost_comes_from_the_table_price_and_is_unknown_off_the_table() -> None:
    usage = {"input_tokens": 1_000_000, "output_tokens": 1_000_000}
    assert eval_run._price("openai:gpt-4.1-mini", usage) == pytest.approx(2.0)
    assert eval_run._price("other-model", usage) is None
    total = eval_run._sum_usage({"gpt-4.1-mini": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}}, "")
    assert total["total_tokens"] == 15 and total["cost_usd"] is not None
    assert (
        eval_run._sum_usage({"x": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}}, "")["cost_usd"] is None
    )


def test_an_unknown_variant_is_refused_before_any_call(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setenv("LEDGERLENS_OFFLINE", "0")
    monkeypatch.setenv("LANGSMITH_API_KEY", FAKE_KEY)
    assert eval_run.main(["--online", "--variants", "A,Z", "--out", str(tmp_path)]) == 2
    assert "--variants" in capsys.readouterr().err


def test_the_committed_online_report_has_no_key_url_or_local_path() -> None:
    if not ONLINE_REPORT.exists():
        pytest.skip("the online report has not been generated yet")
    for path in (ONLINE_REPORT, ONLINE_REPORT.with_suffix(".md")):
        text = path.read_text("utf-8")
        home = "/" + "Users" + "/"
        assert "smith.langchain.com" not in text and home not in text and "ls__" not in text and "sk-" not in text
    report = json.loads(ONLINE_REPORT.read_text("utf-8"))
    assert report["mode"] == "online" and report["cases"] == 30 and "experiments" not in report


# ---- the online run's NLI is the real model, never the stand-in in silence --------------------------------


def _hide_transformers(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib.util

    real = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util,
        "find_spec",
        lambda name, *a, **k: None if name in ("transformers", "torch") else real(name, *a, **k),
    )


def test_the_online_run_refuses_to_fall_back_to_the_stub_nli(
    online_settings: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(eval_run, "get_embeddings", lambda settings=None: eval_run.OfflineEmbeddings())
    monkeypatch.setattr(eval_run, "_online_model", lambda: AnswerModel())
    _hide_transformers(monkeypatch)
    cases = load_cases()[:1]
    with pytest.raises(RuntimeError, match="verify"):
        eval_run.run_online(
            cases,
            variants=("A",),
            settings=online_settings,
            client=FakeClient([eval_run._example(c) for c in cases]),
            evaluate_fn=fake_evaluate,
            work_dir=tmp_path / "w",
            model=AnswerModel(),
        )


def test_the_online_report_names_the_nli_that_ran(
    online_settings: Any, patched: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ledgerlens.verify.nli import HuggingFaceNli

    cases = load_cases()[:1]
    kwargs = {
        "variants": ("A", "C"),
        "settings": online_settings,
        "client": FakeClient([eval_run._example(c) for c in cases]),
        "evaluate_fn": fake_evaluate,
        "model": AnswerModel(),
    }
    stub = eval_run.run_online(cases, work_dir=tmp_path / "s", **kwargs)
    assert stub["nli"] == "stub" and "stand-in" in stub["note"]
    real = HuggingFaceNli(
        "org/model", backend=({0: "entailment", 1: "neutral", 2: "contradiction"}, lambda p, h: [0, 0, 0])
    )
    monkeypatch.setattr(eval_run, "get_nli", lambda offline=None, **kw: real)
    report = eval_run.run_online(cases, work_dir=tmp_path / "r", **kwargs)
    assert report["nli"] == "org/model" and "stand-in" not in report["note"] and "org/model" in report["note"]
    assert "org/model" in eval_run.render_markdown(report) and "NLI stand-in" not in eval_run.render_markdown(report)


def test_the_online_run_adds_a_verification_experiment_to_the_report(
    online_settings: Any, patched: None, tmp_path: Path
) -> None:
    cases = load_cases()[:1]
    client = FakeClient([eval_run._example(c) for c in cases])
    report = eval_run.run_online(
        cases,
        variants=("A", "C"),
        settings=online_settings,
        client=client,
        evaluate_fn=fake_evaluate,
        work_dir=tmp_path / "w",
        model=AnswerModel(),
    )
    v = report["verification"]
    assert eval_run.VERIFICATION_DATASET in client.asked
    assert v["cases"] == 43 and v["experiment"] == "ledgerlens-verification-abc"
    assert v["contradiction_recall"] == 1.0 and v["false_positive_rate"] == 0.0
    assert report["experiments"]["verification"]["url"] == "https://example.invalid/experiment"
    assert "experiments" not in eval_run._public(report) and "url" not in json.dumps(eval_run._public(report))
    assert "ledgerlens-verification-abc" in eval_run.render_markdown(report)


def test_attaching_the_verification_experiment_rewrites_both_report_files(tmp_path: Path) -> None:
    import shutil

    if not ONLINE_REPORT.exists():
        pytest.skip("the online report has not been generated yet")
    shutil.copy(ONLINE_REPORT, tmp_path / "report_online.json")
    verification = {
        "cases": 43,
        "accuracy": 1.0,
        "contradiction_recall": 1.0,
        "false_positive_rate": 0.0,
        "planted": 20,
        "supported": 16,
        "misses": [],
        "nli": "org/model",
        "experiment": "ledgerlens-verification-xyz",
        "_url": "https://smith.langchain.com/o/secret",
    }
    report = eval_run.attach_verification(tmp_path, verification)
    text = (tmp_path / "report_online.md").read_text("utf-8") + (tmp_path / "report_online.json").read_text("utf-8")
    assert report["verification"]["experiment"] == "ledgerlens-verification-xyz"
    assert "ledgerlens-verification-xyz" in text and "smith.langchain.com" not in text


def test_a_stale_remote_dataset_does_not_hide_the_declared_equivalences(
    online_settings: Any, patched: None, tmp_path: Path
) -> None:
    from types import SimpleNamespace as NS

    lookup = next(c for c in load_cases() if c.equivalent_tools)
    stale = eval_run._example(lookup)
    stale = NS(
        id=stale.id, inputs=stale.inputs, outputs={k: v for k, v in stale.outputs.items() if k != "equivalent_tools"}
    )
    client = FakeClient([stale])
    seen: list[Any] = []

    def spy(target, *, data, **kwargs: Any):
        if kwargs["experiment_prefix"] != "ledgerlens-verification":
            seen.extend(data)
        return fake_evaluate(target, data=data, **kwargs)

    eval_run.run_online(
        [lookup],
        variants=("A",),
        settings=online_settings,
        client=client,
        evaluate_fn=spy,
        work_dir=tmp_path / "w",
        model=AnswerModel(),
    )
    assert [e.outputs["equivalent_tools"] for e in seen] == [lookup.equivalent_tools]
