import asyncio
import contextlib
import logging

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db, resources
from .probe_routes import router as probe_router
from .routes import check_probe_statuses
from .routes import router as idx_router
from .token_routes import router as token_router
from .tunnel_auth.models import AuthError, AuthException
from .tunnel_auth.routes import router as tunnel_auth_router
from .tunnel_auth.tunnel_interface_routes import router as tunnel_server_auth_router
from .wireguard_routes import router as wireguard_router

LOGGER = logging.getLogger(__name__)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    from . import models as dbm

    db.create_sessionmaker()

    # TODO remove
    async with db._ENGINE.begin() as conn:  # type: ignore
        await conn.run_sync(dbm.Base.metadata.create_all)

    session = db.create_session()
    status_task = asyncio.create_task(check_probe_statuses(session))

    with resources.templates(), resources.static() as static_dir:
        LOGGER.info(f"Serving static files from: {static_dir}")
        app.mount("/static", StaticFiles(directory=static_dir))
        yield

    status_task.cancel()
    await session.close()

    await db.dispose_engine()


app = FastAPI(lifespan=lifespan)

app.include_router(token_router)
app.include_router(probe_router)
app.include_router(wireguard_router)

app.include_router(tunnel_server_auth_router)
app.include_router(tunnel_auth_router)

app.include_router(idx_router)


@app.exception_handler(AuthException)
async def tunnel_auth_exception_handler(req: Request, exc: AuthException):
    match exc.error:
        case AuthError.InvalidToken:
            content = "Invalid token."
        case AuthError.ExpiredToken:
            content = "Expired token."
        case _:
            content = "Forbidden"

    return JSONResponse(status_code=403, content=content)


def start_dev(host: str, port: int, root_path: str) -> None:
    LOGGER.info("Starting management server ...")

    uvicorn.run(app, host=host, port=port, root_path=root_path)
