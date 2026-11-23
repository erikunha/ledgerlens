# The image of the application of LedgerLens: the api of the visitor and the site of the demo.
#
# Why this file exists: the local run and the continuous integration need one image, built the same way
# everywhere, and the versions of the dependencies of that image are the versions of `uv.lock` and not the
# versions of a resolution of the day.

FROM python:3.12-slim-bookworm

# Why uv and not pip: the lock file of the repository is a lock file of uv, so pip would resolve versions
# the repository never pinned. The version of the installer is pinned too, because an installer that moves
# changes the bytes of the image without a commit.
COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH" \
    LEDGERLENS_OFFLINE=1 \
    LEDGERLENS_RUNTIME_DIR=/var/lib/ledgerlens \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# The user of the image. It is not the root: a container that serves a site has no reason to write to the
# system of the host, and the files of the repository stay readable by it.
#
# Why the home of the user is under `/srv` and not under `/home`: the guard of the public repository refuses
# every path that looks like the home of a person, because a path of a machine of a developer has no place in
# a repository that everybody reads, and the home of a user of a container is exactly such a path.
RUN useradd --system --create-home --uid 10001 --home-dir /srv/ledgerlens ledgerlens \
    && mkdir -p /srv/ledgerlens /var/lib/ledgerlens \
    && chown -R ledgerlens:ledgerlens /srv/ledgerlens /var/lib/ledgerlens

# The manifest and the lock file come first, so the layer of the dependencies is reused when only the code
# changes. The project itself is not installed yet, because the source is not in the image yet.
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --frozen --no-install-project --extra api --extra dev

# The source of the repository and the data it reads: the committed sample, the policies and the prebuilt
# index of the retrieval. The image carries no key and needs none: the offline mode is the default of the
# image, so nothing in it ever calls a provider.
COPY --chown=ledgerlens:ledgerlens ledgerlens/ ./ledgerlens/
COPY --chown=ledgerlens:ledgerlens data/ ./data/
# The tools of the repository and its suite travel with the image: the schema of the store is applied from the
# container with `scripts/apply_sandbox_schema.py`, and the suite of the store runs in it against the database
# of the compose, the way the plan of R2 describes.
COPY --chown=ledgerlens:ledgerlens scripts/ ./scripts/
COPY --chown=ledgerlens:ledgerlens tests/ ./tests/

# The project itself is installed here, and the whole tree belongs to the user of the image, so the
# process may write in the runtime folder it owns.
RUN uv sync --frozen --extra api --extra dev \
    && chown -R ledgerlens:ledgerlens /app \
    && chmod -R a+rX /app

USER ledgerlens

EXPOSE 8010 3000

# The default command is the demo server of the visitor: the wired application of the demo (ADR-039). The
# host is the address of the container, because the port is published by the compose file.
CMD ["ledgerlens-demo", "--host", "0.0.0.0", "--port", "8010"]
