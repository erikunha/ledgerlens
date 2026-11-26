"""Render private sandbox changes and budgeted provider runs using one API session per visitor."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from ipaddress import ip_address
from uuid import uuid4

import httpx
import streamlit as st

from ledgerlens.config import offline
from ledgerlens.demo import load_manifest
from ledgerlens.sandbox.mutation import (
    KIND_DEADLINE,
    KIND_DUPLICATE,
    KIND_FX_ADJUSTMENT,
    KIND_FX_OUTAGE,
    KIND_NOTE,
)

SESSION = "/v1/sessions"
SANDBOXES = "/v1/sandboxes"
RUNS = "/v1/live-runs"
CREDENTIALS = "/v1/credentials"
LIVE_SCENARIO = "S01"
ACTIVE_RUN = {"running", "cancelling"}
CHANGE_TYPES = {
    KIND_FX_ADJUSTMENT: "Adjust refund exchange rate",
    KIND_DUPLICATE: "Simulate duplicate payment",
    KIND_DEADLINE: "Change chargeback deadline",
    KIND_FX_OUTAGE: "Simulate FX tool outage",
    KIND_NOTE: "Add an untrusted record note",
}
LIMITS = {
    "max_model_calls": ("Model calls", 1, 20, 8),
    "max_tool_calls": ("Tool calls", 1, 40, 12),
    "max_wall_seconds": ("Elapsed seconds", 5, 180, 60),
    "max_output_tokens": ("Output tokens", 128, 16000, 2048),
}
VISITOR_KEYS = ("visitor", "branch", "preview", "branch_read", "credential", "live_run")


def _http():
    if "_visitor_http" not in st.session_state:
        st.session_state["_visitor_http"] = httpx.Client(
            base_url=os.getenv("LEDGERLENS_API_BASE_URL", "http://127.0.0.1:8010"),
            timeout=30,
            trust_env=False,
            follow_redirects=False,
        )
    return st.session_state["_visitor_http"]


def _clear_visitor():
    for key in VISITOR_KEYS:
        st.session_state.pop(key, None)


def _request(method, path, **kwargs):
    try:
        response = _http().request(method, path, **kwargs)
    except httpx.RequestError:
        st.error("The investigation API is unavailable. Check the connection and retry.")
        st.stop()
    if response.is_redirect:
        st.error("The investigation API returned an unexpected redirect.")
        st.stop()
    if response.is_error:
        try:
            error = response.json()
        except ValueError:
            error = {}
        if response.status_code == 401 and error.get("code") == "SESSION_REQUIRED":
            _clear_visitor()
        wait = response.headers.get("Retry-After")
        detail = error.get("message", "The investigation API could not complete the request.")
        st.error(
            f"{error.get('code', response.status_code)}: {detail}" + (f" Retry in {wait} seconds." if wait else "")
        )
        st.stop()
    return response


def _session():
    if "visitor" not in st.session_state:
        st.session_state.visitor = _request("POST", SESSION).json()


def _end_session():
    if "visitor" in st.session_state and st.button("End session"):
        _request("DELETE", f"{SESSION}/current")
        _clear_visitor()
        st.rerun()


def _command(case):
    ids = case["ids"]

    def first(group):
        return next(iter(ids.get(group, [])), "")

    kind = st.selectbox("Change", CHANGE_TYPES, format_func=CHANGE_TYPES.get)
    if kind == KIND_FX_ADJUSTMENT:
        data = {
            "refund_id": st.text_input("Refund", first("refund_ids")),
            "applied_rate": st.text_input("Exchange rate", "5.41250000"),
            "effective_at": st.text_input(
                "Effective time (ISO 8601)",
                st.session_state.setdefault("effective_time", datetime.now(UTC).isoformat()),
            ),
        }
    elif kind == KIND_DUPLICATE:
        data = {
            "transaction_id": st.text_input("Transaction", first("transaction_ids")),
            "elapsed_seconds": st.number_input("Seconds between charges", 1, 300, 30),
        }
    elif kind == KIND_DEADLINE:
        data = {
            "chargeback_id": st.text_input("Chargeback", first("chargeback_ids")),
            "new_deadline": st.date_input("New deadline").isoformat(),
        }
    elif kind == KIND_FX_OUTAGE:
        data = {"enabled": st.checkbox("Enable outage", value=True), "error_code": "UPSTREAM_UNAVAILABLE"}
    else:
        data = {"record_id": st.text_input("Record", first("transaction_ids")), "text": st.text_area("Note")}
    if kind in (KIND_DEADLINE, KIND_DUPLICATE, KIND_FX_ADJUSTMENT):
        currency = st.text_input("Expected currency (optional)")
        if currency:
            data["currency"] = currency
    command = {"kind": kind, "data": data}
    if reason := st.text_input("Reason (optional)"):
        command["reason"] = reason
    return command


def _cases():
    return {case["id"]: case for case in load_manifest()["scenarios"]}


def _changed():
    st.session_state.pop("branch_read", None)
    st.session_state.pop("preview", None)
    st.rerun()


def render_sandbox():
    """Open a branch and let its owner preview, apply, inspect and undo changes."""
    st.header("Visitor sandbox")
    st.write("Open a private copy of a published case to see how a change affects its ledger.")
    cases = _cases()
    selected = st.selectbox("Published case", cases, format_func=lambda key: f"{key} · {cases[key]['name']}")
    if st.button("Open private branch"):
        _session()
        branch = _request("POST", SANDBOXES, json={"scenario_id": selected}).json()
        st.session_state.branch = (selected, branch["id"])
        _changed()
    _end_session()
    if "branch" not in st.session_state:
        return
    scenario, branch_id = st.session_state.branch
    path = f"{SANDBOXES}/{branch_id}"
    branch = _request("GET", path).json()
    revision = branch["revision"]
    case = cases[scenario]
    st.caption(f"Revision {revision} · {scenario} · Expires {branch['expires_at']}")
    command = _command(case)
    if st.button("Preview change"):
        result = _request("POST", f"{path}/mutations/preview", json=command).json()
        st.session_state.preview = (command, revision, uuid4().hex, result)
    preview = st.session_state.get("preview")
    if preview and preview[:2] == (command, revision):
        st.subheader("Proposed change")
        st.json(preview[3])
        if st.button("Commit change"):
            headers = {"If-Match": str(revision), "Idempotency-Key": preview[2]}
            _request("POST", f"{path}/mutations", json=command, headers=headers)
            _changed()
    if st.button("Undo last change", disabled=not revision):
        _request("POST", f"{path}/undo", headers={"If-Match": str(revision), "Idempotency-Key": uuid4().hex})
        _changed()
    if st.button("Reset to published case", disabled=not revision):
        _request("POST", f"{path}/reset")
        _changed()
    st.subheader("Inspect this branch")
    for label, endpoint in (("Show changes", "diff"), ("Show history", "history")):
        if st.button(label):
            st.session_state.branch_read = _request("GET", f"{path}/{endpoint}").json()
    account = st.text_input("Ledger account", next(iter(case["ids"].get("customer_ids", [])), ""))
    if st.button("Show ledger", disabled=not account):
        st.session_state.branch_read = _request("GET", f"{path}/ledger", params={"account_id": account}).json()
    if result := st.session_state.get("branch_read"):
        st.json(result)


def _run_result():
    run_path = f"{RUNS}/{st.session_state.live_run}"
    run = _request("GET", run_path).json()
    st.subheader("Run result")
    st.write(f"Status: {run['status']}")
    if run["status"] in ACTIVE_RUN:
        st.button("Refresh run")
        if st.button("Cancel run", disabled=run.get("cancel_requested", False)):
            _request("POST", f"{run_path}/cancel")
            st.rerun()
        st.caption("A provider call already in progress may finish and incur charges.")
        return True
    if run.get("answer"):
        st.write(run["answer"])
    if run.get("error"):
        st.warning(run["error"])
    st.json(_request("GET", f"{run_path}/cost").json())
    if st.button("Show run trace"):
        trace = _request("GET", f"{run_path}/events")
        for line in trace.text.splitlines():
            if line.startswith("data:"):
                st.json(json.loads(line.removeprefix("data:")))
    return False


def _secure_api():
    origin = _http().base_url
    if origin.scheme == "https":
        return True
    if origin.scheme != "http":
        return False
    if origin.host == "localhost":
        return True
    try:
        return ip_address(origin.host).is_loopback
    except ValueError:
        return False


def render_live():
    """Submit a visitor's consent and credential before starting a budgeted live investigation."""
    st.header("Live investigation")
    st.write("Run the published refund case using your OpenAI account.")
    st.caption("This demo uses deterministic checks. Learned verification is unavailable.")
    if offline():
        st.info("Live investigations are disabled in offline mode. The visitor sandbox remains available.")
        return
    if not _secure_api():
        st.error("Configure an HTTPS investigation API to connect a provider key.")
        return
    _session()
    _end_session()
    if st.session_state.get("live_run") and _run_result():
        return
    models = _request("GET", "/v1/models").json()["models"]
    profiles = {
        item["profile_id"]: item for item in models if item["enabled_in_public_demo"] and item["provider"] == "openai"
    }
    if not profiles:
        st.info("No models are enabled for this deployment.")
        return
    selected = st.selectbox("Provider model", profiles, format_func=lambda key: profiles[key]["display_name"])
    provider = profiles[selected]["provider"]
    price = _request("GET", f"/v1/models/{selected}").json()
    st.caption(price["price_note"])
    case = _cases()[LIVE_SCENARIO]
    st.write(case["questions"][0])
    with st.expander("Run limits"):
        limits = {key: st.number_input(*settings) for key, settings in LIMITS.items()}
        limits["max_input_tokens"] = st.number_input("Input token cap (optional)", min_value=1, value=None)
        limits["max_estimated_usd"] = st.text_input("Estimated cost cap in USD (optional)").strip() or None
    st.write(
        "Your provider may charge you for this run. The backend holds your key in memory until "
        "you forget it, end the session, or it expires. Memory erasure cannot be guaranteed."
    )
    credential = st.session_state.get("credential")
    if credential:
        st.caption(f"Key for {credential['provider']} expires {credential['expires_at']}.")
        if st.button("Forget key"):
            _request("POST", f"{CREDENTIALS}/forget", json={"handle": credential["handle"]})
            del st.session_state.credential
            st.rerun()
        if provider != credential["provider"]:
            st.info("Forget the current key to connect a different provider.")
            return
    else:
        with st.form("accept_key", clear_on_submit=True):
            key = st.text_input("Provider API key", type="password")
            consent = st.checkbox("I agree to send my key to the backend and pay my provider for this run.")
            accepted = st.form_submit_button("Connect key")
        if accepted:
            if not key or not consent:
                st.warning("Enter a key and confirm consent to connect.")
            else:
                st.session_state.credential = _request(
                    "POST", CREDENTIALS, json={"provider": provider, "api_key": key}
                ).json()
                st.rerun()
        return
    if st.button("Start live run"):
        branch = _request("POST", SANDBOXES, json={"scenario_id": LIVE_SCENARIO}).json()
        body = {
            "mode": "live_agent",
            "scenario_id": LIVE_SCENARIO,
            "sandbox_id": branch["id"],
            "expected_revision": branch["revision"],
            "account_id": case["ids"]["customer_ids"][0],
            "question": case["questions"][0],
            "variant": "C",
            "model_profile_id": selected,
            "credential_handle": credential["handle"],
            "limits": limits,
        }
        st.session_state.live_run = _request("POST", RUNS, json=body).json()["run_id"]
        st.rerun()
