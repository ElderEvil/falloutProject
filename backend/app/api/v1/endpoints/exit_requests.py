"""Endpoints for dwellers who ask to leave the vault. Granting is one-way."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_user_vault_or_403
from app.db.session import get_async_session
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.schemas.exit_request import ExitDecisionResponse, ExitRequestListResponse, ExitRequestRead
from app.services.exit_request_service import exit_request_service

router = APIRouter(prefix="/vaults/{vault_id}/exit-requests", tags=["exit-requests"])


def _dweller_name(dweller: Dweller) -> str:
    return f"{dweller.first_name} {dweller.last_name or ''}".strip()


def _to_read(dweller: Dweller) -> ExitRequestRead:
    return ExitRequestRead(
        dweller_id=dweller.id,
        dweller_name=_dweller_name(dweller),
        thumbnail_url=dweller.thumbnail_url,
        level=dweller.level,
        happiness=dweller.happiness,
        requested_at=dweller.exit_requested_at,
    )


@router.get("", response_model=ExitRequestListResponse)
async def list_exit_requests(
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ExitRequestListResponse:
    """List dwellers waiting on an answer to their request to leave."""
    pending = await exit_request_service.list_pending(db_session, vault.id)
    return ExitRequestListResponse(requests=[_to_read(dweller) for dweller in pending])


@router.post("/{dweller_id}/grant", response_model=ExitDecisionResponse)
async def grant_exit(
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    dweller_id: UUID4,
) -> ExitDecisionResponse:
    """Let the dweller go: permanent death by exile, with no way back."""
    dweller = await exit_request_service.grant_exit(db_session, vault, dweller_id)
    return ExitDecisionResponse(
        dweller_id=dweller.id,
        dweller_name=_dweller_name(dweller),
        granted=True,
        happiness=dweller.happiness,
        epitaph=dweller.epitaph,
    )


@router.post("/{dweller_id}/refuse", response_model=ExitDecisionResponse)
async def refuse_exit(
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    dweller_id: UUID4,
) -> ExitDecisionResponse:
    """Refuse the ask: the dweller takes a happiness hit and the request stands."""
    dweller = await exit_request_service.refuse_exit(db_session, vault, dweller_id)
    return ExitDecisionResponse(
        dweller_id=dweller.id,
        dweller_name=_dweller_name(dweller),
        granted=False,
        happiness=dweller.happiness,
    )
