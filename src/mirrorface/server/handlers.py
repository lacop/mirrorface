import logging
from typing import List, Optional, Set, Tuple

import aiohttp
from starlette.responses import PlainTextResponse, Response, StreamingResponse

from mirrorface.common.hub import RepositoryRevisionPath
from mirrorface.server import metrics
from mirrorface.server.settings import settings

REQUEST_HEADERS_TO_FORWARD = set()  # TODO: Add headers to forward
RESPONSE_HEADERS_TO_FORWARD = set()  # TODO: Add headers to forward


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
    await session.close()


async def try_serve_locally(
    repository_revision_path: RepositoryRevisionPath,
) -> Optional[Response]:
    # TODO: not implemented yet
    return None


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
    )

    response_headers = dict(
        filtered_headers(response.headers.items(), RESPONSE_HEADERS_TO_FORWARD)
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
        headers=response_headers,
    )
