# Bug: Duplicate SSE Publish in Game Loop

## Status

**Fix applied.** This report documents a bug that existed in the initial SSE
implementation and has since been fixed. See the sections below for the pre-fix
and post-fix states.

---

## Before Fix

The following describes the code before the fix was applied.

### Summary

Every vault game tick published **two identical SSE events** instead of one. SSE subscribers (frontend game tick stream) processed the same update twice per tick, causing redundant renders, double resource/event processing on the client, and unnecessary bandwidth.

### Root Cause

`backend/app/services/game_loop.py` called `sse_manager.publish` in **two places** for the same game tick data:

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

---

## After Fix

The SSE publish in `process_game_tick()` (Location 1) was removed. Only the
publish inside `process_vault_tick()` (Location 2) remains — it fires when the
tick data is fresh and complete.

```python
async def process_game_tick(self, db_session: AsyncSession) -> dict:
    ...
    for vault in active_vaults:
        vault_results = await self.process_vault_tick(db_session, vault.id)
        stats["vaults_processed"] += 1
        # SSE publish removed — process_vault_tick already publishes
    ...
```

### Fix Verification

3 regression tests in `backend/app/tests/test_services/test_game_loop_sse.py`
assert exactly 1 SSE publish per vault per tick.
