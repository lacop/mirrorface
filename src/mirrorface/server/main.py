import contextlib
import logging

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse


@contextlib.asynccontextmanager
async def lifespan(app):
    logging.getLogger().setLevel(logging.INFO)
    # TODO: Structured logs?
    yield


app = Starlette(debug=True, lifespan=lifespan)


@app.route("/mirror/{path:path}")
async def mirror(request):
    path = request.path_params.get("path")
    logging.info(f"Request: {path}")
    return PlainTextResponse("foo")
