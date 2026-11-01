"""Player-facing projection of an expedition run row plus site content."""

from app.core.enums import ExpeditionRunStatus
from app.models.dweller import Dweller
from app.models.exploration import ExpeditionRun, Exploration
from app.schemas.expedition import (
    NodeOptionView,
    NodeOutcome,
    SiteDefinition,
    SiteNodeView,
    SiteRoomView,
)
from app.services.exploration.checks import stat_value, success_odds
from app.services.exploration.runs import rooms_for_run
from app.services.exploration.site_combat_service import combat_view
from app.services.exploration.trivia import trivia_question, trivia_raider


def build_view(
    exploration_id,
    site: SiteDefinition,
    run: ExpeditionRun,
    exploration: Exploration,
    outcome: NodeOutcome | None = None,
    finale_paid: bool = False,
    defeated: bool | None = None,
    dweller: Dweller | None = None,
) -> SiteRoomView:
    """Project the run row plus site JSON into the player-facing room view."""
    rooms = rooms_for_run(site, run)
    room_index = min(run.room_cursor, len(rooms) - 1)
    room = rooms[room_index]
    if defeated is None:
        pending = run.flags.get("pending_fight")
        defeated = run.status == ExpeditionRunStatus.DEFEATED or bool(
            run.is_open() and pending is not None and pending.get("room_id") == room.id
        )
    question_text: str | None = None
    prompt = room.node.prompt
    raider = trivia_raider(room, run) if room.node.kind == "trivia" else None
    raider_image_url = raider.image_url if raider is not None else None
    raider_alt_image_url = raider.alt_image_url if raider is not None else None
    if room.node.kind == "trivia":
        if raider is not None:
            prompt = f"{raider.intro} {prompt}"
        question = trivia_question(room, run)
        if question is not None and run.is_open() and not run.flags.get("combat"):
            question_text = question.prompt
            options = [NodeOptionView(id=option.id, label=option.label) for option in question.options]
        else:
            options = []
    else:
        options = [
            NodeOptionView(
                id=option.id,
                label=option.label,
                stat=option.stat,
                difficulty=option.difficulty,
                success_odds=success_odds(stat_value(exploration, option.stat), option.difficulty),
            )
            for option in room.node.options
        ]
    enemies = (
        [enemy["name"] for enemy in run.flags["combat"]["opponents"]]
        if run.flags.get("combat")
        else [spec.name for spec in room.node.enemies]
    )
    if raider is not None and not run.flags.get("combat") and enemies:
        enemies = [raider.name, *enemies[1:]]
    for option in room.node.options:
        enemies.extend(spec.name for spec in (option.failure.combat_enemies or []))
    return SiteRoomView(
        exploration_id=exploration_id,
        site_id=site.id,
        site_name=site.name,
        room_index=room_index,
        room_total=len(rooms),
        room_name=room.name,
        room_names=[room.name for room in rooms],
        flavor=room.flavor,
        node=SiteNodeView(
            kind=room.node.kind,
            prompt=prompt,
            question=question_text,
            raider_image_url=raider_image_url,
            raider_alt_image_url=raider_alt_image_url,
            options=options,
            enemy_names=enemies,
        ),
        can_retreat=run.is_open(),
        status=run.status.value,
        outcome=outcome,
        finale_paid=finale_paid,
        defeated=defeated,
        dweller_health=dweller.health if dweller is not None else 0,
        dweller_max_health=dweller.effective_max_health if dweller is not None else 0,
        scene_id=site.scene_id,
        lore=site.lore if run.flags.get("single_scene") else "",
        combat_state=combat_view(run.flags["combat"], dweller) if dweller and run.flags.get("combat") else None,
    )
