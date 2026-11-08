"""Repeated runs of the online evaluation, tested with no network and no real model.

What they guarantee, and why: (a) `aggregate_runs` computes mean, minimum and maximum per variant and metric
from the reports of separate runs, so a single run does not carry a conclusion; (b) human review also gets
mean, minimum and maximum; (c) `run_online(repeats=N)` creates N experiments per variant and keeps each name;
(d) with `repeats=1` the report has the usual shape; (e) the Markdown shows `mean [min, max]`; (f) an invalid
`--repeats` is refused before any call.
"""

# ruff: noqa: F811
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from ledgerlens.eval import run as eval_run
from ledgerlens.eval.dataset import load_cases

from .test_online_path import (  # noqa: F401  (shared fixtures and doubles)
    AnswerModel,
    FakeClient,
    fake_evaluate,
    online_settings,
    patched,
)

METRICS = eval_run.ONLINE_METRICS


def _row(case: str, variant: str, score: float, review: bool) -> dict[str, Any]:
    return {
        "case": case,
        "variant": variant,
        "scores": {m: score for m in METRICS},
        "requires_human_review": review,
    }


def _report(scores: list[float], reviews: list[bool], experiment: str) -> dict[str, Any]:
    cases = load_cases()[: len(scores)]
    rows = [_row(c.id, v, s, r) for v in ("A", "C") for c, s, r in zip(cases, scores, reviews, strict=True)]
    report = eval_run.build_report(rows, cases, "online", metrics_keys=METRICS, variants_run=("A", "C"))
    for v in ("A", "C"):
        report["variants"][v]["experiment"] = experiment
        report["variants"][v]["usage"] = {"input_tokens": 5, "output_tokens": 2, "total_tokens": 7, "cost_usd": 0.25}
    report["usage"] = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15, "cost_usd": 0.5}
    return report


def test_the_aggregate_has_mean_min_and_max_per_variant_and_metric() -> None:
    runs = [
        _report([1.0, 0.0], [True, True], "ledgerlens-C-1"),
        _report([1.0, 0.5], [True, False], "ledgerlens-C-2"),
        _report([0.0, 0.0], [False, False], "ledgerlens-C-3"),
    ]
    report = eval_run.aggregate_runs(runs)
    c = report["variants"]["C"]
    assert report["repeats"] == 3
    assert c["aggregate"]["correctness"] == {"mean": 0.4167, "min": 0.0, "max": 0.75}
    assert c["metrics"]["correctness"] == 0.4167
    assert c["human_review_aggregate"] == {"mean": 1.0, "min": 0, "max": 2}
    assert [r["experiment"] for r in c["runs"]] == ["ledgerlens-C-1", "ledgerlens-C-2", "ledgerlens-C-3"]
    assert c["usage"]["total_tokens"] == 21 and c["usage"]["cost_usd"] == 0.75
    assert report["usage"]["cost_usd"] == 1.5


def test_one_run_is_returned_unchanged() -> None:
    run = _report([1.0], [True], "ledgerlens-C-1")
    assert eval_run.aggregate_runs([run]) is run


def test_the_markdown_shows_mean_with_min_and_max() -> None:
    runs = [_report([1.0, 0.0], [True, True], "a"), _report([0.0, 0.0], [False, False], "b")]
    report = eval_run.aggregate_runs(runs)
    report.update(model="m", nli="stub")
    text = eval_run.render_markdown(report)
    assert "0.25 [0.00, 0.50]" in text
    assert "ledgerlens-C" not in text or "`a`" in text
    assert "`a`" in text and "`b`" in text


def test_online_repeats_create_one_experiment_per_variant_and_run(
    online_settings: Any,
    patched: None,
    tmp_path: Path,
) -> None:
    cases = load_cases()[:2]
    client = FakeClient([eval_run._example(c) for c in cases])
    names: list[str] = []

    def evaluate(target, **kwargs: Any):
        results = fake_evaluate(target, **kwargs)
        results.experiment_name = f"{kwargs['experiment_prefix']}-{len(names)}"
        names.append(results.experiment_name)
        return results

    report = eval_run.run_online(
        cases,
        settings=online_settings,
        client=client,
        evaluate_fn=evaluate,
        work_dir=tmp_path / "w",
        model=AnswerModel(),
        repeats=3,
    )
    assert report["repeats"] == 3
    for data in report["variants"].values():
        assert len(data["runs"]) == 3
        assert set(data["aggregate"]) == set(METRICS)
        assert all(set(v) == {"mean", "min", "max"} for v in data["aggregate"].values())
    assert len(report["experiments"]["A"]) == 3
    assert report["variants"]["A"]["runs"][0]["experiment"] in names
    assert len(names) == 9 + 1  # three variants times three runs, plus the verification
    assert report["experiments"]["verification"]["name"] is not None


def test_one_repeat_keeps_the_usual_report_shape(
    online_settings: Any,
    patched: None,
    tmp_path: Path,
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
    assert "repeats" not in report and "aggregate" not in report["variants"]["A"]


def test_a_repeats_below_one_is_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(eval_run, "get_settings", lambda *a, **k: pytest.fail("must not reach the settings"))
    assert eval_run.main(["--online", "--repeats", "0", "--out", str(tmp_path)]) == 2
    assert "--repeats" in capsys.readouterr().err


def test_a_refused_ingestion_runs_without_upload_and_says_so(
    online_settings: Any, patched: None, tmp_path: Path
) -> None:
    cases = load_cases()[:2]
    client = FakeClient([eval_run._example(c) for c in cases])
    seen: list[dict[str, Any]] = []

    def evaluate(target, **kwargs: Any):
        seen.append({**kwargs, "tracing": os.environ.get("LANGSMITH_TRACING")})
        return fake_evaluate(target, **kwargs)

    report = eval_run.run_online(
        cases,
        settings=online_settings,
        client=client,
        evaluate_fn=evaluate,
        work_dir=tmp_path / "w",
        model=AnswerModel(),
        repeats=2,
        refusal=lambda settings: "429 Monthly unique traces usage limit exceeded",
    )
    assert report["storage"] == {"stored": False, "reason": "429 Monthly unique traces usage limit exceeded"}
    assert client.asked == [] and not hasattr(client, "updated")  # nothing was read from or written to LangSmith
    assert all(k.get("upload_results") is False and k["client"] is not client for k in seen)
    assert len(seen) == 6 + 1
    assert all(k["tracing"] == "false" for k in seen)  # no tracing during the run
    assert all(r["experiment"] is None for d in report["variants"].values() for r in d["runs"])
    assert report["experiments"]["verification"]["name"] is None
    assert report["variants"]["C"]["metrics"]["explanation"] == 0.5
    report["previous_stored"] = {
        "variants": {"C": "ledgerlens-C-0d3f2d05"},
        "verification": "ledgerlens-verification-4063d413",
    }
    text = eval_run.render_markdown(report)
    assert "were not stored" in text and "429 Monthly" in text
    assert "ledgerlens-C-0d3f2d05" in text and "ledgerlens-verification-4063d413" in text


def test_a_refused_ingestion_sends_no_run_to_langsmith_at_all(
    online_settings: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With uploads refused, the real `evaluate` runs without any trace reaching the LangSmith client.

    The integrator and ReAct graphs used to open traces inside the target (the "local" mode of `evaluate` with
    `upload_results=False` does not turn them off) and the client sent them with an emptied key, which
    LangSmith answered with 401. The `evaluate` here is the real one and so is the judge; only the network,
    the NLI model and the chat model are doubles.
    """
    from langsmith import Client

    from ledgerlens.verify.nli import StubNli

    monkeypatch.setattr(eval_run, "get_embeddings", lambda settings=None: eval_run.OfflineEmbeddings())
    monkeypatch.setattr(eval_run, "get_nli", lambda offline=None, **kw: StubNli())
    sent: list[str] = []
    for name in ("create_run", "update_run", "multipart_ingest", "batch_ingest_runs"):
        monkeypatch.setattr(Client, name, lambda self, *a, _n=name, **k: sent.append(_n))
    monkeypatch.setattr(Client, "request_with_retries", lambda self, *a, **k: sent.append("request"))
    report = eval_run.run_online(
        load_cases()[:2],
        settings=online_settings,
        work_dir=tmp_path / "w",
        model=AnswerModel(),
        refusal=lambda settings: "HTTP 429: Monthly unique traces usage limit exceeded",
    )
    assert report["storage"]["stored"] is False
    assert sent == []


def test_the_stored_names_of_the_previous_report_are_kept(tmp_path: Path) -> None:
    old = {
        "variants": {"A": {"experiment": "ledgerlens-A-1"}},
        "verification": {"experiment": "ledgerlens-verification-1"},
    }
    path = tmp_path / "report_online.json"
    path.write_text(json.dumps(old), encoding="utf-8")
    assert eval_run.previous_stored_experiments(path) == {
        "variants": {"A": "ledgerlens-A-1"},
        "verification": "ledgerlens-verification-1",
    }
    path.write_text(
        json.dumps(
            {"variants": {"A": {"experiment": None}}, "previous_stored": {"variants": {"A": "x"}, "verification": "y"}}
        ),
        encoding="utf-8",
    )
    assert eval_run.previous_stored_experiments(path)["verification"] == "y"
    assert eval_run.previous_stored_experiments(tmp_path / "none.json") is None


def test_the_refusal_reason_keeps_the_status_and_message_without_the_address() -> None:
    exc = RuntimeError(
        "Rate limit exceeded for https://api.smith.langchain.com/runs. HTTPError('429 Client Error: Too Many "
        "Requests for url: https://api.smith.langchain.com/runs', "
        '\'{"error":"Too many requests: tenant exceeded usage limits: Monthly unique traces usage limit exceeded"}\')'
    )
    assert eval_run.refusal_reason(exc) == (
        "HTTP 429: Too many requests: tenant exceeded usage limits: Monthly unique traces usage limit exceeded"
    )
    assert "http" not in eval_run.refusal_reason(RuntimeError("failed at https://x.invalid/a"))
