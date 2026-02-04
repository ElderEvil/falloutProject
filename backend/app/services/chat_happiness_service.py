"""Service for applying immediate happiness changes from chat interactions."""

import logging

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud import dweller as dweller_crud
from app.crud.vault import vault as vault_crud
from app.utils.exceptions import ResourceNotFoundException

logger = logging.getLogger(__name__)

# Happiness bounds
DWELLER_HAPPINESS_MIN = 10
DWELLER_HAPPINESS_MAX = 100
VAULT_HAPPINESS_MIN = 0
VAULT_HAPPINESS_MAX = 100


async def apply_chat_happiness(
    db_session: AsyncSession,
    dweller_id: UUID4,
    delta: int,
) -> tuple[int, int]:
    """
    Apply an immediate happiness delta from a chat interaction.

    Loads the dweller and vault, applies the delta (clamped 10..100),
    and recomputes vault happiness as the average of all dwellers.
    Commits all changes in a single transaction.

    Args:
        db_session: Database session
        dweller_id: Dweller ID to update
        delta: Happiness change to apply (-10 to +10 typically)

    Returns:
        Tuple of (new_dweller_happiness, new_vault_happiness)

    Raises:
        ResourceNotFoundException: If dweller or vault not found
    """
    # Load dweller (includes vault relationship via eager loading)
    try:
        dweller = await dweller_crud.get(db_session, dweller_id)
    except ResourceNotFoundException:
        logger.warning("Chat happiness: Dweller %s not found", dweller_id)
        raise

    # Load vault
    try:
        vault = await vault_crud.get(db_session, dweller.vault_id)
    except ResourceNotFoundException:
        logger.warning("Chat happiness: Vault %s not found for dweller %s", dweller.vault_id, dweller_id)
        raise

    # Apply delta with clamping (10..100 for dwellers)
    old_happiness = dweller.happiness
    new_happiness = max(DWELLER_HAPPINESS_MIN, min(DWELLER_HAPPINESS_MAX, old_happiness + delta))
    dweller.happiness = new_happiness

    # Get all dwellers in vault to recalculate average
    dwellers = await dweller_crud.get_multi_by_vault(db_session, vault.id)

    # Calculate vault happiness as truncated average
    if dwellers:
        total_happiness = sum(d.happiness for d in dwellers)
        vault_happiness = int(total_happiness / len(dwellers))
    else:
        # Fallback: no dwellers means neutral (this shouldn't happen if we just found one)
        vault_happiness = 50

    # Clamp vault happiness (0..100)
    vault_happiness = max(VAULT_HAPPINESS_MIN, min(VAULT_HAPPINESS_MAX, vault_happiness))
    vault.happiness = vault_happiness

    # Commit all changes in one transaction
    await db_session.commit()

    logger.info(
        "Chat happiness applied: dweller %s: %d -> %d (delta=%+d), vault %s: %d",
        dweller_id,
        old_happiness,
        new_happiness,
        delta,
        vault.id,
        vault_happiness,
    )

    return new_happiness, vault_happiness


def compute_neutral_delta() -> int:
    """
    Return a neutral delta when happiness change cannot be computed.

    Used as fallback when AI analysis fails or returns invalid data.
    """
    return 0
