from typing import Optional

from starlette.responses import Response

from mirrorface.common.hub import RepositoryRevisionPath


async def try_serve_locally(
    repository_revision_path: RepositoryRevisionPath,
) -> Optional[Response]:
    # TODO: not implemented yet
    return None
