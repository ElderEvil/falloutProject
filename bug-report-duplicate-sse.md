# Bug: Duplicate SSE Publish in Game Loop

## Summary

Every vault game tick publishes **two identical SSE events** instead of one. SSE subscribers (frontend game tick stream) will process the same update twice per tick, causing redundant renders, double resource/event processing on the client, and unnecessary bandwidth.

## Root Cause

`backend/app/services/game_loop.py` calls `sse_manager.publish` in **two places** for the same game tick data:

### Location 1 — `process_game_tick()` (line 59–71)

```python
for vault in active_vaults:
    try:
        vault_results = await self.process_vault_tick(db_session, vault.id)
        stats["vaults_processed"] += 1
        try:
            await sse_manager.publish(           # ← FIRST PUBLISH
                vault.id,
                "game_ticks",
                {
                    "event_id": str(vault_results.get("seconds_passed", 0)),
                    "type": "game_tick",
                    "vault_id": str(vault.id),
                    "results": vault_results,
                },
            )
        except Exception:
            ...
```

### Location 2 — `process_vault_tick()` (line 192–204)

```python
# At the end of vault tick processing:
try:
    await sse_manager.publish(                   # ← SECOND PUBLISH
        vault_id,
        "game_ticks",
        {
            "event_id": str(game_state.last_tick_time.isoformat()),
            "type": "game_tick",
            "vault_id": str(vault_id),
            "results": results,
        },
    )
except Exception:
    ...
```

### Call Chain

```
process_game_tick(db_session)
  └─ for each vault:
       └─ process_vault_tick(db_session, vault.id)
            ├─ ... process resources, incidents, explorations, dwellers ...
            ├─ SSE publish #2  ← inside process_vault_tick
            └─ return results
       ├─ SSE publish #1      ← after process_vault_tick returns
       └─ loop next vault
```

Every call to `process_game_tick` triggers `process_vault_tick` which already publishes to SSE. The caller then publishes **the same data again** using the returned results dict.

## Impact

- **Frontend duplication**: The `/stream/game/{vault_id}/ticks` SSE endpoint receives 2 events per tick. If the frontend processes resource updates, dweller changes, etc. on each event, it will double-apply state changes.
- **Minor bandwidth**: Adds ~1–2 KB per vault per tick to the SSE stream.
- **No data corruption**: The SSE stream is fire-and-forget — the second event is a duplicate, not a double-write to the database.

## Event Payload Differences

The two publishes use slightly different `event_id` values:
- Publish #1: `str(vault_results.get("seconds_passed", 0))` → integer-as-string
- Publish #2: `str(game_state.last_tick_time.isoformat())` → ISO datetime string

This inconsistency itself would confuse any subscriber trying to deduplicate by `event_id`.

## Fix

Remove the SSE publish from `process_game_tick()` (Location 1) and keep only the one in `process_vault_tick()` (Location 2). The latter is the natural place — it publishes when the data is fresh and complete.

## Verification

- A test that patches `sse_manager.publish` and calls `process_game_tick` with one active vault should assert exactly **1 call** (not 2).
- A test that calls `process_vault_tick` directly should still assert **1 call**.
