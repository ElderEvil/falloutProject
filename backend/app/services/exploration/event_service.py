"""Event application for active explorations."""

import asyncio
import logging
import random
from typing import Any

from sqlalchemy import orm
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.crud import dweller as dweller_crud
from app.models.exploration import Exploration
from app.models.outfit import Outfit
from app.models.weapon import Weapon
from app.schemas.common import RarityEnum
from app.schemas.exploration_event import ExplorationEventType, OutfitSchema, WeaponSchema
from app.services.exploration.event_generator import event_generator
from app.services.stream_manager import sse_manager

logger = logging.getLogger(__name__)


class EventService:
    """Applies generated wasteland events to explorations and dwellers."""

    async def process_event(self, db_session: AsyncSession, exploration: Exploration) -> Exploration:
        """Generate and process an event for an active exploration.

        Args:
            db_session: Database session
            exploration: Active exploration

        Returns:
            Updated exploration
        """
        event = await asyncio.to_thread(event_generator.generate_event, exploration)

        if not event:
            return exploration

        # Resolve a discovery's world-map location before persisting so the event
        # can carry location_id + coordinates for deep-linking and route drawing.
        location_name = getattr(event, "location_name", None)
        location_id = None
        coord_x = None
        coord_y = None
        if location_name:
            try:
                from app.services.map_service import map_service

                location = await map_service.register_discovery(
                    db_session,
                    exploration.vault_id,
                    exploration.id,
                    exploration.dweller_id,
                    location_name,
                )
                if location is not None:
                    location_id = location.id
                    coord_x = location.coord_x
                    coord_y = location.coord_y
            except Exception:
                logger.exception(
                    "Failed to register discovery: vault=%s exploration=%s location=%r",
                    exploration.vault_id,
                    exploration.id,
                    location_name,
                )

        # Convert loot schema to dict for JSON storage
        loot_dict = None
        if hasattr(event, "loot") and event.loot:
            loot_dict = event.loot.model_dump()

        event_record = exploration.add_event(
            event_type=event.type,
            description=event.description,
            loot=loot_dict,
            location_name=location_name,
            location_id=location_id,
            coord_x=coord_x,
            coord_y=coord_y,
            health_loss=getattr(event, "health_loss", None),
            health_restored=getattr(event, "health_restored", None),
        )
        db_session.add(exploration)
        event_records = [event_record]

        # Handle event-specific logic
        if hasattr(event, "loot") and event.loot:
            event_records.extend(await self._handle_loot_event(db_session, exploration, event))

        if hasattr(event, "health_loss") and event.health_loss:
            await self._apply_health_loss(db_session, exploration, event.health_loss)

        if hasattr(event, "health_restored") and event.health_restored:
            await self._apply_health_restoration(db_session, exploration, event.health_restored)

        # Trigger auto-heal check (if health low or radiation high)
        event_records.extend(await self._handle_auto_heal(db_session, exploration))

        # Update distance traveled for all events
        exploration.total_distance += random.randint(1, 3)

        # Track combat encounters
        if event.type == ExplorationEventType.COMBAT:
            exploration.enemies_encountered += 1

        # Commit changes
        db_session.add(exploration)
        await db_session.commit()
        await db_session.refresh(exploration)

        dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)

        sse_extra: dict[str, Any] = {}
        if dweller_obj is not None:
            sse_extra = {"health": dweller_obj.health, "radiation": dweller_obj.radiation}

        for record in event_records:
            await self.publish_sse(
                exploration,
                event_type=record["type"],
                description=record["description"],
                event=record,
                progress=exploration.progress_percentage(),
                stimpaks=exploration.stimpaks,
                radaways=exploration.radaways,
                total_caps_found=exploration.total_caps_found,
                enemies_encountered=exploration.enemies_encountered,
                total_distance=exploration.total_distance,
                **sse_extra,
            )

        return exploration

    async def _handle_loot_event(self, db_session: AsyncSession, exploration: Exploration, event) -> list[dict]:
        """Handle loot found in event; returns follow-up event records (e.g. auto-equip)."""
        loot_data = event.loot
        item = loot_data.item
        item_type = loot_data.item_type
        caps = loot_data.caps

        # Add item to collected loot
        exploration.add_loot(
            item_name=item.name,
            quantity=1,
            rarity=item.rarity,
            item_type=item_type,
        )

        # Update stats
        exploration.total_caps_found += caps
        exploration.total_distance += random.randint(1, 5)

        # Counter only: the find is already logged by the single loot entry above
        if item_type == "stimpak":
            exploration.stimpaks += 1
        elif item_type == "radaway":
            exploration.radaways += 1

        followups: list[dict] = []
        if item_type in {"weapon", "outfit"}:
            record = await self._handle_auto_equip(db_session, exploration, item, item_type)
            if record is not None:
                followups.append(record)
        return followups

    async def _apply_health_loss(self, db_session: AsyncSession, exploration: Exploration, damage: int) -> None:
        """Apply health loss to dweller.

        If damage would be fatal (health <= 0), the dweller dies from exploration.
        """
        dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)

        # Short-circuit if dweller is already dead - don't apply damage to dead dwellers
        if dweller_obj.is_dead:
            return

        new_health = dweller_obj.health - damage

        if new_health <= 0:
            # Dweller dies in the wasteland
            from app.schemas.common import DeathCauseEnum
            from app.services.death_service import death_service

            await death_service.mark_as_dead(db_session, dweller_obj, DeathCauseEnum.EXPLORATION)
        else:
            # Just apply damage (cap at 1 to give player chance to recall)
            dweller_obj.health = max(1, new_health)
            db_session.add(dweller_obj)
            # Flush so _handle_auto_heal sees updated health
            await db_session.flush()

    async def _apply_health_restoration(self, db_session: AsyncSession, exploration: Exploration, healing: int) -> None:
        """Apply health restoration to dweller."""
        dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)
        dweller_obj.health = min(dweller_obj.max_health, dweller_obj.health + healing)
        db_session.add(dweller_obj)

    async def _handle_auto_heal(self, db_session: AsyncSession, exploration: Exploration) -> list[dict]:
        """Automatically use stimpaks/radaways if needed; returns the item_use event records."""
        dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)

        # Early return if dweller is already dead
        if dweller_obj.is_dead:
            return []

        records: list[dict] = []

        # Auto-use RadAway if radiation > 30
        if exploration.radaways > 0 and dweller_obj.radiation > 30:
            # Radiation removal logic (50% of radiation)
            reduction = int(dweller_obj.radiation * 0.5)
            dweller_obj.radiation = max(0, dweller_obj.radiation - reduction)
            exploration.radaways -= 1
            records.append(
                exploration.add_event(
                    event_type=ExplorationEventType.ITEM_USE,
                    description=f"Dweller used a RadAway. Removed {reduction} radiation. {exploration.radaways} left.",
                )
            )
            db_session.add(dweller_obj)
            db_session.add(exploration)

        # Auto-use Stimpak if health < 50%
        health_percentage = (dweller_obj.health / dweller_obj.max_health) * 100
        if exploration.stimpaks > 0 and health_percentage < 50:
            # Heal logic (40% of max health)
            healing = int(dweller_obj.max_health * 0.4)
            dweller_obj.health = min(dweller_obj.max_health, dweller_obj.health + healing)
            exploration.stimpaks -= 1
            records.append(
                exploration.add_event(
                    event_type=ExplorationEventType.ITEM_USE,
                    description=f"Dweller used a Stimpak. Healed {healing} HP. {exploration.stimpaks} left.",
                    health_restored=healing,
                )
            )
            db_session.add(dweller_obj)
            db_session.add(exploration)

        return records

    async def _handle_auto_equip(
        self,
        db_session: AsyncSession,
        exploration: Exploration,
        item_schema: WeaponSchema | OutfitSchema,
        item_type: str,
    ) -> dict | None:
        """Flag the strongest found weapon/outfit for auto-equip; returns the equip event record."""
        flagged = next(
            (
                entry
                for entry in reversed(exploration.loot_collected)
                if entry.get("item_type") == item_type and entry.get("auto_equip")
            ),
            None,
        )

        if item_type == "weapon":
            new_avg = (item_schema.damage_min + item_schema.damage_max) / 2
            if flagged is not None:
                is_better = new_avg > flagged.get("auto_equip_avg_damage", 0)
            else:
                item_result = await db_session.execute(
                    select(Weapon).where(Weapon.dweller_id == exploration.dweller_id)
                )
                current_item = item_result.scalar_one_or_none()
                current_avg = (current_item.damage_min + current_item.damage_max) / 2 if current_item else 0
                is_better = new_avg > current_avg
        else:
            new_priority = self._rarity_priority(item_schema.rarity)
            new_value = item_schema.value or 0
            if flagged is not None:
                is_better = (new_priority, new_value) > (
                    flagged.get("auto_equip_priority", 0),
                    flagged.get("auto_equip_value", 0),
                )
            else:
                item_result = await db_session.execute(
                    select(Outfit).where(Outfit.dweller_id == exploration.dweller_id)
                )
                current_item = item_result.scalar_one_or_none()
                current_priority = self._rarity_priority(current_item.rarity) if current_item else 0
                current_value = (current_item.value or 0) if current_item else 0
                is_better = (new_priority, new_value) > (current_priority, current_value)

        if not is_better:
            return None

        # The new item outclasses the current champion; move the flag to it.
        for entry in exploration.loot_collected:
            if entry.get("item_type") == item_type and entry.get("auto_equip"):
                entry["auto_equip"] = False
        for entry in reversed(exploration.loot_collected):
            if entry.get("item_type") == item_type and entry.get("item_name") == item_schema.name:
                entry["auto_equip"] = True
                if item_type == "weapon":
                    entry["auto_equip_avg_damage"] = new_avg
                else:
                    entry["auto_equip_priority"] = new_priority
                    entry["auto_equip_value"] = new_value
                break
        orm.attributes.flag_modified(exploration, "loot_collected")

        record = exploration.add_event(
            ExplorationEventType.EQUIP,
            f"Found better {item_type}: {item_schema.name}. Will equip on return.",
        )
        db_session.add(exploration)
        return record

    @staticmethod
    def _rarity_priority(rarity: str | RarityEnum) -> int:
        """Map a rarity (string or enum) to its numeric priority; unknown → 0."""
        raw = rarity.value if isinstance(rarity, RarityEnum) else rarity
        return game_config.exploration.get_rarity_priority(raw)

    @staticmethod
    async def publish_sse(
        exploration: Exploration,
        event_type: str,
        **extra: Any,
    ) -> None:
        """Publish an exploration event to SSE. Best-effort."""
        try:
            await sse_manager.publish(
                exploration.vault_id,
                "exploration",
                {
                    "event_id": str(exploration.id),
                    "type": event_type,
                    "vault_id": str(exploration.vault_id),
                    "exploration_id": str(exploration.id),
                    "dweller_id": str(exploration.dweller_id),
                    **extra,
                },
            )
        except Exception:
            logger.exception("Failed to publish SSE for exploration %s", event_type)


# Singleton instance
event_service = EventService()
