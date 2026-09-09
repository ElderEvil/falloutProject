# Game Mechanics - Agent Rules

Game-domain invariants for the Fallout Shelter simulation. These constrain *what the game must do*,
unlike `AGENTS.md`, which constrains *how code must be structured*. Follow both.

## Progression visibility (red line)

Every player-facing progression event — level-up, loot, training completion, quest/objective completion —
must surface via modal/pop-up or toast **in addition to** the notification bell entry, never
notification-only. A new progression flow without visible surfacing is incomplete; keep existing surfacing
intact when touching these flows.

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
