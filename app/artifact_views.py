"""Browse local investigation artifacts so recorded results can be inspected offline."""

import ast
import json
import re
from collections import Counter
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


CATALOG_LABELS = {slug: name for name, slug in CATALOGS.items()}
TOOL_LABELS = {
    "query_ledger": "Ledger query",
    "calculate": "Calculation",
    "get_reference_fx": "Reference exchange rate",
    "search_policies": "Payment policy",
}
VERDICT_LABELS = {
    "supported": "Supported",
    "contradicted": "Contradicted",
    "not_enough_evidence": "Insufficient evidence",
}


def _events(catalog, scenario):
    if catalog not in CATALOG_LABELS or not re.fullmatch(r"S[0-9]+", scenario):
        raise ValueError("Unknown recording")
    bundle = SITE / catalog / scenario.lower()
    return bundle, [json.loads(line) for line in (bundle / "events.jsonl").read_bytes().splitlines()]


def _tool_results(events):
    for event in events:
        payload = event["payload"]
        if payload.get("run_type") == "tool" and payload.get("outputs"):
            yield event["seq"], payload["name"], payload["outputs"]


def _formula(data):
    result = data.get("result")
    if data.get("operation") == "fx_markup_check" and isinstance(result, dict):
        st.write(
            f"Payment **{result['charge']}** · Refund **{result['refund']}**\n\n"
            f"Difference **{result['gap']}** = exchange-rate movement **{result['rate_move']}** "
            f"+ markup **{result['markup']}**."
        )
    if data.get("formula"):
        st.code(data["formula"], language=None, wrap_lines=True)


def _open_proof(catalog, scenario):
    st.session_state["proof_target"] = (catalog, scenario)
    st.session_state["go_to"] = "Proof"


def render_replay():
    """Show the recorded answer, its calculation and links to the same recording's proof."""
    st.title("Recordings")
    target = st.session_state.pop("replay_target", None)
    if target and target[0] in CATALOG_LABELS:
        st.session_state["recording_kind"] = CATALOG_LABELS[target[0]]
        st.session_state["recording_scenario"] = target[1]
    elif "last_recording" in st.session_state:
        last_catalog, last_scenario = st.session_state["last_recording"]
        st.session_state.setdefault("recording_kind", CATALOG_LABELS[last_catalog])
        st.session_state.setdefault("recording_scenario", last_scenario)
    left, right = st.columns(2)
    catalog = CATALOGS[left.radio("Recording", CATALOGS.keys(), horizontal=True, key="recording_kind")]
    with _artifact_errors():
        records = {row["id"]: row for row in _read(SITE / catalog / "index.json")}
        scenario = right.selectbox("Scenario", records.keys(), key="recording_scenario")
        st.session_state["last_recording"] = (catalog, scenario)
        record = records[scenario]
        bundle, events = _events(catalog, scenario)
        result = events[-1]["payload"].get("outputs") or {}
        st.subheader(record["question"])
        st.write(result.get("answer") or "This recording has no final answer.")
        if result.get("summary"):
            st.caption(result["summary"])

        tools = list(_tool_results(events))
        for seq, name, output in tools:
            if name == "calculate" and output.get("ok"):
                st.subheader("Recorded calculation")
                _formula(output["data"])
                st.caption(f"Event {seq} · {', '.join(output.get('evidence_ids', []))}")

        st.button(
            "Open proof for this recording",
            on_click=_open_proof,
            args=(catalog, scenario),
            key="open_recording_proof",
            type="primary",
        )
        st.subheader("Supporting records")
        for seq, name, output in tools:
            with st.expander(f"{TOOL_LABELS.get(name, name)} · event {seq}"):
                st.json(output, expanded=False)
        with st.expander("Ledger reads"):
            st.json(_read(bundle / "ledger.json"), expanded=False)
        with st.expander("Recording provenance"):
            st.json(_read(bundle / "provenance.json"), expanded=False)
        with st.expander("Event timeline"):
            by_sequence = {event["seq"]: event for event in events}

            def event_label(sequence):
                event = by_sequence[sequence]
                return f"{sequence}. {event['payload'].get('name', '')} · {event['event_type']}"

            trace_key = f"{catalog}-{scenario}"
            history = st.session_state.setdefault("recording_events", {})
            first_event = next(iter(by_sequence))
            if target:
                st.session_state[trace_key] = first_event
            else:
                st.session_state.setdefault(trace_key, history.get(trace_key, first_event))
            selected = st.selectbox("Trace event", by_sequence.keys(), format_func=event_label, key=trace_key)
            history[trace_key] = selected
            st.json(by_sequence[selected])
            _download(bundle / "events.jsonl", "Download recorded events", "application/x-ndjson")


def render_evaluation():
    """Compare published measurements while keeping their denominators and purposes visible."""
    st.title("Evaluation")
    with _artifact_errors():
        path = SITE / "eval" / "index.json"
        report = _read(path)
        tuning, heldout = report["evaluation"], report["verification"]
        left, right = st.columns(2)
        left.metric("Agent correctness · tuning set", tuning["correctness_mean"])
        left.caption(f"{tuning['denominator']} cases · {tuning['repeats']} repeats")
        right.metric("Verifier accuracy · held-out set", heldout["accuracy"])
        right.caption(f"{heldout['correct']} correct out of {heldout['denominator']} cases")
        with st.expander("How to interpret the scores"):
            st.write(tuning["restriction"].capitalize() + ".")
            st.write(heldout["restriction"].capitalize() + ".")
        matrix = report["confusion_matrix"]
        st.subheader("Confusion matrix")
        st.caption("Each row groups the reader’s labels. The remaining columns count the verifier’s decisions.")
        # Compact headers keep every decision visible on narrow screens.
        short = {"supported": "Yes", "contradicted": "No", "not_enough_evidence": "Unsure"}
        labels = matrix["labels"]
        st.table(
            [
                {"Reader": short[label], **{short[col]: matrix["counts"][label][col] for col in labels}}
                for label in labels
            ]
        )
        st.caption("Yes = supported · No = contradicted · Unsure = insufficient evidence")
        failures = {f"{row['set_name']} · {row['id']}": row for row in report["failed_cases"]}
        if failures:
            chosen = st.selectbox("Inspect a failed case", failures.keys())
            case = failures[chosen]
            st.write(case["claim"])
            st.caption(f"Expected: {case['expected']} · Recorded: {case['got']}")
            with st.expander("Evidence for this case"):
                st.text(case["evidence"])
        _download(path, "Download evaluation report")


def render_proof():
    """Show a selected recording's verdicts and evidence with its original receipt."""
    st.title("Proof artifacts")
    with _artifact_errors():
        proofs = _read(SITE / "proof" / "index.json")["artifacts"]
        entries = {(row["catalog"], row["scenario_id"]): row for row in proofs}
        target = st.session_state.pop("proof_target", None)
        if target in entries:
            st.session_state["proof_recording"] = target
        selected = st.selectbox(
            "Investigation",
            entries.keys(),
            key="proof_recording",
            format_func=lambda key: f"{key[1]} · {CATALOG_LABELS[key[0]]}",
        )
        row = entries[selected]
        digest = row["artifact_id"]
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("Invalid proof ID")
        path = SITE / "proof" / f"{digest}.json"
        artifact = _read(path)
        _, events = _events(*selected)
        verifier = [
            e["payload"]["outputs"]
            for e in events
            if e["payload"].get("run_type") == "verifier"
            and isinstance(e["payload"].get("outputs"), dict)
            and "claim_id" in e["payload"]["outputs"]
        ]
        st.subheader("Recorded verdict")
        counts = Counter(item["label"] for item in verifier)
        st.write(
            " · ".join(f"{count} {VERDICT_LABELS.get(label, label).lower()}" for label, count in counts.items())
            or artifact["verdict_summary"]
        )
        st.write(row["claim"])
        if verifier:
            check = st.selectbox("Inspect a claim", verifier, format_func=lambda item: item["claim_id"])
            refs = check["evidence_ids"]
            st.caption(f"{VERDICT_LABELS.get(check['label'], check['label'])} · {', '.join(refs)}")
            if check.get("note"):
                st.write(check["note"])
            for seq, name, output in _tool_results(events):
                if set(refs).intersection(output.get("evidence_ids", [])):
                    with st.expander(f"{TOOL_LABELS.get(name, name)} · event {seq}"):
                        if name == "calculate":
                            _formula(output["data"])
                        st.json(output, expanded=False)
        _download(path, "Download proof JSON")
        with st.expander("Receipt details and limitations"):
            for limitation in artifact["known_limitations"]:
                st.write(limitation)
            st.json(artifact, expanded=False)


def render_engineering():
    """Show each subsystem's purpose before its full documentation and implementation."""
    st.title("Engineering")
    with _artifact_errors():
        name = st.selectbox("Subsystem", MODULES.keys())
        path = ROOT / MODULES[name]
        source = path.read_text(encoding="utf-8")
        description = ast.get_docstring(ast.parse(source)) or name
        purpose, _, details = description.partition("\n\n")
        st.subheader(name)
        st.write(purpose)
        st.caption(MODULES[name])
        if details:
            with st.expander("Module documentation"):
                st.write(details)
        with st.expander("Inspect source"):
            st.code(source, language="python")
        _download(path, "Download module", "text/x-python")
