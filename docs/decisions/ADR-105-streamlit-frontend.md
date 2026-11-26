---
type: adr
status: accepted
date: 2026-11-26
---

# ADR-105: Serve the workspace with Streamlit

Streamlit serves the payments portal, recordings, evaluation results, proof, engineering, sandbox and live investigations through one Python entry point. The recorded views read published files. The interactive views call the demo API with session-specific cookies.

Hosting requires a running Python process and WebSocket support. The portal shares the payment domain types and disclosure text directly with Python. A second frontend would require independent implementations of the same interactions and evidence views.

See the [workspace guide](../frontend.md) for the commands and deployment requirements.
