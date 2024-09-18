from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from . import probe_routes
from . import pydantic_models as pyd
from . import wireguard_routes
from .auth import bearer_token_any, get_basic_auth_admin
from .db import get_db
from .models import MamToken, MamTokenAccessLog, TokenAction, TokenScope
from .resources import get_templates

router = APIRouter(prefix="/tokens", tags=["tokens"])


@router.get("/")
async def token_index(
    session: Annotated[AsyncSession, Depends(get_db)], request: Request
):
    await session.begin()

    load_attrs = [MamToken.logs, MamToken.config, MamToken.probe]
    tokens = (
        await session.scalars(
            select(MamToken)
            .options(*map(selectinload, load_attrs))
            .where(MamToken.token != None)
        )
    ).all()
    token_reqs = (
        await session.scalars(
            select(MamToken)
            .options(*map(selectinload, load_attrs))
            .where(MamToken.token == None)
        )
    ).all()

    ctx = {
        "tokens": tokens,
        "token_reqs": token_reqs,
        "TokenAction": TokenAction,
    }
    return get_templates().TemplateResponse(
        request=request, name="tokens.html", context=ctx
    )


@router.post("/register")
async def token_register(
    session: Annotated[AsyncSession, Depends(get_db)],
    reg: pyd.TokenRegistration,
    response: Response,
) -> None:
    async with session.begin():
        new_cand = await add_token_candidate(
            session, reg.token_candidate, reg.scope, reg.mac
        )

        if new_cand is not None:
            await prune_candidates(session)

    if new_cand is not None:
        response.status_code = status.HTTP_201_CREATED


@router.get("/active")
def token_active(_: Annotated[str, Depends(bearer_token_any)]) -> None:
    return


@router.delete("/revoke")
async def revoke(
    token: Annotated[MamToken, Depends(bearer_token_any)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    async with session.begin():
        session.add(token)
        await session.refresh(token)

        if token.token is None:
            raise AssertionError

        await delete_token(session, token.token)


@router.post("/activate")
async def token_activate(
    basic_auth: Annotated[str, Depends(get_basic_auth_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    args: pyd.ActivateToken,
    response: Response,
) -> None:

    await session.begin()

    token = await session.scalar(
        select(MamToken).where(MamToken.token_candidate == args.root.token_candidate)
    )

    if token is None:
        token = await add_token_candidate(
            session, args.root.token_candidate, args.root.scope
        )
        response.status_code = status.HTTP_201_CREATED

        if token is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Token already exists."
            )

    if token.scope != args.root.scope:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='"scope" does not match the requested scope.',
        )

    token.activate(session)

    if isinstance(args.root, pyd.ActivateWgToken | pyd.ActivateTokenAll):
        await wireguard_routes.after_token_activation(session, token, args.root.ip)  # type: ignore

    if isinstance(args.root, pyd.ActivateProbeToken | pyd.ActivateTokenAll):
        await probe_routes.after_token_activation(session, token, args.root.name)

    try:
        await session.commit()
    except Exception as e:
        await session.rollback()
        await session.begin()

        if not response.status_code == status.HTTP_201_CREATED:
            session.add(token)
            await session.refresh(token)

        if isinstance(args.root, pyd.ActivateWgToken | pyd.ActivateTokenAll):
            await wireguard_routes.handle_activation_error(session, e, token, args.root.ip)  # type: ignore

        if isinstance(args.root, pyd.ActivateProbeToken | pyd.ActivateTokenAll):
            await probe_routes.handle_activation_error(
                session, e, token, args.root.name
            )

        raise


@router.post("/deactivate")
async def token_deactivate(
    basic_auth: Annotated[str, Depends(get_basic_auth_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    token: pyd.Token,
) -> None:
    async with session.begin():
        await delete_token(session, token.token)


async def get_token_by_value(session: AsyncSession, value: str) -> None | MamToken:
    return await session.scalar(
        select(MamToken).where(
            (MamToken.token == value) | (MamToken.token_candidate == value)
        )
    )


async def delete_token(session: AsyncSession, token: str) -> None:
    # we have to use Session.delete here
    # because using Session.execute with
    # sql.expression.delete does not
    # trigger configured cascades
    tokens = await session.scalars(
        select(MamToken).where(
            (MamToken.token == token) | (MamToken.token_candidate == token)
        )
    )

    for t in tokens:
        if TokenScope.Wireguard in t.scope:
            await wireguard_routes.before_token_deletion(session, t)
        if TokenScope.Probe in t.scope:
            await probe_routes.before_token_deletion(session, t)

        session.add(
            MamTokenAccessLog(
                token_value=t.token_value(),
                scope=t.scope,
                action=TokenAction.Deactivated,
                time=datetime.now(tz=timezone.utc),
            )
        )
        await session.delete(t)


async def prune_candidates(session: AsyncSession) -> None:
    subq = (
        select(MamToken.id)
        .join(MamToken.logs)
        .order_by(MamTokenAccessLog.time.desc())
        .offset(10)
    )
    stmt = delete(MamToken).where((MamToken.token == None) & MamToken.id.in_(subq))
    await session.execute(stmt)


async def add_token_candidate(
    session: AsyncSession, token_candidate: str, scope: TokenScope, mac=None
) -> MamToken | None:
    t = MamToken(token_candidate=token_candidate, scope=scope, mac=mac)
    l = MamTokenAccessLog(
        token=t, token_value=token_candidate, scope=scope, action=TokenAction.Registered
    )
    session.add(t)
    session.add(l)

    try:
        await session.flush()
    except IntegrityError:
        return None

    return t
