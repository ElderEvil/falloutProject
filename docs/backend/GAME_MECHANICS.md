# Game Mechanics - Agent Rules

Game-domain invariants for the Fallout Shelter simulation. These constrain *what the game must do*,
unlike `AGENTS.md`, which constrains *how code must be structured*. Follow both.

## Progression visibility (red line)

Every player-facing progression event — level-up, loot, training completion, quest/objective completion —
must surface via modal/pop-up or toast **in addition to** the notification bell entry, never
notification-only. A new progression flow without visible surfacing is incomplete; keep existing surfacing
intact when touching these flows.

## Race and faction switches

Race mechanics are **on** (`FEATURE_RACE_MECHANICS`) and faction mechanics are **off**
(`FEATURE_FACTION_MECHANICS`) until the world is deep enough for factions to mean something. Race stays on and
evolves gradually.

"Off" means faction is unavailable, not hidden from the data model: stored factions are preserved untouched, so
flipping the switch back on restores them. While it is off the roster filter rejects `faction` with 422,
`identity-options` returns no factions (races still offered), and `GET /system/features` tells clients the state
so nothing rejected is ever offered. Ghoul radiation immunity predates both switches and survives them.

**Do not gate faction on the shared identity schema.** `DwellerVisualAttributes` validates curated
`DwellerTemplate` seeds, AI generation and partial updates, which legitimately carry a faction; a schema-level
gate rejects system content and breaks vault initiation, boosted seeding and rewards. Rejection belongs on the
user-edit path.

## AI prompt registry

AI instructions are append-only registry entries. Never edit `Prompt` rows directly:
create and activate a replacement with `uv run fo-cli version-prompt <name> --template-file <path>`.
The command retires the active row, clears the process cache, and rejects format placeholders.

## Background task session compatibility

Dramatiq game-tick actors create raw SQLAlchemy `AsyncSession` instances via
`sqlalchemy.ext.asyncio.async_sessionmaker`. These sessions do not provide
SQLModel's `.exec()` method. CRUD/services used by `game_tick`,
`process_vault_tick`, or other `task_session()` actors must `await
session.execute(...)` (never `.exec()`) unless the session factory explicitly
sets `class_=sqlmodel.ext.asyncio.session.AsyncSession`, and pick the result
accessor by statement shape: `.all()` for multi-column queries,
`scalar_one_or_none()` for aggregates, `.scalars()` only for single-column
entity results. Any session-factory or CRUD refactor in this path requires a
regression test using the raw SQLAlchemy session type.

## Radiation sources and outfit resistance

Radiation is either **ingested** or **external**, and outfits only resist the external kind.

- **Ingested** — irradiated water drunk while the vault has no water. It bypasses outfit
  resistance (`apply_radiation_gain(..., resisted_by_outfit=False)`): a hazmat suit or power
  armor does not help, because the radiation enters through drinking. Ghouls stay immune and
  RadAway is the only cure.
- **External** — radscorpion incidents and wasteland danger events. Outfit resistance applies
  (see `OUTFIT_RADIATION_RESIST_BY_TYPE` / `OUTFIT_RADIATION_RESIST_BY_NAME` in
  `services/radiation_service.py`): hazmat suits block it fully, power armor blocks most.

Drought radiation accrues at 1% of max health per tick after `dehydration_grace_ticks` of zero
water, counting only the ticks past the grace boundary. Radiation saturates at the dweller's own
`max_health` — never a flat cap — so the health ceiling bottoms out at 1 HP and radiation alone
never kills. Recovery is the one-shot **Treat Irradiated Dwellers** action: RadAway first (raises
the ceiling), then a Stimpack heals into it.
