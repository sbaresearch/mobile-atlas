import contextlib
import logging
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from moatt_types.connect import Iccid, Imsi, SessionToken, Token
from sqlalchemy.ext.asyncio import AsyncSession

from .. import auth
from ..auth import Sim
from . import auth as rest_auth
from . import db
from . import models as pydantic_models

LOGGER = logging.getLogger(__name__)


@contextlib.asynccontextmanager
async def lifespan(_: FastAPI):
    db.create_sessionmaker()
    yield
    await db.dispose_engine()


app = FastAPI(lifespan=lifespan)


# TODO: endpoint to request new session token to replace expiring s. token
@app.post("/register")
async def register(
    token: Annotated[Token, Depends(rest_auth.token)],
    session: Annotated[AsyncSession, Depends(db.get_db)],
    response: Response,
) -> pydantic_models.RegistrationResp:
    async with session.begin():
        session_token = await auth.insert_new_session_token(session, token.as_base64())

    response.set_cookie(key="session_token", value=session_token.as_base64())

    return pydantic_models.RegistrationResp(session_token=session_token.as_base64())


@app.route("/deregister", methods=["DELETE"])
async def deregister(
    session_token: Annotated[SessionToken, Depends(rest_auth.session_token)],
    session: Annotated[AsyncSession, db.get_db],
):
    async with session.begin():
        await auth.deregister_session(session, session_token)


# TODO: return already registered sims on error / test HTTP status
@app.put("/provider/sims")
async def provider_register(
    sims_req: pydantic_models.SimList,
    session_token: Annotated[SessionToken, Depends(rest_auth.session_token)],
):
    sims = {Iccid(s.iccid): Sim(Iccid(s.iccid), Imsi(s.imsi)) for s in sims_req.root}

    await auth.register_provider(db.session, session_token, sims)


@app.exception_handler(auth.AuthError)
def autherror_ex_handler(_: Request, _exc: auth.AuthError):
    raise HTTPException(
        status_code=403
    )  # TODO: test whether raising an exception is ok


@app.exception_handler(auth.TokenError)
def tokenerror_ex_handler(_: Request, _exc: auth.TokenError):
    raise HTTPException(
        status_code=403
    )  # TODO: test whether raising an exception is ok / add additinoal information
