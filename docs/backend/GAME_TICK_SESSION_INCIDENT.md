# Game-tick raw-session compatibility incident

## Summary

Background Dramatiq actors use SQLAlchemy's `async_sessionmaker`, whose
sessions are `sqlalchemy.ext.asyncio.AsyncSession` instances. That class does
not have SQLModel's `.exec()` convenience method.

The game-state CRUD module used `.exec()` from the initial game-loop
implementation. This remained latent because the game loop queried game state
directly with `.execute()`. Commit `9ced3190` routed the lookup through
`game_state_crud`, making the incompatible method reachable from the background
tick path. The result was an `AttributeError` before a vault could be processed.

The same session mismatch affected quest completion after `1f24f651` moved
that actor to the shared `task_session()` context manager. Its per-quest
`except Exception` boundary in `QuestService.check_and_complete_quests()`
logged the failure and continued, so the scheduled job could appear healthy
while completing no quests. The regression suite now exercises this complete
path with a raw session, including the delegated
`mark_quest_ready_to_claim()` call.

## Timeline

- `cfd84346` (2025-12-29): the game loop and `game_state_crud` were introduced;
  game-state CRUD used `.exec()`.
- `c313f489` (2026-05-06): Dramatiq actors were introduced with raw
  SQLAlchemy `async_sessionmaker` sessions.
- `1f24f651` (2026-08-23): `task_session()` was added for background actors.
  The game-tick actors intentionally retained inline session makers because
  objective evaluators need the session maker itself.
- `9ced3190` (2026-08-28): `_get_or_create_game_state()` began calling
  `game_state_crud.get_or_create()`, exposing the `.exec()` mismatch in the
  game-tick path.
- PR #482 changes affected queries to `.execute(...).scalars()` and adds a
  regression test using the raw session type.

## Affected call chains and exception boundaries

```text
game_tick
  -> sqlalchemy.async_sessionmaker()
  -> GameLoopService.process_game_tick(session)
  -> process_vault_tick(session, vault_id)
  -> game_state_crud.get_or_create(session, vault_id)
  -> get_by_vault_id(session, vault_id)
```

`backend/app/api/tasks.py` catches and re-raises failures at the actor boundary
in `game_tick()` and `process_vault_tick()`, allowing Dramatiq's retry policy
to observe them. In contrast, the per-quest `except Exception` in
`backend/app/services/quest_service.py` intentionally isolates one quest;
that boundary previously swallowed the session `AttributeError`. It is now
explicitly marked, and compatibility is protected by a test rather than by
silently accepting the failure.

## Prevention rule

When code is reachable from a background actor, verify the concrete session
factory before choosing SQLModel-only APIs. Use SQLAlchemy-compatible
`.execute(...).scalars()` for shared CRUD/services, or set
`class_=sqlmodel.ext.asyncio.session.AsyncSession` explicitly and test that
contract. A regression test must instantiate a raw SQLAlchemy `AsyncSession`
and exercise the affected CRUD/service method.

The regression coverage is in
`backend/app/tests/test_crud/test_game_state.py`: it covers both game-state
CRUD lookup and quest completion through the raw-session contract.
