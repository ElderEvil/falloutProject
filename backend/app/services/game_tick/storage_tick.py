"""One serialized hourly opportunity per eligible stored weapon."""

import random
from collections.abc import Callable
from datetime import datetime, timedelta

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import NotificationType
from app.core.game_config import game_config
from app.crud.notification import notification as notification_crud
from app.services import storage_maintenance_service as maintenance
from app.services.notification_service import notification_service
from app.utils.item_factory import apply_weapon_catalog


async def process_storage_maintenance(
    db: AsyncSession,
    vault_id: UUID4,
    rng: Callable[[], float] = random.random,
) -> dict[str, int]:
    """Consume due trials and persist notifications before publishing after commit."""
    stats = {"checked": 0, "changed": 0}
    config = game_config.storage
    if not config.maintenance_enabled:
        return stats
    storage = await crud.storage.get_storage_by_vault_for_update(db, vault_id)
    if storage is None:
        return stats
    # Read the clock after acquiring the lock, including if another pass just finished.
    now = datetime.utcnow()
    due = await crud.weapon.list_due_for_trial(
        db, storage.id, now - timedelta(seconds=config.trial_interval_seconds), maintenance.eligible_weapon_names()
    )
    if not due:
        await db.commit()
        return stats
    state = await crud.game_state_crud.get_by_vault_id(db, vault_id)
    if state is not None and state.is_paused:
        await db.commit()
        return stats
    online = state is not None and state.is_user_online()
    if config.trials_require_online and not online:
        await crud.weapon.advance_trial_clock(db, [weapon.id for weapon in due], now)
        await db.commit()
        return {"checked": len(due), "changed": 0}
    workers = await crud.dweller.list_storage_workers(db, vault_id)
    direction, chance = maintenance.trial_odds(maintenance.worker_endurance(workers))
    changed: list[tuple[int, str]] = []
    for weapon in due:
        initialized = weapon.last_maintenance_trial_at is not None
        weapon.last_maintenance_trial_at = now
        db.add(weapon)
        stats["checked"] += 1
        if not initialized:
            continue
        target = maintenance.adjacent(weapon.name, direction)
        if target is not None and maintenance.roll_allowed(weapon, target, direction) and rng() < chance:
            apply_weapon_catalog(weapon, target)
            changed.append((weapon.damage_min + weapon.damage_max, weapon.name))
    stats["changed"] = len(changed)
    if changed:
        kind = NotificationType.STORAGE_ITEM_UPGRADED if direction > 0 else NotificationType.STORAGE_ITEM_DEGRADED
        latest = await notification_crud.latest_for_vault(db, vault_id, kind)
        if latest is None or now - latest >= timedelta(hours=config.notify_cooldown_hours):
            vault = await crud.vault.get(db, vault_id)
            verb = "improved" if direction > 0 else "degraded"
            await notification_service.create_and_send(
                db,
                vault.user_id,
                kind,
                f"Stored weapons {verb}",
                f"{len(changed)} stored weapon(s) {verb}. Check storage staffing for protection.",
                vault_id=vault_id,
                meta_data={"count": len(changed), "worst_name": min(changed)[1]},
                commit=False,
            )
    await db.commit()
    await notification_service.deliver_deferred_notifications(db)
    return stats
