# Streamlit workspace

Install the application and API dependencies with `uv sync --extra app --extra api`. Start the portal with synthetic data:

```sh
LEDGERLENS_OFFLINE=1 uv run uvicorn app.server:portal --host 127.0.0.1 --port 8501
```

Open http://localhost:8501. The Workspace selector updates the URL. A link such as `/?view=Replay` opens that workspace.

| Workspace | What you can do |
| --- | --- |
| Payments | Switch demo accounts, inspect synthetic payments and ask a scripted question. Expand the trace to see the evidence behind an answer. |
| Replay | Browse scripted and real-model recordings, then inspect an answer, its evidence and recorded events. Playback requires no credentials. |
| Sandbox | Fork a published case into a private branch and edit it through the demo API. |
| Live | Select a model, connect your key with consent and submit a budgeted investigation. |
| Evaluation | Inspect published evaluation results and download the underlying data. |
| Proof | Inspect and download published evidence. |
| Engineering | Inspect the implementation behind the payment investigation. |

## Connect the API

Start `uv run ledgerlens-demo --port 8010` in a second terminal for Sandbox and Live. Streamlit connects from its server process. Set `LEDGERLENS_API_BASE_URL` if the API listens elsewhere. Each visitor's Streamlit session holds its own API cookies. Reloading the browser can start a new session.

To enable Live, start both processes with `LEDGERLENS_OFFLINE=0`. Payments stays scripted when Live is enabled. Live uses deterministic retrieval and verification. The visitor enters an OpenAI key in a password field. Streamlit forwards it to the API, which returns a session-bound handle. Remote API connections carrying credentials require HTTPS.

A deployment must serve Streamlit's WebSocket connection and package the published artifacts from `site/`. Run one API worker or route each visitor to the same worker throughout the session. The credential vault and live-run coordinator are process-local. Use HTTPS for visitor traffic. Run `bash scripts/gate_web.sh` to check the application and its artifacts.
