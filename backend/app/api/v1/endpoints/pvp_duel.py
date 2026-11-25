"""Cross-vault exhibition duel endpoints: board, post, accept and replay."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentActiveUser, DBSession, get_user_vault_or_403
from app.core.game_config import game_config
from app.schemas.pvp_duel import PvpDuelAccept, PvpDuelBoardEntry, PvpDuelCreate, PvpDuelRead
from app.services.pvp_duel_service import pvp_duel_service


def require_pvp_duels() -> None:
    """Ships dark: 404 rather than 403 so the disabled feature does not advertise its shape."""
    if not game_config.features.pvp_duels:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


router = APIRouter(
    prefix="/vaults/{vault_id}/pvp-duels",
    tags=["PvP Duels"],
    dependencies=[Depends(require_pvp_duels)],
)


@router.get("", response_model=list[PvpDuelBoardEntry])
async def list_pvp_duels(
    vault_id: UUID,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> list[PvpDuelBoardEntry]:
    """List open challenges this vault may accept."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return await pvp_duel_service.list_board(db_session, vault_id)


@router.post("", response_model=PvpDuelRead, status_code=status.HTTP_201_CREATED)
async def post_pvp_duel(
    vault_id: UUID,
    body: PvpDuelCreate,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> PvpDuelRead:
    """Post one open exhibition challenge for this vault."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return await pvp_duel_service.post(
        db_session,
        vault_id,
        defender_vault_id=body.defender_vault_id,
        dweller_ids=body.dweller_ids,
    )


@router.post("/{duel_id}/accept", response_model=PvpDuelRead)
async def accept_pvp_duel(
    vault_id: UUID,
    duel_id: UUID,
    body: PvpDuelAccept,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> PvpDuelRead:
    """Accept a challenge, settle it and write the challenger's result notification."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return await pvp_duel_service.accept(db_session, vault_id, duel_id, dweller_ids=body.dweller_ids)


@router.get("/current", response_model=PvpDuelRead | None)
async def get_current_pvp_duel(
    vault_id: UUID,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> PvpDuelRead | None:
    """Return this vault's open challenge, if any."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return await pvp_duel_service.get_open(db_session, vault_id)


@router.get("/{duel_id}", response_model=PvpDuelRead)
async def get_pvp_duel(
    vault_id: UUID,
    duel_id: UUID,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> PvpDuelRead:
    """Read one duel with its frozen parties and journal for replay."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return await pvp_duel_service.get(db_session, vault_id, duel_id)
