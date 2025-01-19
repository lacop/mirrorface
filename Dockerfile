FROM python:3.12-alpine AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# External dependencies first to help with intermediate layer cahing.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-project

# uv wants the readme to exist to install, but don't bother
# copying it, no reason to invalidate cache when it changes.
RUN touch /app/README.md
ADD src/mirrorface /app/src/mirrorface
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev

ADD src/mirrorface/server/gunicorn.conf.py /app/gunicorn.conf.py
ENTRYPOINT ["/app/.venv/bin/gunicorn", "-c", "/app/gunicorn.conf.py", "mirrorface.server.main:app"]
