import base64
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .. import models as dbm
from ..auth import bearer_token_probe, get_basic_auth_admin
from ..db import get_db
from ..resources import get_templates
from . import models as pyd
from .auth import (
    delete_session_token,
    generate_session_token,
    generate_tunnel_token,
    get_valid_token,
    is_valid_token,
)

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/tunnel", tags=["tunnel"])

MamToken = Annotated[dbm.MamToken, Depends(bearer_token_probe)]
TunnelToken = Annotated[dbm.MoAtToken, Depends(get_valid_token)]
Session = Annotated[AsyncSession, Depends(get_db)]


@router.post("/probe")
async def register_probe(
    mam_token: MamToken, session: Session, reg: pyd.TunnelRegistration
) -> pyd.TunnelRegResponse:
    async with session.begin():
        token = await is_valid_token(session, reg.token)
        probe: dbm.Probe = await mam_token.awaitable_attrs.probe

        stoken = await generate_session_token(
            session, dbm.MoAtTokenScope.Probe, token, probe_id=probe.id
        )

        return pyd.TunnelRegResponse(session_token=base64.b64encode(stoken.value))


@router.delete("/probe")
async def deregister_probe(session: Session, session_token: pyd.Token) -> None:
    LOGGER.debug(f"Deleting probe session token: {session_token}")

    async with session.begin():
        await delete_session_token(session, session_token.root)


# TODO: currently SIM card providers have no registration
# flow and we just require a token that can be used
# for the SIM tunnel. The provider UUID is thus currently
# randomly generated on each registration.
@router.post("/provider")
async def register_provider(
    token: TunnelToken, session: Session
) -> pyd.TunnelRegResponse:
    async with session.begin():
        provider = dbm.Provider()
        session.add(provider)
        await session.flush()
        stoken = await generate_session_token(
            session, dbm.MoAtTokenScope.Provider, token, provider_id=provider.id
        )

        return pyd.TunnelRegResponse(session_token=base64.b64encode(stoken.value))


@router.delete("/provider")
async def deregister_provider(session: Session, session_token: pyd.Token):
    LOGGER.debug(f"Deleting provider session token: {session_token}")

    async with session.begin():
        await delete_session_token(session, session_token.root)


@router.get("/")
async def tunnel_index(session: Session, request: Request):
    await session.begin()

    tokens = (await session.scalars(select(dbm.MoAtToken))).all()
    sims = (
        await session.scalars(
            select(dbm.Sim).options(selectinload(dbm.Sim.token_assoc))
        )
    ).all()

    ctx = {
        "tokens": tokens,
        "sims": sims,
    }

    return get_templates().TemplateResponse(
        request=request, name="tunnel.html", context=ctx
    )


@router.post("/token")
async def create_token(
    basic_auth: Annotated[str, Depends(get_basic_auth_admin)],
    session: Session,
    req: pyd.TokenCreation,
):
    async with session.begin():
        await generate_tunnel_token(session, req.scope, req.admin)


@router.post("/token/{token_id}/sim")
async def add_sim(
    basic_auth: Annotated[str, Depends(get_basic_auth_admin)],
    session: Session,
    token_id: int,
    req: pyd.AllowSim,
):
    LOGGER.debug(f"Updating access rights of token {token_id}.")
    async with session.begin():
        token = await session.get(dbm.MoAtToken, token_id)

        if token is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Couldn't find token {token_id}",
            )

        sim = dbm.Sim(
            imsi=req.imsi.root if req.imsi else None,
            iccid=req.iccid.root if req.iccid else None,
        )
        session.add(sim)
        try:
            await session.flush()
        except IntegrityError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="imsi or iccid already exists.",
            ) from e

        assoc = dbm.TokenSimAssociation(
            sim_id=sim.id, token_id=token.id, provide=req.provide, request=req.request
        )
        session.add(assoc)


# TODO
async def remove_sim():
    pass
