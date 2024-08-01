import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models as dbm
from ..db import get_db
from . import models as pyd
from .auth import (
    get_tunnel_basic_auth,
    get_valid_probe_token,
    get_valid_provider_token,
    get_valid_sess_token,
)

LOGGER = logging.getLogger(__name__)

router = APIRouter(
    prefix="/tunnel-auth",
    tags=["tunnel-auth"],
    dependencies=[Depends(get_tunnel_basic_auth)],
)

Session = Annotated[AsyncSession, Depends(get_db)]
ProviderToken = Annotated[dbm.SessionToken, Depends(get_valid_provider_token)]
ProbeToken = Annotated[dbm.SessionToken, Depends(get_valid_probe_token)]


# Here we only need to check whether the provided token is valid.
@router.post("/allowed-provider-registration")
async def allowed_provider_registration(_: ProviderToken) -> bool:
    return True


@router.post("/allowed-sim-registration")
async def allowed_sim_registration(
    stoken: ProviderToken, session: Session, sims: pyd.SimList
) -> bool:
    await session.begin()
    session.add(stoken)
    await session.refresh(stoken)
    await stoken.awaitable_attrs.token

    if stoken.token.admin:
        LOGGER.debug("Token has admin rights. Allowing arbitrary SIM registrations.")
        return True

    for sim in sims.root:
        stmt = (
            select(dbm.Sim)
            .join(dbm.Sim.token_assoc)
            .where(dbm.TokenSimAssociation.token_id == stoken.token.id)
            .where(dbm.TokenSimAssociation.provide)
        )

        if sim.iccid is not None:
            stmt = stmt.where(dbm.Sim.iccid == sim.iccid.root)

        if sim.imsi is not None:
            stmt = stmt.where(dbm.Sim.imsi == sim.imsi.root)

        permission = (await session.scalars(stmt.limit(2))).all()

        if len(permission) != 1:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission for SIM: (ICCID: {sim.iccid}; IMSI: {sim.imsi})",
            )

    return True


@router.post("/allowed-probe-registration")
async def allowed_probe_registration(_: ProbeToken) -> bool:
    return True


@router.post("/allowed-sim-request")
async def allowed_sim_request(
    stoken: ProbeToken, session: Session, request: pyd.SimRequest
) -> bool:
    await session.begin()
    session.add(stoken)
    await session.refresh(stoken)
    await stoken.awaitable_attrs.token

    if stoken.token.admin:
        return True

    # Currently only admins can request SIM cards with no
    # known IMSI or ICCID as our permission system requires
    # an IMSI/ICCID
    if request.sim.iccid is None and request.sim.imsi is None:
        LOGGER.debug("Neither ICCID nor IMSI was set.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    stmt = select(dbm.Sim)

    if request.sim.iccid is not None:
        stmt = stmt.where(dbm.Sim.iccid == request.sim.iccid.root)

    if request.sim.imsi is not None:
        stmt = stmt.where(dbm.Sim.imsi == request.sim.imsi.root)

    sim = await session.scalar(stmt)

    if sim is None:
        LOGGER.debug(
            "Couldn't find SIM card with ICCID {request.sim.iccid}; IMSI {request.sim.imsi}"
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if sim.public:
        return True

    assoc = await session.get(
        dbm.TokenSimAssociation, {"token_id": stoken.token.id, "sim_id": sim.id}
    )

    if assoc is None:
        LOGGER.debug("Found no entry in TokenSimAssociation.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if assoc.request:
        return True

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)


@router.post("/identity")
async def identity(
    stoken: Annotated[dbm.SessionToken, Depends(get_valid_sess_token)]
) -> UUID:
    if stoken.probe_id is not None:
        return stoken.probe_id
    elif stoken.provider_id is not None:
        return stoken.provider_id
    else:
        raise AssertionError("Expected either probe_id or provider_id to be non null.")
