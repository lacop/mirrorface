import logging
import os
from typing import List, Optional, Set, Tuple

import aiohttp
import multidict
from starlette.responses import (
    FileResponse,
    PlainTextResponse,
    Response,
    StreamingResponse,
)

from mirrorface.common.hub import RepositoryRevisionPath
from mirrorface.common.storage import blob_path, load_full_manifest
from mirrorface.server import metrics
from mirrorface.server.settings import settings

REQUEST_HEADERS_TO_FORWARD = set(
    [
        "user-agent",
        # TODO: Auth headers for private HF Hub repositories.
    ]
)
RESPONSE_HEADERS_TO_FORWARD = set(
    [
        "content-disposition",
        "content-length",
        "content-type",
        "etag",
        "x-repo-commit",
    ]
)


def filtered_headers(headers, headers_to_forward: Set[str]) -> List[Tuple[str, str]]:
    return [
        (name, value) for name, value in headers if name.lower() in headers_to_forward
    ]


async def stream_response(
    repository_revision_path: RepositoryRevisionPath,
    session: aiohttp.ClientSession,
    response: aiohttp.ClientResponse,
):
    total_size = 0
    async for chunk in response.content.iter_chunked(settings.chunk_size):
        yield chunk
        total_size += len(chunk)
    metrics.fallback_total_bytes_inc(repository_revision_path, total_size)
    logging.info(
        f"Upstream response OK for {repository_revision_path}, {total_size} bytes"
    )
    await session.close()


async def try_serve_locally(
    repository_revision_path: RepositoryRevisionPath,
) -> Optional[Response]:
    manifest = load_full_manifest(
        settings.local_directory, repository_revision_path.repository_revision
    )
    if not manifest:
        return None

    blob_hash = manifest.files.get(repository_revision_path.path)
    if not blob_hash:
        # File is not in the repository manifest.
        # This is expected, the client tries various paths without knowing
        # if they are in the repo.
        logging.info(
            f"File {repository_revision_path.path} not in manifest, returning 404"
        )
        return PlainTextResponse("File not found", status_code=404)

    blob_file_path = blob_path(settings.local_directory, blob_hash)
    blob_size = os.path.getsize(blob_file_path)
    logging.info(
        f"Serving {repository_revision_path} from local storage {blob_hash}: {blob_size} bytes"
    )
    metrics.cache_total_bytes_inc(repository_revision_path, blob_size)
    return FileResponse(
        blob_file_path,
        headers={
            # Note: not always the right content type but we have to return
            # something (client expects it), and this seems to work so far.
            "Content-Type": "application/octet-stream",
            # This isn't the request revision (could be eg "main") but the actual
            # resolved commit hash from the manifest.
            "X-Repo-Commit": manifest.revision_hash,
            # Not strictly necessary but otherwise the download progress
            # shows filenames differently than when not using the proxy.
            "Content-Disposition": f'inline; filename="{repository_revision_path.path}";',
        },
    )


async def proxy_request_upstream(
    repository_revision_path: RepositoryRevisionPath,
    upstream_path: str,
    is_head: bool,
    request_headers: List[Tuple[str, str]],
) -> Response:
    session = aiohttp.ClientSession()
    response = await session.request(
        "HEAD" if is_head else "GET",
        upstream_path,
        headers=filtered_headers(request_headers, REQUEST_HEADERS_TO_FORWARD),
        allow_redirects=True,
    )

    # Large model files are stored on CDN and HF Hub will serve a redirect for them,
    # but the CDN response is missing important headers the client expects. Combine
    # all the seen headers (in reverse order, latest value wins).
    combined_response_headers = multidict.CIMultiDict()
    for redirect in response.history[::-1]:
        combined_response_headers.update(redirect.headers)
    combined_response_headers.update(response.headers)

    response_headers = dict(
        filtered_headers(combined_response_headers.items(), RESPONSE_HEADERS_TO_FORWARD)
    )

    if response.status != 200:
        if response.status != 404:
            logging.warning(
                f"Unexpected upstream error: {response.status} for {upstream_path}"
            )
        await session.close()
        metrics.fallback_upstream_error_inc(repository_revision_path, response.status)
        return PlainTextResponse(
            "", status_code=response.status, headers=response_headers
        )

    return StreamingResponse(
        stream_response(repository_revision_path, session, response),
        # status_code=200,
        headers=response_headers,
    )
