import contextlib
import logging
from typing import Annotated

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from moatt_types.connect import Iccid, Imsi, SessionToken, Token
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import auth, db
from .. import models as dbm
from ..auth import Sim
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


# TODO: endpoint to request new session token to replace expiring s. token
@app.post("/register", status_code=201)
async def register(
    token: Annotated[Token, Depends(rest_auth.token)],
    session: Annotated[AsyncSession, Depends(db_utils.get_db)],
    response: Response,
) -> pydantic_models.RegistrationResp:
    async with session.begin():
        session_token = await auth.insert_new_session_token(session, token.as_base64())

    response.set_cookie(
        key="session_token",
        value=session_token.as_base64(),
        secure=True,
        httponly=True,
        samesite="strict",
    )

    return pydantic_models.RegistrationResp(session_token=session_token.as_base64())


@app.delete("/deregister", status_code=204)
async def deregister(
    session_token: Annotated[SessionToken, Depends(rest_auth.session_token)],
    session: Annotated[AsyncSession, Depends(db_utils.get_db)],
):
    async with session.begin():
        await auth.deregister_session(session, session_token)


@app.put("/provider/sims", status_code=204)
async def provider_register(
    sims_req: pydantic_models.SimList,
    session_token: Annotated[SessionToken, Depends(rest_auth.session_token)],
    session: Annotated[AsyncSession, Depends(db_utils.get_db)],
    response: Response,
):
    sims = {
        Iccid(s.iccid.root): Sim(
            Iccid(s.iccid.root), Imsi(s.imsi.root) if s.imsi else None
        )
        for s in sims_req.root
    }

    async with session.begin():
        if await auth.register_provider(session, session_token, sims):
            response.status_code = 201


@app.get("/provider/sims")
async def provider_get_registered_sims(
    session: Annotated[AsyncSession, Depends(db_utils.get_db)],
    session_token: Annotated[SessionToken, Depends(rest_auth.session_token)],
) -> pydantic_models.SimList:
    async with session.begin():
        sims = await db.get_sim_ids(session, session_token)

    return pydantic_models.SimList(
        root=[
            pydantic_models.Sim(
                iccid=pydantic_models.Iccid(root=sim[0]),
                imsi=pydantic_models.Imsi(root=sim[1]) if sim[1] else None,
            )
            for sim in sims
        ]
    )


@app.get("/sims/available")
async def available_sims(
    session: Annotated[AsyncSession, Depends(db_utils.get_db)],
    sims: pydantic_models.SimIds,
) -> bool:
    iccids = set(sims.root)

    async with session.begin():
        return (
            await session.scalar(
                select(dbm.Sim).where(
                    dbm.Sim.iccid.in_(iccids)
                    & (~dbm.Sim.in_use)
                    & dbm.Sim.provider.any(dbm.Provider.available > 0)
                )
            )
            is not None
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
