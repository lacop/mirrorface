import contextlib
import logging
import urllib.parse

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse

from mirrorface.common.hub import RepositoryRevisionPath
from mirrorface.server import metrics
from mirrorface.server.handlers import proxy_request_upstream, try_serve_locally
from mirrorface.server.settings import settings


@contextlib.asynccontextmanager
async def lifespan(app):
    logging.getLogger().setLevel(logging.INFO)
    # TODO: Structured logs?
    yield


app = Starlette(debug=True, lifespan=lifespan)


@app.route("/mirror/{path:path}")
async def mirror(request):
    path = request.path_params.get("path")
    repository_revision_path = RepositoryRevisionPath.from_url_path(path)

    if repository_revision_path is None:
        logging.warning(f"Invalid request path: {path}")
        return PlainTextResponse("Invalid path", status_code=400)
    if request.method not in ["GET", "HEAD"]:
        logging.warning(f"Unsupported method: {request.method}")
        return PlainTextResponse("Unsupported method", status_code=405)

    metrics.total_requests_inc(repository_revision_path)
    logging.info(f"Request: {request.method} {path} -> {repository_revision_path}")

    # First try to serve locally.
    try:
        response = await try_serve_locally(repository_revision_path)
        if response is not None:
            metrics.cache_hit_inc(repository_revision_path)
            return response
        metrics.cache_miss_inc(repository_revision_path)
        logging.info(f"Cache miss for {repository_revision_path}")
    except Exception:
        logging.error("Error serving locally", exc_info=True)
        # Don't return error to client / raise, continue with the fallback so
        # we have strictly higher availability than just using upstream.

    # TODO: Local-only mode where we return an error?
    # if settings.local_only:
    #   return PlainTextResponse("Local serving only", status_code=404 maybe?)

    upstream_path = urllib.parse.urljoin(settings.upstream_url, path)
    metrics.fallback_requests_inc(repository_revision_path)
    logging.info(f"Fallback to upstream: {upstream_path}")

    return await proxy_request_upstream(
        repository_revision_path,
        upstream_path,
        is_head=request.method == "HEAD",
        request_headers=request.headers.items(),
    )
