"""Browse local investigation artifacts so recorded results can be inspected offline."""

import ast
import json
import re
from contextlib import contextmanager
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
CATALOGS = {"Scripted recording": "replay", "Real-model recording": "replay-real"}
MODULES = {
    "Query guard": "ledgerlens/tools/sql_guard.py",
    "Scoped ledger copy": "ledgerlens/api/accounts.py",
    "Decimal calculator": "ledgerlens/tools/calculator.py",
    "Deterministic simulator": "ledgerlens/sim/pipeline.py",
    "Verifier": "ledgerlens/verify/checks.py",
    "Trace recorder": "ledgerlens/observability/trace.py",
}


@contextmanager
def _artifact_errors():
    try:
        yield
    except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError):
        st.error("The selected artifact is missing or unreadable. Check the files in this installation.")


def _read(path):
    return json.loads(path.read_bytes())


def _download(path, label, mime="application/json"):
    st.download_button(label, path.read_bytes(), file_name=path.name, mime=mime)


def render_replay():
    """Show the question, recorded answer, source reads and individual trace events."""
    st.title("Recorded investigations")
    catalog = CATALOGS[st.radio("Recording", CATALOGS.keys(), horizontal=True)]
    with _artifact_errors():
        records = {row["id"]: row for row in _read(SITE / catalog / "index.json")}
        scenario = st.selectbox("Scenario", records.keys())
        record = records[scenario]
        if not re.fullmatch(r"s[0-9]+", record["bundle_path"]):
            raise ValueError("Invalid scenario directory")
        bundle = SITE / catalog / record["bundle_path"]
        events_path = bundle / "events.jsonl"
        events = [json.loads(line) for line in events_path.read_bytes().splitlines()]
        manifest = _read(bundle / "manifest.json")
        st.caption(f"{manifest['model_profile']} · {manifest['recorded_at']}")
        st.subheader("Question")
        st.write(record["question"])
        result = events[-1]["payload"].get("outputs") or {}
        st.subheader("Recorded answer")
        st.write(result.get("answer") or "This recording has no final answer.")
        if result.get("summary"):
            st.caption(result["summary"])
        st.subheader("Source evidence")
        for event in events:
            payload = event["payload"]
            if payload.get("run_type") == "tool" and payload.get("outputs"):
                with st.expander(f"{payload['name']} · event {event['seq']}"):
                    st.json(payload["outputs"], expanded=False)
        with st.expander("Ledger reads"):
            st.json(_read(bundle / "ledger.json"), expanded=False)
        with st.expander("Recording provenance"):
            st.json(_read(bundle / "provenance.json"), expanded=False)
        st.subheader("Event timeline")
        by_sequence = {event["seq"]: event for event in events}

        def event_label(sequence):
            event = by_sequence[sequence]
            return f"{sequence}. {event['payload'].get('name', '')} · {event['event_type']}"

        selected = st.selectbox("Trace event", by_sequence.keys(), format_func=event_label, key=f"{catalog}-{scenario}")
        st.json(by_sequence[selected])
        _download(events_path, "Download recorded events", "application/x-ndjson")


def render_evaluation():
    """Present tuning and held-out measurements with their denominators and source cases."""
    st.title("Evaluation")
    with _artifact_errors():
        path = SITE / "eval" / "index.json"
        report = _read(path)
        tuning, heldout = report["evaluation"], report["verification"]
        st.metric("Agent correctness · tuning set", tuning["correctness_mean"])
        st.caption(f"{tuning['denominator']} cases · {tuning['repeats']} repeats. {tuning['restriction']}.")
        st.metric("Verifier accuracy · held-out set", heldout["accuracy"])
        st.caption(f"{heldout['correct']} of {heldout['denominator']} cases. {heldout['restriction']}.")
        matrix = report["confusion_matrix"]
        st.subheader("Confusion matrix")
        st.caption(f"Rows: {matrix['rows']}. Columns: {matrix['columns']}.")
        st.table([{"Reader label": label, **matrix["counts"][label]} for label in matrix["labels"]])
        failures = {f"{row['set_name']} · {row['id']}": row for row in report["failed_cases"]}
        if failures:
            chosen = st.selectbox("Inspect a failed case", failures.keys())
            case = failures[chosen]
            st.write(case["claim"])
            st.caption(f"Expected: {case['expected']} · Recorded: {case['got']}")
            st.text(case["evidence"])
        _download(path, "Download evaluation report")


def render_proof():
    """Display the recorded claim and download its original proof artifact."""
    st.title("Proof artifacts")
    with _artifact_errors():
        proofs = _read(SITE / "proof" / "index.json")["artifacts"]
        entries = {f"{row['scenario_id']} · {row['catalog']}": row for row in proofs}
        selected = st.selectbox("Investigation", entries.keys())
        row = entries[selected]
        digest = row["artifact_id"]
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("Invalid proof ID")
        path = SITE / "proof" / f"{digest}.json"
        artifact = _read(path)
        st.write(row["claim"])
        st.caption(f"{row['status']} · {row['capture_kind']}")
        st.subheader("Verdict")
        st.write(artifact["verdict_summary"])
        st.subheader("Evidence references")
        st.code("\n".join(artifact["claim_evidence_refs"]) or "No evidence references recorded.")
        for limitation in artifact["known_limitations"]:
            st.caption(limitation)
        with st.expander("Artifact contents"):
            st.json(artifact)
        _download(path, "Download proof JSON")


def render_engineering():
    """Display repository modules with the descriptions shipped alongside their implementation."""
    st.title("Engineering")
    with _artifact_errors():
        name = st.selectbox("Subsystem", MODULES.keys())
        path = ROOT / MODULES[name]
        source = path.read_text(encoding="utf-8")
        st.caption(MODULES[name])
        st.write(ast.get_docstring(ast.parse(source)) or name)
        with st.expander("Inspect source"):
            st.code(source, language="python")
        _download(path, "Download module", "text/x-python")
