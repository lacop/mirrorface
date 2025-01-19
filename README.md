# MirrorFace 🪞 🤗

`HF_ENDPOINT=http://mirrorface:port/mirror python3 model.py`

Proxy for HuggingFace Hub which serves models from a local directory if available, and falls back to being a transparent proxy to the HuggingFace Hub otherwise.

Make your production ML deployments more robust, avoiding downtime when HuggingFace has an outage.

## Usage

### Using the service

TODO

### Mirroring models

To download a repository run the `mirror` command:

```shell
uv run mirror \
  --repository "username/repository" \
  --revision "main" \
  --local_directory /tmp/mirrorface
```

Set `revision` to a branch, tag, or commit hash, or skip it (defaults to `main`).

## Deployment

TODO

## Architecture

TODO

## Local Development

Run the server:

```shell
MIRRORFACE_LOCAL_DIRECTORY=/tmp/mirrorface \
uv run python -m gunicorn -c src/mirrorface/server/gunicorn.conf.py mirrorface.server.main:app
```

Run the unit tests and static checks:

```shell
uv run pytest

uv run pyright
```

Run integration tests (requires Docker):

```shell
uv run integration_tests
```
