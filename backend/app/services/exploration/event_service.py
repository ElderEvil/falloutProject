"""Event application for active explorations."""

import asyncio
import logging
import random
from typing import Any

from sqlalchemy import orm
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import RarityEnum
from app.core.game_config import game_config
from app.crud import dweller as dweller_crud
from app.crud import vault as crud_vault
from app.models.dweller import Dweller
from app.models.exploration import Exploration
from app.models.outfit import Outfit
from app.models.weapon import Weapon
from app.schemas.exploration_event import (
    CombatEventSchema,
    DangerEventSchema,
    ExplorationEventType,
    LootEventSchema,
    OutfitSchema,
    RestEventSchema,
    WeaponSchema,
)
from app.services.exploration import data_loader
from app.services.exploration.event_generator import event_generator
from app.services.notification_service import notification_service
from app.services.radiation_service import apply_radiation_gain, radiation_removal_amount
from app.services.stream_manager import sse_manager
from app.utils.combat import expedition_combat_profile
from app.utils.item_factory import build_catalog_item

logger = logging.getLogger(__name__)

# Equip bell entries are parked during the event transaction and sent after its
# commit: sending mid-event would commit the loot/equip work prematurely.
_PENDING_EQUIP_NOTIFICATIONS = "pending_exploration_equip_notifications"


async def apply_exploration_damage(db_session: AsyncSession, exploration: Exploration, damage: int) -> None:
    """Apply damage to the explorer, marking death when health hits zero.

    Shared by timed events and expedition sites so both kill exactly the same way.
    """

    async def _get_living_dweller() -> Dweller | None:
        dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)
        return None if dweller_obj.is_dead else dweller_obj

    if (dweller_obj := await _get_living_dweller()) is None:
        return

    new_health = dweller_obj.health - damage

    if new_health <= 0:
        # Dweller dies in the wasteland. Delete held mid-run upgrades BEFORE
        # mark_as_dead so the death and the cleanup land in the caller's
        # transaction; the equipped upgrade stays on the corpse. The death
        # notification is parked and delivered after the caller commits.
        from app.core.enums import DeathCauseEnum
        from app.crud import outfit as outfit_crud
        from app.crud import weapon as weapon_crud
        from app.services.family.death_service import death_service

        await weapon_crud.delete_held_for_exploration(db_session, exploration.id)
        await outfit_crud.delete_held_for_exploration(db_session, exploration.id)
        await death_service.mark_as_dead(db_session, dweller_obj, DeathCauseEnum.EXPLORATION, commit=False)
    else:
        # Just apply damage (cap at 1 to give player chance to recall)
        dweller_obj.health = max(1, new_health)
        db_session.add(dweller_obj)
        # Flush so follow-up healing sees updated health
        await db_session.flush()


def apply_loot_find(
    exploration: Exploration,
    *,
    item_name: str,
    rarity: str,
    item_type: str,
    caps: int,
) -> None:
    """Record one loot find: stash the item, add caps, count medical supplies."""
    exploration.add_loot(
        item_name=item_name,
        quantity=1,
        rarity=rarity,
        item_type=item_type,
    )

    # Update stats
    exploration.total_caps_found += caps

    # Counter only: the find is already logged by the single loot entry above
    if item_type == "stimpak":
        exploration.stimpaks += 1
    elif item_type == "radaway":
        exploration.radaways += 1


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
        db_session.info.pop(_PENDING_EQUIP_NOTIFICATIONS, None)
        # Drop death notifications parked by a failed earlier operation on this
        # session; the current operation's are delivered after its commit.
        db_session.info.pop("deferred_notification_deliveries", None)
        dweller_with_equipment = await dweller_crud.get_with_equipment(db_session, exploration.dweller_id)
        profile = None
        if dweller_with_equipment is not None and not dweller_with_equipment.is_dead:
            profile = expedition_combat_profile(dweller_with_equipment)
        event = await asyncio.to_thread(event_generator.generate_event, exploration, profile)

        if not event:
            return exploration

        # Resolve a discovery's world-map location before persisting so the event
        # can carry location_id + coordinates for deep-linking and route drawing.
        location_name = getattr(event, "location_name", None)
        location = None
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
            except Exception:
                logger.exception(
                    "Failed to register discovery: vault=%s exploration=%s location=%r",
                    exploration.vault_id,
                    exploration.id,
                    location_name,
                )
        location_id = location.id if location else None
        coord_x = location.coord_x if location else None
        coord_y = location.coord_y if location else None

        # Convert loot schema to dict for JSON storage
        loot_dict = None
        loot_event = event if isinstance(event, LootEventSchema) else None
        if loot_event is not None and loot_event.loot:
            loot_dict = loot_event.loot.model_dump()

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
            radiation_gain=getattr(event, "radiation_gain", None),
        )
        db_session.add(exploration)
        event_records = [event_record]

        # Handle event-specific logic
        if loot_event is not None and loot_event.loot:
            event_records.extend(await self._handle_loot_event(db_session, exploration, event))

        if isinstance(event, (CombatEventSchema, DangerEventSchema)) and event.health_loss:
            await self._apply_health_loss(db_session, exploration, event.health_loss)

        if isinstance(event, DangerEventSchema) and event.radiation_gain:
            await self._apply_radiation_gain(db_session, exploration, event.radiation_gain)

        if isinstance(event, RestEventSchema) and event.health_restored:
            actual_healing = await self._apply_health_restoration(db_session, exploration, event.health_restored)
            if actual_healing != event.health_restored:
                # Radiation reduced the heal: the journey log must record what the
                # dweller actually received, not the requested amount.
                event_record["health_restored"] = actual_healing
                event_record["description"] = event_record["description"].replace(
                    str(event.health_restored), str(actual_healing), 1
                )
                orm.attributes.flag_modified(exploration, "events")

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

        # Death notifications parked by mark_as_dead(commit=False) ride the
        # caller's commit; deliver them now that the death is durable.
        await notification_service.deliver_deferred_notifications(db_session)

        dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)

        if location_name and location is not None and dweller_obj is not None:
            try:
                from app.services.bio_service import bio_service

                await bio_service.record_visit(db_session, exploration.dweller_id, location_name)
            except Exception:
                logger.exception(
                    "Failed to record bio visit: dweller=%s location=%r",
                    exploration.dweller_id,
                    location_name,
                )

        sse_extra: dict[str, Any] = {}
        if dweller_obj is not None:
            sse_extra = {"health": dweller_obj.health, "radiation": dweller_obj.radiation}

        progress_payload = {
            "progress": exploration.progress_percentage(),
            "stimpaks": exploration.stimpaks,
            "radaways": exploration.radaways,
            "total_caps_found": exploration.total_caps_found,
            "enemies_encountered": exploration.enemies_encountered,
            "total_distance": exploration.total_distance,
        }

        for record in event_records:
            await self.publish_sse(
                exploration,
                event_type=record["type"],
                description=record["description"],
                event=record,
                **progress_payload,
                **sse_extra,
            )

        await self._notify_equips(db_session, exploration)

        return exploration

    async def _handle_loot_event(self, db_session: AsyncSession, exploration: Exploration, event) -> list[dict]:
        """Handle loot found in event; returns follow-up event records (e.g. auto-equip)."""
        loot_data = event.loot
        item = loot_data.item
        item_type = loot_data.item_type
        caps = loot_data.caps

        # Add item to collected loot
        apply_loot_find(
            exploration,
            item_name=item.name,
            rarity=item.rarity,
            item_type=item_type,
            caps=caps,
        )
        exploration.total_distance += random.randint(1, 5)

        followups: list[dict] = []
        if item_type in {"weapon", "outfit"}:
            record = await self._handle_auto_equip(db_session, exploration, item, item_type)
            if record is not None:
                followups.append(record)
        return followups

    async def _get_living_dweller(self, db_session: AsyncSession, exploration: Exploration) -> Dweller | None:
        """Fetch the explorer, or None when already dead (damage/healing are no-ops)."""
        dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)
        return None if dweller_obj.is_dead else dweller_obj

    async def _apply_health_loss(self, db_session: AsyncSession, exploration: Exploration, damage: int) -> None:
        """Apply health loss to dweller.

        If damage would be fatal (health <= 0), the dweller dies from exploration.
        """
        await apply_exploration_damage(db_session, exploration, damage)

    async def _apply_radiation_gain(self, db_session: AsyncSession, exploration: Exploration, rads: int) -> None:
        """Apply radiation gain to dweller."""
        if (dweller_obj := await self._get_living_dweller(db_session, exploration)) is None:
            return

        apply_radiation_gain(dweller_obj, rads)
        db_session.add(dweller_obj)
        await db_session.flush()

    async def _apply_health_restoration(self, db_session: AsyncSession, exploration: Exploration, healing: int) -> int:
        """Apply health restoration to dweller; return the HP actually restored."""
        dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)
        old_health = dweller_obj.health
        dweller_obj.health = min(dweller_obj.effective_max_health, old_health + healing)
        db_session.add(dweller_obj)
        return dweller_obj.health - old_health

    async def _handle_auto_heal(self, db_session: AsyncSession, exploration: Exploration) -> list[dict]:
        """Automatically use stimpaks/radaways if needed; returns the item_use event records."""
        if (dweller_obj := await self._get_living_dweller(db_session, exploration)) is None:
            return []

        records: list[dict] = []

        radaway_threshold = game_config.health.radaway_auto_use_threshold
        if exploration.radaways > 0 and dweller_obj.radiation > radaway_threshold:
            reduction = radiation_removal_amount(dweller_obj.radiation, dweller_obj.max_health)
            dweller_obj.radiation -= reduction
            exploration.radaways -= 1
            records.append(
                exploration.add_event(
                    event_type=ExplorationEventType.ITEM_USE,
                    description=f"Dweller used a RadAway. Removed {reduction} radiation. {exploration.radaways} left.",
                    radiation_removed=reduction,
                )
            )
            db_session.add(dweller_obj)
            db_session.add(exploration)

        # Auto-use Stimpak if health < 50%
        health_percentage = (dweller_obj.health / dweller_obj.effective_max_health) * 100
        if exploration.stimpaks > 0 and health_percentage < 50:
            healing = max(1, int(dweller_obj.max_health * game_config.health.stimpack_heal_percent))
            actual_healing = min(dweller_obj.effective_max_health, dweller_obj.health + healing) - dweller_obj.health
            dweller_obj.health += actual_healing
            exploration.stimpaks -= 1
            records.append(
                exploration.add_event(
                    event_type=ExplorationEventType.ITEM_USE,
                    description=f"Dweller used a Stimpak. Healed {actual_healing} HP. {exploration.stimpaks} left.",
                    health_restored=actual_healing,
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
        """Equip a found weapon/outfit immediately when it beats the equipped one.

        The displaced item is held on the exploration (not sent to storage) and the
        loot entry is marked equipped so settlement skips it. Returns the equip event
        record, or None when the find is not an upgrade or the explorer is dead.
        """
        if await self._get_living_dweller(db_session, exploration) is None:
            return None

        from app.crud import outfit as outfit_crud
        from app.crud import weapon as weapon_crud

        item_crud = weapon_crud if item_type == "weapon" else outfit_crud
        current = await item_crud.get_equipped(db_session, exploration.dweller_id)
        current_score = self._item_score(current)

        match item_type:
            case "weapon" if isinstance(item_schema, WeaponSchema):
                new_score = ((item_schema.damage_min + item_schema.damage_max) / 2,)
            case _:
                new_score = (self._rarity_priority(item_schema.rarity), item_schema.value or 0)

        if new_score <= current_score:
            return None

        weapons_data = await asyncio.to_thread(data_loader.load_weapons)
        outfits_data = await asyncio.to_thread(data_loader.load_outfits)
        new_item = build_catalog_item(
            item_type,
            item_schema.name,
            item_schema.rarity,
            weapons_data=weapons_data,
            outfits_data=outfits_data,
        )
        if new_item is None:
            return None

        db_session.add(new_item)
        await db_session.flush()

        await item_crud.equip(
            db_session=db_session,
            item_id=new_item.id,
            dweller_id=exploration.dweller_id,
            held_exploration_id=exploration.id,
            commit=False,
        )

        for entry in reversed(exploration.loot_collected):
            if entry.get("item_type") == item_type and entry.get("item_name") == item_schema.name:
                entry["equipped"] = True
                entry["equipped_item_id"] = str(new_item.id)
                break
        orm.attributes.flag_modified(exploration, "loot_collected")
        db_session.info.setdefault(_PENDING_EQUIP_NOTIFICATIONS, []).append((item_type, item_schema.name))

        record = exploration.add_event(
            ExplorationEventType.EQUIP,
            f"Equipped a better {item_type}: {item_schema.name}.",
        )
        db_session.add(exploration)
        return record

    async def _notify_equips(self, db_session: AsyncSession, exploration: Exploration) -> None:
        """Best-effort bell entries for gear equipped mid-run (progression visibility)."""
        equipped = db_session.info.pop(_PENDING_EQUIP_NOTIFICATIONS, [])
        if not equipped:
            return
        try:
            vault = await crud_vault.get(db_session, exploration.vault_id)
            dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)
            if not vault or not vault.user_id or dweller_obj is None:
                return
            dweller_name = f"{dweller_obj.first_name} {dweller_obj.last_name or ''}".strip()
            for item_type, item_name in equipped:
                await notification_service.notify_exploration_update(
                    db_session,
                    user_id=vault.user_id,
                    vault_id=vault.id,
                    dweller_id=exploration.dweller_id,
                    dweller_name=dweller_name,
                    event_description=f"equipped a better {item_type} found in the wasteland: {item_name}",
                    meta_data={
                        "dweller_id": str(exploration.dweller_id),
                        "item_name": item_name,
                        "item_type": item_type,
                    },
                )
        except Exception:
            logger.exception("Failed to send equip notifications: exploration=%s", exploration.id)

    def _item_score(self, item: Weapon | Outfit | None) -> tuple:
        """Comparable strength score so weapon and outfit candidates rank uniformly."""
        match item:
            case Weapon():
                return ((item.damage_min + item.damage_max) / 2,)
            case Outfit():
                return (self._rarity_priority(item.rarity), item.value or 0)
            case _:
                return ()

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
