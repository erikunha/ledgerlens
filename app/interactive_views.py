"""Render private sandbox changes and budgeted provider runs using one API session per visitor."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from ipaddress import ip_address
from uuid import uuid4

import httpx
import streamlit as st

from ledgerlens.byok.errors import CredentialExpired, CredentialRevoked, CredentialUnknown
from ledgerlens.config import offline
from ledgerlens.demo import accounts_of, load_manifest
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
CASE_SIMULATOR = "case-simulator"
CASE_SIMULATOR_TITLE = "Case simulator"
CASE_QUERY = "case"
SANDBOX_CASE_WIDGET = "sandbox_case"
SANDBOX_BRANCHES = "sandbox_branches"
SANDBOX_VIEW_SCOPE = "sandbox_view_scope"
SANDBOX_WIDGET_SCOPES = "sandbox_widget_scopes"
SANDBOX_SESSION_ENDED = "sandbox_session_ended"
FX_EXAMPLE_SCENARIO = "S01"
RUN_UNAVAILABLE = "unavailable"
NOT_FOUND_CODE = "NOT_FOUND"
MISSING_BRANCH = (404, NOT_FOUND_CODE)
EXPIRED_BRANCH = (410, "BRANCH_EXPIRED")
STALE_CREDENTIAL_REASONS = {CredentialExpired.reason, CredentialRevoked.reason, CredentialUnknown.reason}
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
VISITOR_KEYS = (
    "visitor",
    SANDBOX_BRANCHES,
    SANDBOX_VIEW_SCOPE,
    SANDBOX_WIDGET_SCOPES,
    "preview",
    "branch_read",
    "credential",
    "live_run",
    "live_run_handle",
    "live_settings",
    "live_drawer",
    "open_live_settings",
    "last_change",
    "live_consent",
    "effective_time",
)


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


class InvestigationAPIError(Exception):
    """Describe an API failure without interrupting the rest of the payment page."""

    def __init__(self, message, *, status=None, code=None, detail=""):
        super().__init__(message)
        self.status = status
        self.code = code
        self.detail = detail


def _request(method, path, **kwargs):
    try:
        response = _http().request(method, path, **kwargs)
    except httpx.RequestError as exc:
        raise InvestigationAPIError("The investigation API is unavailable. Check the connection and retry.") from exc
    if response.is_redirect:
        raise InvestigationAPIError("The investigation API returned an unexpected redirect.")
    if response.is_error:
        try:
            error = response.json()
        except ValueError:
            error = {}
        if response.status_code == 401 and error.get("code") == "SESSION_REQUIRED":
            _clear_visitor()
        wait = response.headers.get("Retry-After")
        detail = error.get("message", "The investigation API could not complete the request.")
        raise InvestigationAPIError(
            f"{error.get('code', response.status_code)}: {detail}" + (f" Retry in {wait} seconds." if wait else ""),
            status=response.status_code,
            code=error.get("code"),
            detail=detail,
        )
    return response


def _session():
    if "visitor" not in st.session_state:
        st.session_state.visitor = _request("POST", SESSION).json()


def _end_session(*, pause_simulator=False):
    if "visitor" not in st.session_state:
        return
    with st.expander("Session settings", expanded=True):
        active = False
        if run_id := st.session_state.get("live_run"):
            active = _read_run(run_id)["status"] in ACTIVE_RUN
        if active:
            st.caption("Cancel the active investigation or wait for it to finish before ending this session.")
        else:
            st.caption("Ending this session removes your private branches and forgets your provider key.")
        if st.button("End session", disabled=active):
            _request("DELETE", f"{SESSION}/current")
            _clear_visitor()
            if pause_simulator:
                st.session_state[SANDBOX_SESSION_ENDED] = True
            st.rerun()


def _command(case, scope):
    ids = case["ids"]

    def first(group):
        return next(iter(ids.get(group, [])), "")

    kind = st.selectbox("Change", CHANGE_TYPES, format_func=CHANGE_TYPES.get, key=f"{scope}-change")
    if kind == KIND_FX_ADJUSTMENT:
        data = {
            "refund_id": st.text_input("Refund", first("refund_ids"), key=f"{scope}-refund"),
            "applied_rate": st.text_input("Exchange rate", "5.41250000", key=f"{scope}-rate"),
            "effective_at": st.text_input(
                "Effective time (ISO 8601)",
                st.session_state.setdefault("effective_time", datetime.now(UTC).isoformat()),
                key=f"{scope}-effective-time",
            ),
        }
    elif kind == KIND_DUPLICATE:
        data = {
            "transaction_id": st.text_input("Transaction", first("transaction_ids"), key=f"{scope}-transaction"),
            "elapsed_seconds": st.number_input("Seconds between charges", 1, 300, 30, key=f"{scope}-seconds"),
        }
    elif kind == KIND_DEADLINE:
        data = {
            "chargeback_id": st.text_input("Chargeback", first("chargeback_ids"), key=f"{scope}-chargeback"),
            "new_deadline": st.date_input("New deadline", key=f"{scope}-deadline").isoformat(),
        }
    elif kind == KIND_FX_OUTAGE:
        data = {
            "enabled": st.checkbox("Enable outage", value=True, key=f"{scope}-outage"),
            "error_code": "UPSTREAM_UNAVAILABLE",
        }
    else:
        data = {
            "record_id": st.text_input("Record", first("transaction_ids"), key=f"{scope}-record"),
            "text": st.text_area("Note", key=f"{scope}-note"),
        }
    if kind in (KIND_DEADLINE, KIND_DUPLICATE, KIND_FX_ADJUSTMENT):
        currency = st.text_input("Expected currency (optional)", key=f"{scope}-currency")
        if currency:
            data["currency"] = currency
    command = {"kind": kind, "data": data}
    if reason := st.text_input("Reason (optional)", key=f"{scope}-reason"):
        command["reason"] = reason
    return command


def _clear_branch_views():
    st.session_state.pop("branch_read", None)
    st.session_state.pop("preview", None)


def _switch_branch_view(scope):
    if st.session_state.get(SANDBOX_VIEW_SCOPE) != scope:
        _clear_branch_views()
        st.session_state.pop("last_change", None)
        st.session_state[SANDBOX_VIEW_SCOPE] = scope


def _changed():
    _clear_branch_views()
    st.rerun()


def _comparison(command, result, *, committed):
    before = result["before"]
    after = result["after"]
    if command["kind"] == KIND_FX_ADJUSTMENT:
        left, right = st.columns(2)
        left.metric("Previous refund" if committed else "Current refund", f"{before['currency']} {before['value']}")
        right.metric("Updated refund" if committed else "Proposed refund", f"{after['currency']} {after['value']}")
    else:
        for entry in result["diff"]:
            field = entry["field"].replace("_", " ").capitalize()
            st.text(f"{entry['record_id']} · {field}: {entry['before']} → {entry['after']}")
    with st.expander("Technical details", expanded=True):
        st.json(result)


def render_sandbox():
    """Keep session controls below the case workflow, including when no branch is open."""
    try:
        _sandbox()
    except InvestigationAPIError as exc:
        st.error(str(exc))
    try:
        _end_session(pause_simulator=True)
    except InvestigationAPIError as exc:
        st.error(str(exc))


def _read_case_branch(scenario, branches, widget_scopes):
    branch_id = branches.get(scenario)
    if branch_id is None:
        return None
    try:
        return _request("GET", f"{SANDBOXES}/{branch_id}").json()
    except InvestigationAPIError as exc:
        unavailable = (exc.status, exc.code)
        if unavailable not in (MISSING_BRANCH, EXPIRED_BRANCH):
            raise
        del branches[scenario]
        # Keep queued clicks for the expired branch away from its replacement.
        new_scope = uuid4().hex
        widget_scopes[scenario] = new_scope
        _switch_branch_view(new_scope)
        if unavailable == EXPIRED_BRANCH:
            st.warning("The previous branch expired. A new change will start from the published case.")
        else:
            st.warning("The previous branch is no longer available. A new change will start from the published case.")
        return None


def _save_case_selection():
    st.query_params[CASE_QUERY] = st.session_state[SANDBOX_CASE_WIDGET]


def _sandbox():
    """Open a branch and let its owner preview, apply, inspect and undo changes."""
    st.title(CASE_SIMULATOR_TITLE)
    st.write("Select a published case to see how changes affect its private copy.")
    manifest = load_manifest()
    cases = {case["id"]: case for case in manifest["scenarios"]}
    requested = st.query_params.get(CASE_QUERY)
    selected = requested if requested in cases else next(iter(cases))
    if st.session_state.get(SANDBOX_CASE_WIDGET) != selected:
        st.session_state[SANDBOX_CASE_WIDGET] = selected
    selected = st.selectbox(
        "Published case",
        cases,
        format_func=lambda key: f"{key} · {cases[key]['name'].replace('_', ' ').capitalize()}",
        key=SANDBOX_CASE_WIDGET,
        on_change=_save_case_selection,
    )
    widget_scopes = st.session_state.setdefault(SANDBOX_WIDGET_SCOPES, {})
    _switch_branch_view(widget_scopes.get(selected, selected))
    case = cases[selected]
    st.write(case["questions"][0])
    accounts = accounts_of(manifest, selected)
    if not accounts:
        if case["truth"].get("exists") is False:
            st.info("This case is read-only. The requested transaction is absent from the ledger.")
        else:
            st.info("This case is read-only because it has no ledger account.")
        return
    if selected == FX_EXAMPLE_SCENARIO:
        st.write(
            "What would the customer receive at a different exchange rate? "
            "Preview the refund before applying a change to your private branch."
        )
    if st.session_state.get(SANDBOX_SESSION_ENDED):
        if "visitor" not in st.session_state and not st.button("Start a new session"):
            return
        del st.session_state[SANDBOX_SESSION_ENDED]

    branches = st.session_state.setdefault(SANDBOX_BRANCHES, {})
    branch = _read_case_branch(selected, branches, widget_scopes)
    published = branch is None
    scope = widget_scopes.get(selected, selected)

    def branch_path():
        nonlocal branch
        if branch is None:
            _session()
            branch = _request("POST", SANDBOXES, json={"scenario_id": selected}).json()
            branches[selected] = branch["id"]
        return f"{SANDBOXES}/{branch['id']}"

    revision = branch["revision"] if branch else 0
    status = f"Expires {branch['expires_at']}" if branch else "Published case"
    st.caption(f"Revision {revision} · {selected} · {status}")
    if applied := st.session_state.get("last_change"):
        st.subheader("Applied change")
        _comparison(*applied, committed=True)
    if revision and st.button("Undo last change", key=f"{scope}-undo"):
        _request("POST", f"{branch_path()}/undo", headers={"If-Match": str(revision), "Idempotency-Key": uuid4().hex})
        st.session_state.pop("last_change", None)
        _changed()
    command = _command(case, scope)
    if st.button("Preview change", key=f"{scope}-preview"):
        result = _request("POST", f"{branch_path()}/mutations/preview", json=command).json()
        st.session_state.preview = (command, branch["revision"], uuid4().hex, result)
    preview = st.session_state.get("preview")
    if preview and preview[:2] == (command, revision):
        st.subheader("Proposed change")
        _comparison(command, preview[3], committed=False)
        if st.button("Commit change", key=f"{scope}-commit"):
            headers = {"If-Match": str(revision), "Idempotency-Key": preview[2]}
            _request("POST", f"{branch_path()}/mutations", json=command, headers=headers)
            st.session_state.last_change = (command, preview[3])
            _changed()
    if st.button("Reset to published case", disabled=not revision, key=f"{scope}-reset"):
        _request("POST", f"{branch_path()}/reset")
        st.session_state.pop("last_change", None)
        _changed()
    st.subheader("Inspect this branch")
    for label, endpoint in (("Show changes", "diff"), ("Show history", "history")):
        if st.button(label, key=f"{scope}-{endpoint}"):
            st.session_state.branch_read = _request("GET", f"{branch_path()}/{endpoint}").json()
    account = st.text_input("Ledger account", accounts[0], key=f"{scope}-account")
    if st.button("Show ledger", disabled=not account, key=f"{scope}-ledger"):
        st.session_state.branch_read = _request("GET", f"{branch_path()}/ledger", params={"account_id": account}).json()
    if published and branch is not None:
        st.rerun()
    if result := st.session_state.get("branch_read"):
        st.json(result)


def _read_run(run_id):
    try:
        return _request("GET", f"{RUNS}/{run_id}").json()
    except InvestigationAPIError as exc:
        if exc.status != 404 or exc.code != NOT_FOUND_CODE:
            raise
        return {
            "run_id": run_id,
            "status": RUN_UNAVAILABLE,
            "error": "This run is no longer available in this session.",
        }


def _run_result():
    run_path = f"{RUNS}/{st.session_state.live_run}"
    run = _read_run(st.session_state.live_run)
    if run["status"] == RUN_UNAVAILABLE:
        st.session_state.pop("live_run", None)
        st.warning(run["error"])
        return run
    st.subheader("Run result")
    st.write(f"Status: {run['status']}")
    if run["status"] in ACTIVE_RUN:
        st.button("Refresh run")
        if st.button("Cancel run", disabled=run.get("cancel_requested", False)):
            _request("POST", f"{run_path}/cancel")
            st.rerun()
        st.caption("A provider call already in progress may finish and incur charges.")
        return None
    if not (run.get("answer") or "").strip() and not run.get("error") and run["status"] == "completed":
        run["answer"] = "The investigation returned no answer. Try asking about a specific payment or refund."
    if run.get("answer"):
        st.write(run["answer"])
    if run.get("error"):
        st.warning(run["error"])
        current_handle = st.session_state.get("credential", {}).get("handle")
        if (
            current_handle
            and current_handle == st.session_state.get("live_run_handle")
            and run["error"].partition(":")[0] in STALE_CREDENTIAL_REASONS
        ):
            st.session_state.pop("credential", None)
            st.info("Configure OpenAI to reconnect the key before another investigation.")
    cost = _request("GET", f"{run_path}/cost").json()
    reported, estimate = st.columns(2)
    for column, label, field in (
        (reported, "Provider-reported cost", "observed_cost_usd"),
        (estimate, "Estimated cost", "estimated_cost_usd"),
    ):
        amount = cost.get(field)
        column.metric(label, f"USD {amount}" if amount is not None else "Unavailable")
    with st.expander("Run usage and cost details", expanded=True):
        st.json(cost)
    if st.button("Show run trace"):
        trace = _request("GET", f"{run_path}/events")
        for line in trace.text.splitlines():
            if line.startswith("data:"):
                st.json(json.loads(line.removeprefix("data:")))
    return run


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


def _forget_key():
    if credential := st.session_state.get("credential"):
        if st.button("Forget key"):
            _request("POST", f"{CREDENTIALS}/forget", json={"handle": credential["handle"]})
            del st.session_state.credential
            st.session_state.requested_answer_mode = "Scripted demo"
            st.rerun()


def render_live_status():
    """Show the current investigation and the visitor's credential and session controls."""
    if "visitor" not in st.session_state:
        return None
    try:
        result = _run_result() if st.session_state.get("live_run") else None
        _forget_key()
        _end_session()
        return result
    except InvestigationAPIError as exc:
        st.error(str(exc))
        return None


def render_live_settings(*, configure: bool = False, active: bool = True) -> bool:
    """Collect the visitor's limits and consent, then enable the shared investigation composer."""
    try:
        return _live_settings(configure, active)
    except InvestigationAPIError as exc:
        st.error(str(exc))
        return False


def _live_settings(configure, active):
    requested = st.session_state.pop("open_live_settings", False) or configure
    if not active and not requested and not st.session_state.get("live_drawer"):
        return False
    if offline():
        st.info("Live investigations are disabled in offline mode. The visitor sandbox remains available.")
        return False
    if not _secure_api():
        st.error("Configure an HTTPS investigation API to connect a provider key.")
        return False
    _session()
    if (run_id := st.session_state.get("live_run")) and _read_run(run_id)["status"] in ACTIVE_RUN:
        return False
    if requested:
        st.session_state.live_drawer = True
    if st.session_state.get("live_drawer"):
        _settings_drawer()
    return bool(st.session_state.get("live_settings") and st.session_state.get("credential"))


def _close_drawer():
    st.session_state.pop("live_drawer", None)


@st.dialog("Configure OpenAI", position="right", on_dismiss=_close_drawer)
def _settings_drawer():
    try:
        _configure_key()
    except InvestigationAPIError as exc:
        st.error(str(exc))


def _configure_key():
    st.caption(
        "Your selected OpenAI model also checks claims against their cited evidence. "
        "These additional calls use your key and count toward your run limits."
    )
    saved = st.session_state.get("live_settings", {})
    models = _request("GET", "/v1/models").json()["models"]
    profiles = {
        item["profile_id"]: item for item in models if item["enabled_in_public_demo"] and item["provider"] == "openai"
    }
    if not profiles:
        st.info("No models are enabled for this deployment.")
        return False
    profile_ids = list(profiles)
    saved_profile = saved.get("model_profile_id")
    selected = st.selectbox(
        "Provider model",
        profile_ids,
        index=profile_ids.index(saved_profile) if saved_profile in profiles else 0,
        format_func=lambda key: profiles[key]["display_name"],
    )
    provider = profiles[selected]["provider"]
    price = _request("GET", f"/v1/models/{selected}").json()
    st.caption(price["price_note"])
    if price.get("price_known"):
        pricing = profiles[selected]["pricing"]
        st.caption(
            f"Per million tokens: USD {pricing['input_per_1m_usd']} input · USD {pricing['output_per_1m_usd']} output."
        )
    with st.expander("Run limits", expanded=True):
        saved_limits = saved.get("limits", {})
        limits = {
            key: st.number_input(label, low, high, value=saved_limits.get(key, default))
            for key, (label, low, high, default) in LIMITS.items()
        }
        limits["max_input_tokens"] = st.number_input(
            "Input token cap (optional)", min_value=1, value=saved_limits.get("max_input_tokens")
        )
        limits["max_estimated_usd"] = (
            st.text_input(
                "Estimated cost cap in USD (optional)", value=saved_limits.get("max_estimated_usd") or ""
            ).strip()
            or None
        )
    money_limit = limits["max_estimated_usd"]
    financial_limit = f"USD {money_limit} estimated cap" if money_limit else "No estimated spending cap"
    st.write(
        f"**{profiles[selected]['display_name']}** · {limits['max_model_calls']} model calls · "
        f"{limits['max_tool_calls']} tool calls · {limits['max_wall_seconds']} seconds · "
        f"{limits['max_output_tokens']} output tokens"
    )
    input_limit = limits["max_input_tokens"]
    st.caption(f"{financial_limit} · " + (f"{input_limit} input tokens" if input_limit else "No input token cap"))
    st.write(
        "OpenAI may bill your account. An estimated cap depends on verified pricing. "
        "The investigation API keeps the key in memory. Forgetting the key or letting it expire prevents new runs. "
        "An active run can still use its copy until it finishes or you cancel it. "
        "OpenAI may charge for a request already in progress. Memory erasure cannot be guaranteed."
    )
    credential = st.session_state.get("credential")
    if credential:
        if provider != credential["provider"]:
            st.info("Forget the current key to connect a different provider.")
            return False
        st.caption(f"Connected key expires {credential['expires_at']}")
        if not st.button("Save settings"):
            return
    else:
        entry = st.empty()
        with entry.container():
            consent = st.checkbox(
                "I agree to send my key to the investigation API and pay OpenAI for this run.", key="live_consent"
            )
            with st.form("accept_key", clear_on_submit=True):
                key = st.text_input("Provider API key", type="password", disabled=not consent)
                accepted = st.form_submit_button("Connect key", disabled=not consent)
        if not accepted:
            return False
        if not key or not consent:
            st.warning("Enter a key and confirm consent to connect.")
            return False
        credential = _request("POST", CREDENTIALS, json={"provider": provider, "api_key": key}).json()
        st.session_state.credential = credential
        entry.empty()
    st.session_state.live_settings = {"model_profile_id": selected, "limits": limits}
    st.session_state.requested_answer_mode = "OpenAI"
    _close_drawer()
    st.rerun()


def submit_live_question(scenario_id: str, account_id: str, question: str) -> str | None:
    """Start a budgeted run using the current account and the visitor's edited question."""
    try:
        return _submit_live_question(scenario_id, account_id, question)
    except InvestigationAPIError as exc:
        st.error(str(exc))
        return None


def _submit_live_question(scenario_id, account_id, question):
    settings = st.session_state.get("live_settings")
    credential = st.session_state.get("credential")
    if not settings or not credential or not question.strip():
        return None
    branch = _request("POST", SANDBOXES, json={"scenario_id": scenario_id}).json()
    body = {
        "mode": "live_agent",
        "scenario_id": scenario_id,
        "sandbox_id": branch["id"],
        "expected_revision": branch["revision"],
        "account_id": account_id,
        "question": question.strip(),
        "variant": "C",
        "credential_handle": credential["handle"],
        **settings,
    }
    try:
        run_id = _request("POST", RUNS, json=body).json()["run_id"]
    except InvestigationAPIError as exc:
        if (
            exc.status == 422
            and exc.code == "MODEL_NOT_ALLOWED"
            and exc.detail.partition(":")[0] in STALE_CREDENTIAL_REASONS
        ):
            st.session_state.pop("credential", None)
            st.session_state.open_live_settings = True
            st.warning(
                "The connected key is no longer available. Configure OpenAI to reconnect and send your question."
            )
            return None
        raise
    st.session_state.live_run_handle = credential["handle"]
    st.session_state.live_run = run_id
    return run_id
