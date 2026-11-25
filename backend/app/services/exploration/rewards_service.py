"""Rewards application for completed explorations."""

import logging
import math
from typing import Any, TypedDict
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import ExplorationPurpose
from app.core.event_bus import GameEvent, event_bus
from app.crud import dweller as dweller_crud
from app.crud import exploration as crud_exploration
from app.crud import outfit as crud_outfit
from app.crud import room as room_crud
from app.crud import storage as crud_storage
from app.crud import vault as crud_vault
from app.crud import weapon as crud_weapon
from app.crud.team import team_crud
from app.models.exploration import Exploration
from app.models.outfit import Outfit
from app.models.weapon import Weapon
from app.options.pet_modifiers import MAX_PCT_BONUS, pet_modifiers_for
from app.schemas.exploration import PendingOverflowRead
from app.schemas.exploration_event import RewardsSchema
from app.services.collectible_service import collectible_service
from app.services.exploration.locking import lock_exploration_with_vault_claim
from app.services.exploration.rewards_calculator import rewards_calculator
from app.services.loot_overflow_service import loot_overflow_service
from app.services.resource_manager_service import compute_medical_capacity
from app.services.vault_service import vault_service
from app.utils.collectibles import EXPEDITION_LOOT_PCT
from app.utils.exceptions import ValidationException
from app.utils.objective_constants import WASTELAND_LOOT_SOURCE

logger = logging.getLogger(__name__)

_PENDING_REWARD_EVENTS = "pending_exploration_reward_events"


class TransferResult(TypedDict):
    """Result of transferring loot to vault storage."""

    transferred: list[dict]
    overflow: list[dict]
    storage_id: UUID | None


class RewardsService:
    """Applies exploration rewards to vault and dweller."""

    @staticmethod
    def _queue_event(db_session: AsyncSession, event: GameEvent, vault_id: UUID, payload: dict[str, Any]) -> None:
        """Park a reward event until the finalization transaction commits."""
        db_session.info.setdefault(_PENDING_REWARD_EVENTS, []).append((event, vault_id, payload))

    async def deliver_pending_reward_events(self, db_session: AsyncSession) -> None:
        """Emit reward events parked while a deferred finalization was in flight."""
        for event, vault_id, payload in db_session.info.pop(_PENDING_REWARD_EVENTS, []):
            await event_bus.emit(event, vault_id, payload)

    def discard_pending_rewards(self, db_session: AsyncSession) -> None:
        """Drop parked reward events for a rolled-back finalization."""
        db_session.info.pop(_PENDING_REWARD_EVENTS, None)

    @staticmethod
    def _held_spec(row: Weapon | Outfit, item_type: str) -> dict:
        return {
            "item_name": row.name,
            "item_type": item_type,
            "rarity": row.rarity.value,
            "quantity": 1,
            "held_row_id": row.id,
            "held_model": item_type,
        }

    @staticmethod
    def _plain_spec(candidate: dict) -> dict:
        return {key: value for key, value in candidate.items() if key not in ("held_row_id", "held_model")}

    async def _transfer_loot_to_storage(self, db_session: AsyncSession, exploration: Exploration) -> TransferResult:
        """Transfer loot and expedition-held equipment to vault storage with space validation.

        Held rows and ordinary loot share ONE rarity-first capacity budget (one slot per unit), split once by
        grant_or_hold; entries already equipped mid-run are skipped.
        """
        held_weapon_rows = await crud_weapon.get_held_for_exploration(db_session, exploration.id)
        held_outfit_rows = await crud_outfit.get_held_for_exploration(db_session, exploration.id)
        loot_entries = [entry for entry in exploration.loot_collected if not entry.get("equipped")]

        if not loot_entries and not held_weapon_rows and not held_outfit_rows:
            exploration.unclaimed_loot = []
            return {"transferred": [], "overflow": [], "storage_id": None}

        candidates = list(loot_entries)
        candidates.extend(self._held_spec(row, "weapon") for row in held_weapon_rows)
        candidates.extend(self._held_spec(row, "outfit") for row in held_outfit_rows)
        held_rows: dict[UUID, Weapon | Outfit] = {row.id: row for row in (*held_weapon_rows, *held_outfit_rows)}

        vault = await crud_vault.get(db_session, exploration.vault_id)
        storage = await crud_storage.get_storage_by_vault(db_session, vault.id)
        if not storage:
            logger.error("Storage not found for vault", extra={"vault_id": str(vault.id)})
            overflow = [self._plain_spec(candidate) for candidate in candidates]
            for candidate in candidates:
                if "held_row_id" in candidate:
                    await db_session.delete(held_rows[candidate["held_row_id"]])
            exploration.unclaimed_loot = overflow
            return {"transferred": [], "overflow": overflow, "storage_id": None}
        storage_id = storage.id

        # Check available space once; held rows have storage_id IS NULL, so they are not counted and the merged list
        # shares this single budget.
        available_space = await crud_storage.get_available_space(db_session, storage_id)

        logger.info(
            "Storage transfer starting",
            extra={
                "vault_id": str(vault.id),
                "exploration_id": str(exploration.id),
                "available_space": available_space,
                "items_to_transfer": len(candidates),
            },
        )

        granted, overflow = loot_overflow_service.grant_or_hold(candidates, available_space)

        transferred: list[dict] = []
        materialization_failures: list[dict] = []
        junk_collected: dict[str, int] = {}

        for loot_item in granted:
            if "held_row_id" in loot_item:
                row = held_rows[loot_item["held_row_id"]]
                row.storage_id = storage_id
                row.exploration_id = None
                db_session.add(row)
                transferred.append(self._plain_spec(loot_item))
                continue

            item_name = loot_item.get("item_name", "Unknown Item")
            item_type = loot_item.get("item_type", "junk")
            rarity_str = loot_item.get("rarity", "Common")
            stored_quantity = 0
            # Resolve the material from the catalog by name: the built row's junk_type defaults to
            # VALUABLES and is not authoritative for credit.
            material = loot_overflow_service.resolved_junk_type(loot_item) if item_type == "junk" else None

            for _ in range(loot_item["quantity"]):
                item = loot_overflow_service.build_storage_row(
                    loot_item, storage_id, junk_description="Found during wasteland exploration"
                )
                if item is None:
                    materialization_failures.append({**loot_item, "quantity": loot_item["quantity"] - stored_quantity})
                    break

                db_session.add(item)

                if item_type in {"weapon", "outfit"}:
                    self._queue_event(
                        db_session, GameEvent.ITEM_COLLECTED, vault.id, {"item_type": item_type, "amount": 1}
                    )

                if item_type not in {"weapon", "outfit"}:
                    key = material or ""
                    junk_collected[key] = junk_collected.get(key, 0) + 1

                stored_quantity += 1

            if stored_quantity:
                transferred.append({**loot_item, "quantity": stored_quantity})
                logger.info(
                    "Item transferred to storage",
                    extra={
                        "vault_id": str(vault.id),
                        "item_name": item_name,
                        "item_type": item_type,
                        "rarity": rarity_str,
                    },
                )

        for material, amount in junk_collected.items():
            payload = {"item_type": "junk", "amount": amount, "source": WASTELAND_LOOT_SOURCE}
            if material:
                payload["junk_type"] = material
            self._queue_event(db_session, GameEvent.ITEM_COLLECTED, vault.id, payload)

        overflow_specs: list[dict] = list(materialization_failures)
        for loot_item in overflow:
            if "held_row_id" in loot_item:
                await db_session.delete(held_rows[loot_item["held_row_id"]])
                overflow_specs.append(self._plain_spec(loot_item))
            else:
                overflow_specs.append(loot_item)

        await db_session.flush()

        # Update storage used_space counter
        await crud_storage.update_used_space(db_session, storage_id)

        # Log summary
        if overflow_specs:
            logger.warning(
                "Storage overflow occurred during transfer",
                extra={
                    "vault_id": str(vault.id),
                    "exploration_id": str(exploration.id),
                    "transferred_count": len(transferred),
                    "overflow_count": len(overflow_specs),
                    "overflow_items": [i.get("item_name") for i in overflow_specs],
                },
            )
        else:
            logger.info(
                "Storage transfer completed successfully",
                extra={
                    "vault_id": str(vault.id),
                    "exploration_id": str(exploration.id),
                    "transferred_count": len(transferred),
                },
            )

        exploration.unclaimed_loot = overflow_specs

        return {
            "transferred": transferred,
            "overflow": overflow_specs,
            "storage_id": storage_id,
        }

    async def _load_unclaimed(self, db_session: AsyncSession, exploration_id: UUID) -> tuple[Exploration, list[dict]]:
        exploration = await lock_exploration_with_vault_claim(db_session, exploration_id)
        if exploration.is_in_progress():
            raise ValidationException("Exploration is still in progress")
        return exploration, list(exploration.unclaimed_loot or [])

    async def get_pending_overflow(self, db_session: AsyncSession, vault_id: UUID) -> list[PendingOverflowRead]:
        """Return every completed exploration with loot still awaiting a player decision."""
        explorations = await crud_exploration.get_by_vault(db_session, vault_id=vault_id)
        return [
            PendingOverflowRead(
                exploration_id=exploration.id,
                dweller_id=exploration.dweller_id,
                unclaimed_loot=exploration.unclaimed_loot,
            )
            for exploration in explorations
            if not exploration.is_in_progress() and exploration.unclaimed_loot
        ]

    async def take_unclaimed_item(self, db_session: AsyncSession, exploration_id: UUID, index: int) -> list[dict]:
        """Store one overflow item. 409 when storage is still full."""
        exploration, unclaimed = await self._load_unclaimed(db_session, exploration_id)
        taken, unclaimed = await loot_overflow_service.settle_take_decision(
            db_session,
            unclaimed,
            index,
            owner=Exploration,
            owner_id=exploration.id,
            vault_id=exploration.vault_id,
            junk_description="Found during wasteland exploration",
        )
        exploration.unclaimed_loot = unclaimed
        db_session.add(exploration)
        await db_session.commit()
        if payload := loot_overflow_service.collect_event_payload(taken):
            await event_bus.emit(GameEvent.ITEM_COLLECTED, exploration.vault_id, payload)
        return unclaimed

    async def sell_unclaimed_item(
        self, db_session: AsyncSession, exploration_id: UUID, index: int
    ) -> tuple[int, list[dict]]:
        """Sell one overflow item for caps. Needs no storage space."""
        exploration, unclaimed = await self._load_unclaimed(db_session, exploration_id)
        value, unclaimed = await loot_overflow_service.settle_sell_decision(
            db_session,
            unclaimed,
            index,
            owner=Exploration,
            owner_id=exploration.id,
            vault_id=exploration.vault_id,
        )
        exploration.unclaimed_loot = unclaimed
        db_session.add(exploration)
        await db_session.commit()
        if value > 0:
            await event_bus.emit(
                GameEvent.RESOURCE_COLLECTED, exploration.vault_id, {"resource_type": "caps", "amount": value}
            )
        return value, unclaimed

    async def _grant_member_xp(
        self,
        db_session: AsyncSession,
        exploration: Exploration,
        dweller_obj,
        *,
        experience_scale: float = 1.0,
        commit: bool = False,
    ) -> int:
        """Grant exploration XP to one living member, settling any level-up."""
        # A caravan pays no XP at all, not even the distance XP the spatial ticker accrues (issue 1493).
        if exploration.purpose == ExplorationPurpose.TRADE:
            return 0
        from app.services.leveling_service import leveling_service

        full_experience = rewards_calculator.calculate_exploration_xp(exploration, dweller_obj)
        experience = int(full_experience * experience_scale)

        dweller_obj.experience = max(0, dweller_obj.experience + experience)
        db_session.add(dweller_obj)

        leveled_up, levels_gained = await leveling_service.check_level_up(db_session, dweller_obj, commit=commit)
        if leveled_up:
            await leveling_service.settle_level_up(
                db_session,
                dweller_obj,
                old_level=dweller_obj.level - levels_gained,
                levels_gained=levels_gained,
                commit=commit,
            )
        return experience

    @staticmethod
    def _journey_distance(exploration: Exploration) -> int:
        """Miles covered by a spatial journey, measured from the path it walked.

        Spatial runs move through the world snapshot — they update `pos_x`/`pos_y` and append to
        `trail`, and never touch `total_distance`, which only the legacy event generator increments.
        The trail is therefore the only record of how far the run went: the farthest point it reached,
        counted twice when it came home along the same line.
        """
        if exploration.world_version is None or not exploration.trail:
            return exploration.total_distance
        if exploration.origin_x is None or exploration.origin_y is None:
            return exploration.total_distance
        origin = (exploration.origin_x, exploration.origin_y)
        farthest = max(
            (
                math.dist(origin, (float(step["x"]), float(step["y"])))
                for step in exploration.trail
                if "x" in step and "y" in step
            ),
            default=0.0,
        )
        legs = 2 if exploration.return_started_at is not None else 1
        return max(exploration.total_distance, round(farthest * legs))

    async def apply_rewards(
        self,
        db_session: AsyncSession,
        exploration: Exploration,
        progress_multiplier: float = 1.0,
        *,
        commit: bool = True,
    ) -> RewardsSchema:
        """Apply rewards to vault and dweller."""
        # Get dweller
        dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)
        # The report is built from `total_distance`, so settle it before anything is credited.
        # Assigning is enough: the run is already tracked by this session, and adding it here would
        # leave a dirty row for the post-commit world-event rollback to expire.
        exploration.total_distance = self._journey_distance(exploration)

        # Transfer caps to vault
        total_caps = exploration.total_caps_found
        credited = 0
        if total_caps > 0:
            # The one place a run's caps become vault caps: apply the completed comic set here, so
            # the find-time loot stays the run's raw haul and the bonus can never be paid twice.
            loot_multiplier = await collectible_service.bonus_multiplier(
                db_session, vault_id=exploration.vault_id, bonus_type=EXPEDITION_LOOT_PCT
            )
            pet_multiplier = 1 + min(pet_modifiers_for(dweller_obj).caps_pct, MAX_PCT_BONUS)
            total_caps = int(total_caps * pet_multiplier * loot_multiplier)
            vault = await crud_vault.get(db_session, exploration.vault_id)
            credited = await vault_service.deposit_caps(
                db_session=db_session, vault_obj=vault, amount=total_caps, commit=commit, emit_event=False
            )
            self._queue_event(
                db_session,
                GameEvent.RESOURCE_COLLECTED,
                exploration.vault_id,
                {"resource_type": "caps", "amount": credited},
            )

        # Calculate and apply experience
        if exploration.team_id is not None:
            members = await team_crud.get_exploration_team_dwellers(db_session, exploration.id)
            experience = 0
            for member in members:
                if member.is_dead:
                    continue
                experience += await self._grant_member_xp(
                    db_session, exploration, member, experience_scale=progress_multiplier, commit=commit
                )
        else:
            experience = await self._grant_member_xp(
                db_session, exploration, dweller_obj, experience_scale=progress_multiplier, commit=commit
            )

        # Transfer loot items to vault storage (with space validation)
        transfer_result = await self._transfer_loot_to_storage(db_session, exploration)

        # Return unused stimpaks and radaways to vault storage
        stimpaks_stored = 0
        radaways_stored = 0
        if exploration.stimpaks > 0 or exploration.radaways > 0:
            storage_obj = await crud_storage.get_storage_by_vault_for_update(db_session, exploration.vault_id)
            if storage_obj:
                rooms = await room_crud.get_multy_by_vault(
                    db_session=db_session, vault_id=exploration.vault_id, skip=0, limit=1000
                )
                capacity = compute_medical_capacity(rooms)
                before_stimpacks = storage_obj.stimpack or 0
                before_radaways = storage_obj.radaway or 0
                storage_obj.stimpack = min(
                    before_stimpacks + exploration.stimpaks,
                    capacity.get("stimpack", 99999),
                )
                storage_obj.radaway = min(
                    before_radaways + exploration.radaways,
                    capacity.get("radaway", 99999),
                )
                db_session.add(storage_obj)
                stimpaks_stored = max(0, (storage_obj.stimpack or 0) - before_stimpacks)
                radaways_stored = max(0, (storage_obj.radaway or 0) - before_radaways)

        # Credit only what storage kept: collect objectives must not count dropped supplies.
        if stimpaks_stored > 0:
            self._queue_event(
                db_session,
                GameEvent.ITEM_COLLECTED,
                exploration.vault_id,
                {"item_type": "stimpak", "amount": stimpaks_stored},
            )
        if radaways_stored > 0:
            self._queue_event(
                db_session,
                GameEvent.ITEM_COLLECTED,
                exploration.vault_id,
                {"item_type": "radaway", "amount": radaways_stored},
            )

        if commit:
            try:
                await db_session.commit()
            except Exception:
                self.discard_pending_rewards(db_session)
                raise
            await self.deliver_pending_reward_events(db_session)

        return RewardsSchema(
            exploration_id=exploration.id,
            caps=total_caps,
            caps_credited=credited,
            items=transfer_result["transferred"],
            overflow_items=transfer_result["overflow"],
            experience=experience,
            distance=exploration.total_distance,
            enemies_defeated=exploration.enemies_encountered,
            events_encountered=len(exploration.events),
            stimpaks=exploration.stimpaks,
            radaways=exploration.radaways,
            stimpaks_stored=stimpaks_stored,
            radaways_stored=radaways_stored,
        )


# Singleton instance
rewards_service = RewardsService()
