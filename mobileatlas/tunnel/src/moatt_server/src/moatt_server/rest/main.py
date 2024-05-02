import contextlib
import logging
from typing import Annotated

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from moatt_types.connect import Token
from sqlalchemy.ext.asyncio import AsyncSession

from .. import auth, db
from . import auth as rest_auth
from . import db as db_utils
from . import models as pydantic_models

LOGGER = logging.getLogger(__name__)


@contextlib.asynccontextmanager
async def lifespan(_: FastAPI):
    db_utils.create_sessionmaker()
    yield
    await db_utils.dispose_engine()


app = FastAPI(lifespan=lifespan)


@app.put("/provider/sims", status_code=204)
async def provider_register(
    sims_req: pydantic_models.SimList,
    session_token: Annotated[Token, Depends(rest_auth.session_token)],
    session: Annotated[AsyncSession, Depends(db_utils.get_db)],
    response: Response,
):
    sims = {s.id: (s.get_iccid(), s.get_imsi()) for s in sims_req.root}

    async with session.begin():
        if await auth.register_provider(session, session_token, sims):
            response.status_code = 201


@app.get("/provider/sims")
async def provider_get_registered_sims(
    session: Annotated[AsyncSession, Depends(db_utils.get_db)],
    session_token: Annotated[Token, Depends(rest_auth.session_token)],
) -> pydantic_models.SimList:
    async with session.begin():
        sims = await db.get_sim_ids(session, session_token)

    return pydantic_models.SimList(
        root=[
            pydantic_models.Sim(
                id=sim[0],
                iccid=(
                    pydantic_models.Iccid(root=sim[1]) if sim[1] is not None else None
                ),
                imsi=pydantic_models.Imsi(root=sim[2]) if sim[2] is not None else None,
            )
            for sim in sims
        ]
    )


@app.exception_handler(auth.AuthError)
def autherror_ex_handler(_: Request, _exc: auth.AuthError) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"detail": "Unauthorized"},
    )


@app.exception_handler(auth.TokenError)
def tokenerror_ex_handler(_: Request, _exc: auth.TokenError) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"detail": "Unauthorized"},
    )
