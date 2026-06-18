"""General dweller business logic service."""

import logging
from typing import Any

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.crud.dweller import determine_status_for_room
from app.schemas.dweller import DwellerUpdate

logger = logging.getLogger(__name__)


class DwellerService:
    """Service for general dweller operations that span multiple CRUD modules."""

    async def update_dweller(
        self,
        db_session: AsyncSession,
        dweller_id: UUID4,
        dweller_data: DwellerUpdate | dict[str, Any],
    ) -> Any:
        """Update a dweller, computing room-based status automatically.

        When room_id is being changed, determines the correct dweller status
        (idle/working/training) based on the target room's category.
        """
        # Ensure we work with a dict for mutation
        data = dweller_data if isinstance(dweller_data, dict) else dweller_data.model_dump(exclude_unset=True)
        room_id = data.get("room_id")

        # Compute status if room_id is being set or cleared
        if room_id is not None or "room_id" in data:
            if room_id is None:
                data["status"] = determine_status_for_room(None)
            else:
                room_obj = await crud.room.get(db_session, room_id)
                if not room_obj:
                    from app.utils.exceptions import ResourceNotFoundException

                    raise ResourceNotFoundException(model="Room", identifier=room_id)
                data["status"] = determine_status_for_room(room_obj.category)

        return await crud.dweller.update(db_session, dweller_id, DwellerUpdate(**data))


dweller_service = DwellerService()
