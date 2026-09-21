"""Game tick phase for passive radio recruitment."""

import logging
import random
from types import ModuleType

from pydantic import UUID4
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.services.game_tick.guard import recover_session
from app.services.game_tick.tick_results import RadioStats
from app.services.radio_service import radio_service
from app.utils.exceptions import ResourceNotFoundException, VaultOperationException

logger = logging.getLogger(__name__)


async def process_radio(db_session: AsyncSession, vault_id: UUID4, *, rng: ModuleType = random) -> RadioStats:
    """Roll the radio's passive recruitment for one vault.

    The service owns the gates — recruitment mode and an operating radio room —
    and the rate calculation. This phase only isolates a failure so a bad roll
    cannot abort the rest of the vault's tick.
    """
    stats: RadioStats = {"recruited": 0}

    try:
        dweller = await radio_service.check_for_recruitment(db_session, vault_id, rng=rng)
    except (SQLAlchemyError, ResourceNotFoundException, VaultOperationException) as e:
        await recover_session(db_session)
        logger.error(f"Error processing radio recruitment for vault {vault_id}: {e}", exc_info=True)
        stats["error"] = str(e)
    else:
        if dweller is not None:
            stats["recruited"] = 1
            logger.info(f"Radio recruited {dweller.first_name} {dweller.last_name} into vault {vault_id}")

    return stats
