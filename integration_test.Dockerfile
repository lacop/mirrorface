# Simplified version of the main Dockerfile without cache mounts
# or other buildkit-only features not available in docker-py.
FROM python:3.12-alpine

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
ADD src/mirrorface /app/src/mirrorface
ADD pyproject.toml uv.lock /app/
ADD src/mirrorface/server/gunicorn.conf.py /app/gunicorn.conf.py
RUN touch README.md
RUN uv sync --frozen --no-dev
ENTRYPOINT ["/app/.venv/bin/gunicorn", "-c", "/app/gunicorn.conf.py", "mirrorface.server.main:app"]
