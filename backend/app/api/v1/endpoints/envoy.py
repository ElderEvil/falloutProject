"""Envoy Terminal endpoints: signals, hails, filings and the effective knobs."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentActiveUser, DBSession, get_user_vault_or_403
from app.core.game_config import game_config
from app.schemas.envoy import (
    EnvoyConfigRead,
    EnvoyFilingCreate,
    EnvoyFilingRead,
    EnvoyFilingRespond,
    EnvoyHailCreate,
    EnvoySignalRead,
)
from app.services.envoy_service import envoy_service


def require_vault_diplomacy() -> None:
    """Ships dark: 404 rather than 403 so the disabled feature does not advertise its shape."""
    if not game_config.features.vault_diplomacy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


router = APIRouter(
    prefix="/vaults/{vault_id}/envoy",
    tags=["Envoy Terminal"],
    dependencies=[Depends(require_vault_diplomacy)],
)


@router.get("/signals", response_model=list[EnvoySignalRead])
async def list_envoy_signals(
    vault_id: UUID,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> list[EnvoySignalRead]:
    """List every live vault with this vault's relation and radio range."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return await envoy_service.list_signals(db_session, vault_id)


@router.post("/hail", response_model=EnvoyFilingRead, status_code=status.HTTP_201_CREATED)
async def hail_vault(
    vault_id: UUID,
    body: EnvoyHailCreate,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> EnvoyFilingRead:
    """File a hail at one vault in radio range."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return await envoy_service.hail(db_session, vault_id, target_vault_id=body.target_vault_id)


@router.post("/filings", response_model=EnvoyFilingRead, status_code=status.HTTP_201_CREATED)
async def file_filing(
    vault_id: UUID,
    body: EnvoyFilingCreate,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> EnvoyFilingRead:
    """File one offer; only a hail is accepted in this slice."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return await envoy_service.file(
        db_session, vault_id, to_vault_id=body.to_vault_id, kind=body.kind, terms=body.terms
    )


@router.post("/filings/{filing_id}/respond", response_model=EnvoyFilingRead)
async def respond_to_filing(
    vault_id: UUID,
    filing_id: UUID,
    body: EnvoyFilingRespond,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> EnvoyFilingRead:
    """Accept or refuse one filing addressed to this vault."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return await envoy_service.respond(db_session, vault_id, filing_id, accept=body.accept)


@router.get("/log", response_model=list[EnvoyFilingRead])
async def list_filing_log(
    vault_id: UUID,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> list[EnvoyFilingRead]:
    """List this vault's filings in both directions, newest first."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return await envoy_service.log(db_session, vault_id)


@router.get("/config", response_model=EnvoyConfigRead)
async def get_envoy_config(
    vault_id: UUID,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> EnvoyConfigRead:
    """Read the effective diplomacy knobs."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return envoy_service.config()
