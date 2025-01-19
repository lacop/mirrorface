# MirrorFace 🪞 🤗

`HF_ENDPOINT=http://mirrorface/mirror python3 model.py`

Proxy for HuggingFace Hub which serves models from a local directory if available, and falls back to being a transparent proxy to the HuggingFace Hub otherwise.

Make your production ML deployments more robust, avoiding downtime when HuggingFace has an outage.

## Usage

### Using the service

Supports code that load models via `huggingface-hub` library (including the `transofmers` library).

Simply set the `HF_ENDPOINT` environment variable to point to your MirrorFace deployment.

```shell
HF_ENDPOINT=http://mirrorface-hostname:port/mirror python3 model.py
```

### Mirroring models

To download a repository run the `mirror` command (must have [`uv`](https://docs.astral.sh/uv/) installed):

```shell
uvx --from git+https://github.com/lacop/mirrorface mirror \
  --repository "username/repository" \
  --revision "main" \
  --gcs_bucket "my-mirrorface-bucket"
```

Set `revision` to a branch, tag, or commit hash, or skip it (defaults to `main`).

Must have `gcloud` CLI tool installed and authenticated so it can write to the provided `gcs_bucket`.

## Deployment

Helm chart is available at `ghcr.io/lacop/mirrorface-server`. Use it with your favorite gitops tool, or if you like to YOLO things:

```shell
helm template \
  <mirrorface-deployment-name-here> \
  oci://ghcr.io/lacop/mirrorface-server:<version-here> \
  --set bucketName=<your-mirrorface-bucket> \
  | kubectl apply -f -
```

You can also run the Docker package `ghcr.io/lacop/mirrorface` directly. Just provide the `MIRRORFACE_LOCAL_DIRECTORY` environment variable.

## Architecture

MirrorFace server hosts an `/mirror` endpoint that can be used as drop-in replacement for the upstream HuggingFace Hub using `HF_ENDPOINT` environment variable. It checks if the requested model is available locally and will serve it from there, otherwise it will proxy the request to the upstream HuggingFace Hub.

By itself it will not mirror anything, the local directory is read-only. To mirror models to the local directory use the `mirror` command.

The MirrorFace server can only read from local filesystem. In production deployments this should be a GCS bucket mounted through GCS FUSE CSI driver (the provided Helm chart does this).

There are metrics and logs for monitoring. You should monitor the cache misses and run `mirror` to download the missing models as needed.

## Local Development

Run the server:

```shell
MIRRORFACE_LOCAL_DIRECTORY=/tmp/mirrorface \
uv run python -m gunicorn -c src/mirrorface/server/gunicorn.conf.py mirrorface.server.main:app
```

Download models locally:

```shell
uv run mirror --repository "username/repository" --local_directory /tmp/mirrorface
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
