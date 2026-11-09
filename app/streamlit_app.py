"""LedgerLens Pay: a demo payments portal whose Help panel is the investigation agent.

The person is signed in to one account from the generated data (a customer `C-nnnn` or a merchant `M-nn`; "Switch
demo account" at the top picks another). The left side is their portal: an account card, and their activity in
tabs (Activity, Refunds, Disputes and, for a merchant, Payouts), amount first, with a status pill and filters. A line
opens to its details. "Ask about this" only fills the Help box with a question about that line and puts the cursor
there; the person edits it and sends it. The right side is the Help panel, where the agent answers as the support
assistant; the conversation scrolls inside the panel, so the box stays on screen.

What the agent gets: the question, and a context message with the signed-in account and the line picked. Its tools
and the verifier read a copy of the ledger that holds only that account's records (`scoped_ledger`), so a query
cannot reach another customer's rows.

The conversation lives in `session_state` with one `thread_id` per account; switching account starts a new one.
The question shows up right away, before the investigation. While the agent works, the assistant's message shows the
investigation's trace in an `st.status`, like LangSmith's run tree: the root `investigate`, triage (prompt, model,
parser), the agent with each model call (name, tokens) and each tool (arguments, the response envelope and the
generated SQL), the plan's single follow-up, verification with one node per claim (check, label, NLI scores) and
escalation. Each node shows `run_type · name · latency · tokens` and opens the span's JSON; an error shows in red. At
the end the block collapses into a one-line summary ("Checked 4 sources in 6.2 s: 3 claims supported, 1 without
evidence"), the answer appears below it, and the spans are kept with the message, so the trace can still be opened
in the history. With LangSmith on in the process, the links to the runs sent to it appear under the summary. The
spans come from `investigate(..., on_event=...)` (`ledgerlens.observability.trace`); the tools run in the graph's
threads, so the investigation runs in a thread of its own and the page draws the spans that arrive on a queue. The
answer does not stream token by token: the verifier reads the whole answer and may rewrite it (an unavailable rate
gets named), so it appears finished, after verification. `st.chat_input` takes no initial value, so the question box
is a form with `st.text_input` and a submit button.

The switch "Show the agent trace" (on by default) shows the trace on each answer, the evidence citations in the text
and the ledger records the agent read, and marks the lines read on the statement. With it off, the answer shows with
no trace and no citations, as a support reply would, and the trace stays stored with the message.

Offline (`LEDGERLENS_OFFLINE=1`) the model is scripted and only the planted questions have a script, as written:
"Ask about this" is offered only on the lines that have one. Online the page uses the configured model.
Run: `uv run streamlit run app/streamlit_app.py`.
"""

from __future__ import annotations

import logging
import queue
import re
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any

import streamlit as st

from ledgerlens import demo
from ledgerlens.agents.integrator import Integrator, build_integrator, investigate
from ledgerlens.api.accounts import Account, account_statement, load_account_profile, load_accounts, scoped_ledger
from ledgerlens.config import ConfigError, get_settings, offline
from ledgerlens.observability.trace import Span
from ledgerlens.offline import ScriptedChatModel, text_message
from ledgerlens.schemas import InvestigationResult
from ledgerlens.sim.config import SimConfig
from ledgerlens.sim.pipeline import build_ledger
from ledgerlens.tools.fx import FxClient

log = logging.getLogger(__name__)

BRAND = "LedgerLens Pay"
DEFAULT_ACCOUNT = "C-0412"
PAGE_SIZE = 10
CHAT_HEIGHT = 420
USER_AVATAR = ":material/person:"
ASSISTANT_AVATAR = ":material/support_agent:"
WORKING = "Checking your account"
# the icon of each state of a trace span
SPAN_ICONS = {
    "running": ":gray[:material/hourglass_top:]",
    "ok": ":green[:material/check_circle:]",
    "error": ":red[:material/error:]",
}
VERDICT_COLORS = {"supported": "green", "contradicted": "red", "not_enough_evidence": "orange"}
# what Streamlit's Markdown would read as formatting: emphasis, code, link and quote, math, HTML, table
MARKDOWN_SPECIAL = re.compile(r"([\\`*_\[\]$<>~|])")
OFFLINE_REFUSAL = (
    "I can only answer the suggested questions in this offline demo. "
    "With a configured model I can answer any question about your account."
)
OFFLINE_ASK_HELP = "This offline demo has scripted answers for some lines only. Try a suggested question in Help."
TABS = {"activity": None, "refunds": "Refund", "disputes": "Chargeback", "payouts": "Payout"}
CITATION = re.compile(r"\s*\[((?:sql|api|policy|fx|calc|case):[^\]]*)\]")
STYLE = """
<style>
header[data-testid="stHeader"], [data-testid="stMainMenu"], [data-testid="stStatusWidget"],
[data-testid="stHeadingActionElements"], [data-testid="stSidebarCollapsedControl"],
[data-testid="InputInstructions"] { display: none !important; }
.block-container { padding-top: 2rem; max-width: 1480px; }
[data-testid="stCaptionContainer"] { opacity: 1; }
[data-testid="stCaptionContainer"] p { color: #5f5c58; }
.st-key-brand h1 { font-size: 1.75rem; padding: 0; }
.st-key-account-card { background: var(--secondary-background-color); }
.st-key-account-card [data-testid="stMetricValue"] { font-size: 1.35rem; }
.ll-avatar { width: 2.6rem; height: 2.6rem; border-radius: 50%; background: #2f5bd3; color: #fff;
  display: flex; align-items: center; justify-content: center; font-weight: 600; letter-spacing: 0.02em; }
.st-key-help h3 { font-size: 1.2rem; font-weight: 600; padding-top: 0; }
.st-key-help [data-testid="stChatMessage"] p { font-size: 0.95rem; }
[class*="st-key-line-"] details summary p { font-size: 0.95rem; }
@media (min-width: 641px) { .st-key-help { position: sticky; top: 1rem; } }
@media (max-width: 640px) {
  .st-key-account-card [data-testid="stHorizontalBlock"] { flex-direction: row !important; flex-wrap: wrap; }
  .st-key-account-card [data-testid="stColumn"] { min-width: 30% !important; flex: 1 1 30% !important; }
  .st-key-account-card [data-testid="stColumn"]:first-child { flex-basis: 100% !important; }
  .st-key-chat { height: auto !important; max-height: none !important; }
}
</style>
"""
# After "Ask about this": bring the question box into view, put the cursor in it and flash it once.
FOCUS_DRAFT = """
<style>
@keyframes ll-flash { 0% { box-shadow: 0 0 0 3px rgba(47, 91, 211, 0.55); } 100% { box-shadow: 0 0 0 0 transparent; } }
.st-key-draft input { animation: ll-flash 1.6s ease-out; }
</style>
<script>
setTimeout(() => {
  const box = document.querySelector('.st-key-draft input');
  if (box) { box.scrollIntoView({block: 'nearest', behavior: 'smooth'}); box.focus({preventScroll: true}); }
}, 250);
</script>
"""


# ---- data ------------------------------------------------------------------------------------------------


@st.cache_resource
def sample_ledger() -> Path:
    """Ledger of the committed sample, in a temporary file."""
    path = Path(tempfile.mkdtemp(prefix="ledgerlens_app_")) / "ledger.db"
    build_ledger(SimConfig(source="sample"), path).conn.close()
    return path


def base_ledger(is_offline: bool) -> Path:
    """Offline, the sample ledger. Online, the configured one (`LEDGERLENS_LEDGER_DB`), or the sample when that
    file was never built (`ledgerlens-sim` builds it)."""
    configured = Path(get_settings().ledger_db)
    return configured if not is_offline and configured.exists() else sample_ledger()


@st.cache_resource
def account_ledger(account_id: str, is_offline: bool) -> Path:
    """The copy of the ledger that holds only the account's records: what the agent's tools read."""
    folder = Path(tempfile.mkdtemp(prefix=f"ledgerlens_{account_id}_"))
    return scoped_ledger(base_ledger(is_offline), account_id, folder / "ledger.db")


@st.cache_resource
def portal_accounts(is_offline: bool) -> list[Account]:
    """The accounts offered at sign-in: the customers and merchants of the planted cases."""
    reserved = demo.load_manifest()["reserved_ids"]
    return load_accounts(base_ledger(is_offline), [*reserved["customers"], *reserved["merchants"]])


# ---- the agent -----------------------------------------------------------------------------------------


def offline_session(account_id: str) -> dict[str, Any]:
    """The account's offline agent with its scripted models (agent, SQL and triage), which start with no script."""
    model, query_model, triage_model = (ScriptedChatModel(script=[]) for _ in range(3))
    agent = build_integrator(
        model,
        db_path=account_ledger(account_id, True),
        query_model=query_model,
        triage_model=triage_model,
        fx_client=FxClient(mode="fixtures", sleep=lambda _: None),
    )
    return {"agent": agent, "model": model, "query_model": query_model, "triage_model": triage_model}


def prepare_offline_turn(session: dict[str, Any], question: str) -> None:
    """Adds the turn's script: the planted question's, or the refusal for a question with no script.

    Triage gets its scripted answer too, so the offline trace shows the intent and the plan."""
    manifest = demo.load_manifest()
    session["triage_model"].script.append(demo.offline_triage(question, manifest))
    script = demo.offline_script(question, manifest)
    if script is None:
        session["model"].script.append(text_message(OFFLINE_REFUSAL))
        return
    messages, sqls = script
    session["model"].script.extend(messages)
    session["query_model"].script.extend(sqls)


def ask_agent(question: str, account_id: str, is_offline: bool) -> Integrator:
    """The agent for the account: the one injected (tests), the scripted offline one or the configured one."""
    if "agent" in st.session_state:
        return st.session_state["agent"]
    agents = st.session_state.setdefault("agents", {})
    if account_id not in agents:
        if is_offline:
            agents[account_id] = offline_session(account_id)
        else:
            agents[account_id] = {"agent": build_integrator(db_path=account_ledger(account_id, False))}
    session = agents[account_id]
    if is_offline:
        prepare_offline_turn(session, question)
    return session["agent"]


# ---- callbacks -----------------------------------------------------------------------------------------


def fill_draft(text: str, selected: list[str]) -> None:
    """Puts the question in the box, without sending: the person reads, edits and sends."""
    st.session_state["draft"] = text
    st.session_state["selected"] = selected
    st.session_state["focus_draft"] = True


def clear_selection() -> None:
    st.session_state["selected"] = []


def show_all(tab: str) -> None:
    st.session_state[f"all-{tab}"] = True


def submit_draft() -> None:
    """Keeps the box's text as the turn's question and clears the box."""
    st.session_state["question"] = st.session_state.get("draft", "").strip()
    st.session_state["draft"] = ""


def switch_account() -> None:
    """Another account signs in: new conversation, empty box, filters reset."""
    st.session_state["turns"] = []
    st.session_state["thread_id"] = f"app-{uuid.uuid4().hex[:8]}"
    st.session_state["draft"] = ""
    st.session_state["selected"] = []
    for key in [k for k in st.session_state if str(k).startswith(("f_", "all-"))]:
        del st.session_state[key]


# ---- the Help panel ------------------------------------------------------------------------------------


def plain(text: str) -> str:
    """Agent or tool text as a literal in Markdown: `*`, `[sql:1]` and `$` do not become formatting."""
    return MARKDOWN_SPECIAL.sub(r"\\\1", text)


def depth_of(span: Span, spans: dict[str, Span]) -> int:
    depth, parent = 0, span.parent_run_id
    while parent is not None and parent in spans and depth < 12:
        depth, parent = depth + 1, spans[parent].parent_run_id
    return depth


def span_header(span: Span, depth: int) -> str:
    """A span's line: `run_type · name · latency · tokens`, indented by its depth in the tree."""
    parts = [f"`{span.run_type}`", f"**{plain(span.name)}**"]
    if span.metadata.get("label"):  # a claim's verdict
        label = span.metadata["label"]
        parts.append(f":{VERDICT_COLORS.get(label, 'gray')}[{label}] ({plain(str(span.metadata.get('check')))})")
    if span.latency_ms is not None:
        parts.append(f"{span.latency_ms} ms")
    tokens = (span.metadata.get("tokens") or {}).get("total")
    if tokens:
        parts.append(f"{tokens} tokens")
    # Streamlit trims leading spaces in Markdown, so the indent is one bar per level
    indent = f":gray[{'│ ' * depth}]" if depth else ""
    return indent + f"{SPAN_ICONS[span.status]} " + " · ".join(parts)


def draw_span(span: Span, depth: int) -> None:
    """A trace node: the header always in view; the generated SQL, the error in red and the span's JSON, collapsed."""
    st.markdown(span_header(span, depth))
    if span.error:
        st.error(span.error, icon=":material/error:")
    sql = ((span.outputs or {}).get("data") or {}).get("sql") if isinstance(span.outputs, dict) else None
    if span.run_type == "tool" and isinstance(sql, str):
        st.code(sql, language="sql")
    body = {
        "run_id": span.run_id,
        "parent_run_id": span.parent_run_id,
        "start_time": span.start_time,
        "end_time": span.end_time,
        "inputs": span.inputs,
        "outputs": span.outputs,
        "metadata": span.metadata,
    }
    st.json(body, expanded=False)


class TraceView:
    """The trace inside an `st.status`, drawn live: one node per span, in the order they started, replaced in place
    when the span ends. The block's title says what is running now."""

    def __init__(self, status: Any) -> None:
        self.status = status
        self.spans: dict[str, Span] = {}
        self.slots: dict[str, Any] = {}

    def add(self, span: Span) -> None:
        self.spans[span.run_id] = span
        if span.status == "running":
            # without `expanded`, updating the title collapses the block in the browser and the spans are hidden
            self.status.update(label=f"{span.run_type} · {span.name}", expanded=True)
        slot = self.slots.get(span.run_id)
        if slot is None:
            # `status.empty()` and not `with status:`: leaving a `with` block makes Streamlit mark it complete
            slot = self.slots[span.run_id] = self.status.empty()
        with slot.container():
            draw_span(span, depth_of(span, self.spans))


def final_spans(events: list[Span]) -> list[Span]:
    """The last version of each span, in the order they started: what is stored with the message."""
    latest: dict[str, Span] = {}
    for span in events:
        latest[span.run_id] = span  # a dict keeps the position of the first insertion
    return list(latest.values())


def trace_summary(spans: list[Span]) -> tuple[str, str]:
    """The title of the closed trace and the block's state, taken from the root `investigate`."""
    root = next((s for s in spans if s.parent_run_id is None), None)
    if root is None:
        return WORKING, "complete"
    if root.error:
        return f"Failed: {root.error}", "error"
    return str((root.outputs or {}).get("summary") or WORKING), "complete"


def langsmith_links(spans: list[Span]) -> None:
    root = next((s for s in spans if s.parent_run_id is None), None)
    links = (root.metadata.get("langsmith") if root else None) or []
    if links:
        st.caption("LangSmith: " + ", ".join(f"[{plain(link['name'])}]({link['url']})" for link in links))


def show_trace(spans: list[Span]) -> None:
    """The trace of an answer already given: the closed summary, which opens to the whole tree."""
    label, state = trace_summary(spans)
    by_id = {s.run_id: s for s in spans}
    with st.status(label, state=state, expanded=False):
        for span in spans:
            draw_span(span, depth_of(span, by_id))
    langsmith_links(spans)


def investigate_live(
    agent: Integrator, question: str, *, thread_id: str, context: str, show: bool
) -> tuple[InvestigationResult | None, list[Span]]:
    """Runs the investigation in a thread and, with `show`, draws each span as soon as it arrives.

    The tools call `on_event` from the graph's threads, and Streamlit only draws on the page's thread: the spans go
    through a queue and this function, on the page's thread, takes them off and draws them. Returns the result (or
    `None` if the investigation failed, after showing the error) and the spans, to store them with the message."""
    inbox: queue.Queue[Span] = queue.Queue()
    outcome: dict[str, Any] = {}

    def work() -> None:
        try:
            outcome["result"] = investigate(agent, question, thread_id=thread_id, context=context, on_event=inbox.put)
        except Exception as exc:  # shown on the page; the conversation goes on
            log.exception("the investigation failed")
            outcome["error"] = exc

    worker = threading.Thread(target=work, name="ledgerlens-investigation", daemon=True)
    worker.start()
    events: list[Span] = []
    status = st.status(WORKING, expanded=True) if show else None
    view = TraceView(status) if status is not None else None
    spinner = st.spinner(WORKING) if status is None else None
    if spinner is not None:
        spinner.__enter__()
    try:
        while worker.is_alive() or not inbox.empty():
            try:
                span = inbox.get(timeout=0.1)
            except queue.Empty:
                continue
            events.append(span)
            if view is not None:
                view.add(span)
    finally:
        if spinner is not None:
            spinner.__exit__(None, None, None)
    worker.join()
    spans = final_spans(events)
    if status is not None:
        label, state = trace_summary(spans)
        status.update(label=label, state=state, expanded=False)
        langsmith_links(spans)
    if "error" in outcome:
        error = outcome["error"]
        st.error(f"The investigation failed: {type(error).__name__}: {error}")
        return None, spans
    return outcome["result"], spans


def render_result(result: InvestigationResult, observer: bool, statement_ids: set[str] | None = None) -> None:
    """The support reply; with `observer`, also the citations and the ledger records the agent read.

    The trace, above the answer, already shows each tool with its arguments and envelope, each verdict and the review
    reason; here goes only what it does not show."""
    if result.answer == OFFLINE_REFUSAL:  # nothing was looked up: there is nothing to verify or review
        st.markdown(result.answer)
        return
    if not observer:
        st.markdown(CITATION.sub("", result.answer))
        if result.requires_human_review:
            st.caption("A support specialist will also look at this case.")
        return
    st.markdown(CITATION.sub(lambda m: f" :gray[\\[{m.group(1)}\\]]", result.answer))
    read = sorted(demo.ids_read(result))
    if read:
        caption = f"Ledger records read: {', '.join(read)}"
        outside = [i for i in read if statement_ids is not None and i not in statement_ids and i[:2] != "M-"]
        st.caption(caption + (f". Not on this account: {', '.join(outside)}" if outside else ""))


def show_turn(turn: dict[str, Any], observer: bool, statement_ids: set[str]) -> None:
    """A turn already answered: the question and, below it, the assistant's reply."""
    with st.chat_message("user", avatar=USER_AVATAR):
        st.markdown(turn["question"])
        if turn.get("selected"):
            st.caption(f"About {', '.join(turn['selected'])}")
    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        if observer and turn.get("trace"):
            show_trace(turn["trace"])
        render_result(turn["result"], observer, statement_ids)


# ---- the portal ----------------------------------------------------------------------------------------


def initials(name: str) -> str:
    parts = [p for p in re.split(r"\s+", name) if p[:1].isalpha()]
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper() if parts else "?"


def account_card(account: Account, lines: list[dict[str, Any]], profile: dict[str, Any]) -> None:
    with st.container(border=True, key="account-card"):
        who, *figures = st.columns([1.7, 1, 1, 1], vertical_alignment="center")
        with who.container(horizontal=True, vertical_alignment="center", gap="small"):
            st.html(f'<div class="ll-avatar">{initials(account.name)}</div>', width="content")
            plan = "Personal account" if account.kind == "customer" else f"Business account, {profile['category']}"
            st.markdown(f":gray[Signed in as]  \n**{account.name}**  \n:gray[{plan}, {account.id}]")
        for cell, (label, value) in zip(figures, demo.account_summary(lines, account.kind), strict=True):
            cell.metric(label, value)


def line_label(line: dict[str, Any], kind: str, marks: dict[str, set[str]]) -> str:
    """The closed line: amount first, then what it is, the date and the status pill; demo marks at the end."""
    label, color = demo.status_pill(line)
    parts = [
        f"**{demo.money(line['amount'], line['currency'])}**",
        demo.line_title(line, kind),
        f":gray[{demo.nice_date(line['date'])}]",
        f":{color}-badge[{label}]",
    ]
    if line["id"] in marks["asked"]:
        parts.append(":blue-badge[asked about]")
    if line["id"] in marks["read"]:
        parts.append(":orange-badge[read by assistant]")
    return " ".join(parts)


def render_lines(
    tab: str, lines: list[dict[str, Any]], account: Account, marks: dict[str, set[str]], is_offline: bool
) -> None:
    """One tab of activity: a line per record, opened for its details and "Ask about this"."""
    if not lines:
        st.caption("Nothing here for these filters.")
        return
    manifest = demo.load_manifest()
    visible = lines if st.session_state.get(f"all-{tab}") else lines[:PAGE_SIZE]
    for line in visible:
        with st.expander(line_label(line, account.kind, marks), key=f"line-{tab}-{line['id']}"):
            st.markdown(f":gray[{demo.ID_LABELS[line['type']]}] `{line['id']}`")
            cells = st.columns(3)
            for index, (name, value) in enumerate(demo.line_details(line, account.kind)):
                with cells[index % 3]:
                    st.caption(name)
                    st.markdown(value)
            question = demo.ask_question(line, account.id, manifest)
            scripted = demo.offline_script(question, manifest) is not None
            st.button(
                "Ask about this",
                key=f"ask-{tab}-{line['id']}",
                help=OFFLINE_ASK_HELP if is_offline and not scripted else f"Puts this question in Help: {question}",
                on_click=fill_draft,
                args=(question, [line["id"]]),
                type="primary",
                disabled=is_offline and not scripted,
            )
            if line["id"] in st.session_state["selected"]:
                st.caption("Question ready in Help: review it and press Send.")
    if len(visible) < len(lines):
        st.button(f"Show all {len(lines)}", key=f"show-all-{tab}", type="tertiary", on_click=show_all, args=(tab,))


def render_portal(account: Account, lines: list[dict[str, Any]], marks: dict[str, set[str]], is_offline: bool) -> None:
    account_card(account, lines, load_account_profile(account_ledger(account.id, is_offline), account.id))
    st.markdown("#### Your activity")
    with st.expander("Filters", icon=":material/filter_list:"):
        period, status, search = st.columns([1, 1.4, 1])
        period.selectbox("Period", list(demo.PERIODS), key="f_period")
        status.multiselect(
            "Status",
            sorted({demo.status_pill(line)[0] for line in lines}),
            key="f_status",
            placeholder="Any status",
        )
        search.text_input("Search by ID", key="f_search", placeholder="Search by ID")
    shown = demo.filter_lines(
        lines,
        period=st.session_state["f_period"],
        statuses=st.session_state["f_status"],
        search=st.session_state["f_search"],
    )
    names = ["activity", "refunds", "disputes"] + (["payouts"] if account.kind == "merchant" else [])
    groups = {
        name: [x for x in shown if (x["type"] != "Payout" if TABS[name] is None else x["type"] == TABS[name])]
        for name in names
    }
    st.caption(f"Newest first. {len(shown)} of {len(lines)} records match the filters.")
    for tab, name in zip(st.tabs([f"{n.capitalize()} ({len(groups[n])})" for n in names]), names, strict=True):
        with tab:
            render_lines(name, groups[name], account, marks, is_offline)
    marked = sorted(marks["asked"] | marks["read"])
    if marked:  # a soft background on the lines asked about or read, for the demo viewer
        selectors = ", ".join(f".st-key-line-{name}-{i}" for name in names for i in marked)
        st.html(f"<style>{selectors} {{ background: rgba(250, 170, 40, 0.12); border-radius: 0.5rem; }}</style>")


def mode_line(is_offline: bool) -> str:
    if is_offline:
        return "Offline demo: scripted answers, recorded FX rates and sample data."
    return f"Online: model {get_settings().model or 'not configured'}."


def main() -> None:
    st.set_page_config(page_title=BRAND, page_icon=":material/payments:", layout="wide")
    st.html(STYLE)
    is_offline = offline()
    manifest = demo.load_manifest()
    accounts = {a.id: a for a in portal_accounts(is_offline)}
    st.session_state.setdefault("account", DEFAULT_ACCOUNT if DEFAULT_ACCOUNT in accounts else next(iter(accounts)))
    st.session_state.setdefault("turns", [])
    st.session_state.setdefault("selected", [])
    st.session_state.setdefault("thread_id", f"app-{uuid.uuid4().hex[:8]}")

    brand, switch = st.columns([3, 1.2], vertical_alignment="center")
    with brand.container(key="brand"):
        st.title(BRAND, anchor=False)
        st.caption("Demo payments portal with simulated data. Help is answered by the LedgerLens agent.")
    with switch.popover("Switch demo account", icon=":material/swap_horiz:", width="stretch"):
        st.selectbox(
            "Signed in as",
            list(accounts),
            key="account",
            format_func=lambda i: accounts[i].label,
            on_change=switch_account,
        )
        st.caption(f"Conversation `{st.session_state['thread_id']}`")
    account = accounts[st.session_state["account"]]

    lines = account_statement(account_ledger(account.id, is_offline), account.id)
    statement_ids = {i for line in lines for i in [line["id"], *line["ids"]]}
    turns = st.session_state["turns"]
    st.session_state.setdefault("observer", True)  # the trace shows by default; the switch hides it
    observer = bool(st.session_state["observer"])
    last = turns[-1] if turns else None
    marks: dict[str, set[str]] = {"asked": set(), "read": set()}
    if observer:
        marks["read"] = demo.ids_read(last["result"]) if last else set()
        marks["asked"] = set(st.session_state["selected"]) | (set(demo.ledger_ids(last["question"])) if last else set())

    left, right = st.columns([7, 4], gap="large")
    with left:
        render_portal(account, lines, marks, is_offline)

    with right, st.container(border=True, key="help"):
        st.subheader("Help", anchor="help")
        st.caption(
            "Ask the support assistant about your payments, refunds, disputes or payouts. " + mode_line(is_offline)
        )
        st.toggle(
            "Show the agent trace",
            key="observer",
            help="The run tree of each answer, as in LangSmith: triage, each model and tool call with inputs and "
            "outputs, the verification of each claim and escalation. Off, the answer reads as a support reply, with "
            "no citations.",
        )
        talking = bool(turns) or bool(st.session_state.get("question"))
        chat = st.container(height=CHAT_HEIGHT, key="chat", autoscroll=True) if talking else st.container()
        with chat:
            if not talking:
                hint = "Open a payment and press **Ask about this**, or pick a question below."
                if is_offline:
                    hint += " In this offline demo only the suggested questions have scripted answers."
                st.caption(hint)
            for turn in turns:
                show_turn(turn, observer, statement_ids)

        tries = st.expander("Questions to try") if turns else st.container()
        with tries:
            for index, text in enumerate(demo.account_questions(account.id, manifest)):
                st.button(text, key=f"suggestion-{index}", width="stretch", on_click=fill_draft, args=(text, []))
        if st.session_state["selected"]:
            about, clear = st.columns([4, 1], vertical_alignment="center")
            about.caption(f"About {', '.join(st.session_state['selected'])} from your activity")
            clear.button("Clear", key="clear-selection", type="tertiary", on_click=clear_selection)
        with st.form("composer", border=False):
            field, send = st.columns([5, 1.3], vertical_alignment="bottom")
            field.text_input(
                "Question",
                key="draft",
                placeholder="Type your question",
                label_visibility="collapsed",
            )
            send.form_submit_button("Send", key="send", type="primary", width="stretch", on_click=submit_draft)
        if st.session_state.pop("focus_draft", False):
            st.toast("Question added to Help. Review it and press Send.", icon=":material/support_agent:")
            st.html(FOCUS_DRAFT, unsafe_allow_javascript=True)
        question = st.session_state.pop("question", "")

        if question:  # the question shows up right away: the online investigation takes tens of seconds
            selected = list(st.session_state["selected"])
            with chat:
                with st.chat_message("user", avatar=USER_AVATAR):
                    st.markdown(question)
                try:
                    agent = ask_agent(question, account.id, is_offline)
                except ConfigError as error:
                    st.error(f"Could not build the agent: {error}")
                    return
                context = demo.account_context(account.id, account.kind, account.name, selected)
                with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
                    result, spans = investigate_live(
                        agent, question, thread_id=st.session_state["thread_id"], context=context, show=observer
                    )
                    if result is None:
                        return
                    render_result(result, observer, statement_ids)
            turns.append(
                {"question": question, "result": result, "selected": selected, "context": context, "trace": spans}
            )
            st.session_state["selected"] = []  # the line picked belongs to the question just sent
            st.rerun()  # draws the activity again with the lines the assistant read


main()
