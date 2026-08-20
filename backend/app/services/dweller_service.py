"""General dweller business logic service."""

import logging
from typing import Any

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.crud import training as training_crud
from app.crud.dweller import determine_status_for_room
from app.schemas.dweller import DwellerUpdate
from app.services.training_service import training_service

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

        if "room_id" in data:
            dweller = await crud.dweller.get(db_session, dweller_id)
            if room_id != dweller.room_id:
                active_training = await training_crud.training.get_active_by_dweller(db_session, dweller_id)
                if active_training:
                    await training_service.cancel_training(db_session, active_training.id, dweller=dweller)

        # Compute status if room_id is being set or cleared
        if room_id is not None or "room_id" in data:
            if room_id is None:
                data["status"] = determine_status_for_room(None)
            else:
                room_obj = await crud.room.get(db_session, room_id)
                if not room_obj:
                    from app.utils.exceptions import ResourceNotFoundException

                    raise ResourceNotFoundException(model="Room", identifier=room_id)
                data["status"] = determine_status_for_room(room_obj.category, room_obj.name)

        return await crud.dweller.update(db_session, dweller_id, DwellerUpdate(**data))


dweller_service = DwellerService()
