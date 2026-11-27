# Streamlit workspace

Install the application and API dependencies with `uv sync --extra app --extra api`. Start the portal with synthetic data:

```sh
LEDGERLENS_OFFLINE=1 uv run uvicorn app.server:portal --host 127.0.0.1 --port 8501
```

Open http://localhost:8501. Start with **Use this question**, edit the suggested question, then press **Send**. More sample questions appear below the question field. The trace is optional. Follow **See the recorded calculation** to inspect the same case and open its published proof. The mode indicator above the case shows whether the next answer is scripted or uses your key. Choose **Use my OpenAI key** to configure OpenAI on the same page. Configure the key, model and limits in the side panel. It closes when the API accepts the key. The connected status appears in the investigation, and the current question stays editable. Press **Send to OpenAI** to submit it. **Switch to demo** returns to scripted answers. A paid run requires a published snapshot for the selected account and case. **Recordings** opens the published cases. **Project details** presents published scores, evidence and the technical implementation. The view parameter uses the lowercase page title with hyphens between words. The default is `/?view=investigations`. An unknown view opens Investigations. A link such as `/?view=recordings` opens that workspace.

| Workspace | What you can do |
| --- | --- |
| Investigations | Switch demo accounts, inspect synthetic payments and ask a scripted question. Enable the trace to see the evidence behind an answer. |
| Explore data | Browse all nine sample tables or switch to the current demo account. |
| Project details | Read how the agent works and inspect published evaluation results, proofs and implementation. |
| Recordings | Browse scripted and real-model recordings, then inspect an answer, its evidence and recorded events. Playback requires no credentials. |
| Case simulator | Open `/?view=case-simulator` to load the first published case, or follow an investigation link to load that case. Choosing another case shows it immediately. Browsing uses no private branch slots. The first branch action opens a private copy, and revisiting the case restores its committed changes for the active session. The missing-transaction case has no ledger to edit. |
| OpenAI mode in Investigations | Connect a key with consent and investigate the selected payment using the same question field. |
| Evaluation | Inspect published evaluation results and download the underlying data. |
| Proof artifacts | Inspect and download published evidence. |
| Engineering | Inspect the implementation behind the payment investigation. |

Collapsible sections open by default across pages and tabs. Select a section heading to collapse it.

## Connect the API

Start `uv run ledgerlens-demo --port 8010` in a second terminal for Case simulator and Live. Streamlit connects from its server process. Set `LEDGERLENS_API_BASE_URL` if the API listens elsewhere. Each visitor's Streamlit session holds its own API cookies. The simulator previews the changed refund before you apply it and offers Undo afterward. Live shows the model and budget before you enter a key. Finish or cancel an active investigation before ending its session from either workspace. The API returns HTTP 409 (`RUN_RUNNING`) if a run is still active. Its credential and case remain available. Forgetting a key or letting it expire blocks new runs. An active run can continue using its copy. Cancellation can still incur charges for a request already in progress. The running API publishes its contract at `/openapi.json`. Reloading the browser can start a new session.

To enable Live, start both processes with `LEDGERLENS_OFFLINE=0`. The investigation starts in scripted mode. Switch to OpenAI to use your own key. Live uses deterministic retrieval and numeric checks. The selected OpenAI model also checks text claims against their cited evidence within the same run limits. The visitor enters an OpenAI key in a password field. Streamlit forwards it to the API, which returns a session-bound handle. Remote API connections carrying credentials require HTTPS.

A deployment must serve Streamlit's WebSocket connection and package the published artifacts from `site/`. Run one API worker or route each visitor to the same worker throughout the session. The credential vault and live-run coordinator are process-local. Use HTTPS for visitor traffic. Run `bash scripts/gate_web.sh` to check the application and its artifacts.

### Consult the sample database

**Explore data** at `/?view=explore-data` opens the full synthetic sample. **Records** contains payments, refunds, disputes, currency conversions, settlements, customers, merchants and the projector checkpoint. **Events** shows the event history. Filter by payment or inspect the whole database. The full sample includes simulator-generated card fingerprints and the shortened hashes stored as invoice references. Browsing does not require an OpenAI key.

A payment shortcut opens **Current demo account** with the payment selected. In this scope **Ask about this record** prepares an editable investigation draft. The full database is for inspection. Live questions are sent only when the visitor submits a supported case against its account snapshot.

The investigation acknowledges short greetings and test messages, including `teste`, in either mode without calling a provider. If an investigation finishes without answer text, the chat suggests a more specific question.

In **Project details** → **Evaluation**, the cutoff verifier experiment shows the valid dates cleared, the required reviews retained and the paraphrases that still went to review. Its link opens the [case definitions and comparison](evaluation.md#receipt-backed-cutoff-verification).
