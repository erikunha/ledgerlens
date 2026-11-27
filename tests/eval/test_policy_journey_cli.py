"""Exercise the diagnostic CLI and provider accounting without spending tokens."""

import asyncio
import json
import sys
from decimal import Decimal
from unittest.mock import Mock

import httpx
import pytest

from scripts import report_policy_journeys as runner


def _cli(monkeypatch, arguments, reports):
    async def fake_run(root, case_ids, *, checkpoint=None, configuration=None):
        return [dict(reports[i % len(reports)], case_id=case_id) for i, case_id in enumerate(case_ids)]

    monkeypatch.setattr(runner, "run_journeys", fake_run)
    monkeypatch.setattr(runner, "run_config", lambda **kw: kw)
    monkeypatch.setattr(sys, "argv", ["report_policy_journeys", *arguments])
    runner.main()


def _answered(cost="0.001"):
    return {"status": "answered", "estimated_online_usd": cost, "searches": [], "provider_tokens": {"input": 10}}


def test_all_repeats_each_case_and_sums_cost(monkeypatch, capsys):
    _cli(monkeypatch, ["--all", "--repeat", "2", "--strict"], [_answered()])
    output = json.loads(capsys.readouterr().out)
    expected = list(runner.CASES) * 2
    assert [case["case_id"] for case in output["cases"]] == expected
    billing = output["billing"]
    assert billing["total_cases"] == billing["priced_cases"] == len(expected)
    assert Decimal(billing["estimated_online_usd"]) == Decimal("0.001") * len(expected)


@pytest.mark.parametrize("status", ["partial", "no_answer", "error"])
def test_strict_preserves_report_before_exiting_on_incomplete_runs(monkeypatch, capsys, status):
    with pytest.raises(SystemExit) as exc:
        _cli(
            monkeypatch,
            ["--case", "refund-trigger", "--repeat", "2", "--strict"],
            [_answered(), {**_answered(None), "status": status}],
        )
    assert exc.value.code == 1
    output = json.loads(capsys.readouterr().out)
    assert output["counts"] == {"answered": 1, status: 1}
    assert output["billing"] == {"estimated_online_usd": None, "priced_cases": 1, "total_cases": 2}


@pytest.mark.parametrize(
    "failure",
    [
        {"searches": [{"status": "error", "error": "INDEX_SEARCH_FAILED", "candidate_ids": None}]},
        {"estimated_online_usd": None, "provider_tokens": {"unpriced_requests": 1}},
    ],
)
def test_strict_rejects_operational_failures_even_with_an_answer(monkeypatch, capsys, failure):
    with pytest.raises(SystemExit) as exc:
        _cli(monkeypatch, ["--case", "fee-trigger", "--strict"], [{**_answered(), **failure}])
    assert exc.value.code == 1
    assert json.loads(capsys.readouterr().out)["cases"][0]["status"] == "answered"


def test_checkpoint_is_exclusive_and_a_collision_cannot_start_inference(tmp_path, monkeypatch):
    checkpoint = tmp_path / "report.jsonl"
    checkpoint.write_text("earlier report\n")
    monkeypatch.setattr(sys, "argv", ["runner", "--checkpoint", str(checkpoint)])
    monkeypatch.setattr(runner, "run_journeys", Mock(side_effect=AssertionError("inference started")))
    with pytest.raises((FileExistsError, SystemExit)):
        runner.main()
    assert checkpoint.read_text() == "earlier report\n"


def test_zero_repetitions_rejected_before_creating_checkpoint(tmp_path, monkeypatch):
    checkpoint = tmp_path / "report.jsonl"
    monkeypatch.setattr(sys, "argv", ["runner", "--repeat", "0", "--checkpoint", str(checkpoint)])
    with pytest.raises(SystemExit) as exc:
        runner.main()
    assert exc.value.code == 2
    assert not checkpoint.exists()


@pytest.mark.parametrize("fault", [None, "transport", "missing_usage", "missing_completion", "classifier"])
def test_provider_usage_from_http_requests_and_checkpoints(tmp_path, monkeypatch, fault):
    def serve(request):
        if request.url.path.endswith("/embeddings"):
            usage = {"prompt_tokens": 50}
        elif request.url.path.endswith("/failed"):
            if fault == "transport":
                raise httpx.ReadTimeout("simulated lost response", request=request)
            usage = {"prompt_tokens": 10} if fault == "missing_completion" else {}
        else:
            usage = {"prompt_tokens": 100, "prompt_tokens_details": {"cached_tokens": 30}, "completion_tokens": 5}
        return httpx.Response(
            200,
            json={
                "usage": usage,
                "model": runner.VERIFIER_MODEL.removeprefix("openai:")
                if request.url.path.endswith("/classifier")
                else runner.OPENAI_MODEL,
            },
        )

    original_client = httpx.Client
    monkeypatch.setattr(
        runner.httpx, "Client", lambda **kw: original_client(transport=httpx.MockTransport(serve), **kw)
    )
    monkeypatch.setattr(runner, "get_chat_model", lambda *a, **kw: kw["http_client"])
    monkeypatch.setattr(runner, "OpenAIEmbeddings", lambda **kw: object())
    monkeypatch.setattr(runner, "index_dir_for", lambda root, embeddings: root)
    monkeypatch.setattr(runner, "check", lambda *args: [])
    monkeypatch.setattr(
        runner, "run_config", lambda: {"verifier": runner.VERIFIER_MODEL if fault == "classifier" else "offline_stub"}
    )
    monkeypatch.setattr(runner, "create_database", lambda path: Mock())
    monkeypatch.setattr(runner, "CaseMemory", lambda *a, **kw: None)
    monkeypatch.setattr(runner, "build_integrator", lambda model, **kw: (model, kw["verifier"].keywords["nli"]))
    monkeypatch.setenv("LEDGERLENS_ENV_FILE", str(tmp_path / "unused.env"))

    def exercise(agent, case):
        client, classifier = agent
        if fault == "classifier":
            assert isinstance(classifier, runner.EvidenceClassifier)
            classifier.model.post("https://example.invalid/classifier")
        client.post("https://example.invalid/chat/completions")
        client.post("https://example.invalid/embeddings")
        if fault and fault != "classifier":
            try:
                client.post("https://example.invalid/failed")
            except httpx.TransportError:
                pass
        return {"status": "answered", "case_id": case[0]}

    monkeypatch.setattr(runner, "report_journey", exercise)
    checkpoint_path = tmp_path / "report.jsonl"
    with checkpoint_path.open("x") as checkpoint:
        reports = asyncio.run(runner.run_journeys(tmp_path, ["fee-trigger"] * 2, checkpoint=checkpoint))
    assert [json.loads(line)["case"] for line in checkpoint_path.read_text().splitlines()] == reports
    assert [r["repetition"] for r in reports] == [1, 2]
    for report in reports:
        if fault and fault != "classifier":
            assert report["estimated_online_usd"] is None
            assert report["provider_tokens"]["unpriced_requests"] >= 1
        else:
            expected_cost = "0.000235" if fault == "classifier" else "0.000196"
            assert Decimal(report["estimated_online_usd"]) == Decimal(expected_cost)


@pytest.mark.parametrize("enabled", [False, True])
def test_cli_selects_and_records_receipt_verification(tmp_path, monkeypatch, capsys, enabled):
    from scripts.report_cutoff_receipts import ARCHIVE, reconstruct_archived_case

    archive = json.loads(ARCHIVE.read_text())
    record = next(case for case in archive["cases"] if case["case_id"] == "july-cutoff-usd")
    monkeypatch.setenv("LEDGERLENS_ENV_FILE", str(tmp_path / "unused.env"))
    monkeypatch.setattr(runner, "get_chat_model", lambda *a, **kw: object())
    monkeypatch.setattr(runner, "OpenAIEmbeddings", lambda **kw: object())
    monkeypatch.setattr(runner, "index_dir_for", lambda root, embeddings: root)
    monkeypatch.setattr(runner, "check", lambda *args: [])
    monkeypatch.setattr(runner, "CaseMemory", lambda *a, **kw: None)
    monkeypatch.setattr(runner, "build_integrator", lambda model, **kw: kw["verifier"])

    def exercise(verifier, case):
        result = verifier(reconstruct_archived_case(record))
        return {**_answered(), "requires_human_review": result.requires_human_review}

    monkeypatch.setattr(runner, "report_journey", exercise)
    checkpoint = tmp_path / "results.jsonl"
    arguments = ["runner", "--case", record["case_id"], "--checkpoint", str(checkpoint)]
    if enabled:
        arguments.append("--use-cutoff-receipts")
    monkeypatch.setattr(sys, "argv", arguments)
    runner.main()
    report = json.loads(capsys.readouterr().out)
    assert report["use_cutoff_receipts"] is enabled
    assert report["cases"][0]["requires_human_review"] is (not enabled)
    assert json.loads(checkpoint.read_text())["configuration"]["use_cutoff_receipts"] is enabled


def test_cli_records_frozen_classifier_model(monkeypatch, capsys):
    async def fake_run(root, case_ids, *, checkpoint=None, configuration=None):
        return [_answered()]

    monkeypatch.setattr(runner, "run_journeys", fake_run)
    monkeypatch.setattr(sys, "argv", ["runner", "--openai-verifier", "--case", "fee-trigger"])
    runner.main()
    assert json.loads(capsys.readouterr().out)["verifier"] == runner.VERIFIER_MODEL
