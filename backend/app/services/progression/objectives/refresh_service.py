"""One persisted UTC refresh policy shared by vault ticks and scheduled sweeps."""

from datetime import UTC, datetime, timedelta

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import ObjectiveCategoryEnum
from app.crud.game_state import game_state_crud
from app.crud.objective import objective_crud
from app.crud.vault import vault as vault_crud
from app.services.progression.objectives.assignment import ObjectiveAssignmentService


def objective_periods(now: datetime) -> tuple[datetime, datetime]:
    """Naive UTC daily midnight and Monday midnight for the supplied instant."""
    utc = now.astimezone(UTC).replace(tzinfo=None) if now.tzinfo else now
    daily = utc.replace(hour=0, minute=0, second=0, microsecond=0)
    return daily, daily - timedelta(days=daily.weekday())


async def ensure_current_objectives(db: AsyncSession, vault_id: UUID4, *, now: datetime | None = None) -> list[str]:
    """Commit assignments and successful periods atomically; failures leave them due.

    Existing links with an unknown period are adopted for the current period,
    preserving work when deploying or adding state for an older vault.
    """
    await vault_crud.lock_for_update(db, vault_id)
    state = await game_state_crud.get_or_create(db, vault_id, commit=False)
    await db.refresh(state)
    daily, weekly = objective_periods(now or datetime.now(UTC))
    if (
        state.achievement_tracks_initialized
        and state.daily_objectives_period == daily
        and state.weekly_objectives_period == weekly
    ):
        await db.commit()  # Release the vault lock even when a sweep has no work.
        return []
    links = await objective_crud.get_links_for_vault(db, vault_id)
    service = ObjectiveAssignmentService(db)
    refreshed = []
    for category, field, period, refresh in (
        (ObjectiveCategoryEnum.DAILY, "daily_objectives_period", daily, service.refresh_daily_objectives),
        (ObjectiveCategoryEnum.WEEKLY, "weekly_objectives_period", weekly, service.refresh_weekly_objectives),
    ):
        previous = getattr(state, field)
        if previous is not None and previous >= period:
            continue
        templates = await objective_crud.get_by_category(db, category)
        ids = {objective.id for objective in templates}
        if previous is not None or not any(link.objective_id in ids for link in links):
            if not templates:
                continue  # Do not record a successful refresh of an empty catalog.
            await refresh(vault_id, auto_commit=False)
            refreshed.append(category.value)
        setattr(state, field, period)
    if not state.achievement_tracks_initialized or refreshed:
        await service.assign_achievement_objectives(vault_id, auto_commit=False)
        state.achievement_tracks_initialized = True
    db.add(state)
    await db.commit()
    if refreshed:
        from app.services.progression.objectives.notifications import notify_objectives_refreshed

        await notify_objectives_refreshed(db, vault_id, refreshed)
    return refreshed
