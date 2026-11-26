"""Serve the Streamlit portal with gzip so its JavaScript fits a cold mobile connection."""

from pathlib import Path

from starlette.middleware import Middleware
from starlette.middleware.gzip import GZipMiddleware
from streamlit.starlette import App

# Level one keeps compression work low during concurrent cold starts.
portal = App(
    Path(__file__).with_name("streamlit_app.py"),
    middleware=[Middleware(GZipMiddleware, compresslevel=1)],
)
